"""Write RUNDIR/segments.txt ("[t0-t1] text") and RUNDIR/segwords.txt ("i| 0:word 1:word ...") from words.json.

Usage: python segwords.py RUNDIR
segments.txt goes to the block-marking agent, segwords.txt to the translation agent (parts need word numbers).
"""
import json
import sys

R = sys.argv[1]
w = json.load(open(R + "/words.json", encoding="utf-8"))
W = w["words"]
with open(R + "/segments.txt", "w", encoding="utf-8") as f:
    for s in w["segments"]:
        f.write("[%.2f-%.2f] %s\n" % (s["t0"], s["t1"], s["text"]))
with open(R + "/segwords.txt", "w", encoding="utf-8") as f:
    for s in w["segments"]:
        f.write("%d| " % s["i"] + " ".join("%d:%s" % (k, W[j]["text"]) for k, j in enumerate(range(s["w0"], s["w1"]))) + "\n")
print("segments", len(w["segments"]))
