"""Turn a fan-translated NOVA_FileList_Vita_patch.cpk back into the official 1.05 one, as far as the base game allows.

A fan translation replaces the update's archive with its own: its English in 2,254 of the update's messages and three
tables, 14,898 of the base game's messages copied in translated, and one UI texture dropped. localize.py runs this
first for such a copy, so the English localization is built on official-like data and none of the fan's text is left:

- an entry the official archive does not have gets the base game's copy of it (the game read that before);
- a changed message the localization rewrites keeps the fan's copy as its layout template (its box position and
  texture header are the official ones; its box height is set back from fan_restore.json where the fan changed it);
  one the localization does not rewrite gets the base game's copy, so it shows the base game's Japanese again;
- ColdSleepCharacter.csv, CharacterMake_Design_Gacha_NPC.csv and NpcBaseParameter.csv are put back by the rules in
  fan_restore.json (made by dev/psnova/make_fan_restore.py), which give the official bytes;
- anything left is reported: the base game has no copy of it, so it keeps the fan's bytes or stays missing.

fan_restore.json holds the official entries' names, sizes and SHA-256, so the result is checked entry by entry.

Usage: fan_restore.py <fan patch.cpk> <base NOVA_FileList_Vita.cpk> <out.cpk>
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cpk  # noqa: E402
import cpk_build  # noqa: E402
from rmdlib import Rmd  # noqa: E402

RULES = HERE / 'fan_restore.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def npc_row(fan_cols, base_cols, recorded):
    """one NpcBaseParameter.csv row: the base game's when it differs from the fan's only in the name (26) and height (75)
    columns, else the fan's with its Japanese name, its height written as the game wrote it, and its column count"""
    cols = list(fan_cols)
    if base_cols is not None and len(base_cols) == len(cols) and \
            all(a == b or i in (26, 75) for i, (a, b) in enumerate(zip(cols, base_cols))):
        return b','.join(base_cols)
    if base_cols is not None and len(cols) > 26 and len(base_cols) > 26:
        cols[26] = base_cols[26]
    if len(cols) > 75 and cols[75] and b'.' not in cols[75] and cols[75].lstrip(b'-').isdigit():
        cols[75] += b'.0'
    if recorded is not None:
        jp, count = recorded
        if jp is not None and len(cols) > 26:
            cols[26] = jp.encode('cp932')
        cols = (cols + [b''] * count)[:count]
    return b','.join(cols)


def restore_npc(fan, base, rules):
    rows = fan.replace(b'\r\n', b'\n').split(b'\n')
    base_rows = {r.split(b',')[0]: r.split(b',') for r in base.split(b'\r\n')}
    recorded = rules['npc_rows']
    out = []
    for row in rows:
        cols = row.split(b',')
        key = cols[0]
        out.append(npc_row(cols, base_rows.get(key), recorded.get(key.decode('cp932', 'replace'))))
    return b'\r\n'.join(out)


def restore_coldsleep(fan, rules):
    drop = {k.encode() for k in rules['coldsleep_drop']}
    rows = fan.replace(b'\r\n', b'\n').split(b'\n')
    return b'\r\n'.join(r for r in rows if r.split(b',')[0] not in drop)


def restore_gacha(fan, rules):
    rows = fan.split(b'\r\n')
    keys = [k.encode() for k in rules['gacha_swap']]
    at = {r.split(b',', 1)[0]: i for i, r in enumerate(rows)}
    if all(k in at for k in keys):
        i, j = (at[k] for k in keys)
        a, b = rows[i].split(b',', 1), rows[j].split(b',', 1)
        rows[i], rows[j] = a[0] + b',' + b[1], b[0] + b',' + a[1]
    return b'\r\n'.join(rows)


def height_param(raw):
    """an RMD message's box height less 20 px per line: what the English encoder keeps from its layout template"""
    rmd = Rmd(raw)
    return rmd.box[1] - 20.0 * (1 + sum(1 for token in rmd.tokens() if token[0] == 'nl'))


