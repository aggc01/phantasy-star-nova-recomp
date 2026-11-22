"""build_sheet.py - decode every message file (Japanese: base archive + Sega's 1.05 update; English: the fan rePatch) into
one translation sheet. Written 2026-11-18; format notes in docs/psnova/text-format.md.

  python build_sheet.py <text dir> <map dir> <out prefix>
  -> <out prefix>.xlsx (sheet "messages" + sheet "tags"), <out prefix>.tsv (UTF-8 with BOM), <out prefix>_tokens.json
     (the parsed tokens per message, for the re-encoder that will write translated .rmd files back)

Text conventions in the sheet (the same in every column, so a translator keeps them):
  a real line break        = a new line in the cell (the game's 0x8080)
  {ruby:reading}base{/ruby} = furigana: the reading shown over "base" (e.g. {ruby:ほし}惑星{/ruby})
  {8081:03} {8099:1c} {8094:0000}  = control codes with their parameter bytes (meanings in text-format.md)
  {/color}                 = 0x8082, the text colour back to white (was {end}: it is NOT an end, 2026-11-19)
  {8081:03}                = text colour (03 red, 06 cyan, 07 yellow) until {/color}
  〔#1a2b3c〕               = a kanji picture not read yet (its picture hash); 〔x0123〕 = an unknown code
"""
import collections, glob, json, os, pickle, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rmdlib import Rmd, read_mdic, LOCAL_BASE, ruby_text
from learn_map import ghash
from xlsxw import write_xlsx

HERE = os.path.dirname(os.path.abspath(__file__))
UNSURE = {}          # picture hash -> reading the reviewers were not fully sure of


def load_maps(mapdir):
    B = {int(k, 16): v[0] for k, v in json.load(open(os.path.join(mapdir, 'map_basic.json'), encoding='utf-8')).items()}
    for k, v in json.load(open(os.path.join(HERE, 'map_manual.json'), encoding='utf-8')).items():
        if not k.startswith('_'):
            B.setdefault(int(k, 16), v.rstrip('?') if len(v) > 1 else v)
    G = {h: v[0] for h, v in pickle.load(open(os.path.join(mapdir, 'map_glyph.pkl'), 'rb')).items()}
    conf = os.path.join(mapdir, 'glyph_confirmed.json')       # reviewed readings (2 readers + judge, 2026-11-18); they win over votes
    UNSURE.clear()
    if os.path.exists(conf):
        for h, v in json.load(open(conf, encoding='utf-8')).items():
            if v['char']:
                G[h] = v['char']
                if v['confidence'] != 'high':
                    UNSURE[h] = v['char']
    return B, G


def decode(r, B, G, stats=None):
    lc = r.local_count()
    out, toks = [], []
    for t in r.tokens():
        if t[0] == 'c':
            c = t[1]
            if c >= LOCAL_BASE:
                if c - LOCAL_BASE < lc:
                    h = ghash(r.glyph(c - LOCAL_BASE))
                    ch = G.get(h)
                    if ch is None:
                        ch = '〔#%s〕' % h[:6]
                        if stats is not None: stats['picture unread'] += 1
                    toks.append(['g', h])
                    if h in UNSURE and stats is not None:
                        stats.setdefault('unsure', set()).add(UNSURE[h])
                else:
                    ch = '〔x%04x〕' % c; toks.append(['c', c])
            else:
                ch = B.get(c)
                if ch is None:
                    ch = '〔x%04x〕' % c
                    if stats is not None: stats['code unknown'] += 1
                toks.append(['c', c])
            out.append(ch)
        elif t[0] == 'nl':
            out.append('\n'); toks.append(['nl'])
        elif t[0] == 'ruby':
            out.append('{ruby:%s}' % ruby_text(t[1])); toks.append(['ruby', t[1].hex()])
        elif t[0] == 'rend':
            out.append('{/ruby}'); toks.append(['rend'])
        elif t[0] == 'ctl':
            if t[1] == 0x8082:
                out.append('{/color}')
            else:
                out.append('{%04x%s}' % (t[1], (':' + t[2].hex()) if t[2] else ''))
            toks.append(['ctl', t[1], t[2].hex()])
    s = ''.join(out)
    if s.endswith('{/color}'):
        s = s[:-8]
    return s, toks


