"""Survey the 13 movies that carry no burned-in subtitle line: audio energy / speech-likeness per second + a contact sheet
(a frame every ~3 s, time stamped) to look for spoken dialogue without subtitles. Written 2026-11-18 evening.
Speech-likeness is crude (no speech model installed): fraction of energy in 300-3400 Hz, and 3-8 Hz envelope modulation
of that band (syllable rate); music is flat in both. Judge with the sheets, not the numbers alone.
Output: dump/psnova-l10n/others/<name>_audio.txt, <name>_sheet.png"""
import os, subprocess, sys
import numpy as np, cv2
FF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'ffmpeg.exe')   # the project's own copy (ffmpeg-static 6.x: libx264, harfbuzz, fribidi)
ROOT = r"F:\Antigravity Proj\Recomp-decomp\Phantasy Star Nova Recomp\dump\psnova-l10n"
NAMES = "Attention Logo_SEGA_triAce MP09_030_030 MP09_040_025 MP09_040_030 OpeningDemo Trial_001 Trial_002 Trial_003 Trial_004 Trial_005 Trial_Attention Trial_End".split()
SR = 16000

def audio(name):
    p = subprocess.run([FF, '-v', 'error', '-i', os.path.join(ROOT, 'movies_jp', name + '.mp4'), '-vn', '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True)
    return np.frombuffer(p.stdout, np.int16).astype(np.float32) / 32768

def per_second(x):
    out = []
    for s in range(int(len(x) / SR)):
        seg = x[s * SR:(s + 1) * SR]
        rms = float(np.sqrt((seg ** 2).mean()) + 1e-9)
        sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
        fr = np.fft.rfftfreq(len(seg), 1 / SR)
        tot = sp.sum() + 1e-9
        band = sp[(fr >= 300) & (fr <= 3400)].sum() / tot
        # envelope of the speech band, 20 ms hops, modulation energy at 3-8 Hz relative to total envelope energy
        b = np.fft.rfft(seg); f2 = np.fft.rfftfreq(len(seg), 1 / SR)
        b[(f2 < 300) | (f2 > 3400)] = 0
        y = np.fft.irfft(b, len(seg))
        env = np.abs(y).reshape(-1, 320).mean(axis=1)           # 50 Hz envelope
        e = env - env.mean()
        es = np.abs(np.fft.rfft(e)) ** 2
        ef = np.fft.rfftfreq(len(e), 1 / 50)
        mod = es[(ef >= 3) & (ef <= 8)].sum() / (es.sum() + 1e-12)
        out.append((s, 20 * np.log10(rms), band, mod))
    return out

def sheet(name):
    c = cv2.VideoCapture(os.path.join(ROOT, 'movies_jp', name + '.mp4'))
    n = int(c.get(7)); fps = c.get(5)
    step = max(1, int(round(fps * 3)))
    idx = list(range(0, n, step))[:30]
    tiles = []
    for k in idx:
        c.set(cv2.CAP_PROP_POS_FRAMES, k); ok, f = c.read()
        if not ok: continue
        t = cv2.resize(f, (320, 181)); cv2.putText(t, f'{k/fps:.0f}s', (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        tiles.append(t)
    while len(tiles) % 5: tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + 5]) for i in range(0, len(tiles), 5)]
    cv2.imwrite(os.path.join(ROOT, 'others', name + '_sheet.png'), np.vstack(rows))

if __name__ == '__main__':
    for name in (sys.argv[1:] or NAMES):
        ps = per_second(audio(name))
        with open(os.path.join(ROOT, 'others', name + '_audio.txt'), 'w') as f:
            f.write('sec  dBFS  speechband  mod3-8Hz\n')
            for s, db, b, m in ps: f.write(f'{s:4d} {db:6.1f} {b:6.2f} {m:6.2f}\n')
        sheet(name)
        sp = [m for s, db, b, m in ps if db > -45]
        print(name, 'secs', len(ps), 'loud secs', len(sp), 'mean mod %.2f' % (np.mean(sp) if sp else 0), flush=True)
