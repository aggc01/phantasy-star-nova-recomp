"""Burn English or Arabic subtitles into a Phantasy Star Nova movie (2026-11-19).

usage: python burn_subs.py <source.mp4> <subs.json> [<lines.npz>] <out.mp4> --lang en|ar --y0 470 --y1 497 [--preview dir]

- subs.json: dump/psnova-l10n/subs/<movie>.json ({"lines": [{"line", "en", "ar", ...}]}); lines.npz: the cleaning's line
  table (dump/psnova-l10n/movies_v3_check/lines_<movie>.npz: cs/ce = frames of the line at full strength, a/b = with its
  fades, masks = where the Japanese text was).
- For authored timings, omit lines.npz and give each cue start/end in movie seconds.
  Authored English line breaks are preserved. Done by Codex.
- Each subtitle gets a soft dark strip (rounded, 58 % black) centered on the text. The translated text and the
  detected Japanese line set its minimum width. Done by Codex.
  The text is white with a dark outline. Fades: 6 frames in and out over the line's own time (a..b).
- Text: fonts and sizes from fonts.json, with Arabic shaping from arabic.py.
  Captions are centred and use up to two lines. Empty translations draw nothing.
- Output: libx264 CRF 19, preset medium, high@4.0, yuv420p, audio copied, faststart (as the cleaner); exit 1 unless the
  frame count matches. IDLE CPU priority on Windows.
"""
import argparse, ctypes, json, os, subprocess, sys
from math import ceil
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'rmdtext'))
from arabic import to_display

FFMPEG = os.path.join(HERE, '..', '..', 'tools', 'ffmpeg.exe')
# fonts and sizes: dev/psnova/fonts.json subs_english / subs_arabic (paths relative to the project folder)
_FJ = json.load(open(os.path.join(HERE, 'fonts.json'), encoding='utf-8'))
_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
FONTS = {'en': os.path.join(_ROOT, _FJ['subs_english']['file']), 'ar': os.path.join(_ROOT, _FJ['subs_arabic']['file'])}
SIZES = {'en': _FJ['subs_english'].get('size', 24), 'ar': _FJ['subs_arabic'].get('size', 24)}
SIZE = 24                                   # set per language in main()
FADE = 6


def lang_font(lang, size=None):
    size = size or SIZE
    try:
        return ImageFont.truetype(FONTS[lang], size, layout_engine=ImageFont.Layout.BASIC)
    except AttributeError:
        return ImageFont.truetype(FONTS[lang], size, layout_engine=ImageFont.LAYOUT_BASIC)


# Done by Codex: fit English words using a smaller font, never a stretched bitmap.
def fit_english(text, width, keep_breaks=False):
    words = text.split()
    if not words:
        return [], lang_font('en')
    rows = text.splitlines()
    if keep_breaks and len(rows) > 2:
        raise ValueError('authored subtitle exceeds two lines: ' + text)
    for size in range(SIZES['en'], 0, -1):
        font = lang_font('en', size)
        if keep_breaks:
            if max(font.getlength(row) for row in rows) <= width:
                return rows, font
            continue
        candidates = [([' '.join(words)], font.getlength(' '.join(words)))]
        candidates += [([ ' '.join(words[:i]), ' '.join(words[i:]) ],
                        max(font.getlength(' '.join(words[:i])), font.getlength(' '.join(words[i:]))))
                       for i in range(1, len(words))]
        lines, widest = (candidates[0] if candidates[0][1] <= width else
                         min(candidates[1:], key=lambda item: item[1]) if len(candidates) > 1 else candidates[0])
        if widest <= width:
            return lines, font
    raise ValueError('subtitle cannot fit in two lines: ' + text)


def render(text, lang, font, mask_x0, mask_x1, W, H, y_mid, keep_breaks=False):
    """-> (RGBA overlay W x H) for one subtitle"""
    if lang == 'en':
        lines, font = fit_english(text, W - 64, keep_breaks)
    else:
        lines = [l for l in text.split('\n') if l.strip()][:2]
    if lang == 'ar':
        lines = [to_display(l) for l in lines]
    widths = [font.getlength(l) for l in lines]
    line_size = font.size
    lh = line_size + 6
    total_h = lh * len(lines)
    # Done by Codex. The detected original subtitle supplies a minimum
    # width. Center the backing on the translated text.
    half_width = max(max(widths), mask_x1 - mask_x0) / 2 + 30
    x0, x1 = W / 2 - half_width, W / 2 + half_width
    y0 = y_mid - total_h / 2 - 5; y1 = y_mid + total_h / 2 + 5
    strip = Image.new('L', (W, H), 0)
    ImageDraw.Draw(strip).rounded_rectangle([x0, y0, x1, y1], radius=10, fill=148)
    strip = strip.filter(ImageFilter.GaussianBlur(4))
    txt = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    for k, (l, w) in enumerate(zip(lines, widths)):
        x = (W - w) / 2; y = y0 + 5 + k * lh + line_size - 2
        d.text((x, y), l, font=font, fill=(255, 255, 255, 255), anchor='ls', stroke_width=2, stroke_fill=(20, 20, 30, 255))
    return strip, txt              # the strip's alpha (darkened more over bright frames, main()) and the text layer


