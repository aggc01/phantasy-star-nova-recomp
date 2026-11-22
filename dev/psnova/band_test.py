import cv2, os, sys, numpy as np
td, out, a, b = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
rows = []
for k in range(a, b + 1, 100):
    im = cv2.imread(os.path.join(td, 'shot_%05d.ppm' % k))
    if im is None: continue
    s = im[440:544].copy()
    cv2.putText(s, str(k), (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,0), 1)
    rows.append(s)
half = (len(rows) + 1) // 2
L = rows[:half]; R = rows[half:] + [np.zeros_like(rows[0])] * (half - len(rows[half:]))
cv2.imwrite(out, np.hstack([np.vstack(L), np.vstack(R)]))
print(len(rows), im.shape)
