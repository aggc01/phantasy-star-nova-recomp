"""Check the English layout in a built or installed archive. Done by Codex."""
import argparse
from collections import Counter
from pathlib import Path

from build_l10n import COLS, cpk_build, has_english_text, unesc
from english_layout import CAPTION_CELL, WIDTH_PX, message_contexts
from rmdlib import LOCAL_BASE, Rmd


def inspect_message(rmd, basic, context):
    caption = context == 'caption'
    widths = [0]
    glyphs = 0
    for token in rmd.tokens():
        kind = token[0]
        if kind == 'nl':
            widths.append(0)
        elif kind == 'c':
            glyphs += 1
            code = token[1]
            if code >= LOCAL_BASE:
                record = rmd.recs[code - LOCAL_BASE]
                width = record[0]
                if caption and (width != CAPTION_CELL or
                                round((record[5] - record[3]) * rmd.W) != CAPTION_CELL):
                    raise ValueError(f'{rmd.id}: subtitle cell would stretch')
            else:
                index = ((code & 0x7f) | (code >> 8) << 7) - 1
                width = basic.recs[index][0]
            widths[-1] += CAPTION_CELL if caption else width
        elif kind == 'ctl':
            widths[-1] += {0x8099: 24, 0x8094: 48}.get(token[1], 0)
    limit = WIDTH_PX[context]
    if glyphs > 128 or max(widths) > limit or len(widths) > (2 if caption else 3):
        raise ValueError(f'{rmd.id}: {glyphs} glyphs, {widths} pixel rows')
    if not caption and any(a <= b for a, b in zip(widths, widths[1:])):
        raise ValueError(f'{rmd.id}: dialogue widths {widths}')
    return widths


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sheet', type=Path)
    ap.add_argument('archive', type=Path)
    args = ap.parse_args()
    assets = args.sheet.resolve().parent.parent
    basic = Rmd((assets / 'sample/charset_jp/BasicCharSet.rmd').read_bytes())
    rows = args.sheet.read_text(encoding='utf-8-sig').splitlines()
    contexts = message_contexts(assets / 'scan', (int(row.partition('\t')[0]) for row in rows[1:]))
    archive = cpk_build.C.Cpk(str(args.archive))
    counts = Counter()
    try:
        entries = {e['path']: e for e in archive.entries}
        header = rows[0].split('\t')
        en, ja = header.index(COLS['en']), header.index(COLS['ja'])
        for row in rows[1:]:
            cells = row.split('\t')
            mid = int(cells[0])
            context = contexts.get(mid)
            if not context or not has_english_text(unesc(cells[en]), unesc(cells[ja])):
                continue
            rmd = Rmd(cpk_build.C.read_entry(archive, entries[f'msg_{mid}.rmd']))
            if rmd.id != mid:
                raise ValueError(f'Expected message {mid}, read {rmd.id}')
            widths = inspect_message(rmd, basic, context)
            counts[context, len(widths)] += 1
            if mid in (261211, 101010020140051):
                print(f'{mid}: {widths} px')
    finally:
        archive.close()
    print(dict(sorted(counts.items())))


if __name__ == '__main__':
    main()
