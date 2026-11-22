"""Character names for the HUD, the head labels and the portrait message window (2026-11-19).

The user saw ルティナ / フィルディア in Japanese over characters, in the party HUD and in the portrait message window with
English selected. Those names are not messages: they are Shift-JIS strings in two tables of Sega's update archive that
the game turns into BasicCharSet glyphs (fn_8157e7d0: Shift-JIS -> UTF-16; the font has ASCII, kana and full-width
letters, no Arabic -- docs/psnova/ui-strings-research.md):
  uireferenceparameter.csv  StringFix_NameRut,,,,ルティナ  ...  (the 15 character names)
  NpcBaseParameter.csv      column 27 of the character rows (key5001 ... ,ルティナ,530001,...)
This writes copies with the English names (from the sheet's name messages, group 30000, Japanese -> English) in plain
ASCII, still Shift-JIS encoded, for the language overlay archives. Arabic mode gets the English names too (the game's
table path cannot draw Arabic letters).
usage: python make_name_tables.py <sheet.tsv> <out dir>   -> <out>/uireferenceparameter.csv, <out>/NpcBaseParameter.csv"""
import csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'pipeline', 'cri'))
import cpk as C

ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PATCH = os.path.join(ROOT, 'dump', 'decrypted', 'PCSG00351', 'app0_patched', 'NOVA_FileList_Vita_patch.cpk')
EXTRA = {'？？？': '???', 'セイル': 'Sail', 'ヒュペリオン': 'Hyperion', 'オルクス': 'Orcus', 'カリスト': 'Callisto',
         'レイヴァン覚醒時': 'Raven', 'ユノホログラム時': 'Juno', 'リーンベル': 'Leanne', 'コプト': 'Copt',
         'レイヴァン幼少期（欠番）': 'Raven'}   # (variants: awakened Raven, Juno as a hologram; 'unused number' row)


def main():
    sheet, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    names = dict(EXTRA)
    for r in csv.DictReader(open(sheet, encoding='utf-8-sig'), delimiter='\t'):
        if r['id'].isdigit() and 30000 <= int(r['id']) < 40000:
            jp, en = r['Japanese (original)'].strip(), r['English (fan rePatch, to revise)'].strip()
            if jp and en and en.isascii() and jp not in names:
                names[jp] = en
    c = C.Cpk(PATCH)
    ent = {e['path'].lower(): e for e in c.entries}
    done = {}
    for fname, fix in (('uireferenceparameter.csv', 'ui'), ('NpcBaseParameter.csv', 'npc')):
        raw = C.read_entry(c, ent[fname.lower()])
        text = raw.decode('cp932')
        lines, n = text.split('\r\n') if '\r\n' in text else text.split('\n'), 0
        nl = '\r\n' if '\r\n' in text else '\n'
        for k, l in enumerate(lines):
            cells = l.split(',')
            if fix == 'ui' and cells[0].startswith('StringFix_Name') and len(cells) >= 5 and cells[4] in names:
                cells[4] = names[cells[4]]; n += 1
            elif fix == 'npc' and len(cells) > 27 and cells[0].startswith('key50') and cells[26] in names:
                cells[26] = names[cells[26]]; n += 1
            lines[k] = ','.join(cells)
        data = nl.join(lines).encode('cp932')
        open(os.path.join(out, fname), 'wb').write(data)
        done[fname] = n
        missing = sorted({l.split(',')[4] for l in lines if l.startswith('StringFix_Name') and not l.split(',')[4].isascii()}) if fix == 'ui' else []
        print(fname, 'names replaced', n, ('still Japanese: %s' % missing) if missing else '')


if __name__ == '__main__':
    main()
