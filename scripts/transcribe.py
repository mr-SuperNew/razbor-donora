"""Word-level transcript of a donor video. Code only, no LLM tokens.

Engines:
  groq  (default) - Groq Whisper large-v3 API, key GROQ_API_KEY from the environment or .env. Fast, does not load this machine.
  local           - faster-whisper large-v3 on the GPU (CPU fallback). Free, but takes ~3-4 GB of memory: on 02.11 the
                    system killed it for low memory. Use only when Groq is unavailable.

Usage: python transcribe.py VIDEO OUT_words.json [--engine groq|local] [--lang auto|en|ru] [--prompt "names"]
Output JSON: {"source", "engine", "model", "lang", "duration",
              "segments": [{"i", "t0", "t1", "text", "w0", "w1"}],   # w0..w1: index range into words (w1 exclusive)
              "words":    [{"i", "text", "t0", "t1", "seg", "p"}]}  # p: word probability (local only, else null)
Times are seconds from the start of the video, rounded to 0.01.
Exit codes: 0 ok, 2 usage/key error, 3 Groq API error (rerun with --engine local).
"""
import argparse
import json
import os
import re
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):  # Russian messages must not crash on a cp1252/cp1251 console
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
import shutil
import tempfile
from pathlib import Path

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MAX = 25 * 1024 * 1024  # Groq upload limit per request
GAP = 3.0  # seconds between word starts that are re-asked on their own slice
DEFAULT_PROMPT = "Claude, Claude Code, Anthropic, ChatGPT, OpenAI, Codex, Opus, Sonnet, Telegram, YouTube."


LANG_CODES = {"russian": "ru", "english": "en", "ukrainian": "uk", "spanish": "es", "german": "de", "french": "fr"}
# Whisper spells product names by ear in Russian speech; the prompt alone does not fix it on Groq (02.11: 9 x "Клод")
TERM_FIXES = [(re.compile(r"^(Клод|Клауд)(а|у|ом|е)?$", re.I), "Claude"), (re.compile(r"^Антропик(а|у|ом|е)?$", re.I), "Anthropic"),
              (re.compile(r"^Кодекс(а|у|ом|е)?$"), "Codex"),
              # English speech: Whisper hears "Clawed Code" (03.11: 13 times in a 10-min video)
              (re.compile(r"^(Clawed|Clawd|Clawde|Claud|Clode)$", re.I), "Claude")]


def fix_terms(data):
    for w in data["words"]:
        m = re.match(r"^([\W_]*)(.*?)([\W_]*)$", w["text"])
        for rx, good in TERM_FIXES:
            if rx.match(m.group(2)):
                w["text"] = m.group(1) + good + m.group(3)
                break
    for s in data["segments"]:
        s["text"] = " ".join(x["text"] for x in data["words"][s["w0"]:s["w1"]])
    lang = str(data.get("lang") or "").lower()
    data["lang"] = LANG_CODES.get(lang, lang or None)
    return data


def r2(x):
    return round(float(x), 2)


def to_struct_local(segments_iter, info, source, model):
    segs, words = [], []
    for s in segments_iter:
        w0 = len(words)
        for w in (s.words or []):
            text = (w.word or "").strip()
            if not text:
                continue
            words.append({"i": len(words), "text": text, "t0": r2(w.start), "t1": r2(max(w.end, w.start + 0.01)),
                          "seg": len(segs), "p": round(float(getattr(w, "probability", 0) or 0), 3)})
        if len(words) == w0:
            continue
        segs.append({"i": len(segs), "t0": words[w0]["t0"], "t1": words[-1]["t1"],
                     "text": " ".join(x["text"] for x in words[w0:]), "w0": w0, "w1": len(words)})
    return {"source": source, "engine": "local", "model": model, "lang": getattr(info, "language", None),
            "duration": r2(getattr(info, "duration", 0) or 0), "segments": segs, "words": words}


def norm(t):
    return re.sub(r"[^\w]", "", t.lower())


