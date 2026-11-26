"""Make packs/PCSG00351/english/text/fan_restore.json: what turns a fan-translated update archive back into the official
1.05 one, as far as the base game allows.

A fan translation (Arks-Layer's rePatch, often merged into a "v1.05 English" copy) replaces the update's
NOVA_FileList_Vita_patch.cpk. The English localization is built from the official archive, so for a fan copy
localize.py first rebuilds an official-like archive from the fan one and the untouched base game (fan_restore.py). This
script derives the rules for that from three archives on this PC and checks each rule against the official files:

    official  the 1.05 update's own NOVA_FileList_Vita_patch.cpk
    fan       the fan translation's NOVA_FileList_Vita_patch.cpk
    base      the base game's NOVA_FileList_Vita.cpk (a fan translation leaves it as it is)

What it writes holds no game file: the official entries' names, sizes and SHA-256, the official box heights of the
messages whose fan copy changed them, and for the NPC table the rows the base game cannot give back (each row's key,
its Japanese name and its column count).

Usage: make_fan_restore.py <official patch.cpk> <fan patch.cpk> <base cpk> [out.json]
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT = ROOT / 'packs/PCSG00351/english/text'
sys.path[:0] = [str(TEXT), str(ROOT / 'pipeline/cri')]

import cpk  # noqa: E402
import fan_restore  # noqa: E402


class Archive:
    def __init__(self, path):
        self.archive = cpk.Cpk(str(path))
        self.entries = {e['path'].casefold(): e for e in self.archive.entries}

    def read(self, name):
        return cpk.read_entry(self.archive, self.entries[name.casefold()])

    def has(self, name):
        return name.casefold() in self.entries


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    official, fan, base = (Archive(p) for p in sys.argv[1:4])
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else TEXT / 'fan_restore.json'
    manifest = {e['path']: [e['extract_size'], sha(official.read(e['path']))] for e in official.archive.entries}

    # the NPC table: rows the base game holds (with the same columns but the name) come from it; the rest keep the fan's
    # row with their Japanese name and column count put back, recorded here
    name = 'NpcBaseParameter.csv'
    rows = official.read(name).split(b'\r\n')
    base_rows = {r.split(b',')[0]: r.split(b',') for r in base.read(name).split(b'\r\n')}
    fan_rows = {r.split(b',')[0]: r.split(b',') for r in fan.read(name).replace(b'\r\n', b'\n').split(b'\n')}
    npc = {}
    for row in rows:
        cols = row.split(b',')
        key = cols[0]
        candidate = fan_restore.npc_row(fan_rows.get(key, []), base_rows.get(key), None)
        if candidate != row:
            npc[key.decode('ascii')] = [cols[26].decode('cp932') if len(cols) > 26 else None, len(cols)]
    # the box heights of the messages the English rewrites whose fan copy (the encoder's layout template) has another
    english = {f'msg_{k}.rmd'.casefold() for k in json.loads((TEXT / 'messages.json').read_text(encoding='utf-8'))}
    heights = {}
    for entry in official.archive.entries:
        n = entry['path']
        if n.casefold() in english and fan.has(n):
            want, got = fan_restore.height_param(official.read(n)), fan_restore.height_param(fan.read(n))
            if want != got:
                heights[n] = want
    rules = {
        'schema': 1,
        'msg_heights': heights,
        'official': manifest,
        'npc_rows': npc,
        'coldsleep_drop': ['key407'],                    # the row the fan translation adds to ColdSleepCharacter.csv
        'gacha_swap': ['key59760', 'key60010'],          # two rows whose costume parts it swaps
    }
    out.write_text(json.dumps(rules, ensure_ascii=False, indent=0, sort_keys=True), encoding='utf-8')

    # check: every rule-made entry against the official one
    restored = fan_restore.restore_entries(fan, base, rules)
    exact = sum(1 for n, data in restored.items() if n in manifest and sha(data) == manifest[n][1])
    changed = [n for n in manifest if fan.has(n) and sha(fan.read(n)) != manifest[n][1]]
    print(f'{len(heights)} message heights recorded; {len(manifest)} official entries; {len(changed)} changed by the fan translation; restored {len(restored)}, '
          f'{exact} of them byte-exact; {len(npc)} NPC rows recorded -> {out}')
    for n in ('ColdSleepCharacter.csv', 'CharacterMake_Design_Gacha_NPC.csv', name):
        key = next(k for k in restored if k.casefold() == n.casefold())
        print(f'  {n}: {"exact" if sha(restored[key]) == manifest[next(k for k in manifest if k.casefold() == n.casefold())][1] else "DIFFERS"}')


if __name__ == '__main__':
    main()
