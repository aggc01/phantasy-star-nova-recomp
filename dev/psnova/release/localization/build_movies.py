"""Build the Windows release's English movie archive from the player's copy."""

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
sys.path[:0] = [str(RECIPES), str(HERE.parent / 'engine/pipeline/cri')]

import cleaner
import cpk
import repack
import subtitles


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def encode(ffmpeg, source, destination, frames, transform):
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
            '-crf', '19', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level', '4.0',
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
        '-map', '[v]', '-map', '1:a', '-c:v', 'libx264', '-profile:v', 'high', '-level', '3.1',
        '-refs', '3', '-preset', 'slow', '-crf', '16', '-colorspace', 'bt709',
        '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
        '-c:a', 'copy', '-metadata:s:v', 'language=eng', '-metadata:s:a', 'language=eng',
        '-movflags', '+faststart', str(output),
    ], cwd=source.parent, check=True)


def replace_movies(base, out, work, font, ffmpeg):
    recipes = json.loads((RECIPES / 'english.json').read_text(encoding='utf-8'))
    key_files = [Path(__file__), font, ffmpeg, *sorted(RECIPES.glob('*.py')), RECIPES / 'english.json']
    key = hashlib.sha256(''.join(file_hash(path) for path in key_files).encode('ascii')).hexdigest()
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
                raise ValueError(f'{base.name}: {name} does not match the supported Japanese original')
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
                    generated = stage / 'output.mp4'
                    build(ffmpeg, font, original, generated, recipe)
                    if movie_size(generated) != (960, 544, recipe['frames']):
                        raise ValueError(f'{name}: encoded frame count or size does not match the original')
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
        replace_movies(base, output, args.work.resolve(), font, ffmpeg)
    else:
        with tempfile.TemporaryDirectory(prefix='nova-movies-', dir=output.parent) as scratch:
            replace_movies(base, output, Path(scratch), font, ffmpeg)


if __name__ == '__main__':
    main()
