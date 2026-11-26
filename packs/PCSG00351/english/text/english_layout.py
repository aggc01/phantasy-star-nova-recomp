"""English dialogue and caption layout."""

import re
from functools import lru_cache
from pathlib import Path


CAPTION_CELL = 21
# ui_field.crbpj body casts 0xf01c and 0xdae4, and 23 fixed cinematic cells.
WIDTH_PX = {'dialogue': 483, 'radio': 462, 'caption': 23 * CAPTION_CELL}

_SCRIPT_CAPTION = re.compile(rb'ShowCaption[ \t]*:[ \t]*\w+[ \t]*\.rmd[ \t]*,[ \t]*(\d+)')
_SCRIPT_DIALOGUE = re.compile(rb'ShowMessage[ \t]*:[ \t]*\w+[ \t]*\.rmd[ \t]*,[^,\x00\r\n]*,[ \t]*(\d+)')
_TIMED_CAPTION = re.compile(rb'^key\d+,\s*\d+,\s*\d+,\s*(\d+)', re.M)


def message_contexts(scan_dir, sheet_ids=()):
    """Read message IDs from compiled Lua call diagnostics and timed caption lists."""
    scan_dir = Path(scan_dir)
    captions, dialogue, radio, table_dialogue, selections = set(), set(), set(), set(), set()
    for archive in ('b', 'p'):
        for path in (scan_dir / f'{archive}_lua').glob('*.lua'):
            script = path.read_bytes()
            captions.update(map(int, _SCRIPT_CAPTION.findall(script)))
            dialogue.update(map(int, _SCRIPT_DIALOGUE.findall(script)))
            for call in re.findall(rb'ShowSelectMessage[^\x00\r\n]*', script):
                selections.update(map(int, re.findall(rb'(?<!\d)\d{15}(?!\d)', call)))
        csv_dir = scan_dir / f'{archive}_csv'
        for path in csv_dir.glob('*_CaptionList.csv'):
            captions.update(map(int, _TIMED_CAPTION.findall(path.read_bytes())))
        # Operator transmissions and NPC conversations reference RMD IDs in
        # fixed CSV columns, rather than in ShowMessage diagnostics.
        guide_columns = (6, 12) if archive == 'b' else tuple(range(11, 56, 6))
        for name, columns in (('guide_message_parameter.csv', guide_columns),
                              ('quest_message_parameter.csv', (6,)),
                              ('NpcTalkParameter.csv', (26,))):
            path = csv_dir / name
            destination = dialogue if name == 'NpcTalkParameter.csv' else radio
            if path.exists():
                for row in path.read_bytes().splitlines():
                    fields = row.split(b',')
                    if fields[0].startswith(b'key'):
                        for column in columns:
                            if len(fields) > column:
                                value = fields[column].strip()
                                if value.isdigit() and int(value):
                                    destination.add(int(value))
        # Event text tables contain message rows omitted by Lua diagnostics.
        # Match the table header rather than broad numeric ID prefixes, so
        # menu choices and other unrelated RMD files are not swept in.
        for path in csv_dir.glob('*.csv'):
            data = path.read_bytes()
            if b'MessageID,CueID,CharacterID,FacialID' in data:
                for row in data.splitlines():
                    first = row.split(b',', 1)[0].strip()
                    if re.fullmatch(rb'\d{15}', first):
                        table_dialogue.add(int(first))
    if not captions or not dialogue:
        raise ValueError(f'English layout requires extracted event scripts and caption lists in {scan_dir}')
    dialogue.update(table_dialogue - selections)
    # Some sheet v7 NPC and battle voice variants have no
    # literal caller (e.g. 302010020011099 vs the table's 302010020011000).
    # These two 15-digit banks contain field conversations and transmissions.
    # Explicit selection IDs are still excluded. Unreferenced main-story
    # cues use full cells, compatible with the cinematic and TextBox drawers.
    for mid in sheet_ids:
        if mid in selections or mid in captions or mid in dialogue or mid in radio:
            continue
        bank = mid // 10**14
        if bank == 3:
            dialogue.add(mid)
        elif bank == 4:
            radio.add(mid)
        elif bank == 1:
            captions.add(mid)
    # If a message is used by both callers its pictures must satisfy the fixed-cell renderer.
    return {**dict.fromkeys(dialogue, 'dialogue'), **dict.fromkeys(radio, 'radio'),
            **dict.fromkeys(captions, 'caption')}


def reflow(items, measure, context):
    """Reflow only whitespace between words, retaining visible text and controls in order."""
    # Existing line breaks, including blank ones, are whitespace, not
    # separate pages; retaining them can silently create more than three lines.
    paragraph = []
    for item in items:
        if item[0] == 'nl':
            if paragraph and paragraph[-1] != ('ch', ' '):
                paragraph.append(('ch', ' '))
        else:
            paragraph.append(item)
    words, separators, word, spaces = [], [], [], []
    for item in paragraph:
        if item[0] == 'ch' and item[1].isspace():
            if word:
                words.append(word)
                separators.append([])
                word = []
            spaces.append(item)
        else:
            if spaces and words:
                separators[-1] = spaces
            spaces = []
            word.append(item)
    if word:
        words.append(word)
        separators.append([])
    return _wrap_words(words, separators, measure, context) if words else []


def _wrap_words(words, separators, measure, context):
    count = len(words)
    flat, starts, ends = [], [], []
    for word, gap in zip(words, separators):
        starts.append(len(flat))
        flat.extend(word)
        ends.append(len(flat))
        flat.extend(gap)

    @lru_cache(None)
    def width(a, b):
        return measure(flat[starts[a]:ends[b - 1]])

    limit = WIDTH_PX[context]
    if width(0, count) <= limit or count == 1:
        return flat[:ends[-1]]

    if context == 'caption':
        # The longest cue may exceed the preferred width. Keep it in two
        # lines at the original font size, minimizing the wider line.
        cut = min(range(1, count), key=lambda i: (
            max(width(0, i), width(i, count)), width(0, i) < width(i, count)))
        return flat[:ends[cut - 1]] + [('nl',)] + flat[starts[cut]:ends[-1]]

    # A gentle taper gives the last row enough words to read as a phrase.
    # Favor a nearby sentence/clause boundary over breaking a phrase.
    total = width(0, count)
    @lru_cache(None)
    def plan(start, remaining, upper, rows):
        if remaining == 1:
            return (0, (count,)) if width(start, count) <= upper else None
        weight = (0.58,) if rows == 2 else (0.43, 0.33)
        ideal = total * weight[rows - remaining]
        best = None
        for stop in range(count - remaining + 1, start, -1):
            px = width(start, stop)
            if px <= upper:
                tail = plan(stop, remaining - 1, px - 1, rows)
                if tail:
                    last = words[stop - 1][-1]
                    punctuation = last[0] == 'ch' and last[1] in '.!?…,:;'
                    cost = abs(px - ideal) + tail[0] - (28 if punctuation else 0)
                    if best is None or cost < best[0]:
                        best = (cost, (stop,) + tail[1])
        return best

    # A failed fit is returned at full width so the encoder retries with a
    # smaller font. Every successful multiline layout is strictly descending.
    stops = None
    for lines in range(2, min(3, count) + 1):
        candidate = plan(0, lines, limit, lines)
        if candidate:
            stops = candidate[1]
            break
    if stops is None:
        return flat[:ends[-1]]

    result = []
    start = 0
    for stop in stops:
        if result:
            result.append(('nl',))
        result.extend(flat[starts[start]:ends[stop - 1]])
        start = stop
    return result
