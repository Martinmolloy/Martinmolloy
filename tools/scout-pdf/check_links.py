"""Checks that every link in the print-edition HTML became a PDF link pointing at the right place.

Usage: python3 check_links.py out.pdf anchors.json
"""
import json
import sys

from pypdf import PdfReader

r = PdfReader(sys.argv[1])
A = json.load(open(sys.argv[2]))
H = float(r.pages[0].mediabox.height)
page_of = {s["id"]: s["i"] for s in A}
ref2idx = {pg.indirect_reference.idnum: i for i, pg in enumerate(r.pages)}
problems, total = [], 0
for s in A:
    annots = []
    for a in r.pages[s["i"]].get("/Annots") or []:
        a = a.get_object()
        x0, y0, x1, y1 = [float(v) for v in a["/Rect"]]
        if "/Dest" in a:
            tgt = ("page", ref2idx[a["/Dest"][0].idnum], str(a["/Dest"][1]))
        else:
            tgt = ("uri", str(a["/A"]["/URI"]), "")
        annots.append(((x0, H - y1, x1, H - y0), tgt))
    for L in s["links"]:
        total += 1
        want = ("page", page_of[L["href"][1:]], "/Fit") if L["href"].startswith("#") else ("uri", L["href"], "")
        # a link that wraps onto two lines becomes one PDF link per line; each must point the same way
        for R in L["rects"]:
            box = (R["x"] * 0.75, R["y"] * 0.75, (R["x"] + R["w"]) * 0.75, (R["y"] + R["h"]) * 0.75)
            if want not in [t for (bx, t) in annots if all(abs(u - v) < 2.5 for u, v in zip(bx, box))]:
                problems.append((s["id"], L["href"], L["text"]))
                break
print(f"links checked: {total}, wrong or missing: {len(problems)}")
for p in problems[:20]:
    print("  ", p)
sys.exit(1 if problems else 0)
