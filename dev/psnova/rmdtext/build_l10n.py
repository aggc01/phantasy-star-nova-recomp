"""build_l10n.py - build a language overlay for Phantasy Star Nova from the text sheet: encode the chosen column into .rmd
files and rebuild Sega's 1.05 update archive with them (dev/psnova/cpk_build.py). Written 2026-11-18.

  python build_l10n.py <sheet .tsv> <lang en|ja|ar> <out dir> [--column NAME] [--only ids.json] [--arabic ar.json]
                       [--arabic-mode word|form] [--english-atlas-scale {1,2}]
  -> <out dir>/rmd/msg_<id>.rmd and <out dir>/overlay/NOVA_FileList_Vita_patch.cpk (+ build_report.json)

Rows are taken when the column has text; for 'en' rows whose English is still Japanese (fan patch gaps) are skipped (the
game keeps its Japanese). --arabic: a JSON {id: {"text", "mode", "rtl" (default true: right-aligned via the 0x8095 mark)}} of Arabic lines added on top (tests, or the Arabic
column). Rows that fail to encode are listed in the report and left out.
"""
import argparse, glob, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
from encode_text import Encoder
from english_layout import message_contexts
from center_dialogue_names import patch as center_dialogue_names
from check_sheet import unesc
import cpk_build

COLS = {'en': 'English (fan rePatch, to revise)', 'ja': 'Japanese (original)', 'ar': 'Arabic'}
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TEXT = os.path.join(ROOT, 'dump', 'psnova-l10n', 'text')
BASE_PATCH = os.path.join(ROOT, 'dump', 'decrypted', 'PCSG00351', 'app0_patched', 'NOVA_FileList_Vita_patch.cpk')


