r"""merge_ref_index.py <out.md> <workflow output json>... : the reference-footage index rows written from the contact sheets
(workflow psnova-reference-index: [{part, rows:[{sheet,start,end,scene,summary,text_seen,prompts}]}]) as one markdown
table per part, sorted by time, naming any sheet that got no row. Sheets list: dump/reference/part<N>/sheets.txt.
"""
import json
import os
import sys

out_path, inputs = sys.argv[1], sys.argv[2:]
here = os.path.dirname(os.path.abspath(__file__))
ref = os.path.join(here, "..", "..", "dump", "reference")
rows = []
for f in inputs:
    d = json.load(open(f, encoding="utf-8"))
    res = d.get("result", d) if isinstance(d, dict) else d
    if isinstance(res, str):
        res = json.loads(res)
    for b in res:
        for r in b["rows"]:
            rows.append((b["part"], r))
rows.sort(key=lambda x: (x[0], x[1]["start"]))
have = {(p, r["sheet"]) for p, r in rows}
missing = []
for p in (1, 2):
    for line in open(os.path.join(ref, f"part{p}", "sheets.txt"), encoding="utf-8"):
        if line.strip() and (p, line.split()[0]) not in have:
            missing.append(f"part{p}/{line.split()[0]}")
esc = lambda s: (s or "").replace("|", "/").replace("\n", " ")
out = ["# Phantasy Star Nova: real-Vita reference index", "",
       "Two YouTube walkthroughs of the real game (Japanese release, no English patch), one frame a second, that I gave",
       r"on 2026-11-18 (`C:\New PATH\screenshots`). Contact sheets of 16 seconds each in `dump/reference/part1|part2/`",
       "(git-ignored). Rows written from the sheets (`dev/psnova/make_ref_sheets.py`, workflow",
       "`psnova-reference-index`, merged by `dev/psnova/merge_ref_index.py`); spot-check against the sheets before",
       "relying on a row.", ""]
if missing:
    out += ["Sheets with no row (an agent skipped them): " + ", ".join(missing), ""]
for p, title in ((1, "Part 1: character creator + intro"), (2, "Part 2: mission 1")):
    out += [f"## {title}", "", "| Time | Scene | What happens | Text seen | Prompts |", "|---|---|---|---|---|"]
    out += [f"| {r['start']}-{r['end'][3:]} | {r['scene']} | {esc(r['summary'])} | {esc(r.get('text_seen'))} | {esc(r.get('prompts'))} |"
            for q, r in rows if q == p]
    out.append("")
open(out_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print(f"{len(rows)} rows, {len(missing)} sheets without one -> {out_path}")
