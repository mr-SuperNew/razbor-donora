"""Blocks and Russian translation through a Groq-hosted LLM: no Claude tokens are spent.

Usage:
  python llm_groq.py blocks RUNDIR [--out blocks.json] [--model openai/gpt-oss-120b]
  python llm_groq.py translate RUNDIR [--out translation.json] [--batch 40]
Inputs: RUNDIR/words.json (segments + words). Key GROQ_API_KEY from the environment or .env (never printed).
blocks    -> {"blocks":[{n,title,role,t0,t1,why}]}; bounds snapped to segment t0/t1, ordered, no overlap.
translate -> {"lang":"ru","segments":[{i,ru,parts:[{ru,w0,w1}]}]}; every batch is validated (parts cover every word once,
             parts joined == ru); a batch that fails twice falls back to one part per phrase (still a valid file).
Exit codes: 0 ok, 2 key/usage, 3 API error.
"""
import argparse
import json
import os
import sys

for _stream in (sys.stdout, sys.stderr):  # Russian messages must not crash on a cp1252/cp1251 console
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
import time
from pathlib import Path

import requests

URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_BLOCK = 120  # seconds: a longer block is too coarse for editing and is split by a second request
ROLES = "хук|обещание|раздел|демо|установка|цена|призыв|финал|вставка"


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


