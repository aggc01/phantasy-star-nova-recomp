"""jpg_sheet.py <out.png> <cols> <tile_width> <image...>: tile reference frames (any format PIL reads) into one PNG, each
labelled with its file name's time stamp (frame_000123_00-02-03.jpg -> 00:02:03). Needs PIL (C:\Python314 has it)."""
import sys, os, re
from PIL import Image, ImageDraw
out, cols, tw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); files = sys.argv[4:]
im0 = Image.open(files[0]); th = round(tw * im0.height / im0.width)
rows = (len(files) + cols - 1) // cols; sheet = Image.new("RGB", (cols * tw, rows * th))
d = ImageDraw.Draw(sheet)
for n, f in enumerate(files):
    im = Image.open(f).convert("RGB").resize((tw, th)); x, y = (n % cols) * tw, (n // cols) * th
    sheet.paste(im, (x, y)); m = re.search(r"(\d\d)-(\d\d)-(\d\d)", os.path.basename(f))
    lab = ":".join(m.groups()) if m else os.path.basename(f)
    d.rectangle([x, y, x + 7 * len(lab) + 4, y + 12], fill=(0, 0, 0)); d.text((x + 2, y), lab, fill=(255, 255, 0))
sheet.save(out); print(out, sheet.size, len(files))
