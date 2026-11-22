"""apply_spec.py - redraw the Japanese labels of one PS Nova UI texture (.aif, DXT3 or DXT1) from a spec (SPEC.md).

usage:
  apply_spec.py <spec.json> <en|ar> <out dir> [--src file.aif] [--quiet]

  -> <out dir>/<texture>.aif            same 0x1e0 header, same file size, same texture ID, same format (DXT3 or DXT1)
     <out dir>/preview/<name>.png       the whole result texture as decoded back from the new .aif
     <out dir>/preview/<name>_ba.png    before (top) above after (bottom), only the changed rows, 2x, on a checkerboard
  (<name> = the texture name without .aif). Exit code 1 when the round-trip check fails, 2 on a spec error.

Steps per label (spec order):
  1. clear the Japanese inside `box` [x0, y0, x1, y1) with `clear`:
       transparent  RGBA (0,0,0,0) (the original textures store transparent pixels as black);
       inpaint      text strokes = pixels that stand out from the local background (median of the surroundings):
                    `inpaint_polarity` "bright" (default: brighter by more than `inpaint_threshold`, default 40, in
                    luma, or of a strongly different colour), "dark" (darker text) or "any"; opposite-sign pixels
                    within `inpaint_shadow` px (default 2) of a stroke join the mask (outline / drop shadow); the
                    mask is dilated by `inpaint_dilate` px (default 1) and repainted by `inpaint_method`:
                    "telea" (default, OpenCV, radius `inpaint_radius` 3) or "ns" from the pixels around it, or
                    "median" = the median background itself (best on flat or smoothly shaded panels);
                    `inpaint_window` = median window (odd px, default ~2x the box height); sources are the box rows
                    and pixels left/right of the box, plus `inpaint_margin` rows above/below (default 0: panel
                    edges just outside the box do not bleed in);
                    `inpaint_mask: "box"` repaints the whole box instead (use with a box hugging the text);
       fill         the box becomes `fill_color` [r,g,b] or [r,g,b,a];
       keep         nothing removed.
  2. draw the language's text ("" = draw nothing) with fonts.json `ui_english` / `ui_arabic`; Arabic lines go through
     dev/psnova/rmdtext/arabic.py to_display() and Pillow's BASIC layout (we shape ourselves, as encode_text.py does).
     `size` null = the largest size whose text block fits the box (width and height, outline included, `pad` px
     free on the left/right, default 1); `align` left/center/right, `valign` top/center/bottom; "\n" = more lines
     (`line_gap` px between them, default 0). `color` [r,g,b(,a)], `outline` [r,g,b(,a)] with `outline_px` (default 1
     when outline is set), `glow` [r,g,b(,a)] with `glow_px` (blur radius, default 2) and `glow_strength` (default 1.0): a soft halo
     under the text.
     Everything is drawn on a layer of the box's size, so nothing leaves the box.
  Per-language overrides: any key may be given as `<key>_<lang>` (e.g. `size_ar`, `align_ar`, `box_en`), which wins.
  Arabic: `align: "left"` becomes "right" unless `align_ar` says otherwise (SPEC.md: Arabic labels align right when
  the Japanese was left-aligned; centred boxes stay centred).
  3. re-encode DXT3: only blocks whose pixels changed are encoded (4-bit explicit alpha written exactly, nearest
     nibble; colour by a weighted principal-axis fit + least-squares refinement on the 565 grid, error measured with
     the decoder's own integer palette), every other block is copied byte for byte; blocks go back in Vita Morton
     order (rmdlib._perm). Then the new file is decoded again and compared with the intended picture.
     DXT1 (format 0x10, e.g. ev_dlc_104): same colour fit; blocks without transparent pixels use 4-colour mode
     (c0 > c1), blocks with any pixel of alpha < 128 use 3-colour mode with index 3 = transparent (1-bit alpha).
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'dev', 'psnova', 'rmdtext'))
sys.path.insert(0, HERE)
import aiftex  # noqa: E402  (needs rmdlib from rmdtext, put on the path above)
import arabic  # noqa: E402

RESEARCH = os.path.join(ROOT, 'dump', 'psnova-l10n', 'scratch', 'research')
HDR = 0x1e0
LANGS = ('en', 'ar')


# ----------------------------------------------------------------------------------------------------------- spec
def opt(label, key, lang, default=None):
    k = '%s_%s' % (key, lang)
    if k in label:
        return label[k]
    return label.get(key, default)


def find_source(spec, src=None):
    if src:
        return src
    name = spec['texture']
    arch = spec.get('archive')
    order = [arch] if arch in ('patch', 'base') else ['patch', 'base']
    for a in order:              # research/<archive>/ first, then the full research render set research/uitex/<archive>/
        for p in (os.path.join(RESEARCH, a, name), os.path.join(RESEARCH, 'uitex', a, name)):
            if os.path.exists(p):
                return p
    raise SystemExit('source texture not found: %s (archive %s)' % (name, arch))


_font_cache = {}
_fonts_cfg = []


def font_for(lang, size):
    if not _fonts_cfg:
        _fonts_cfg.append(json.load(open(os.path.join(ROOT, 'dev', 'psnova', 'fonts.json'), encoding='utf-8')))
    cfg = _fonts_cfg[0]
    ent = cfg['ui_arabic' if lang == 'ar' else 'ui_english']
    path = os.path.join(ROOT, ent['file'])
    key = (path, size)
    if key not in _font_cache:
        try:
            basic = ImageFont.Layout.BASIC
        except AttributeError:
            basic = ImageFont.LAYOUT_BASIC
        _font_cache[key] = ImageFont.truetype(path, size, layout_engine=basic)
    return _font_cache[key]


def rgba(c, default_a=255):
    if c is None:
        return None
    c = [int(v) for v in c]
    return tuple(c[:4]) if len(c) >= 4 else tuple(c[:3]) + (default_a,)


# ----------------------------------------------------------------------------------------------------------- clear
def _region(img, x0, y0, x1, y1, mx, my):
    H, W = img.shape[:2]
    return max(0, x0 - mx), max(0, y0 - my), min(W, x1 + mx), min(H, y1 + my)


def _background(img, x0, y0, x1, y1, k=None, my=0):
    """Median background of the box: window ~2x the box height (glyph strokes are thinner than that), taken from the
    box rows (+ `my` rows above/below) and k px left/right, so panel edges above/below do not leak in.
    Returns (bg RGB of the region, region rectangle)."""
    import cv2
    bh = y1 - y0
    k = int(k) if k else max(5, (bh * 2) | 1)
    k = min(k | 1, 255)
    X0, Y0, X1, Y1 = _region(img, x0, y0, x1, y1, k, my)
    reg = np.ascontiguousarray(img[Y0:Y1, X0:X1, :3])
    return cv2.medianBlur(reg, k), (X0, Y0, X1, Y1)          # 8-bit: any odd kernel size


def _stroke_mask(img, box, thr, polarity='bright', shadow=2, k=None, my=0):
    """Text strokes inside the box: pixels that stand out from the local median background.
    polarity 'bright' = brighter than the background by thr (luma) or of a strongly different colour and not darker;
    'dark' = darker by thr; 'any' = |dR|+|dG|+|dB| > 2*thr. With 'bright'/'dark', pixels of the opposite sign
    (darker/brighter by thr/2) within `shadow` px of a stroke are added: the outline or drop shadow of the text.
    Horizontal runs longer than 2x the box height (panel edges) are left out."""
    import cv2
    x0, y0, x1, y1 = box
    H, W = img.shape[:2]
    bg, (X0, Y0, X1, Y1) = _background(img, x0, y0, x1, y1, k, my)
    rf, bf = img[Y0:Y1, X0:X1, :3].astype(np.int32), bg.astype(np.int32)
    luma = lambda c: (c[..., 0] * 299 + c[..., 1] * 587 + c[..., 2] * 114) // 1000
    dl = luma(rf) - luma(bf)
    dsum = np.abs(rf - bf).sum(-1)
    if polarity == 'any':
        mask = dsum > 2 * thr
    else:
        if polarity == 'dark':
            core, rim = dl < -thr, dl > thr // 2
        else:
            core, rim = (dl > thr) | ((dsum > 3 * thr) & (dl > -thr // 2)), dl < -(thr // 2)
        # long horizontal runs are panel edges or underlines, not glyph strokes (a katakana bar is about one glyph
        # wide, i.e. about the box height): drop runs longer than 2x the box height
        L = max(24, 2 * (y1 - y0) + 1)
        line = cv2.morphologyEx(core.astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, L), np.uint8)).astype(bool)
        core = core & ~line
        mask = core
        if shadow > 0:
            near = cv2.dilate(core.astype(np.uint8), np.ones((2 * shadow + 1, 2 * shadow + 1), np.uint8)).astype(bool)
            mask = core | (rim & near)
    out = np.zeros((H, W), np.uint8)
    out[Y0:Y1, X0:X1] = mask
    keep = np.zeros_like(out); keep[y0:y1, x0:x1] = 1
    return out * keep


def clear_box(img, label, lang):
    x0, y0, x1, y1 = [int(v) for v in opt(label, 'box', lang)]
    mode = opt(label, 'clear', lang, 'transparent')
    if mode == 'transparent':
        img[y0:y1, x0:x1] = 0
    elif mode == 'fill':
        img[y0:y1, x0:x1] = rgba(opt(label, 'fill_color', lang, [0, 0, 0, 0]))
    elif mode == 'keep':
        pass
    elif mode == 'inpaint':
        import cv2
        H, W = img.shape[:2]
        box = np.zeros((H, W), np.uint8); box[y0:y1, x0:x1] = 1
        k = opt(label, 'inpaint_window', lang, None)
        my = int(opt(label, 'inpaint_margin', lang, 0))     # rows above/below the box used as source
        if opt(label, 'inpaint_mask', lang, 'auto') == 'box':
            mask = box.copy()
        else:
            mask = _stroke_mask(img, (x0, y0, x1, y1), int(opt(label, 'inpaint_threshold', lang, 40)),
                                opt(label, 'inpaint_polarity', lang, 'bright'),
                                int(opt(label, 'inpaint_shadow', lang, 2)), k, my)
            dil = int(opt(label, 'inpaint_dilate', lang, 1))
            if dil > 0:
                mask = cv2.dilate(mask, np.ones((2 * dil + 1, 2 * dil + 1), np.uint8)) * box
        method = opt(label, 'inpaint_method', lang, 'telea')
        if method == 'median':                      # the median background itself (flat or smoothly shaded panels)
            bg, (X0, Y0, X1, Y1) = _background(img, x0, y0, x1, y1, k, my)
            sel = mask[Y0:Y1, X0:X1].astype(bool)
            img[Y0:Y1, X0:X1, :3][sel] = bg[sel]
        elif method in ('telea', 'ns'):
            r = int(opt(label, 'inpaint_radius', lang, 3))
            X0, Y0, X1, Y1 = _region(img, x0, y0, x1, y1, max(16, 4 * r), my)
            sub = np.ascontiguousarray(img[Y0:Y1, X0:X1, :3])
            rep = cv2.inpaint(sub, np.ascontiguousarray(mask[Y0:Y1, X0:X1] * 255), r,
                              cv2.INPAINT_TELEA if method == 'telea' else cv2.INPAINT_NS)
            sel = mask[Y0:Y1, X0:X1].astype(bool)
            img[Y0:Y1, X0:X1, :3][sel] = rep[sel]
        else:
            raise ValueError('unknown inpaint_method %r' % method)
        # alpha is kept as it was (screenshots are opaque)
    else:
        raise ValueError('unknown clear mode %r' % mode)


# ----------------------------------------------------------------------------------------------------------- draw
def _lines(text, lang):
    ls = text.split('\n')
    return [arabic.to_display(l) for l in ls] if lang == 'ar' else ls


def _measure(lines, font, stroke, gap):
    """Per-line ink boxes (union with the 'Hg' reference so baselines stay put); returns (width, height, rows)."""
    ref = font.getbbox('Hg', stroke_width=stroke)
    rows, y, wmax = [], 0, 0
    for l in lines:
        b = font.getbbox(l, stroke_width=stroke) if l else ref
        top, bot = min(b[1], ref[1]), max(b[3], ref[3])
        left, right = (b[0], b[2]) if l else (0, 0)
        rows.append((l, left, right, top, bot, y))
        y += bot - top + gap
        wmax = max(wmax, right - left)
    return wmax, y - gap, rows


def draw_label(img, label, lang, log):
    text = opt(label, lang, lang, None)
    if text is None:
        text = ''
    if text == '':
        return None
    x0, y0, x1, y1 = [int(v) for v in opt(label, 'box', lang)]
    bw, bh = x1 - x0, y1 - y0
    color = rgba(opt(label, 'color', lang, [255, 255, 255]))
    outline = rgba(opt(label, 'outline', lang, None))
    stroke = int(opt(label, 'outline_px', lang, 1 if outline else 0)) if outline else 0
    glow = rgba(opt(label, 'glow', lang, None))
    glow_px = float(opt(label, 'glow_px', lang, 2))
    pad = int(opt(label, 'pad', lang, 1))
    gap = int(opt(label, 'line_gap', lang, 0))
    align = opt(label, 'align', lang, 'center')
    if lang == 'ar' and align == 'left' and 'align_ar' not in label:
        align = 'right'
    valign = opt(label, 'valign', lang, 'center')
    lines = _lines(text, lang)
    size = opt(label, 'size', lang, None)
    fits = True
    if size is None:
        size = None
        for s in range(min(200, 3 * bh), 5, -1):
            w, h, _ = _measure(lines, font_for(lang, s), stroke, gap)
            if w <= bw - 2 * pad and h <= bh:
                size = s; break
        if size is None:
            size, fits = 6, False
    size = int(size)
    font = font_for(lang, size)
    w, h, rows = _measure(lines, font, stroke, gap)
    if w > bw - 2 * pad or h > bh:
        fits = False
    layer = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    if valign == 'top':
        ty = 0
    elif valign == 'bottom':
        ty = bh - h
    else:
        ty = (bh - h) // 2
    for l, left, right, top, bot, yy in rows:
        if not l:
            continue
        lw = right - left
        if align == 'left':
            tx = pad - left
        elif align == 'right':
            tx = bw - pad - lw - left
        else:
            tx = (bw - lw) // 2 - left
        dr.text((tx, ty + yy - top), l, font=font, fill=color,
                stroke_width=stroke, stroke_fill=outline if stroke else None)
    if glow:
        k = float(opt(label, 'glow_strength', lang, 1.0)) * glow[3] / 255
        a = layer.split()[3].filter(ImageFilter.GaussianBlur(glow_px))
        a = a.point(lambda v: min(255, int(v * k)))
        g = Image.new('RGBA', layer.size, glow[:3] + (0,)); g.putalpha(a)
        g.alpha_composite(layer)
        layer = g
    region = Image.fromarray(np.ascontiguousarray(img[y0:y1, x0:x1]), 'RGBA')
    region.alpha_composite(layer)
    img[y0:y1, x0:x1] = np.array(region)
    log('  %-14s -> %-28s size %3d  %s%s' % (label.get('jp', '')[:14], text.replace('\n', ' / ')[:28], size,
                                          '' if fits else 'DOES NOT FIT ', '(text %dx%d in box %dx%d)' % (w, h, bw, bh)))
    return fits


# ----------------------------------------------------------------------------------------------------------- DXT3
def _expand(c):
    """565 integer endpoints (N,3) -> 888 the way the decoder (aiftex.rgb565) expands them."""
    return np.stack([c[:, 0] * 255 // 31, c[:, 1] * 255 // 63, c[:, 2] * 255 // 31], -1)


def _quant(e):
    e = np.clip(e, 0, 255)
    return np.stack([np.rint(e[:, 0] * 31 / 255), np.rint(e[:, 1] * 63 / 255), np.rint(e[:, 2] * 31 / 255)],
                    -1).astype(np.int64)


def _eval(X, Wt, q0, q1):
    p0, p1 = _expand(q0), _expand(q1)
    pal = np.stack([p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3], 1).astype(np.float64)   # (N,4,3)
    d = ((X[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)                                # (N,16,4)
    sel = d.argmin(-1)
    err = (np.take_along_axis(d, sel[..., None], -1)[..., 0] * Wt).sum(-1)
    return sel, err


def encode_colour(X, Wt):
    """X (N,16,3) float 0..255, Wt (N,16) weights -> (c0, c1 uint16 (N,), sel (N,16))."""
    N = X.shape[0]
    ws = Wt.sum(1, keepdims=True)
    ws = np.where(ws > 0, ws, 1)
    mu = (X * Wt[..., None]).sum(1) / ws
    D = X - mu[:, None, :]
    C = np.einsum('nki,nkj,nk->nij', D, D, Wt)
    v = np.ones((N, 3)) / np.sqrt(3)
    for _ in range(12):
        v2 = np.einsum('nij,nj->ni', C, v)
        nrm = np.linalg.norm(v2, axis=1, keepdims=True)
        v = np.where(nrm > 1e-9, v2 / np.maximum(nrm, 1e-12), v)
    t = np.einsum('nki,ni->nk', D, v)
    on = Wt > 0
    tmin = np.where(on, t, np.inf).min(1); tmax = np.where(on, t, -np.inf).max(1)
    tmin = np.where(np.isfinite(tmin), tmin, 0); tmax = np.where(np.isfinite(tmax), tmax, 0)
    e0 = mu + tmax[:, None] * v; e1 = mu + tmin[:, None] * v
    best0, best1 = _quant(e0), _quant(e1)
    bsel, berr = _eval(X, Wt, best0, best1)
    # a 1/16 inset of the range is often better for smooth blocks
    ins = (tmax - tmin)[:, None] / 16
    q0, q1 = _quant(e0 - ins * v), _quant(e1 + ins * v)
    s, e = _eval(X, Wt, q0, q1)
    better = e < berr
    best0[better], best1[better], bsel[better], berr[better] = q0[better], q1[better], s[better], e[better]
    # least-squares refinement of the endpoints for the chosen indices
    wa = np.array([1.0, 0.0, 2 / 3, 1 / 3])
    for _ in range(3):
        a = wa[bsel]; b = 1 - a
        aa = (Wt * a * a).sum(1); bb = (Wt * b * b).sum(1); ab = (Wt * a * b).sum(1)
        ax = (Wt[..., None] * a[..., None] * X).sum(1); bx = (Wt[..., None] * b[..., None] * X).sum(1)
        det = aa * bb - ab * ab
        ok = np.abs(det) > 1e-9
        dd = np.where(ok, det, 1)[:, None]
        n0 = (ax * bb[:, None] - bx * ab[:, None]) / dd
        n1 = (bx * aa[:, None] - ax * ab[:, None]) / dd
        n0 = np.where(ok[:, None], n0, mu); n1 = np.where(ok[:, None], n1, mu)
        q0, q1 = _quant(n0), _quant(n1)
        s, e = _eval(X, Wt, q0, q1)
        better = e < berr
        if not better.any():
            break
        best0[better], best1[better], bsel[better], berr[better] = q0[better], q1[better], s[better], e[better]
    # greedy polish: move one endpoint channel by one 565 step while that lowers the block error
    lim = np.array([31, 63, 31])
    for _ in range(6):
        improved = False
        for which in (0, 1):
            for ch in range(3):
                for step in (-1, 1):
                    q0, q1 = best0.copy(), best1.copy()
                    q = q0 if which == 0 else q1
                    q[:, ch] = np.clip(q[:, ch] + step, 0, lim[ch])
                    s, e = _eval(X, Wt, q0, q1)
                    better = e < berr - 1e-9
                    if better.any():
                        improved = True
                        best0[better], best1[better], bsel[better], berr[better] = \
                            q0[better], q1[better], s[better], e[better]
        if not improved:
            break
    c0 = (best0[:, 0] << 11) | (best0[:, 1] << 5) | best0[:, 2]
    c1 = (best1[:, 0] << 11) | (best1[:, 1] << 5) | best1[:, 2]
    return c0.astype(np.uint16), c1.astype(np.uint16), bsel


def _pack_colour(out, o, c0, c1, sel):
    out[:, o] = c0 & 255; out[:, o + 1] = c0 >> 8; out[:, o + 2] = c1 & 255; out[:, o + 3] = c1 >> 8
    bits = np.zeros(out.shape[0], np.uint32)
    for i in range(16):
        bits |= sel[:, i].astype(np.uint32) << np.uint32(2 * i)
    for k in range(4):
        out[:, o + 4 + k] = (bits >> np.uint32(8 * k)) & 255


def _unpack565(c):
    c = c.astype(np.int64)
    return np.stack([(c >> 11) & 31, (c >> 5) & 63, c & 31], -1)


def encode_blocks_bc1(px):
    """px (N,16,4) uint8 RGBA -> (N,8) uint8 DXT1 blocks (1-bit alpha at 128)."""
    N = px.shape[0]
    out = np.zeros((N, 8), np.uint8)
    X = px[..., :3].astype(np.float64)
    opaque = px[..., 3] >= 128
    Wt = opaque.astype(np.float64)
    allt = ~opaque.any(1)
    Wt[allt] = 1.0                                                   # fully transparent block: any colour (black)
    c0, c1, sel = encode_colour(X, Wt)
    c0 = c0.astype(np.int64); c1 = c1.astype(np.int64); sel = sel.astype(np.int64)
    hast = ~opaque.all(1)
    # 4-colour mode (no transparent pixel): needs c0 > c1
    four = ~hast
    sw = four & (c0 < c1)
    c0[sw], c1[sw] = c1[sw].copy(), c0[sw].copy()
    sel[sw] = np.array([1, 0, 3, 2])[sel[sw]]
    eq = four & (c0 == c1)
    sel[eq] = 0                                                      # equal endpoints decode as 3-colour: index 0 = c0
    # 3-colour mode (some pixel transparent): c0 <= c1, palette c0, c1, (c0+c1)/2, index 3 = transparent
    if hast.any():
        a, b = np.minimum(c0[hast], c1[hast]), np.maximum(c0[hast], c1[hast])
        c0[hast], c1[hast] = a, b
        p0 = _expand(_unpack565(a)); p1 = _expand(_unpack565(b))
        pal = np.stack([p0, p1, (p0 + p1) // 2], 1).astype(np.float64)
        d = ((X[hast][:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)
        s3 = d.argmin(-1)
        s3[~opaque[hast]] = 3
        sel[hast] = s3
    _pack_colour(out, 0, c0, c1, sel)
    return out


def encode_blocks(px, fmt=0x12):
    """px (N,16,4) uint8 RGBA, pixel i = row i//4, column i%4 of the block -> (N,16) uint8 DXT3 blocks
    (fmt 0x10: (N,8) DXT1 blocks)."""
    if fmt == 0x10:
        return encode_blocks_bc1(px)
    N = px.shape[0]
    out = np.zeros((N, 16), np.uint8)
    a = (px[..., 3].astype(np.int32) + 8) // 17                     # nearest of the 16 levels (x17)
    out[:, :8] = (a[:, 0::2] | (a[:, 1::2] << 4)).astype(np.uint8)  # pixel i -> nibble i, low nibble first
    X = px[..., :3].astype(np.float64)
    Wt = np.maximum(px[..., 3].astype(np.float64) / 255.0, 0.02)    # transparent pixels: tiny weight (stay near black)
    c0, c1, sel = encode_colour(X, Wt)
    _pack_colour(out, 8, c0, c1, sel)
    return out


def to_blocks(img):
    H, W = img.shape[:2]
    return img.reshape(H // 4, 4, W // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(H // 4, W // 4, 16, 4)


def reencode(d, orig, new):
    """Return (new file bytes, changed block mask (bh,bw)). Unchanged blocks are copied from d byte for byte."""
    W, H, fmt, tid = aiftex.info(d)
    bw, bh = W // 4, H // 4
    bs = aiftex.FMT[fmt][1]
    ob, nb = to_blocks(orig), to_blocks(new)
    changed = (ob != nb).any(axis=(2, 3))                         # (bh, bw)
    perm = aiftex._perm(bw, bh)                                    # perm[by, bx] = block index in the file
    data = np.frombuffer(d, np.uint8, count=bw * bh * bs, offset=HDR).reshape(-1, bs).copy()
    if changed.any():
        enc = encode_blocks(nb[changed], fmt)
        data[perm[changed]] = enc
    out = d[:HDR] + data.tobytes() + d[HDR + bw * bh * bs:]
    assert len(out) == len(d)
    return out, changed


# ----------------------------------------------------------------------------------------------------------- previews
def _checker(h, w, s=8):
    yy, xx = np.mgrid[0:h, 0:w]
    c = np.where(((yy // s) + (xx // s)) % 2 == 0, 96, 128).astype(np.uint8)
    return np.stack([c, c, c + 8, np.full_like(c, 255)], -1)


def _flat(img):
    bg = Image.fromarray(_checker(*img.shape[:2]), 'RGBA')
    bg.alpha_composite(Image.fromarray(img, 'RGBA'))
    return np.array(bg.convert('RGB'))


def before_after(before, after, changed, path, scale=2, margin=8):
    """Only the rows (and the columns around them) that changed: runs of changed block rows, before over after."""
    H, W = before.shape[:2]
    rows = np.where(changed.any(1))[0]
    cols = np.where(changed.any(0))[0]
    if rows.size == 0:
        return False
    xa, xb = max(0, cols.min() * 4 - 3 * margin), min(W, cols.max() * 4 + 4 + 3 * margin)
    runs, s, p = [], rows[0], rows[0]
    for r in rows[1:]:
        if r - p > 3:
            runs.append((s, p)); s = r
        p = r
    runs.append((s, p))
    strips = []
    for a, b in runs:
        ya, yb = max(0, a * 4 - margin), min(H, b * 4 + 4 + margin)
        sep = np.zeros((2, xb - xa, 3), np.uint8); sep[:] = (255, 200, 0)
        strips.append(np.concatenate([_flat(before[ya:yb, xa:xb]), sep, _flat(after[ya:yb, xa:xb])], 0))
        strips.append(np.full((6, xb - xa, 3), 20, np.uint8))
    pic = np.concatenate(strips[:-1], 0)
    im = Image.fromarray(pic, 'RGB')
    im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(path)
    return True


# ----------------------------------------------------------------------------------------------------------- main
def apply(spec_path, lang, out_dir, src=None, quiet=False):
    log = (lambda *a: None) if quiet else print
    spec = json.load(open(spec_path, encoding='utf-8'))
    src = find_source(spec, src)
    d = open(src, 'rb').read()
    W, H, fmt, tid = aiftex.info(d)
    if fmt not in (0x10, 0x12):
        raise SystemExit('%s: format 0x%02x, only DXT3 (0x12) and DXT1 (0x10) are supported' % (src, fmt))
    bs = aiftex.FMT[fmt][1]
    nbytes = (W // 4) * (H // 4) * bs
    orig = aiftex.decode(d[HDR:], W, H, fmt)
    img = orig.copy()
    log('%s [%s] %s %dx%d id %06x' % (spec['texture'], lang, os.path.relpath(src, ROOT), W, H, tid))
    labels = spec.get('labels', [])
    for lab in labels:                      # clear everything first, then draw (neighbouring boxes cannot erase text)
        clear_box(img, lab, lang)
    nfit = 0
    for lab in labels:
        if draw_label(img, lab, lang, log) is False:
            nfit += 1
    new_d, changed = reencode(d, orig, img)
    # ---- round-trip check
    W2, H2, fmt2, tid2 = aiftex.info(new_d)
    assert (W2, H2, fmt2, tid2) == (W, H, fmt, tid) and new_d[:HDR] == d[:HDR] and len(new_d) == len(d)
    back = aiftex.decode(new_d[HDR:], W, H, fmt)
    ob = np.frombuffer(d, np.uint8, count=nbytes, offset=HDR).reshape(-1, bs)
    nb = np.frombuffer(new_d, np.uint8, count=nbytes, offset=HDR).reshape(-1, bs)
    perm = aiftex._perm(W // 4, H // 4)
    untouched = ~changed
    same_bytes = (ob[perm[untouched]] == nb[perm[untouched]]).all()
    tail_same = new_d[HDR + nbytes:] == d[HDR + nbytes:]
    if fmt == 0x10:
        aq = np.where(img[..., 3] >= 128, 255, 0)                  # DXT1: 1-bit alpha
    else:
        aq = ((img[..., 3].astype(np.int32) + 8) // 17) * 17
    a_err = np.abs(back[..., 3].astype(np.int32) - img[..., 3].astype(np.int32)).max()
    a_exact = (back[..., 3].astype(np.int32) == aq).all()
    vis = (img[..., 3] >= 128) & np.repeat(np.repeat(changed, 4, 0), 4, 1)   # visible pixels of re-encoded blocks
    cerr = np.abs(back[..., :3].astype(np.int32) - img[..., :3].astype(np.int32)).max(-1)
    cmax = int(cerr[vis].max()) if vis.any() else 0
    cmean = float(cerr[vis].mean()) if vis.any() else 0.0
    # 4 colours per block on a line: a block holding white fill, dark outline and the anti-aliased greys between them
    # can be off by up to (255-0)/6 = 43 on a mid grey; measured on the button guide: max 40, mean ~10 (Pillow's
    # DXT3 encoder on the same blocks: max 45, mean 12.9)
    # Screenshots (inpaint) hold blocks with more than 4 colours, so a single pixel may be off by more; the check fails
    # only on structure (header, size, untouched bytes, alpha) or a mean that points to an encoder fault.
    ok = bool(same_bytes and tail_same and a_exact and cmean <= 16)
    if cmax > 48:
        log('  note: some re-encoded pixels differ by up to %d (blocks with more than 4 colours; DXT limit)' % cmax)
    log('  blocks re-encoded %d of %d; untouched blocks byte-identical: %s; alpha exact (%s): %s (max %d); '
        'colour error on visible re-encoded pixels: max %d, mean %.2f -> %s'
        % (int(changed.sum()), changed.size, same_bytes and tail_same, '1-bit' if fmt == 0x10 else '4-bit',
           a_exact, a_err, cmax, cmean,
           'OK' if ok else 'CHECK FAILED'))
    # ---- outputs
    os.makedirs(os.path.join(out_dir, 'preview'), exist_ok=True)
    out_aif = os.path.join(out_dir, spec['texture'])
    open(out_aif, 'wb').write(new_d)
    stem = os.path.splitext(spec['texture'])[0]
    Image.fromarray(back, 'RGBA').save(os.path.join(out_dir, 'preview', stem + '.png'))
    before_after(orig, back, changed, os.path.join(out_dir, 'preview', stem + '_ba.png'))
    if nfit:
        log('  WARNING: %d label(s) do not fit their box' % nfit)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('spec'); ap.add_argument('lang', choices=LANGS); ap.add_argument('out_dir')
    ap.add_argument('--src', help='source .aif (default: patch copy, else base, per the spec)')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    try:
        ok = apply(a.spec, a.lang, a.out_dir, a.src, a.quiet)
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print('spec error in %s: %r' % (a.spec, e)); sys.exit(2)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