def fan_template(raw, param):
    """the fan's copy of a message as the English encoder's layout template: its box position and texture header are
    the official ones; its box height is set back to the official one for its own line count"""
    rmd = Rmd(raw)
    lines = 1 + sum(1 for token in rmd.tokens() if token[0] == 'nl')
    data = bytearray(raw)
    struct.pack_into('<f', data, 0xa0, param + 20.0 * lines)
    return bytes(data)


def restore_entries(fan, base, rules):
    """{entry name: bytes} to put over the fan archive. fan and base: objects with has(name) and read(name)"""
    official = {name.casefold(): (name, size, digest) for name, (size, digest) in rules['official'].items()}
    english = {f'msg_{key}.rmd' for key in json.loads((HERE / 'messages.json').read_text(encoding='utf-8'))}
    heights = {name.casefold(): value for name, value in rules['msg_heights'].items()}
    out = {}
    for entry in fan.archive.entries:
        name = entry['path']
        known = official.get(name.casefold())
        if known is None:
            if base.has(name):
                out[name] = base.read(name)
            continue
        data = fan.read(name)
        if sha(data) == known[2]:
            continue
        folded = name.casefold()
        if folded == 'coldsleepcharacter.csv':
            out[name] = restore_coldsleep(data, rules)
        elif folded == 'charactermake_design_gacha_npc.csv':
            out[name] = restore_gacha(data, rules)
        elif folded == 'npcbaseparameter.csv' and base.has(name):
            out[name] = restore_npc(data, base.read(name), rules)
        elif folded.startswith('msg_') and folded in english:
            # rewritten by the English: the fan's copy is only its layout template (height corrected where it differs)
            out[name] = fan_template(data, heights[folded]) if folded in heights else data
        elif base.has(name):
            out[name] = base.read(name)
    return out


class Archive:
    def __init__(self, path):
        self.archive = cpk.Cpk(str(path))
        self.entries = {e['path'].casefold(): e for e in self.archive.entries}

    def read(self, name):
        return cpk.read_entry(self.archive, self.entries[name.casefold()])

    def has(self, name):
        return name.casefold() in self.entries

    def close(self):
        self.archive.close()


def main():
    fan_path, base_path, out_path = (Path(p) for p in sys.argv[1:4])
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    fan, base = Archive(fan_path), Archive(base_path)
    try:
        replacements = restore_entries(fan, base, rules)
        official = rules['official']
        missing = [n for n in official if not fan.has(n)]
        by_name = {k.casefold(): v for k, v in replacements.items()}
        exact, nearest = 0, []
        for name, (size, digest) in official.items():
            if not fan.has(name):
                continue
            data = by_name.get(name.casefold())
            if sha(data if data is not None else fan.read(name)) == digest:
                exact += 1
            else:
                nearest.append(name)
    finally:
        fan.close()
        base.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cpk_build.build(str(fan_path), str(out_path), replacements, log=lambda *a: None)
    print(f'Fan translation removed from the update archive: {len(replacements):,} entries put back; '
          f'{exact:,} of {len(official):,} official entries match the 1.05 update exactly.', flush=True)
    if nearest:
        english = {f'msg_{key}.rmd' for key in json.loads((HERE / 'messages.json').read_text(encoding='utf-8'))}
        templates = [n for n in nearest if n.casefold() in english]
        japanese = [n for n in nearest if n.casefold().startswith('msg_') and n.casefold() not in english]
        other = [n for n in nearest if not n.casefold().startswith('msg_')]
        print(f'  {len(templates):,} messages keep the fan\'s copy only as the layout template the English rewrites.',
              flush=True)
        if japanese:
            print(f'  {len(japanese)} messages the English does not rewrite show the base game\'s Japanese: '
                  f'{", ".join(japanese)}.', flush=True)
        if other:
            print(f'  Not the official bytes: {", ".join(other)}.', flush=True)
    if missing:
        print(f'  Missing from this copy, with no official copy to restore: {", ".join(missing)}.', flush=True)


if __name__ == '__main__':
    main()