def to_struct_groq(resp, source, model):
    """Groq gives words (no punctuation) and segments (with punctuation) separately: assign words to segments by time,
    then take each word's spelling with punctuation from the segment text when the letters match."""
    gw = [w for w in resp.get("words") or [] if str(w.get("word", "")).strip()]
    gs = resp.get("segments") or []
    segs, words, k = [], [], 0
    for si, s in enumerate(gs):
        end = float(s["end"]) if si + 1 < len(gs) else float("inf")
        nxt = float(gs[si + 1]["start"]) if si + 1 < len(gs) else float("inf")
        bucket = []
        while k < len(gw) and (float(gw[k]["start"]) < min(end, nxt) or si + 1 == len(gs)):
            bucket.append(gw[k]); k += 1
        if not bucket:
            continue
        tokens, ti = str(s.get("text", "")).split(), 0
        w0 = len(words)
        for w in bucket:
            text = str(w["word"]).strip()
            # look ahead a few tokens for the same letters, keep punctuation from the segment text
            for j in range(ti, min(ti + 3, len(tokens))):
                if norm(tokens[j]) == norm(text) and norm(text):
                    text, ti = tokens[j], j + 1
                    break
            words.append({"i": len(words), "text": text, "t0": r2(w["start"]), "t1": r2(max(float(w["end"]), float(w["start"]) + 0.01)),
                          "seg": len(segs), "p": None})
        segs.append({"i": len(segs), "t0": words[w0]["t0"], "t1": words[-1]["t1"],
                     "text": " ".join(x["text"] for x in words[w0:]), "w0": w0, "w1": len(words)})
    return {"source": source, "engine": "groq", "model": model, "lang": resp.get("language"),
            "duration": r2(resp.get("duration") or 0), "segments": segs, "words": words}


def groq_key(run_dir):
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key
    for path in (Path(run_dir) / ".env", Path(run_dir).resolve().parent / ".env", Path.cwd() / ".env"):
        if path.is_file():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                name, sep, value = line.partition("=")
                if sep and name.strip() == "GROQ_API_KEY":
                    key = value.strip().strip("\"'")
                    if key:
                        return key
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    print("GROQ_API_KEY is missing. Get a free key at https://console.groq.com and set GROQ_API_KEY.\n"
          "GROQ_API_KEY не найден. Получите бесплатный ключ на https://console.groq.com и задайте GROQ_API_KEY.", file=sys.stderr)
    sys.exit(2)


