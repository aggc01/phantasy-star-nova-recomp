import cv2, glob, os, sys, numpy as np
td = sys.argv[1]; out = sys.argv[2]
fs = sorted(glob.glob(os.path.join(td, 'shot_*.ppm')))
th = []
for f in fs:
    im = cv2.imread(f)
    if im is None: continue
    t = cv2.resize(im, (320, int(im.shape[0]*320/im.shape[1])))
    cv2.putText(t, os.path.basename(f)[5:10], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
    th.append(t)
print(len(th), th[0].shape if th else None)
cols = 6; h, w = th[0].shape[:2]
rows = [np.hstack(th[i:i+cols] + [np.zeros_like(th[0])]*(cols-len(th[i:i+cols]))) for i in range(0, len(th), cols)]
cv2.imwrite(out, np.vstack(rows))
