"""Nova English subtitle rendering from authored cues and detected story timings."""

from math import ceil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 28
FADE = 6


def load_font(path, size):
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.BASIC)


# Fit English words using a smaller font, never a stretched bitmap.
def fit_english(text, width, font_path, keep_breaks=False):
    words = text.split()
    if not words:
        return [], load_font(font_path, SIZE)
    rows = text.splitlines()
    if keep_breaks and len(rows) > 2:
        raise ValueError('authored subtitle exceeds two lines: ' + text)
    for size in range(SIZE, 0, -1):
        font = load_font(font_path, size)
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


def render(text, font_path, mask_x0, mask_x1, W, H, y_mid, keep_breaks=False):
    lines, font = fit_english(text, W - 64, font_path, keep_breaks)
    widths = [font.getlength(l) for l in lines]
    line_size = font.size
    lh = line_size + 6
    total_h = lh * len(lines)
    # The detected original subtitle supplies a minimum
    # width. Center the backing on the translated text.
    half_width = max(max(widths), mask_x1 - mask_x0) / 2 + 30
    x0, x1 = W / 2 - half_width, W / 2 + half_width
    y0 = y_mid - total_h / 2 - 5
    y1 = y_mid + total_h / 2 + 5
    strip = Image.new('L', (W, H), 0)
    ImageDraw.Draw(strip).rounded_rectangle([x0, y0, x1, y1], radius=10, fill=148)
    strip = strip.filter(ImageFilter.GaussianBlur(4))
    txt = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    for k, (l, w) in enumerate(zip(lines, widths)):
        x = (W - w) / 2
        y = y0 + 5 + k * lh + line_size - 2
        d.text((x, y), l, font=font, fill=(255, 255, 255, 255), anchor='ls', stroke_width=2, stroke_fill=(20, 20, 30, 255))
    return strip, txt              # the strip's alpha (darkened more over bright frames, main()) and the text layer


# Cues without a detection table use artist-authored movie seconds.
def authored_spans(cues, fps, frame_count, width):
    previous_end = 0
    for i, cue in enumerate(cues):
        start = ceil(cue['start'] * fps)
        end = ceil(cue['end'] * fps)
        if not previous_end <= start < end <= frame_count:
            raise ValueError(f'invalid or overlapping subtitle interval in cue {i + 1}')
        yield cue, start, end - 1, width // 2, width // 2
        previous_end = end


def story_spans(cues, timings, width):
    for index, line in enumerate(timings):
        cols = np.flatnonzero(line['mask'].any(axis=0))
        x0, x1 = (int(cols[0]), int(cols[-1])) if len(cols) else (width // 2, width // 2)
        yield {'en': cues.get(str(index), '')}, line['a'], line['b'], x0, x1


class Captions:
    def __init__(self, spans, font_path, width, height, y_mid, keep_breaks):
        self.layers = []
        for cue, start, end, x0, x1 in spans:
            text = (cue.get('en') or '').replace('\\n', '\n').strip()
            if not text:
                continue
            strip, text_layer = render(text, font_path, x0, x1, width, height, y_mid, keep_breaks)
            backing_alpha = np.asarray(strip, dtype=np.float32)[:, :, None] / 255.0
            overlay = np.asarray(text_layer, dtype=np.float32) / 255.0
            rows = np.where(np.maximum(backing_alpha[:, :, 0], overlay[:, :, 3]).max(axis=1) > 0)[0]
            row0, row1 = int(rows.min()), int(rows.max()) + 1
            alpha = overlay[row0:row1, :, 3:4]
            bgr = overlay[row0:row1, :, 2::-1] * alpha
            self.layers.append((start, end, row0, row1, bgr, alpha, backing_alpha[row0:row1]))

    def apply(self, frame_index, frame):
        for start, end, row0, row1, bgr, alpha, backing_alpha in self.layers:
            if not start <= frame_index <= end:
                continue
            fade = min(1.0, (frame_index - start + 1) / FADE, (end - frame_index + 1) / FADE)
            band = frame[row0:row1].astype(np.float32) / 255.0
            under = backing_alpha[:, :, 0] > 0.3
            brightness = float(band[under].mean()) if under.any() else 0.0
            strength = 1.0 + 0.55 * min(1.0, max(0.0, (brightness - 0.45) / 0.35))
            band *= 1 - np.minimum(backing_alpha * strength, 0.92) * fade
            band = band * (1 - alpha * fade) + bgr * fade
            frame[row0:row1] = np.clip(band * 255 + 0.5, 0, 255).astype(np.uint8)