def collect(textdir, subs):
    files = {}
    for sub in subs:
        for p in glob.glob(os.path.join(textdir, sub, '**', '*.rmd'), recursive=True):
            files[os.path.basename(p)] = (p, sub)
    return files


def main():
    textdir, mapdir, prefix = sys.argv[1:4]
    B, G = load_maps(mapdir)
    jp = collect(textdir, ('jp_base', 'jp_patch'))
    en = collect(textdir, ('en_patch',))
    D, _ = read_mdic(os.path.join(textdir, 'jp_patch', 'novamessagedictionary.mdic'))
    stats = collections.Counter()
    rows, tokens = [], {}
    names = sorted(set(jp) | set(en), key=lambda n: (len(n), n))
    for n in names:
        mid = n[4:-4]
        jtxt = etxt = ''; src = ''; box = ('', '')
        note = ''
        if n in jp:
            r = Rmd(open(jp[n][0], 'rb').read())
            st = collections.Counter()
            jtxt, jt = decode(r, B, G, st); src = 'update 1.05' if jp[n][1] == 'jp_patch' else 'base'
            box = ('%g' % r.box[0], '%g' % r.box[1]); tokens[mid] = {'jp': jt}
            stats['jp messages'] += 1
            stats['picture unread'] += st['picture unread']; stats['code unknown'] += st['code unknown']
            if st.get('unsure'):
                note = 'check kanji reading: ' + ' '.join(sorted(st['unsure'])); stats['rows with an unsure kanji'] += 1
        if n in en:
            r2 = Rmd(open(en[n][0], 'rb').read())
            etxt, et = decode(r2, B, G)
            tokens.setdefault(mid, {})['en'] = et
            stats['en messages'] += 1
            if not box[0]:
                box = ('%g' % r2.box[0], '%g' % r2.box[1])
        jl = jtxt.count('\n') + 1 if jtxt else 0
        if etxt and etxt == jtxt:
            note = (note + '; ' if note else '') + 'fan patch left this in Japanese'
        rows.append([mid, src or 'fan patch only', box[1], jl, jtxt, etxt, '', note])
    header = ['id', 'source', 'text height px', 'JP lines', 'Japanese (original)', 'English (fan rePatch, to revise)',
              'Arabic', 'notes']
    tags = [['line break', 'new line in the cell', '0x8080'],
            ['{ruby:reading}...{/ruby}', 'furigana: the small reading shown over the text between (e.g. {ruby:ほし}惑星{/ruby} = 惑星 read as ほし). In a translation keep the base text only, or drop the tags.', '0x8090 <reading bytes> 0 ... 0x8091'],
            ['{8081:xx}', 'text colour from here: 03 red, 06 cyan, 07 yellow (until {/color})', '0x8081'],
            ['{/color}', 'text colour back to white; the text goes on', '0x8082'],
            ['{8099:xx}', 'control code with 1 parameter byte; meaning not known yet', '0x8099'],
            ['{8094:xxxx}', 'value slot filled in by the game (2 parameter bytes)', '0x8094'],
            ['〔#xxxxxx〕', 'a kanji picture not read yet', 'per-file glyph'],
            ['〔x0123〕', 'a code not known yet', ''],
            ['rule', 'keep every {tag} in the translation, in a sensible place', '']]
    write_xlsx(prefix + '.xlsx', [('messages', header, rows, [18, 11, 8, 6, 60, 60, 60, 34]),
                                  ('tags', ['tag', 'meaning', 'bytes'], tags, [24, 70, 34])])
    with open(prefix + '.tsv', 'w', encoding='utf-8-sig', newline='') as f:
        f.write('\t'.join(header) + '\n')
        for row in rows:
            f.write('\t'.join(str(x).replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t') for x in row) + '\n')
    json.dump(tokens, open(prefix + '_tokens.json', 'w', encoding='utf-8'), ensure_ascii=False)
    stats['rows'] = len(rows)
    stats.pop('unsure', None)
    print(dict(stats))


if __name__ == '__main__':
    main()
