"""Picture sheets of every subtitle line of the 8 story movies, for transcription (2026-11-19).
usage: python make_sub_sheets.py <out dir>
For each line of dump/psnova-l10n/movies_v3_check/lines_<movie>.npz (cs/ce = frames where the line is at full strength):
the Japanese line (band of the original movie, movies_jp/) and the fan English line burned under it (the rePatch movie,
movies/, same frame) at the line's middle frame, enlarged 2x, numbered. Writes <out>/<movie>_NN.png (12 lines per
sheet) and <out>/lines.json = [{movie, line, start, end, start_s, end_s}] (frames at 29.97 fps)."""
import json, os, sys
import cv2
import numpy as np

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'dump', 'psnova-l10n')
BANDS = {'MP09_040_040': (464, 491), 'MP00_000_000': (470, 497), 'MP00_010_050': (470, 496), 'MP09_040_070': (470, 497),
         'MP06_030_070': (470, 497), 'MP00_000_010': (472, 499), 'MP06_030_050': (470, 497), 'MP06_030_040': (470, 497)}
FPS = 30000 / 1001


def frame(path, k):
    c = cv2.VideoCapture(path); c.set(cv2.CAP_PROP_POS_FRAMES, k); ok, f = c.read(); c.release()
    return f if ok else None


def main():
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    allrows = []
    for mv, (y0, y1) in sorted(BANDS.items()):
        L = np.load(os.path.join(D, 'movies_v3_check', 'lines_%s.npz' % mv))
        rows = []
        for i, (cs, ce) in enumerate(zip(L['cs'], L['ce'])):
            mid = int((cs + ce) // 2)
            jp = frame(os.path.join(D, 'movies_jp', mv + '.mp4'), mid)
            en = frame(os.path.join(D, 'movies', mv + '.mp4'), mid)
            a = jp[y0 - 8:y1 + 8] if jp is not None else np.zeros((y1 - y0 + 16, 960, 3), np.uint8)
            b = en[455:544] if en is not None else np.zeros((89, 960, 3), np.uint8)
            img = np.vstack([a, np.full((4, 960, 3), 80, np.uint8), b])
            img = cv2.resize(img, None, fx=1.5, fy=1.5)
            lab = np.zeros((img.shape[0], 90, 3), np.uint8)
            cv2.putText(lab, '%d' % i, (8, img.shape[0] // 2 + 10), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 2)
            rows.append(np.hstack([lab, img, np.full((img.shape[0], 1, 3), 0, np.uint8)]))
            allrows.append(dict(movie=mv, line=i, start=int(L['a'][i]), end=int(L['b'][i]), core_start=int(cs), core_end=int(ce),
                                start_s=round(int(cs) / FPS, 3), end_s=round(int(ce) / FPS, 3), weak=bool(L['weak'][i])))
        for s in range(0, len(rows), 12):
            sep = np.full((6, rows[0].shape[1], 3), 200, np.uint8)
            sheet = np.vstack(sum([[r, sep] for r in rows[s:s + 12]], []))
            cv2.imwrite(os.path.join(out, '%s_%02d.png' % (mv, s // 12)), sheet)
    json.dump(allrows, open(os.path.join(out, 'lines.json'), 'w', encoding='utf-8', newline='\n'), indent=0)
    print('lines', len(allrows))


if __name__ == '__main__':
    main()