def groq(video, lang, prompt, run_dir=None):
    import requests
    key = groq_key(run_dir or Path(video).resolve().parent)
    tmpdir = tempfile.mkdtemp(prefix="razbor-audio-")

    def ask(start=None, end=None):
        """One Groq request for the whole audio or for [start, end] seconds; returns the JSON response."""
        part = os.path.join(tmpdir, "a.ogg")
        cut = (["-ss", str(start), "-to", str(end)] if start is not None else [])
        subprocess.run(["ffmpeg", "-y", "-v", "error"] + cut + ["-i", video, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "32k", part], check=True)
        if os.path.getsize(part) > GROQ_MAX:
            print("звук больше 25 МБ (ролик длиннее ~100 минут): нужна нарезка, запусти --engine local", file=sys.stderr); sys.exit(3)
        data = [("model", "whisper-large-v3"), ("response_format", "verbose_json"), ("temperature", "0"),
                ("timestamp_granularities[]", "word"), ("timestamp_granularities[]", "segment")]
        if lang != "auto":
            data.append(("language", lang))
        if prompt:
            data.append(("prompt", prompt))
        try:
            with open(part, "rb") as f:
                r = requests.post(GROQ_URL, headers={"Authorization": "Bearer " + key},
                                  files={"file": ("audio.ogg", f, "audio/ogg")}, data=data, timeout=900)
        except requests.RequestException as e:
            print("Groq: ошибка сети: %s. Повтори или запусти --engine local" % type(e).__name__, file=sys.stderr); sys.exit(3)
        if r.status_code != 200:
            print("Groq: код %s: %s. Повтори позже или --engine local" % (r.status_code, r.text[:300].replace(key, "[redacted]")), file=sys.stderr); sys.exit(3)
        return r.json()

    resp = ask()
    if not resp.get("words"):
        print("Groq не вернул время слов: запусти --engine local", file=sys.stderr); sys.exit(3)
    # Whisper on a long file sometimes skips 10-30 s of speech (02.11: two holes, 46 s, in a 15-min video).
    # Every pause longer than GAP is asked again on its own slice; words found inside the pause are inserted.
    words, segs = list(resp["words"]), list(resp.get("segments") or [])
    dur = float(resp.get("duration") or 0)
    added, asked, tried = 0, 0, set()
    for _round in range(3):  # the first request may skip a different piece each time; repeat until no holes
        words.sort(key=lambda w: float(w["start"]))
        # by word STARTS: Whisper may stretch one word over a skipped piece, so word ends hide the hole
        st = [float(w["start"]) for w in words]
        holes = [(st[k], st[k + 1]) for k in range(len(st) - 1) if st[k + 1] - st[k] > GAP]
        holes = [(0.0, st[0])] * (st[0] > GAP) + holes + [(st[-1], dur)] * (dur - st[-1] > GAP)
        holes = [h for h in holes if (round(h[0], 1), round(h[1], 1)) not in tried]  # a real pause stays silent: ask once
        if not holes:
            break
        for a, b in holes:
            tried.add((round(a, 1), round(b, 1))); asked += 1
            off = max(0.0, a - 0.5)
            extra = ask(off, b + 0.5)
            new_w = [dict(w, start=float(w["start"]) + off, end=float(w["end"]) + off) for w in extra.get("words") or []]
            new_w = [w for w in new_w if a + 0.6 < w["start"] < b - 0.05]  # a+0.6: skip the word that starts the hole
            if new_w:
                words += new_w; added += len(new_w)
                segs += [dict(s, start=float(s["start"]) + off, end=float(s["end"]) + off) for s in extra.get("segments") or []
                         if a < float(s["start"]) + off + 0.3 and float(s["end"]) + off - 0.3 < b]
    shutil.rmtree(tmpdir, ignore_errors=True)
    words.sort(key=lambda w: float(w["start"]))
    segs.sort(key=lambda s: float(s["start"]))
    print("groq: pauses re-asked %d, words added %d" % (asked, added))
    resp = dict(resp, words=words, segments=segs)
    return to_struct_groq(resp, video, "whisper-large-v3")


def local(video, lang, prompt, model_name, device):
    from faster_whisper import WhisperModel
    dev = device
    if dev == "auto":
        try:
            import ctranslate2
            dev = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            dev = "cpu"

    def run(d):
        m = WhisperModel(model_name, device=d, compute_type="float16" if d == "cuda" else "int8")
        segs, info = m.transcribe(video, language=None if lang == "auto" else lang, word_timestamps=True,
                                  vad_filter=True, beam_size=5, initial_prompt=prompt or None)
        return to_struct_local(segs, info, video, model_name)
    try:
        return run(dev)
    except Exception as e:  # CUDA libs missing etc. -> CPU retry
        if dev != "cuda":
            raise
        print("cuda failed, retry on cpu:", e, file=sys.stderr)
        return run("cpu")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--engine", choices=["groq", "local"], default="groq")
    ap.add_argument("--model", default="large-v3", help="local engine model")
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--device", default="auto", help="local engine device")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT,
                    help="names Whisper should spell right (otherwise Russian speech gives 'Клод')")
    a = ap.parse_args()
    data = fix_terms(groq(a.video, a.lang, a.prompt, Path(a.out).resolve().parent) if a.engine == "groq" else local(a.video, a.lang, a.prompt, a.model, a.device))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("engine", data["engine"], "words", len(data["words"]), "segments", len(data["segments"]), "lang", data["lang"])


if __name__ == "__main__":
    main()
