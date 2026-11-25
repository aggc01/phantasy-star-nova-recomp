"""Redraw Attention.mp4 (the boot anti-piracy notice) in English and Arabic.

The original is 149 frames (4.97 s) at 29.97 fps, 960x544: plain white text on black. It fades in over frames 0-30,
holds, and fades out over frames 119-148. Its audio track is silent (-91 dB) and is copied unchanged.
Measured text block: heading plus 4 lines, glyph rows 141-165, 189-213, 237-261, 284-308, 332-356, x 100-860.

Arabic is shaped by ffmpeg drawtext (text_shaping=1; this ffmpeg-static build has harfbuzz + fribidi), so joined
letter forms and right-to-left order come from HarfBuzz/FriBidi, not from hand reshaping. Each line goes through its
own textfile, so nothing needs escaping.

Run: python dev/psnova/redraw_attention.py   -> dump/psnova-l10n/movies_l10n/Attention_{en,ar}.mp4 (+ _still.png)
The source movie is only read. Nothing here installs or touches the game's archives.
"""
import os, subprocess, sys

R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(R, "dump", "psnova-l10n", "movies_jp", "Attention.mp4")
OUT = os.path.join(R, "dump", "psnova-l10n", "movies_l10n")
FF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'ffmpeg.exe')   # the project's own copy (ffmpeg-static 6.x: libx264, harfbuzz, fribidi)
# fonts: dev/psnova/fonts.json warning_english / warning_arabic (paths relative to the project folder; 2026-11-19)
import json as _json
_FJ = _json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts.json'), encoding='utf-8'))
FONT_FILE = {'en': os.path.join(R, _FJ['warning_english']['file']), 'ar': os.path.join(R, _FJ['warning_arabic']['file'])}

# Japanese original (for the record):
#   <ご注意>
#   ゲームソフトを権利者の許諾なく、インターネットを通じて配信、配布する行為、また、違法なインターネット配信と
#   知りながらダウンロードする行為は法律で固く禁じられております。みなさまのご理解とご協力をお願いいたします。
TEXT = {
    "en": {
        # Three centered lines including the title.
        "size": 20, "heading_size": 32, "align": "center",
        "centers": [223, 278, 319],
        "heading": "Notice",
        "lines": [
            "Sharing this game online without permission or knowingly downloading an illegal copy is prohibited by law.",
            "Thank you for your understanding and cooperation.",
        ],
    },
    "ar": {
        # Segoe UI: with ffmpeg 6.1's drawtext shaping, Dubai drew several letters as boxes and Tahoma placed the
        # tanween on the wrong letter; Segoe UI drew every letter. No tashkeel (normal for on-screen text).
        # RLM (U+200F) after a final period: drawtext lays lines out with a left-to-right base direction, so a
        # trailing period otherwise lands on the right; the RLM makes it resolve right-to-left (left end).
        "font": "segoeui.ttf", "size": 26, "align": "right",
        "heading": "< تنبيه >",
        "lines": [
            "يحظر القانون حظرا تاما توزيع برامج الألعاب أو نشرها عبر الإنترنت",
            "دون إذن صاحب الحقوق، وكذلك تنزيلها مع العلم بأنها منشورة",
            "عبر الإنترنت بصورة غير قانونية.‏",
            "نشكركم على تفهمكم وتعاونكم.‏",
        ],
    },
}

LEFT, RIGHT = 100, 860           # the original's text margins
CENTERS = [153, 201, 249, 296, 344]  # vertical centres of the original's five glyph rows
FRAMES = 149


def ffpath(p):
    # drawtext option values: forward slashes, and the drive colon escaped
    return p.replace("\\", "/").replace(":", "\\:")


def measure_baseline(font, tf, size):
    """Render one line at y=0 and return the row with the most ink (the Arabic joining stroke = baseline)."""
    import numpy as np
    raw = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=960x80",
                          "-vf", f"drawtext=fontfile='{font}':textfile='{ffpath(tf)}':text_shaping=1:"
                                 f"fontsize={size}:fontcolor=white:x=10:y=0,format=gray",
                          "-frames:v", "1", "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
    g = np.frombuffer(raw, np.uint8).reshape(80, 960)
    return int((g > 128).sum(1).argmax())


def build(lang):
    t = TEXT[lang]
    tdir = os.path.join(OUT, "text", lang)
    os.makedirs(tdir, exist_ok=True)
    font = ffpath(os.path.abspath(FONT_FILE[lang]))
    rows = [t["heading"]] + t["lines"]
    parts = []
    for i, line in enumerate(rows):
        tf = os.path.join(tdir, f"line{i}.txt")
        with open(tf, "w", encoding="utf-8", newline="") as f:
            f.write(line)
        size = t.get("heading_size", t["size"]) if i == 0 else t["size"]
        center = t.get("centers", CENTERS)[i]
        if i == 0 or t["align"] == "center":
            x = "(w-text_w)/2"
        elif t["align"] == "right":
            x = f"{RIGHT}-text_w"
        else:
            x = f"{LEFT}"
        # ffmpeg 6.1 places each line by its own tallest glyph, so Arabic rows drifted by a few pixels. For Arabic the
        # baseline (the row with the most ink: the joining stroke) is measured on a test render and each row is put
        # on a fixed grid (row centre + 8). Latin rows looked even with the plain box centring.
        if t["align"] == "right":
            y = str(center + 8 - measure_baseline(font, tf, size))
        else:
            y = f"{center}-(ascent-descent)/2"
        parts.append(f"drawtext=fontfile='{font}':textfile='{ffpath(tf)}':text_shaping=1:fontsize={size}:"
                     f"fontcolor=white:x={x}:y={y}")
    vf = ",".join(parts) + f",fade=t=in:s=0:n=30,fade=t=out:s={FRAMES - 30}:n=30,format=yuv420p"
    mp4 = os.path.join(OUT, f"Attention_{lang}.mp4")
    cmd = [FF, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"color=c=black:s=960x544:r=30000/1001:d={FRAMES * 1001 / 30000:.4f}",
           "-i", SRC,
           "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a",  # video length from the colour source, so the audio keeps its full 5.01 s
           "-c:v", "libx264", "-profile:v", "high", "-level", "3.1", "-refs", "3", "-preset", "slow", "-crf", "16",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-c:a", "copy", "-metadata:s:v", "language=eng", "-metadata:s:a", "language=eng",
           "-movflags", "+faststart", mp4]
    subprocess.run(cmd, check=True)
    still = os.path.join(OUT, f"Attention_{lang}_still.png")
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-ss", "2.5", "-i", mp4, "-frames:v", "1", still],
                   check=True)
    print("wrote", mp4)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for lang in (sys.argv[1:] or ["en", "ar"]):
        build(lang)
