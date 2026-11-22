import sys
from PIL import Image
src, x0, y0, x1, y1, scale, out = sys.argv[1], *map(int, sys.argv[2:7]), sys.argv[7]
im = Image.open(src).convert('RGBA')
c = im.crop((x0, y0, x1, y1))
bg = Image.new('RGBA', c.size, (255, 0, 255, 255)); bg.alpha_composite(c)
bg = bg.convert('RGB').resize((c.width*scale, c.height*scale), Image.NEAREST)
bg.save(out)
