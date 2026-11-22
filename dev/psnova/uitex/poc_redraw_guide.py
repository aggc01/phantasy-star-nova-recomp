"""poc_redraw_guide.py - proof of concept: redraw two button-guide labels of tex_nova_ui_common.aif (1.05 update
version) in English inside their layout cells, re-encode BC2 + Morton, and render the result. NOT installed anywhere.
Cells (from ui_common.crbpj, patch, UVs x1024): Cast_Camera 0x259198 = x925-1023 y636-657 (カメラ初期化),
0x25c7d4 = x971-1023 y657-678 (ズーム).
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import aiftex, aif_encode_test  # noqa: E402

ROOT = os.path.join(HERE, '..')
PROJ = os.path.join(ROOT, '..', '..', '..', '..', '..')
font = ImageFont.truetype(os.path.join(PROJ, 'tools', 'fonts', 'segoeuib.ttf'), 15)
src = os.path.join(ROOT, 'patch', 'tex_nova_ui_common.aif')
d = open(src, 'rb').read()
img, (W, H, f, tid, n) = aiftex.load(src)
im = Image.fromarray(img, 'RGBA')
cells = [((925, 636, 1023, 657), 'Reset Camera'), ((971, 657, 1023, 678), 'Zoom')]
for (x0, y0, x1, y1), text in cells:
    im.paste((0, 0, 0, 0), (x0, y0, x1 + 1, y1))          # clear the cell
    layer = Image.new('RGBA', (x1 + 1 - x0, y1 - y0), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    w = dr.textlength(text, font=font)
    dr.text((layer.width - 2 - w, 1), text, font=font, fill=(255, 255, 255, 255), stroke_width=1,
            stroke_fill=(8, 0, 0, 255))
    im.alpha_composite(layer, (x0, y0))
out = os.path.join(ROOT, 'enc')
os.makedirs(out, exist_ok=True)
im.save(os.path.join(out, 'poc_common_en.png'))
data = aif_encode_test.encode_bc2_morton(np.array(im))
new = d[:0x1e0] + data + d[0x1e0 + len(data):]
open(os.path.join(out, 'poc_tex_nova_ui_common.aif'), 'wb').write(new)
back, _ = aiftex.load(os.path.join(out, 'poc_tex_nova_ui_common.aif'))
crop = Image.fromarray(back, 'RGBA').crop((848, 572, 1024, 700))
bg = Image.new('RGBA', crop.size, (60, 90, 60, 255)); bg.alpha_composite(crop)
bg.resize((crop.width * 4, crop.height * 4), Image.NEAREST).save(os.path.join(out, 'poc_guide_decoded_zoom.png'))
print('written', len(new), 'bytes (same as source %d), texture id %06x kept' % (len(d), tid))
