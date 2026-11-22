"""sheet.py <out.jpg> <cols> <thumb_px> <png>...  - contact sheet on a dark background with file names."""
import sys, os
from PIL import Image, ImageDraw, ImageFont

out, cols, T = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
files = sys.argv[4:]
lab = 14
rows = (len(files) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (T + 6), rows * (T + lab + 6)), (36, 36, 48))
dr = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype('arial.ttf', 12)
except Exception:
    font = ImageFont.load_default()
for i, f in enumerate(files):
    im = Image.open(f).convert('RGBA')
    im.thumbnail((T, T), Image.LANCZOS)
    bg = Image.new('RGBA', im.size, (36, 36, 48, 255)); bg.alpha_composite(im)
    x = (i % cols) * (T + 6) + 3; y = (i // cols) * (T + lab + 6) + 3
    sheet.paste(bg.convert('RGB'), (x, y + lab))
    dr.text((x, y), os.path.basename(f)[:-4][:34], fill=(230, 230, 120), font=font)
sheet.save(out, quality=88)
print(out, sheet.size)
