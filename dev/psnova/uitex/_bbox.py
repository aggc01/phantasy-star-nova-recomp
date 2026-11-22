import sys
from PIL import Image
import numpy as np
src = sys.argv[1]; x0,y0,x1,y1 = map(int, sys.argv[2:6]); mode = sys.argv[6]
a = np.asarray(Image.open(src).convert('RGBA')).astype(int)
r,g,b = a[...,0],a[...,1],a[...,2]
if mode=='red': m = (r>170)&(g<90)&(b<90)
elif mode=='white': m = (r>215)&(g>215)&(b>215)
elif mode=='redwhite': m = ((r>170)&(g<90)&(b<90)) | ((r>225)&(g>225)&(b>225))
sub = m[y0:y1,x0:x1]
ys,xs = np.nonzero(sub)
if len(xs)==0: print('none'); sys.exit()
print('bbox', xs.min()+x0, ys.min()+y0, xs.max()+x0+1, ys.max()+y0+1, 'n', len(xs))
# column profile
cols = sub.any(0); rows = sub.any(1)
def runs(v, off):
    out=[];s=None
    for i,t in enumerate(v):
        if t and s is None: s=i
        if not t and s is not None: out.append((s+off,i+off)); s=None
    if s is not None: out.append((s+off,len(v)+off))
    return out
print('rowruns', runs(rows,y0))
print('colruns', runs(cols,x0)[:60])
