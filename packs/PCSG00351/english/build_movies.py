"""Build the English movie archive from your own copy of the game: the burned-in Japanese subtitles are removed from the
story movies and English subtitles drawn in their place."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
RECIPES = HERE / 'movies'
sys.path[:0] = [str(RECIPES), str(HERE.parents[2] / 'pipeline/cri')]   # (the repository's pipeline/cri)

import cleaner
import cpk
import repack
import subtitles


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def encode(ffmpeg, source, destination, frames, transform, crf=19):
    video = cv2.VideoCapture(str(source))
    try:
        fps = video.get(cv2.CAP_PROP_FPS)
        width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not video.isOpened() or (width, height) != (960, 544) or not 29.9 < fps < 30:
            raise ValueError(f'{source.name}: expected 960 x 544 video at 29.97 FPS')
        command = [
            str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{width}x{height}',
            '-r', f'{fps:.6f}', '-i', '-', '-i', str(source),
            '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium',
            '-crf', str(crf), '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level', '4.0',
            '-c:a', 'copy', '-movflags', '+faststart', str(destination),
        ]
        with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
            count = 0
            try:
                while True:
                    ok, frame = video.read()
                    if not ok:
                        break
                    transform(count, frame)
                    encoder.stdin.write(frame.tobytes())
                    count += 1
                encoder.stdin.close()
                if encoder.wait():
                    raise RuntimeError(f'{source.name}: FFmpeg failed to encode the video')
            except BaseException:
                if encoder.poll() is None:
                    encoder.kill()
                raise
        if count != frames:
            raise ValueError(f'{source.name}: decoded {count} frames, expected {frames}')
    finally:
        video.release()


def movie_size(path):
    cap = cv2.VideoCapture(str(path))
    try:
        return (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        )
    finally:
        cap.release()


def build_story(ffmpeg, font, source, output, recipe):
    top, bottom = recipe['top'], recipe['bottom']
    signal = np.unpackbits(
        np.frombuffer(bytes.fromhex(recipe['presence_bits']), dtype=np.uint8),
        count=recipe['frames'],
    ).astype(bool)
    analysis = cleaner.analyse(source, top, bottom, recipe['threshold'], signal)
    if len(analysis['lines']) != recipe['expected_lines']:
        raise ValueError(f'{source.name}: the Japanese subtitle detector returned {len(analysis["lines"])} '
                         f'lines, expected {recipe["expected_lines"]}')
    filler = cleaner.Filler(analysis, top, bottom)
    clean = source.with_name('clean.mp4')

    def remove_japanese(index, frame):
        if index < recipe['frames']:
            band = filler.fill(index)
            if band is not None:
                frame[filler.m0:filler.m1] = band

    encode(ffmpeg, source, clean, recipe['frames'], remove_japanese)
    lines = list(subtitles.story_spans(recipe['cues'], analysis['lines'], 960))
    del filler, analysis
    captions = subtitles.Captions(lines, font, 960, 544, (top + bottom) / 2, False)
    print(f'{source.name}: applying {len(captions.layers)} English subtitle cues', flush=True)
    encode(ffmpeg, clean, output, recipe['frames'], captions.apply)


def build_opening(ffmpeg, font, source, output, recipe):
    video = cv2.VideoCapture(str(source))
    fps = video.get(cv2.CAP_PROP_FPS)
    video.release()
    captions = subtitles.Captions(
        subtitles.authored_spans(recipe['cues'], fps, recipe['frames'], 960),
        font, 960, 544, (recipe['top'] + recipe['bottom']) / 2, True,
    )
    print(f'{source.name}: applying {len(captions.layers)} English subtitle cues', flush=True)
    encode(ffmpeg, source, output, recipe['frames'], captions.apply)


def build_notice(ffmpeg, font, source, output, recipe):
    # Use fixed relative names for drawtext so spaces, apostrophes, drive letters
    # and Unicode in the release and font paths do not need FFmpeg filter escaping.
    shutil.copyfile(font, source.parent / 'font.ttf')
    filters = []
    for index, row in enumerate(recipe['rows']):
        text = f'line{index}.txt'
        (source.parent / text).write_text(row['text'], encoding='utf-8')
        filters.append(
            f'drawtext=fontfile=font.ttf:textfile={text}:text_shaping=1:fontsize={row["size"]}:'
            f'fontcolor=white:x=(w-text_w)/2:y={row["center"]}-(ascent-descent)/2',
        )
    frames = recipe['frames']
    filters.extend(['fade=t=in:s=0:n=30', f'fade=t=out:s={frames - 30}:n=30', 'format=yuv420p'])
    duration = frames * 1001 / 30000
    subprocess.run([
        str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'lavfi', '-i', f'color=c=black:s=960x544:r=30000/1001:d={duration:.4f}',
        '-i', str(source), '-filter_complex', '[0:v]' + ','.join(filters) + '[v]',
        '-map', '[v]', '-map', '1:a?', '-c:v', 'libx264', '-profile:v', 'high', '-level', '3.1',
        '-refs', '3', '-preset', 'slow', '-crf', '16', '-colorspace', 'bt709',
        '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
        '-c:a', 'copy', '-metadata:s:v', 'language=eng', '-metadata:s:a', 'language=eng',
        '-movflags', '+faststart', str(output),
    ], cwd=source.parent, check=True)


# A fan translation re-encodes the story movies with its English burned in under the Japanese line, in rows FAN_TOP to
# FAN_BOTTOM (measured on all eight: its letters reach rows 500 to 532, their outline a few rows further).
FAN_TOP, FAN_BOTTOM = 499, 538


def frame_count(path):
    video = cv2.VideoCapture(str(path))
    try:
        return int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        video.release()


def build_fan_story(ffmpeg, font, source, output, recipe):
    """a fan translation's story movie, in two passes: the Japanese line is erased as in an original copy (the recipe's
    band and timing), then the fan's English line under it, with its own timing found in its own rows; then the English
    subtitles are drawn with the timings recorded from the original (recipe['spans'], dev/psnova/make_movie_spans.py)"""
    frames = frame_count(source)
    original = np.unpackbits(np.frombuffer(bytes.fromhex(recipe['presence_bits']), dtype=np.uint8),
                             count=recipe['frames']).astype(bool)
    # the fan re-encode starts on the original's first frame (checked against the originals for all eight movies: it only
    # gains or loses a frame at the end), so the recorded timings apply as they are
    signal = np.zeros(frames, bool)
    count = min(frames, len(original))
    signal[:count] = original[:count]
    top, bottom = recipe['top'], recipe['bottom']
    print(f'{source.name}: fan re-encode, {frames} frames; erasing the Japanese line', flush=True)
    analysis = cleaner.analyse(source, top, bottom, recipe['threshold'], signal)
    filler = cleaner.Filler(analysis, top, bottom)
    first = source.with_name('clean-japanese.mp4')

    def remove_japanese(index, frame):
        band = filler.fill(index)
        if band is not None:
            frame[filler.m0:filler.m1] = band

    encode(ffmpeg, source, first, frames, remove_japanese, crf=8)   # (near-lossless: read again by the second pass)
    del filler, analysis
    print(f'{source.name}: erasing the fan translation\'s English line', flush=True)
    # (its letters are outlined in black: found by the white strokes or the outline, and masked wider than the Japanese;
    # no background cut: the fan's lines follow each other so closely that their letters would pass for background)
    analysis = cleaner.analyse(first, FAN_TOP, FAN_BOTTOM, recipe['threshold'], np.zeros(frames, bool),
                               detect=cleaner.outlined, bgcut=False)
    # each frame's own letters are masked as they are: the persistence vote and the tall-structure rule suit the Japanese
    # line, but here they drop letters beside dark scenery
    analysis['K30'] = analysis['TH'] > cleaner.TH_MASK
    analysis['present'] |= (analysis['TH'] > cleaner.TH_DET).sum(axis=(1, 2)) > recipe['threshold']
    filler = cleaner.Filler(analysis, FAN_TOP, FAN_BOTTOM, grow=np.ones((13, 13), np.uint8), near=np.ones((9, 9), np.uint8))
    spans = [({'en': recipe['cues'].get(str(i), '')}, min(a, frames - 1), min(b, frames - 1), x0, x1)
             for i, (a, b, x0, x1) in enumerate(recipe['spans'])]
    captions = subtitles.Captions(spans, font, 960, 544, (top + bottom) / 2, False)
    print(f'{source.name}: applying {len(captions.layers)} English subtitle cues', flush=True)

    def remove_fan_and_caption(index, frame):
        band = filler.fill(index)
        if band is not None:
            frame[filler.m0:filler.m1] = band
        captions.apply(index, frame)

    encode(ffmpeg, first, output, frames, remove_fan_and_caption)


def replace_movies(base, out, work, font, ffmpeg, fan=False):
    """fan: the archive is a fan translation's. Each clip that is still the original is built as usual; a story movie the
    fan re-encoded is cleaned of both subtitle lines (build_fan_story); the warning notice, which a fan translation turns
    into its credits, is drawn from the recipe as always (only its sound comes from the clip)"""
    recipes = json.loads((RECIPES / 'english.json').read_text(encoding='utf-8'))
    key_files = [Path(__file__), font, ffmpeg, *sorted(RECIPES.glob('*.py')), RECIPES / 'english.json']
    key = ''.join(file_hash(path) for path in key_files) + (' fan' if fan else '')
    key = hashlib.sha256(key.encode('ascii')).hexdigest()
    work.mkdir(parents=True, exist_ok=True)
    cache = work / key
    cache.mkdir(exist_ok=True)
    cv2.setNumThreads(2)
    clips = [(f'{name}.mp4', recipe, build_story) for name, recipe in recipes['stories'].items()]
    clips += [('OpeningDemo.mp4', recipes['opening'], build_opening),
              ('Attention.mp4', recipes['notice'], build_notice)]

    replacements = {}
    archive = cpk.Cpk(base)
    try:
        entries = {entry['path']: entry for entry in archive.entries}
        for index, (name, recipe, build) in enumerate(clips, 1):
            if name not in entries:
                raise ValueError(f'{base.name}: missing {name}')
            body = cpk.read_entry(archive, entries[name])
            if hashlib.sha256(body).hexdigest() != recipe['sha256']:
                if not fan:
                    raise ValueError(f'{base.name}: {name} does not match the supported Japanese original')
                if build is build_story:
                    build = build_fan_story
                elif build is not build_notice:
                    raise ValueError(f'{base.name}: {name} is neither the original nor a known fan-translated movie')
            destination = cache / name
            receipt = destination.with_suffix('.sha256')
            print(f'English movies ({index}/{len(clips)}) {name}', flush=True)
            if destination.is_file() and receipt.is_file() and receipt.read_text() == file_hash(destination):
                print('Using verified output from the previous setup run', flush=True)
            else:
                with tempfile.TemporaryDirectory(prefix='clip-', dir=work) as scratch:
                    stage = Path(scratch)
                    original = stage / name
                    original.write_bytes(body)
                    del body
                    frames = frame_count(original) if build is build_fan_story else recipe['frames']
                    generated = stage / 'output.mp4'
                    build(ffmpeg, font, original, generated, recipe)
                    if movie_size(generated) != (960, 544, frames):
                        raise ValueError(f'{name}: encoded frame count or size does not match the source')
                    digest = file_hash(generated)
                    os.replace(generated, destination)
                    receipt.write_text(digest, encoding='ascii')
            replacements[name] = destination
    finally:
        archive.close()
    with tempfile.TemporaryDirectory(prefix='movie-cpk-', dir=out.parent) as scratch:
        stage = Path(scratch) / out.name
        repack.replace(base, stage, replacements)
        os.replace(stage, out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--font', type=Path, required=True)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    parser.add_argument('--work', type=Path, help='local cache for interrupted builds')
    parser.add_argument('--fan', action='store_true',
                        help='a fan-translated archive: erase its dual subtitles and draw the English ones')
    args = parser.parse_args()
    base, output = args.source.resolve(), args.output.resolve()
    if base == output:
        parser.error('the source and output archives must be different files')
    for label, path in [('source movie archive', base), ('English font', args.font), ('FFmpeg', args.ffmpeg)]:
        if not path.is_file():
            parser.error(f'missing {label}: {path}')
    output.parent.mkdir(parents=True, exist_ok=True)
    font, ffmpeg = args.font.resolve(), args.ffmpeg.resolve()
    if args.work:
        replace_movies(base, output, args.work.resolve(), font, ffmpeg, args.fan)
    else:
        with tempfile.TemporaryDirectory(prefix='nova-movies-', dir=output.parent) as scratch:
            replace_movies(base, output, Path(scratch), font, ffmpeg, args.fan)


if __name__ == '__main__':
    main()
