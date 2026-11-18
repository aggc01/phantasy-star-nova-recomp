"""make_ref_sheets.py <frames dir> <out dir> [--per 16] [--cols 4] [--width 400]

Contact sheets of reference footage extracted one frame a second (files named frame_<n>_<hh-mm-ss>.jpg, as the user's
"C:\\New PATH\\screenshots" folders are): <per> consecutive frames a sheet, each labelled with its time, written as
sheet_<first second>.jpg plus sheets.txt ("<sheet file> <first time> <last time>"). The sheets are what a reviewer
(or a cheap subagent) reads to index the footage; they stay in dump/ (git-ignored): they are someone else's video.
Run with the system Python (Pillow): C:\\Python314\\python.exe
"""
import argparse
import glob
import os
import re

from PIL import Image, ImageDraw, ImageFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames"); ap.add_argument("out")
    ap.add_argument("--per", type=int, default=16); ap.add_argument("--cols", type=int, default=4); ap.add_argument("--width", type=int, default=400)
    a = ap.parse_args()
    fs = sorted(glob.glob(os.path.join(glob.escape(a.frames), "frame_*.jpg")))
    os.makedirs(a.out, exist_ok=True)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    w = a.width; h = w * 9 // 16; rows = (a.per + a.cols - 1) // a.cols
    lines = []
    for i in range(0, len(fs), a.per):
        chunk = fs[i:i + a.per]
        sheet = Image.new("RGB", (w * a.cols, h * rows), (0, 0, 0)); d = ImageDraw.Draw(sheet)
        times = []
        for k, f in enumerate(chunk):
            m = re.search(r"_(\d\d)-(\d\d)-(\d\d)\.jpg$", f)
            t = f"{m.group(1)}:{m.group(2)}:{m.group(3)}" if m else os.path.basename(f)
            times.append(t)
            x, y = (k % a.cols) * w, (k // a.cols) * h
            sheet.paste(Image.open(f).convert("RGB").resize((w, h)), (x, y))
            d.rectangle([x, y, x + 86, y + 22], fill=(0, 0, 0)); d.text((x + 4, y + 2), t, fill=(255, 255, 0), font=font)
        name = f"sheet_{times[0].replace(':', '-')}.jpg"
        sheet.save(os.path.join(a.out, name), quality=85)
        lines.append(f"{name} {times[0]} {times[-1]}")
    open(os.path.join(a.out, "sheets.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{len(lines)} sheets from {len(fs)} frames -> {a.out}")


if __name__ == "__main__":
    main()
