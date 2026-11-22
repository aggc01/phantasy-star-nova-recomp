# Measure tight boxes of the Japanese labels in load024.png (spec authoring helper, 2026-11-19).
import sys
import numpy as np
from PIL import Image
P = r"F:/Antigravity Proj/Recomp-decomp/Phantasy Star Nova Recomp/dump/psnova-l10n/scratch/research/uitex/png/base/load024.png"
a = np.array(Image.open(P).convert("RGB")).astype(int)
R = {
 "title": (30, 5, 200, 46),
 "L": (30, 50, 115, 72), "D1": (30, 75, 330, 95),
 "dpad": (66, 122, 150, 145), "D2": (30, 148, 215, 188), "D3": (30, 192, 215, 231),
 "lstick": (62, 265, 170, 288), "D4": (30, 290, 175, 311),
 "touch": (360, 50, 515, 72), "D5": (360, 75, 632, 111),
 "R": (900, 50, 995, 72), "D6": (870, 75, 995, 95),
 "tri": (932, 112, 995, 135), "D7": (870, 137, 978, 156), "D7mark": (976, 137, 995, 156),
 "sq": (932, 162, 995, 185), "D8": (930, 187, 995, 206),
 "ci": (932, 213, 995, 236), "D9": (940, 239, 995, 259),
 "x": (932, 275, 995, 298), "D10": (735, 299, 995, 320),
 "rstick": (878, 327, 995, 351), "D11": (890, 351, 995, 371),
 "selb": (410, 328, 480, 351), "D12": (305, 351, 390, 371),
 "stab": (612, 328, 680, 351), "D13": (515, 351, 625, 371),
 "box1": (56, 395, 160, 418), "box2": (174, 395, 340, 418),
 "note": (35, 432, 655, 458),
}
for k, (x0, y0, x1, y1) in R.items():
    s = a[y0:y1, x0:x1]
    r, g, b = s[..., 0], s[..., 1], s[..., 2]
    if k == "title":
        m = (g > 150) & (b > 150) & (r < 200) & (r > 60)
    elif k in ("note", "D7mark"):
        m = (r > 180) & (g < 170) & (r - b > 40)
    else:
        m = (r > 170) & (g > 170) & (b > 170)
    if not m.any():
        print(k, "none"); continue
    ys, xs = np.nonzero(m)
    col = s[m].mean(0).round().astype(int).tolist()
    print(f"{k:7s} tight [{xs.min()+x0},{ys.min()+y0},{xs.max()+x0+1},{ys.max()+y0+1}) col {col}")
