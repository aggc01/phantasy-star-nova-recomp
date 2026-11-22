# match each game screenshot to the frame of the cleaned movie; stack band crops: game / cleaned file (ffmpeg/cv2 decode) / original
import cv2, os, sys, numpy as np
td, clean, orig, out = sys.argv[1:5]
shots = [k for k in range(2100, 5101, 100) if os.path.exists(os.path.join(td, 'shot_%05d.ppm' % k))]
G = {k: cv2.imread(os.path.join(td, 'shot_%05d.ppm' % k)) for k in shots}
def small(f): return cv2.resize(f[:430], (120, 54)).astype(np.float32)
c = cv2.VideoCapture(clean); C = []
while True:
    ok, f = c.read()
    if not ok: break
    C.append(small(f))
C = np.stack(C)
res = {}
for k in shots:
    g = small(G[k]); d = np.abs(C - g).mean(axis=(1, 2, 3)); j = int(d.argmin()); res[k] = (j, float(d[j]))
print({k: res[k] for k in shots})
def frames_at(path, idxs):
    c = cv2.VideoCapture(path); want = set(idxs); got = {}; i = 0
    while want - set(got):
        ok, f = c.read()
        if not ok: break
        if i in want: got[i] = f
        i += 1
    return got
idx = [res[k][0] for k in shots]
FC, FO = frames_at(clean, idx), frames_at(orig, idx)
rows = []
for k in shots:
    j = res[k][0]
    trio = [G[k][440:544], FC[j][440:544], FO[j][440:544]]
    for t, lab in zip(trio, ['game %d' % k, 'clean file f%d' % j, 'original f%d' % j]):
        t = t.copy(); cv2.putText(t, lab, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
    rows.append(np.hstack([cv2.putText(trio[0].copy(), 'game %d' % k, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,0), 1),
                           cv2.putText(trio[1].copy(), 'clean f%d' % j, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,0), 1)]))
np.save(out + '_match.npy', np.array([[k, res[k][0]] for k in shots]))
cv2.imwrite(out + '.png', np.vstack(rows))
