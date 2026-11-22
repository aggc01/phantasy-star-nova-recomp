"""Check the cleaned movies: frame count, audio stream, bitrate, and a before/after sheet (2026-11-18)."""
import cv2, numpy as np, subprocess, re, sys
FF = r"F:\Antigravity Proj\animation\node_modules\ffmpeg-static\ffmpeg.exe"
bands = {'MP00_000_000':(470,497),'MP00_000_010':(472,499),'MP00_010_050':(470,496),'MP06_030_040':(470,497),
         'MP06_030_050':(470,497),'MP06_030_070':(470,497),'MP09_040_040':(464,491),'MP09_040_070':(470,497)}
def info(p):
    t = subprocess.run([FF,'-hide_banner','-i',p],capture_output=True,text=True).stderr
    dur = re.search(r'Duration: (\S+),', t).group(1)
    return dur, 'Audio: aac' in t, re.search(r'Video: (\w+).*?(\d+x\d+)', t).groups()
sheet = []
for n,(y0,y1) in bands.items():
    a, b = f'movies/{n}.mp4', f'movies_clean/{n}.mp4'
    ca, cb = cv2.VideoCapture(a), cv2.VideoCapture(b)
    fa, fb = int(ca.get(7)), int(cb.get(7))
    ia, ib = info(a), info(b)
    print(n, 'frames', fa, fb, 'dur', ia[0], ib[0], 'audio', ia[1], ib[1], ib[2])
    for frac in (0.3, 0.7):
        k = int(fa*frac)
        ca.set(1,k); cb.set(1,k); _, A = ca.read(); _, B = cb.read()
        sheet.append(np.vstack([A[y0-24:y1+40], B[y0-24:y1+40]]))
cv2.imwrite('verify_sheet.png', np.vstack(sheet[:8]))
cv2.imwrite('verify_sheet2.png', np.vstack(sheet[8:]))
