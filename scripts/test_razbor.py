"""Acceptance test for razbor-donora scripts (written by the orchestrator, NOT by the implementer).

Run: python -I test_razbor.py <scripts_dir>
Offline: synthetic video via ffmpeg, fixture yt-dlp JSON, fake words.json. Needs ffmpeg/ffprobe in PATH.
Exit 0 = all checks pass.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(__file__))
PY = sys.executable
FAILS = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def run(args, **kw):
    r = subprocess.run([PY, "-I"] + args, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
    return r


def probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    hub = tempfile.mkdtemp(prefix="razbor-hub-")
    run_dir = os.path.join(hub, "output", "projects", "x", "donors", "demo-AAA")
    os.makedirs(run_dir)
    # 12 s synthetic video, 30 fps, with a frame counter burned in (time is visible on frames)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=12",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=12", "-shortest", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", os.path.join(run_dir, "video.mp4")], check=True)

    # ---------- fetch_meta.py (offline fixtures) ----------
    info = {"id": "AAA", "title": "Demo <video> & \"quotes\"", "channel": "Chan", "uploader": "Chan",
            "channel_url": "https://www.youtube.com/channel/UC1", "upload_date": "20261006", "duration": 12,
            "view_count": 50000, "like_count": 2500, "comment_count": 100,
            "webpage_url": "https://www.youtube.com/watch?v=AAA", "thumbnail": "https://i.ytimg.com/vi/AAA/hqdefault.jpg",
            "extractor_key": "Youtube"}
    views = [10000, 8000, 12000, 9000, 11000, 50000]  # last one is the video itself, must be excluded
    chan = {"entries": [{"id": "V%d" % i, "view_count": v} for i, v in enumerate(views[:-1])] +
                       [{"id": "AAA", "view_count": 50000}]}
    ij, cj = os.path.join(hub, "info.json"), os.path.join(hub, "chan.json")
    json.dump(info, open(ij, "w", encoding="utf-8"))
    json.dump(chan, open(cj, "w", encoding="utf-8"))
    r = run([os.path.join(SCRIPTS, "fetch_meta.py"), info["webpage_url"], run_dir, "--info-json", ij, "--channel-json", cj])
    check(r.returncode == 0, "fetch_meta.py exits 0")
    meta = json.load(open(os.path.join(run_dir, "meta.json"), encoding="utf-8"))
    check(meta.get("views") == 50000 and meta.get("id") == "AAA", "meta: views and id")
    check(meta.get("upload_date") == "2026-10-06", "meta: upload_date formatted YYYY-MM-DD")
    check(meta.get("norm", {}).get("n") == 5 and meta["norm"].get("median") == 10000, "meta: norm excludes the video itself, median 10000")
    check(abs(float(meta.get("ratio", 0)) - 5.0) < 0.01, "meta: ratio = views / median = 5.0")
    check(isinstance(meta.get("z"), (int, float)) and meta["z"] > 2, "meta: z-score present and > 2")
    check(abs(float(meta.get("like_rate", 0)) - 5.0) < 0.01, "meta: like_rate in percent = 5.0")
    check(meta.get("rank") == "1 из 6", "meta: rank among channel videos incl. itself = '1 из 6'")
    # small channel -> no norm
    json.dump({"entries": [{"id": "V1", "view_count": 5}, {"id": "AAA", "view_count": 50000}]}, open(cj, "w"))
    small = os.path.join(hub, "small")
    os.makedirs(small)
    r2 = run([os.path.join(SCRIPTS, "fetch_meta.py"), info["webpage_url"], small, "--info-json", ij, "--channel-json", cj])
    m2 = json.load(open(os.path.join(small, "meta.json"), encoding="utf-8"))
    check(r2.returncode == 0 and m2.get("ratio") is None and m2.get("norm") is None, "meta: fewer than 3 channel videos -> norm and ratio null")

    # ---------- words.json (format of transcribe.py) ----------
    texts = "Hello and welcome . this is a test of the donor page with many words . Second part starts here and ends there".split()
    texts = [t for t in texts if t != "."]
    words, t = [], 0.3
    for i, tx in enumerate(texts):
        if i == 13:
            t = 6.5  # pause between parts
        words.append({"i": i, "text": tx, "t0": round(t, 2), "t1": round(t + 0.3, 2), "seg": 0 if i < 13 else 1, "p": 0.9})
        t += 0.38
    segs = [{"i": 0, "t0": words[0]["t0"], "t1": words[12]["t1"], "text": " ".join(texts[:13]), "w0": 0, "w1": 13},
            {"i": 1, "t0": words[13]["t0"], "t1": words[-1]["t1"], "text": " ".join(texts[13:]), "w0": 13, "w1": len(words)}]
    json.dump({"source": "video.mp4", "model": "fake", "lang": "en", "duration": 12, "segments": segs, "words": words},
              open(os.path.join(run_dir, "words.json"), "w", encoding="utf-8"))

    # ---------- blocks_draft.py ----------
    r = run([os.path.join(SCRIPTS, "blocks_draft.py"), os.path.join(run_dir, "words.json"),
             os.path.join(run_dir, "blocks.draft.json"), "--min", "2", "--max", "8", "--gap", "1.0"])
    check(r.returncode == 0, "blocks_draft.py exits 0")
    d = json.load(open(os.path.join(run_dir, "blocks.draft.json"), encoding="utf-8"))
    bl = d.get("blocks", [])
    check(len(bl) == 2, "draft: split at the 1 s+ pause into 2 blocks (got %d)" % len(bl))
    check(all(set(["n", "title", "role", "t0", "t1"]) <= set(b) for b in bl), "draft: blocks have n,title,role,t0,t1")

    # ---------- blocks.json: block 2 ends early -> its last words are dropped ----------
    blocks = {"blocks": [
        {"n": 1, "title": "Хук <b>", "role": "хук", "t0": 0.0, "t1": 6.0, "why": "обещание"},
        {"n": 2, "title": "Демо", "role": "демо", "t0": 6.3, "t1": 9.0, "why": ""}]}
    json.dump(blocks, open(os.path.join(run_dir, "blocks.json"), "w", encoding="utf-8"), ensure_ascii=False)
    in_blocks = [w for w in words if (0.0 <= w["t0"] < 6.0) or (6.3 <= w["t0"] < 9.0)]

    # ---------- translation.json (mandatory for non-ru videos) ----------
    tr = {"lang": "ru", "segments": [
        {"i": 0, "ru": "Привет и добро пожаловать <i>", "parts": [{"ru": "Привет и", "w0": 0, "w1": 2}, {"ru": "добро пожаловать <i>", "w0": 2, "w1": 13}]},
        {"i": 1, "ru": "Вторая часть начинается", "parts": [{"ru": "Вторая часть начинается", "w0": 0, "w1": 7}]}]}
    json.dump(tr, open(os.path.join(run_dir, "translation.json"), "w", encoding="utf-8"), ensure_ascii=False)

    # ---------- build.py ----------
    r = run([os.path.join(SCRIPTS, "build.py"), run_dir, "--width", "320", "--tol", "0.2"])
    check(r.returncode == 0, "build.py exits 0")
    donor = json.load(open(os.path.join(run_dir, "donor.json"), encoding="utf-8"))
    check(len(donor.get("blocks", [])) == 2, "donor.json: 2 blocks")
    allw = [w for b in donor["blocks"] for w in b.get("words", [])]
    check(len(allw) == len(in_blocks), "donor.json: one entry per word inside blocks (%d vs %d)" % (len(allw), len(in_blocks)))
    check(donor.get("dropped_words") == len(words) - len(in_blocks), "donor.json: dropped_words counts words outside blocks")
    okt = all(abs(float(w["ft"]) - float(w["t0"])) <= 0.2 for w in allw)
    check(okt, "every frame time ft within 0.2 s of word start")
    files_ok = all(os.path.isfile(os.path.join(run_dir, w["frame"])) and os.path.getsize(os.path.join(run_dir, w["frame"])) > 1000 for w in allw)
    check(files_ok, "every word has a non-empty frame jpg (path relative to run dir)")
    check(all("/" in w["frame"] and "\\" not in w["frame"] for w in allw), "frame paths use forward slashes")
    for b in donor["blocks"]:
        clip = os.path.join(run_dir, b.get("clip", "missing"))
        ok = os.path.isfile(clip) and abs(probe_dur(clip) - (b["t1"] - b["t0"])) < 0.35
        check(ok, "block %s clip exists and duration matches t1-t0" % b["n"])
        check(isinstance(b.get("segments"), list) and b["segments"], "block %s has segments (phrases)" % b["n"])
    check(donor.get("meta", {}).get("id") == "AAA", "donor.json embeds meta")
    check(donor.get("lang") == "en", "donor.json: lang from words.json")
    check(donor.get("orientation") == "horizontal", "donor.json: orientation horizontal for 1280x720")
    segs_all = [s for b in donor["blocks"] for s in b["segments"]]
    check(all("i" in s and s.get("ru") for s in segs_all), "donor.json: every block segment has source index i and Russian text ru")
    b1 = donor["blocks"][0]
    p1 = b1["segments"][0].get("parts", [])
    check([(p["k0"], p["k1"]) for p in p1] == [(0, 2), (2, 13)], "donor.json: parts mapped to block word indexes k0/k1 (block 1)")
    b2 = donor["blocks"][1]
    p2 = b2["segments"][0].get("parts", [])
    check(len(p2) == 1 and p2[0]["k0"] == 0 and p2[0]["k1"] == len(b2["words"]), "donor.json: parts clipped to words kept in block 2 (%s)" % p2)
    # idempotent rerun keeps frames
    mt = os.path.getmtime(os.path.join(run_dir, allw[0]["frame"]))
    r = run([os.path.join(SCRIPTS, "build.py"), run_dir, "--width", "320"])
    check(r.returncode == 0 and os.path.getmtime(os.path.join(run_dir, allw[0]["frame"])) == mt, "build.py rerun skips existing frames")

    # ---------- page.py ----------
    page = os.path.join(hub, "page")
    r = run([os.path.join(SCRIPTS, "page.py"), run_dir, "--out", page, "--hub", hub, "--mode", "review"])
    check(r.returncode == 0, "page.py exits 0")
    html = open(os.path.join(page, "index.html"), encoding="utf-8").read()
    rel = "output/projects/x/donors/demo-AAA/"
    check('src="/__review.js"' in html and "reviewAnswer(" in html, "page: has /__review.js and reviewAnswer")
    check(html.count('class="flipbook"') == 2, "page: one flipbook per block")
    check(len(re.findall(r'<details[^>]*class="block"', html)) == 2, "page: every block is a collapsible <details class=block>")
    check(re.search(r'<details[^>]*class="block"[^>]*\sopen[\s>]', html) is not None, "page: first block open by default")
    check(html.count('id="toggle-all"') == 1, "page: one button to expand/collapse all blocks")
    check("Привет и добро пожаловать &lt;i&gt;" in html, "page: Russian translation shown and escaped")
    check('class="caption-ru"' in html, "page: translation line under the caption")
    check("???" not in html.replace("??[", "") and "Весь текст" in html, "page: no Cyrillic broken into ??? (Codex on Windows), labels readable")
    check("ru-part" in html, "page: Russian translation split into parts highlighted with the English word")
    sec = html.split('id="b01"')[1].split('id="b02"')[0] if 'id="b02"' in html else ""
    check(0 <= sec.find('class="caption"') < sec.find('class="picture"'), "page: subtitle text (caption) is above the frame")
    check('class="lines"' in sec and "data-all" in sec, "page: block text shown line by line with a 'show all' control")
    check('data-orientation="horizontal"' in html, "page: orientation marker on main/body")
    check(html.count("<video") == 2 and ("/m/" + rel + "blocks/") in html, "page: one <video> per block via /m/ path")
    check(("/m/" + rel) in html and "frames/" in html, "page: frames referenced via /m/ hub-relative paths")
    check("https://www.youtube.com/watch?v=AAA" in html, "page: link to the original video")
    check("50" in html and ("×5" in html or "x5" in html or "5,0" in html or "5.0" in html), "page: views and ratio shown")
    check("Хук <b>" not in html and "Demo <video>" not in html, "page: titles are HTML-escaped")
    check(re.search(r"</script", html.split('id="donor-data"')[1].split("</script>")[0] if 'id="donor-data"' in html else "") is None,
          "page: embedded JSON in <script id=donor-data> has no raw </script")
    check("word-active" in html and "ArrowRight" in html, "page: active-word highlight and arrow keys")
    check("prefers-color-scheme: dark" in html or "prefers-color-scheme:dark" in html, "page: dark theme")
    check(html.count("<img") <= 4, "page: frames are not all <img> tags (one swapped image per flipbook)")
    check("Что нового" in html and "Что нужно от тебя" in html and "Что дальше" in html, "page: top block Что нового/Что нужно от тебя/Что дальше")
    check(os.path.getsize(os.path.join(page, "index.html")) < 3_000_000, "page: index.html under 3 MB")
    os.remove(os.path.join(run_dir, "translation.json"))
    run([os.path.join(SCRIPTS, "build.py"), run_dir, "--width", "320"])
    r = run([os.path.join(SCRIPTS, "page.py"), run_dir, "--out", os.path.join(hub, "page-nt"), "--hub", hub, "--mode", "review"])
    check(r.returncode == 3, "page.py exits 3 when an English video has no translation (got %s)" % r.returncode)
    r = run([os.path.join(SCRIPTS, "page.py"), run_dir, "--out", os.path.join(hub, "page-nt"), "--hub", hub, "--mode", "review", "--allow-no-translation"])
    check(r.returncode == 0, "page.py --allow-no-translation builds anyway")

    # ---------- vertical video ----------
    vdir = os.path.join(hub, "output", "projects", "x", "donors", "vert-BBB")
    os.makedirs(vdir)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=4",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=4", "-shortest", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", os.path.join(vdir, "video.mp4")], check=True)
    vw = [{"i": i, "text": t, "t0": 0.3 + i * 0.5, "t1": 0.6 + i * 0.5, "seg": 0, "p": 0.9} for i, t in enumerate("Это вертикальный ролик тест".split())]
    json.dump({"source": "video.mp4", "model": "fake", "lang": "ru", "duration": 4,
               "segments": [{"i": 0, "t0": vw[0]["t0"], "t1": vw[-1]["t1"], "text": "Это вертикальный ролик тест", "w0": 0, "w1": len(vw)}],
               "words": vw}, open(os.path.join(vdir, "words.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({"blocks": [{"n": 1, "title": "Весь", "role": "хук", "t0": 0.0, "t1": 3.5, "why": ""}]},
              open(os.path.join(vdir, "blocks.json"), "w", encoding="utf-8"), ensure_ascii=False)
    r = run([os.path.join(SCRIPTS, "build.py"), vdir, "--width", "640"])
    check(r.returncode == 0, "vertical: build.py exits 0")
    vd = json.load(open(os.path.join(vdir, "donor.json"), encoding="utf-8"))
    check(vd.get("orientation") == "vertical", "vertical: orientation detected")
    vclip = os.path.join(vdir, vd["blocks"][0]["clip"])
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", vclip], capture_output=True, text=True)
    wv, hv = [int(x) for x in pr.stdout.strip().split(",")[:2]]
    check(wv == 720 and hv > wv, "vertical: clip short side 720, stays vertical (got %dx%d)" % (wv, hv))
    vf = os.path.join(vdir, vd["blocks"][0]["words"][0]["frame"])
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", vf], capture_output=True, text=True)
    fw_, fh_ = [int(x) for x in pr.stdout.strip().split(",")[:2]]
    check(fh_ > fw_, "vertical: frames stay vertical (got %dx%d)" % (fw_, fh_))
    r = run([os.path.join(SCRIPTS, "page.py"), vdir, "--out", os.path.join(hub, "page-v"), "--hub", hub, "--mode", "review"])
    check(r.returncode == 0, "vertical: Russian video needs no translation, page.py exits 0")
    vh = open(os.path.join(hub, "page-v", "index.html"), encoding="utf-8").read()
    check('data-orientation="vertical"' in vh, "vertical: page carries orientation marker for its layout")

    # ---------- standalone mode (public version: no review server, opens as a file) ----------
    tr2 = {"lang": "ru", "segments": [{"i": 0, "ru": "Привет", "parts": [{"ru": "Привет", "w0": 0, "w1": 13}]},
                                      {"i": 1, "ru": "Вторая", "parts": [{"ru": "Вторая", "w0": 0, "w1": 7}]}]}
    json.dump(tr2, open(os.path.join(run_dir, "translation.json"), "w", encoding="utf-8"), ensure_ascii=False)
    run([os.path.join(SCRIPTS, "build.py"), run_dir, "--width", "320"])
    r = run([os.path.join(SCRIPTS, "page.py"), run_dir])
    sa = os.path.join(run_dir, "index.html")
    check(r.returncode == 0 and os.path.isfile(sa), "standalone: page.py RUNDIR writes RUNDIR/index.html by default")
    sh = open(sa, encoding="utf-8").read() if os.path.isfile(sa) else ""
    check("/m/" not in sh and "__review.js" not in sh and "reviewAnswer(" not in sh, "standalone: no review-server URLs or helpers")
    check("blocks/b0" in sh and "frames/b0" in sh, "standalone: clips and frames referenced by relative paths")
    check('id="export"' in sh and "Blob" in sh, "standalone: comments exported as a downloaded JSON file (button id=export)")
    check("localStorage" in sh, "standalone: comments survive reload (localStorage)")

    # ---------- no hub paths or hub-only loaders in scripts ----------
    for f in ("fetch_meta.py", "transcribe.py", "blocks_draft.py", "build.py", "page.py", "llm_groq.py", "run.py", "segwords.py", "check_parts.py"):
        fp = os.path.join(SCRIPTS, f)
        txt = open(fp, encoding="utf-8").read() if os.path.isfile(fp) else ""
        check(bool(txt) and "SuperHub" not in txt and "superhub_env" not in txt and "C:/" not in txt and "C:\\" not in txt,
              "portable: %s exists, no SuperHub paths or hub secret loader" % f)
    r = run([os.path.join(SCRIPTS, "run.py"), "--help"])
    check(r.returncode == 0 and "url" in (r.stdout or "").lower(), "run.py --help works (one-command pipeline)")

    # ---------- llm_groq.repair: small word-number mistakes of the free model are fixed, not thrown away ----------
    sys.path.insert(0, SCRIPTS)
    import llm_groq
    fixed = llm_groq.repair(6, {"i": 0, "parts": [{"ru": "раз", "w0": 0, "w1": 2}, {"ru": "два", "w0": 3, "w1": 9}]})
    check([(q["w0"], q["w1"]) for q in fixed["parts"]] == [(0, 2), (2, 6)], "repair: gap closed and end clipped (%s)" % fixed["parts"])
    kept = llm_groq.repair(6, {"i": 0, "parts": [{"ru": "раз", "w0": 3, "w1": 6}, {"ru": "два", "w0": 0, "w1": 3}]})
    check([(q["w0"], q["w1"]) for q in kept["parts"]] == [(3, 6), (0, 3)], "repair: Russian order different from English is left alone")

    jsfile = os.path.join(hub, "flip.js")
    m = re.findall(r"<script>(.*?)</script>", html, re.S)
    open(jsfile, "w", encoding="utf-8").write("\n".join(m))
    if shutil.which("node"):
        nr = subprocess.run(["node", "--check", jsfile], capture_output=True, text=True)
        check(nr.returncode == 0, "page: inline JS parses (node --check) " + nr.stderr[:200])
    else:
        print("skip page JS syntax check: Node.js is not installed (optional)")

    shutil.rmtree(hub, ignore_errors=True)
    print("\n%d failed" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