def chat(k, model, system, user, usage):
    for attempt in range(12):  # free tier: 8000 tokens per minute, 429 is normal, wait and retry
        try:
            r = requests.post(URL, headers={"Authorization": "Bearer " + k}, timeout=300, json={
                "model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
                # free tier is 8000 tokens per minute: short reasoning and a capped answer keep one request under it
                "reasoning_effort": "low", "max_completion_tokens": 3500,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        except requests.RequestException as e:
            err = type(e).__name__
        else:
            if r.status_code == 200:
                j = r.json()
                for x in ("prompt_tokens", "completion_tokens"):
                    usage[x] = usage.get(x, 0) + (j.get("usage") or {}).get(x, 0)
                return json.loads(j["choices"][0]["message"]["content"])
            err = "%s %s" % (r.status_code, r.text[:200].replace(k, "[redacted]"))
            if r.status_code == 400 and "json_validate_failed" in r.text:  # the model broke JSON once: ask again
                continue
            if r.status_code == 429 and "per day" in r.text:  # daily cap: waiting minutes will not help
                print("Groq: дневной лимит бесплатного тарифа (200 тыс. токенов в сутки) исчерпан. Прогресс сохранён, "
                      "повтори ту же команду завтра или после смены тарифа.", file=sys.stderr); sys.exit(3)
            if r.status_code == 429:
                time.sleep(min(70.0, float(r.headers.get("retry-after", 20)) + 2)); continue
        time.sleep(3)
    print("Groq LLM: " + err, file=sys.stderr); sys.exit(3)


def fmt(t):
    return "%d:%05.2f" % (t // 60, t % 60)


def blocks(R, k, model, out, usage):
    w = json.load(open(os.path.join(R, "words.json"), encoding="utf-8"))
    segs = w["segments"]
    text = "\n".join("%d [%.2f] %s" % (s["i"], s["t0"], s["text"]) for s in segs)
    system = ("You split a video transcript into editing blocks, the way an editor cuts a talking-head YouTube video. "
              "Answer with JSON only.")
    user = ("Phrases: `index [start seconds] text`. Make blocks of whole phrases: hook, promise, sections, demo, setup, price, "
            "call to action, final; ads or 'subscribe' inserts are their own block. Usually 20-90 s, hook may be shorter; each list item, step or topic is its own block; never call a part 'demo' unless the screen is shown."
            "Every phrase belongs to exactly one block, blocks in order. Return "
            '{"blocks":[{"first":<first phrase index>,"last":<last phrase index>,"title":"<Russian, up to 6 words>",'
            '"role":"<one of %s>","why":"<Russian, one line: what the block does for the viewer>"}]}\n\n%s' % (ROLES, text))
    j = chat(k, model, system, user, usage)
    res, nxt = [], 0
    for b in sorted(j.get("blocks", []), key=lambda b: int(b["first"])):
        f, l = max(int(b["first"]), nxt), min(int(b["last"]), len(segs) - 1)
        if l < f:
            continue
        res.append({"n": len(res) + 1, "title": str(b.get("title", "")).strip() or "Блок %d" % (len(res) + 1),
                    "role": b.get("role") if b.get("role") in ROLES.split("|") else "раздел",
                    "t0": segs[f]["t0"], "t1": segs[l]["t1"], "why": str(b.get("why", "")).strip()})
        nxt = l + 1
    if nxt < len(segs) and res:  # phrases the model forgot at the end go to the last block
        res[-1]["t1"] = segs[-1]["t1"]
    final = []
    for b in res:
        inner = [s for s in segs if b["t0"] <= s["t0"] < b["t1"]]
        if b["t1"] - b["t0"] <= MAX_BLOCK or len(inner) < 4:
            final.append(b); continue
        want = max(2, round((b["t1"] - b["t0"]) / 50))
        text2 = "\n".join("%d [%.2f] %s" % (s["i"], s["t0"], s["text"]) for s in inner)
        j2 = chat(k, model, system, ("Split this part of the video (block '%s') into about %d editing blocks of 20-90 s by meaning "
                  "(each list item, step or topic its own block). Do not invent content that is not in the phrases. Return "
                  '{"blocks":[{"first":i,"last":i,"title":"<Russian>","role":"<one of %s>","why":"<Russian>"}]}\n\n%s')
                 % (b["title"], want, ROLES, text2), usage)
        lo, sub = inner[0]["i"], []
        for x in sorted(j2.get("blocks", []), key=lambda x: int(x["first"])):
            f, l = max(int(x["first"]), lo), min(int(x["last"]), inner[-1]["i"])
            if l < f:
                continue
            sub.append({"title": str(x.get("title", "")).strip() or b["title"],
                        "role": x.get("role") if x.get("role") in ROLES.split("|") else b["role"],
                        "t0": segs[f]["t0"], "t1": segs[l]["t1"], "why": str(x.get("why", "")).strip()})
            lo = l + 1
        if sub:
            sub[0]["t0"], sub[-1]["t1"] = b["t0"], b["t1"]
            final += sub
        else:
            final.append(b)
    # no holes and no overlaps: a phrase the model skipped joins the block before it
    for p, q in zip(final, final[1:]):
        q["t0"] = max(q["t0"], p["t1"])
        before = [s for s in segs if p["t1"] <= s["t0"] and s["t1"] <= q["t0"]]
        if before:
            p["t1"] = before[-1]["t1"]
    for n, b in enumerate(final, 1):
        b["n"] = n
    res = final
    json.dump({"blocks": res}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("blocks", len(res))


def valid(seg_words, item):
    n = len(seg_words)
    parts = item.get("parts") or []
    cov = []
    try:
        for p in parts:
            if not str(p.get("ru", "")).strip() or not (0 <= int(p["w0"]) < int(p["w1"]) <= n):
                return False
            cov += range(int(p["w0"]), int(p["w1"]))
    except (AttributeError, KeyError, TypeError, ValueError):  # malformed part from the model
        return False
    return bool(parts) and sorted(cov) == list(range(n))


def repair(n, item):
    """The free model often gets word numbers slightly wrong (a gap, an overlap, w1 past the end), and a strict check
    then throws the split away (03.11: only 15 of 137 phrases kept their parts). If the parts already go in English word
    order, close gaps and overlaps so they cover 0..n exactly; otherwise leave the item as it is."""
    try:
        parts = [{"ru": str(p["ru"]).strip(), "w0": int(p["w0"]), "w1": int(p["w1"])} for p in item.get("parts") or []
                 if str(p.get("ru", "")).strip()]
    except (AttributeError, KeyError, TypeError, ValueError):
        return item
    if not parts or [p["w0"] for p in parts] != sorted(p["w0"] for p in parts):
        return item
    for k, p in enumerate(parts):
        p["w0"] = 0 if k == 0 else parts[k - 1]["w1"]
        p["w1"] = n if k == len(parts) - 1 else max(p["w0"] + 1, min(p["w1"], n - (len(parts) - 1 - k)))
    if all(p["w0"] < p["w1"] for p in parts):
        return dict(item, parts=parts)
    return item


def translate(R, k, model, out, batch, usage):
    w = json.load(open(os.path.join(R, "words.json"), encoding="utf-8"))
    W, segs = w["words"], w["segments"]
    system = ("You translate English video subtitles into natural spoken Russian and align the translation to the English words. "
              "Answer with JSON only.")
    rules = ("For each phrase `i| 0:word 1:word ...` give the Russian translation split into parts of 1-5 Russian words in "
             "Russian order; each part names the continuous range of English word numbers it translates (w0 first, w1 after last). "
             "Parts together cover every English word of the phrase exactly once. A phrase may stop mid-sentence: translate so that "
             "consecutive phrases read as connected Russian. Do not translate product names (Claude, Claude Code, HyperFrames, "
             "FFmpeg, YouTube...). No em dash. Return {\"segments\":[{\"i\":<i>,\"parts\":[{\"ru\":\"...\",\"w0\":0,\"w1\":3}]}]}")
    # progress survives the free-tier daily limit (200k tokens/day): a rerun continues from the saved phrases
    partial = out + ".partial.json"
    result = {int(i): v for i, v in json.load(open(partial, encoding="utf-8")).items()} if os.path.exists(partial) else {}
    for b0 in range(0, len(segs), batch):
        chunk = [s for s in segs[b0:b0 + batch] if s["i"] not in result]
        if not chunk:
            continue
        ctx = " ".join(s["text"] for s in segs[max(0, b0 - 3):b0])
        lines = "\n".join("%d| " % s["i"] + " ".join("%d:%s" % (q, W[j]["text"]) for q, j in enumerate(range(s["w0"], s["w1"]))) for s in chunk)
        todo = {s["i"]: s for s in chunk}
        for _ in range(2):
            j = chat(k, model, system, rules + ("\n\nPrevious context: " + ctx if ctx else "") + "\n\n" + lines, usage)
            items = j.get("segments", []) if isinstance(j, dict) else []
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):  # the model sometimes returns a bare string: skip, the phrase is retried
                    continue
                try:
                    i = int(item.get("i", -1))
                except (TypeError, ValueError):
                    continue
                if i in todo:
                    item = repair(todo[i]["w1"] - todo[i]["w0"], item)
                if i in todo and valid(W[todo[i]["w0"]:todo[i]["w1"]], item):
                    result[i] = [{"ru": str(p["ru"]).strip(), "w0": int(p["w0"]), "w1": int(p["w1"])} for p in item["parts"]]
                    del todo[i]
            if not todo:
                break
            lines = "\n".join(l for l in lines.split("\n") if int(l.split("|")[0]) in todo)
        for i, s in todo.items():  # still invalid: one part per phrase, translated alone
            j = chat(k, model, system, "Translate into Russian, return {\"ru\":\"...\"}: " + s["text"], usage)
            result[i] = [{"ru": str(j.get("ru", "")).strip() or s["text"], "w0": 0, "w1": s["w1"] - s["w0"]}]
        json.dump(result, open(partial, "w", encoding="utf-8"), ensure_ascii=False)
        print("translated", len(result), "of", len(segs), flush=True)
    data ={"lang": "ru", "segments": [{"i": s["i"], "ru": " ".join(p["ru"] for p in result[s["i"]]), "parts": result[s["i"]]} for s in segs]}
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.remove(partial)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["blocks", "translate"])
    ap.add_argument("rundir")
    ap.add_argument("--out")
    ap.add_argument("--model", default="openai/gpt-oss-120b")
    ap.add_argument("--batch", type=int, default=12)
    a = ap.parse_args()
    k, usage = groq_key(a.rundir), {}
    out = a.out or os.path.join(a.rundir, "blocks.json" if a.mode == "blocks" else "translation.json")
    if a.mode == "blocks":
        blocks(a.rundir, k, a.model, out, usage)
    else:
        translate(a.rundir, k, a.model, out, a.batch, usage)
    print("groq tokens: in %d, out %d (Claude tokens: 0)" % (usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)))


if __name__ == "__main__":
    main()
