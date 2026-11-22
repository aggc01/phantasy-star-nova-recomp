"""learn_map.py - learn which character each text code (shared font) and each per-file glyph picture (kanji) stands for,
by lining up each Japanese message's first line with the game's own message dictionary (novamessagedictionary.mdic,
UTF-16). Written 2026-11-18; notes in docs/psnova/text-format.md.

Facts used (found 2026-11-18):
  - the dictionary entry for a file is at the NEXT id: short ids +1 (msg_530171 -> 530172), dialogue ids +10000
    (msg_100010020030008 -> 100010020040008); some at +0 or other steps, so a pattern match over all entries is the fallback
  - hiragana codes 0xc2..0x112 are the shared font's order (を ぁ ぃ ... ぽ), used as the first anchors

Rounds: match each first line (codes up to the first 0x8080, files with other control codes skipped) to a dictionary entry
whose known characters agree; vote code -> character and glyph-picture -> character; take codes whose vote is clear into the
known map; repeat. Output: map_basic.json (code -> char, votes), map_glyph.pkl ({glyph hash: (char, votes)}), report.

  python learn_map.py <text dir with jp_base/ jp_patch/> <out dir>
"""
import collections, glob, hashlib, json, os, pickle, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rmdlib import Rmd, read_mdic, LOCAL_BASE

HIRA = 'をぁぃぅぇぉゃゅょっゎあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ'


def ghash(g):
    return hashlib.sha1(bytes(g.shape) + g.tobytes()).hexdigest()[:16]


def load(textdir):
    files = {}
    for sub in ('jp_base', 'jp_patch'):              # the update's copy wins
        for p in glob.glob(os.path.join(textdir, sub, '**', '*.rmd'), recursive=True):
            files[os.path.basename(p)] = p
    D, _ = read_mdic(os.path.join(textdir, 'jp_patch', 'novamessagedictionary.mdic'))
    msgs = []
    for n, p in sorted(files.items()):
        r = Rmd(open(p, 'rb').read())
        line = []
        for c in r.codes:
            if c == 0x8080:
                break
            line.append(c)
        tok = []
        ok = not any(c >= 0x8000 for c in line)
        if ok:
            for c in line:
                if c >= LOCAL_BASE:
                    i = c - LOCAL_BASE
                    if i >= r.local_count():
                        ok = False; break
                    tok.append(('g', ghash(r.glyph(i))))
                else:
                    tok.append(('c', c))
        msgs.append((n, r.id, tok if ok else None))
    return msgs, D


def main():
    textdir, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    msgs, D = load(textdir)
    byl = collections.defaultdict(list)
    for k, s in D.items():
        byl[len(s)].append((k, s))
    known = {('c', 0xc2 + i): ch for i, ch in enumerate(HIRA)}
    log = []
    for rnd in range(10):
        relaxed = rnd >= 2      # from round 2 a new code may stand for a character that already has one (0x187 = で as 0x107)
        kchars = set(known.values())
        cchars = set(ch for t, ch in known.items() if t[0] == 'c')
        votes = collections.defaultdict(collections.Counter)
        matched = 0; how = collections.Counter()
        for n, mid, tok in msgs:
            if not tok or len(tok) < 2:
                continue
            nk = sum(1 for t in tok if t in known)
            if nk < 2 and rnd == 0:
                continue

            def fits(s):
                if len(s) != len(tok):
                    return False
                for t, ch in zip(tok, s):
                    if t in known:
                        if known[t] != ch:
                            return False
                    elif t[0] == 'g':
                        if ch in cchars:        # a per-file picture is a kanji or symbol, never a character the shared font has
                            return False
                    elif ch in kchars and not relaxed:
                        return False
                return True
            pick = None
            for step in (1, 10000, 0):
                s = D.get(mid + step)
                if s is not None and fits(s):
                    pick = s; how['next id +%d' % step] += 1; break
            if pick is None and nk >= 3:
                c = [s for k, s in byl[len(tok)] if fits(s)]
                if len(c) == 1:
                    pick = c[0]; how['unique pattern'] += 1
            if pick is None:
                continue
            matched += 1
            for t, ch in zip(tok, pick):
                votes[t][ch] += 1
        added = 0
        for t, cnt in votes.items():
            ch, v = cnt.most_common(1)[0]
            if t not in known and v >= (2 if t[0] == 'c' else 1) and v >= 0.9 * sum(cnt.values()):
                known[t] = ch; added += 1
        log.append('round %d: %d first lines matched (%s); %d new; known codes %d, glyphs %d' % (
            rnd, matched, dict(how), added, sum(1 for t in known if t[0] == 'c'), sum(1 for t in known if t[0] == 'g')))
        print(log[-1], flush=True)
        if not added and relaxed:
            break
    # final count with the finished map: every token's votes from the lines that fit it (nothing added any more), so a
    # label learned in an early round shows how many first lines support it now (0 = check it)
    cchars = set(ch for t, ch in known.items() if t[0] == 'c')
    votes = collections.defaultdict(collections.Counter)
    for n, mid, tok in msgs:
        if not tok or len(tok) < 2:
            continue
        for step in (1, 10000, 0):
            s = D.get(mid + step)
            if s is not None and len(s) == len(tok) and all(
                    (known[t] == ch) if t in known else (t[0] != 'g' or ch not in cchars) for t, ch in zip(tok, s)):
                for t, ch in zip(tok, s):
                    votes[t][ch] += 1
                break
    weak = [t for t in known if t[0] == 'g' and votes[t][known[t]] == 0]
    log.append('final count: %d glyph labels without support from a next-id line (kept, listed in learn_report)' % len(weak))
    print(log[-1], flush=True)
    basic ={('%04x' % t[1]): [ch, sum(votes[t].values()), votes[t].most_common(3)] for t, ch in sorted(known.items(), key=lambda x: str(x[0])) if t[0] == 'c'}
    json.dump(basic, open(os.path.join(out, 'map_basic.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    gl = {t[1]: (ch, sum(votes[t].values())) for t, ch in known.items() if t[0] == 'g'}
    pickle.dump(gl, open(os.path.join(out, 'map_glyph.pkl'), 'wb'))
    # conflicts: glyph pictures whose votes disagree, codes never resolved
    unresolved = {('%04x' % t[1] if t[0] == 'c' else t[1]): cnt.most_common(3) for t, cnt in votes.items() if t not in known}
    json.dump({'log': log, 'weak_glyph_labels': {t[1]: known[t] for t in weak},
               'unresolved': {k: v for k, v in list(unresolved.items())[:500]}, 'n_unresolved': len(unresolved)},
              open(os.path.join(out, 'learn_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
