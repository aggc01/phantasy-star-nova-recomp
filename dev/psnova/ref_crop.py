"""ref_crop.py <out.png> <image...>: the game picture cut out of the reference video's streamer frame (part 1/2 frames:
the game sits at about x 30-99.5%, y 2-60% of the 1920x1080 frame), two a row at 960x540, labelled with the time stamp."""
import sys
from PIL import Image, ImageDraw
out, fs = sys.argv[1], sys.argv[2:]; W, H = 960, 540
img = Image.new("RGB", (W * 2, H * ((len(fs) + 1) // 2))); d = ImageDraw.Draw(img)
for i, f in enumerate(fs):
    im = Image.open(f).convert("RGB"); w, h = im.size
    g = im.crop((int(w * 0.30), int(h * 0.02), int(w * 0.995), int(h * 0.60))).resize((W, H))
    x, y = (i % 2) * W, (i // 2) * H; img.paste(g, (x, y)); d.text((x + 4, y + 2), f.replace("\\", "/").split("/")[-1], fill=(255, 255, 0))
img.save(out); print(out, img.size, len(fs))