# Done by Codex. Cues without a detection table use artist-authored movie seconds.
def authored_spans(cues, fps, frame_count, width):
    previous_end = 0
    for i, cue in enumerate(cues):
        start = ceil(cue['start'] * fps)
        end = ceil(cue['end'] * fps)
        if not previous_end <= start < end <= frame_count:
            raise ValueError(f'invalid or overlapping subtitle interval in cue {i + 1}')
        yield cue, start, end - 1, width // 2, width // 2
        previous_end = end


def detected_spans(cues, timings, width):
    by_line = {cue['line']: cue for cue in cues}
    for i in range(len(timings['cs'])):
        cols = np.flatnonzero(timings['masks'][i].any(axis=0))
        x0, x1 = (int(cols[0]), int(cols[-1])) if len(cols) else (width // 2, width // 2)
        yield by_line.get(i, {}), int(timings['a'][i]), int(timings['b'][i]), x0, x1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('subs'); ap.add_argument('lines', nargs='?'); ap.add_argument('dst')
    ap.add_argument('--lang', required=True); ap.add_argument('--y0', type=int, required=True); ap.add_argument('--y1', type=int, required=True)
    ap.add_argument('--preview'); ap.add_argument('--normal', action='store_true')
    a = ap.parse_args()
    if os.name == 'nt' and not a.normal:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
    with open(a.subs, encoding='utf-8') as subs:
        cues = json.load(subs)['lines']
    cap = cv2.VideoCapture(a.src); fps = cap.get(cv2.CAP_PROP_FPS); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not cap.isOpened() or fps <= 0 or n <= 0:
        ap.error(f'cannot read movie: {a.src}')
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    global SIZE
    SIZE = SIZES[a.lang]
    font = lang_font(a.lang)
    y_mid = (a.y0 + a.y1) / 2
    spans = []                                   # (start, end, overlay premultiplied float arrays)
    if a.lines:
        with np.load(a.lines) as timings:
            cue_spans = list(detected_spans(cues, timings, W))
    else:
        cue_spans = authored_spans(cues, fps, n, W)
    for i, (cue, start, end, mx0, mx1) in enumerate(cue_spans):
        text = (cue.get(a.lang) or '').replace('\\n', '\n').strip()
        if not text:
            continue
        st, tx = render(text, a.lang, font, mx0, mx1, W, H, y_mid, keep_breaks=not a.lines)
        sa = np.asarray(st).astype(np.float32)[:, :, None] / 255.0
        ov = np.asarray(tx).astype(np.float32) / 255.0
        ys = np.where(np.maximum(sa[:, :, 0], ov[:, :, 3]).max(axis=1) > 0)[0]
        r0, r1 = int(ys.min()), int(ys.max()) + 1
        rgb = ov[r0:r1, :, 2::-1] * ov[r0:r1, :, 3:4]          # text RGBA -> premultiplied BGR
        spans.append((start, end, r0, r1, rgb, ov[r0:r1, :, 3:4], sa[r0:r1], i))
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
           '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps:.6f}', '-i', '-',
           '-i', a.src, '-map', '0:v', '-map', '1:a?',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p',
           '-profile:v', 'high', '-level', '4.0', '-c:a', 'copy', '-movflags', '+faststart', a.dst]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    k = wrote = 0; shown = set()
    while True:
        ok, f = cap.read()
        if not ok:
            break
        for (s0, s1, r0, r1, rgb, al, sa, i) in spans:
            if s0 <= k <= s1:
                g = min(1.0, (k - s0 + 1) / FADE, (s1 - k + 1) / FADE)
                part = f[r0:r1].astype(np.float32) / 255.0
                # over a bright frame (a white flash, a sunlit sky) the strip darkens up to ~90 % so the text stays
                # readable (the recomp session saw MP00_000_000's line at frame ~3450 hard to read, 2026-11-19)
                under = sa[:, :, 0] > 0.3
                lum = float(part[under].mean()) if under.any() else 0.0
                sf = 1.0 + 0.55 * min(1.0, max(0.0, (lum - 0.45) / 0.35))
                part = part * (1 - np.minimum(sa * sf, 0.92) * g)
                part = part * (1 - al * g) + rgb * g
                f = f.copy(); f[r0:r1] = np.clip(part * 255 + 0.5, 0, 255).astype(np.uint8)
                if a.preview and i not in shown and k >= (s0 + s1) // 2:
                    shown.add(i); cv2.imwrite(os.path.join(a.preview, 'line%02d_%05d.png' % (i, k)), f)
        p.stdin.write(f.tobytes()); wrote += 1; k += 1
    p.stdin.close(); rc = p.wait()
    print(f'{a.dst}: {len(spans)} subtitles, wrote {wrote} frames (source {n}), ffmpeg rc {rc}', flush=True)
    sys.exit(0 if rc == 0 and wrote == n else 1)


if __name__ == '__main__':
    main()