def has_english_text(english, japanese):
    # The Japanese placeholder for MP00_010_050 differs
    # only by the width of one space in the English column.
    return bool(english.strip()) and english.split() != japanese.split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sheet'); ap.add_argument('lang'); ap.add_argument('out')
    ap.add_argument('--column'); ap.add_argument('--only'); ap.add_argument('--arabic'); ap.add_argument('--arabic-mode', default='word')
    ap.add_argument('--extra-dir', action='append', default=[], help='a folder of more files to put into the archive as they are (repeatable: the name tables of make_name_tables.py, redrawn UI textures)')
    # Update an existing English overlay without regenerating unrelated assets.
    ap.add_argument('--layout-base', help='rebuild only dialogue, captions and speaker plates in this existing English CPK')
    # A 2x pilot can replace explicit IDs in the existing English archive.
    ap.add_argument('--english-atlas-scale', type=int, choices=(1, 2), default=1,
                    help='raster resolution for English text, with the original layout')
    a = ap.parse_args()
    scaled = a.english_atlas_scale == 2
    pilot = scaled and bool(a.layout_base and a.only)
    if scaled and (a.lang != 'en' or a.arabic):
        ap.error('--english-atlas-scale 2 requires an English build without Arabic overrides')
    if pilot and a.extra_dir:
        ap.error('a scaled --only pilot replaces only the specified messages')
    if a.layout_base and (a.lang != 'en' or a.arabic or (a.only and not pilot)):
        ap.error('--layout-base requires the English column and the full set of dialogue IDs')
    base = a.layout_base or BASE_PATCH
    enc = Encoder(TEXT, os.path.join(TEXT, 'map'), english_atlas_scale=a.english_atlas_scale)
    L = io.open(a.sheet, encoding='utf-8-sig').read().splitlines()
    h = L[0].split('\t'); col = h.index(a.column or COLS[a.lang]); iN = h.index('notes')
    only = set(str(x) for x in json.load(open(a.only))) if a.only else None
    texts = {}
    for l in L[1:]:
        c = l.split('\t')
        if only is not None and c[0] not in only:
            continue
        s = unesc(c[col]) if col < len(c) else ''
        # (English rows still identical to the Japanese -- fan patch gaps not yet translated -- keep the game's own file)
        if not s or (a.lang == 'en' and not has_english_text(s, unesc(c[h.index('Japanese (original)')]))):
            continue
        texts[c[0]] = (s, a.lang, a.arabic_mode, True)
    if a.arabic:
        for k, v in json.load(open(a.arabic, encoding='utf-8')).items():
            if not k.startswith('_'):
                texts[k] = (v['text'], 'ar', v.get('mode', a.arabic_mode), v.get('rtl', True))
    if pilot:
        archive = cpk_build.C.Cpk(base)
        try:
            entries = {entry['path']: entry for entry in archive.entries}
            missing = sorted(mid for mid in only if mid not in texts or f'msg_{mid}.rmd' not in entries)
            if missing or not only:
                ap.error(f'pilot IDs must name existing translated messages (missing: {", ".join(missing)})')
            installed = {mid: cpk_build.C.read_entry(archive, entries[f'msg_{mid}.rmd']) for mid in only}
        finally:
            archive.close()
    contexts = {}
    if a.lang == 'en' and not a.arabic:
        contexts = message_contexts(os.path.join(os.path.dirname(TEXT), 'scan'), map(int, texts))
    rdir = os.path.join(a.out, 'rmd'); odir = os.path.join(a.out, 'overlay')
    os.makedirs(rdir, exist_ok=True); os.makedirs(odir, exist_ok=True)
    orig = {}                                  # the game's own file per id (update over base): its 0x9c/0xa0 values are kept
    for sub in ('jp_base', 'jp_patch'):
        for p in glob.glob(os.path.join(TEXT, sub, '**', 'msg_*.rmd'), recursive=True):
            orig[os.path.basename(p)[4:-4]] = p
    files, failed = {}, {}
    reference = Encoder(TEXT, os.path.join(TEXT, 'map')) if pilot else None
    for mid, (s, lang, mode, rtl) in texts.items():
        if a.layout_base and not pilot and int(mid) not in contexts:
            continue
        try:
            tmpl = open(orig[mid], 'rb').read() if mid in orig else None
            number = int(mid)
            context = contexts.get(number)
            if reference and reference.encode(number, s, lang, template=tmpl, context=context) != installed[mid]:
                raise ValueError('default encode differs from the base archive')
            data = enc.encode(number, s, lang, template=tmpl, arabic_mode=mode, rtl=rtl,
                              context=context)
        except Exception as e:
            failed[mid] = str(e); continue
        name = 'msg_%s.rmd' % mid
        files[name] = data
        open(os.path.join(rdir, name), 'wb').write(data)
    for d in a.extra_dir:                      # whole files as they are (2026-11-19: name tables, redrawn UI textures)
        for n in sorted(os.listdir(d)):
            if os.path.isfile(os.path.join(d, n)):
                files[n] = open(os.path.join(d, n), 'rb').read()
    # Use the English source project's native text-box alignment.
    if a.lang == 'en' and not a.arabic and not a.only:
        name = 'ui_field.crbpj'
        if name not in files:
            archive = cpk_build.C.Cpk(base)
            try:
                entry = next(e for e in archive.entries if e['path'] == name)
                files[name] = cpk_build.C.read_entry(archive, entry)
            finally:
                archive.close()
        files[name] = center_dialogue_names(files[name])
    if a.layout_base and failed:
        raise ValueError('English overlay encoding failed: ' + json.dumps(failed))
    cpk_build.build(base, os.path.join(odir, 'NOVA_FileList_Vita_patch.cpk'), files)
    rep = {'lang': a.lang, 'messages': len(files), 'failed': failed, 'arabic_overrides': sorted(k for k, v in texts.items() if v[1] == 'ar')}
    if scaled:
        rep['english_atlas_scale'] = a.english_atlas_scale
    json.dump(rep, open(os.path.join(a.out, 'build_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('encoded %d messages, %d failed' % (len(files), len(failed)))


if __name__ == '__main__':
    main()
