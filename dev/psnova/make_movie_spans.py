"""Record each story movie's subtitle lines (first frame, last frame, left and right edge) in english.json.

build_movies.py times the English subtitles of a story movie from the Japanese lines it detects in the original. A
fan-translated copy no longer has the original movies (they are re-encoded with the fan's English under the Japanese),
so the timings found in the originals are kept in the recipe as "spans", and build_movies.py uses them for such a copy.
They are frame numbers and pixel columns only.

Usage: make_movie_spans.py <original NOVA_FileList_Vita_movie.cpk>
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MOVIES = ROOT / 'packs/PCSG00351/english/movies'
sys.path[:0] = [str(MOVIES), str(ROOT / 'pipeline/cri')]

import cleaner  # noqa: E402
import cpk  # noqa: E402


def main():
    recipe_path = MOVIES / 'english.json'
    recipes = json.loads(recipe_path.read_text(encoding='utf-8'))
    archive = cpk.Cpk(sys.argv[1])
    entries = {e['path']: e for e in archive.entries}
    with tempfile.TemporaryDirectory() as scratch:
        for name, recipe in recipes['stories'].items():
            source = Path(scratch) / f'{name}.mp4'
            source.write_bytes(cpk.read_entry(archive, entries[f'{name}.mp4']))
            signal = np.unpackbits(np.frombuffer(bytes.fromhex(recipe['presence_bits']), dtype=np.uint8),
                                   count=recipe['frames']).astype(bool)
            analysis = cleaner.analyse(source, recipe['top'], recipe['bottom'], recipe['threshold'], signal)
            if len(analysis['lines']) != recipe['expected_lines']:
                raise SystemExit(f'{name}: {len(analysis["lines"])} lines, expected {recipe["expected_lines"]}')
            spans = []
            for line in analysis['lines']:
                cols = np.flatnonzero(line['mask'].any(axis=0))
                x0, x1 = (int(cols[0]), int(cols[-1])) if len(cols) else (480, 480)
                spans.append([int(line['a']), int(line['b']), x0, x1])
            recipe['spans'] = spans
            print(f'{name}: {len(spans)} spans', flush=True)
            source.unlink()
    archive.close()
    recipe_path.write_text(json.dumps(recipes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
