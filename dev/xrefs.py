#!/usr/bin/env python3
"""Who uses what, in a game's main module: an index of every constant each function builds (movw/movt pairs and
literal-pool loads) and every function it calls, from its analysis JSON (dump/decrypted/<TITLE>/analysis/eboot.data.json),
then queries over it. For finding the code behind a string (a shader's file name, an error message) or a C++ class
(its RTTI name: the typeinfo, the vtable and its virtual functions).

  .venv/bin/python dev/xrefs.py <analysis.json> index                 build <analysis>.xrefs.json (a minute or two, once)
  .venv/bin/python dev/xrefs.py <analysis.json> str <regex>           the strings matching, and the functions using each
  .venv/bin/python dev/xrefs.py <analysis.json> class <regex>         the classes whose RTTI name matches: vtables, methods
  .venv/bin/python dev/xrefs.py <analysis.json> callers <hex addr>    the functions calling it
  .venv/bin/python dev/xrefs.py <analysis.json> calls <hex addr>      the functions it calls, and the strings it uses
"""
import json, os, re, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM

def load(path):
    d = json.load(open(path))
    segs = [(b['start'], bytes.fromhex(b['bytes'])) for b in d['blocks'] if b.get('bytes')]
    return d, segs

def rd32(segs, a):
    for s, by in segs:
        if s <= a and a + 4 <= s + len(by): return struct.unpack_from('<I', by, a - s)[0]
    return None

def in_code(d, v):
    if 'starts' not in d: d['starts'] = {b[2] for b in d['bodies']}
    return (v & ~1) in d['starts']

def build_index(path, d, segs):
    th, arm = Cs(CS_ARCH_ARM, CS_MODE_THUMB), Cs(CS_ARCH_ARM, CS_MODE_ARM)
    armset = set(d['arm'])
    text_s, text = segs[0]
    consts, calls = {}, {}
    for n, (start, end, fn) in enumerate(d['bodies']):
        code = text[start - text_s:end + 1 - text_s]
        if not code: continue
        cs = arm if fn in armset else th
        k, c, movw = consts.setdefault(fn, set()), calls.setdefault(fn, set()), {}
        for ins in cs.disasm(code, start):
            m, op = ins.mnemonic, ins.op_str
            if m in ('bl', 'blx') and op.startswith('#'):
                c.add(int(op[1:], 16))
            elif m.startswith('movw') and ', #' in op:
                r, v = op.split(', #'); movw[r] = int(v, 16)
            elif m.startswith('movt') and ', #' in op:
                r, v = op.split(', #')
                if r in movw: k.add(movw.pop(r) | int(v, 16) << 16)
            elif m.startswith('ldr') and '[pc' in op:
                mm = re.search(r'\[pc, #(-?0x[0-9a-f]+|-?\d+)\]', op)
                off = int(mm.group(1), 0) if mm else 0
                base = (ins.address + (8 if cs is arm else 4)) & ~3
                v = rd32(segs, base + off)
                if v is not None: k.add(v)
        if n % 5000 == 0: print(f'  {n}/{len(d["bodies"])} bodies', file=sys.stderr)
    out = {'consts': {str(f): sorted(v) for f, v in consts.items() if v},
           'calls': {str(f): sorted(v) for f, v in calls.items() if v}}
    json.dump(out, open(idx_path(path), 'w'))
    print(f'{len(out["consts"])} functions with constants, {len(out["calls"])} with calls -> {idx_path(path)}')

def idx_path(path): return path.replace('.data.json', '.xrefs.json')

def strings(segs, pat):
    rx = re.compile(pat.encode())
    for s, by in segs:
        for m in re.finditer(rb'[\x20-\x7e]{4,}\x00', by):
            if rx.search(m.group()): yield s + m.start(), m.group()[:-1].decode()

def main():
    path, cmd = sys.argv[1], sys.argv[2]
    d, segs = load(path)
    if cmd == 'index': return build_index(path, d, segs)
    ix = json.load(open(idx_path(path)))
    names = {v: k for k, v in d['functions'].items()}
    nm = lambda f: names.get(f, names.get(f | 1, names.get(f & ~1, '')))
    users = {}
    for f, vs in ix['consts'].items():
        for v in vs: users.setdefault(v, []).append(int(f))
    if cmd == 'str':
        for a, s in strings(segs, sys.argv[3]):
            fs = users.get(a, [])
            print(f'{a:#010x} {s}' + ''.join(f'\n    fn_{f:08x} {nm(f)}' for f in fs))
    elif cmd == 'class':
        words = {}
        for s, by in segs:   # (typeinfo and some vtables sit in .text, with the strings)
            for o in range(0, len(by) - 3, 4):
                words.setdefault(struct.unpack_from('<I', by, o)[0], []).append(s + o)
        for a, s in strings(segs, sys.argv[3]):
            if not re.fullmatch(r'N?[0-9]+\w+E?', s): continue
            for ti in (w - 4 for w in words.get(a, [])):
                for vp in words.get(ti, []):
                    vt = vp + 4   # the address point: the typeinfo pointer sits just before it
                    meths = []
                    while True:
                        v = rd32(segs, vt + 4 * len(meths))
                        if v is None or not in_code(d, v): break
                        meths.append(v & ~1)
                    if not meths: continue
                    print(f'{s}  typeinfo {ti:#010x}  vtable {vt:#010x}: {len(meths)} virtual functions')
                    for i, m in enumerate(meths):
                        print(f'    [{i:2}] fn_{m:08x} {nm(m)}  ({len(callers_of(ix, m))} callers)')
    elif cmd == 'callers':
        a = int(sys.argv[3], 16) & ~1
        for f in callers_of(ix, a): print(f'fn_{f:08x} {nm(f)}')
    elif cmd == 'calls':
        a = int(sys.argv[3], 16) & ~1
        for c in ix['calls'].get(str(a), []): print(f'call fn_{c & ~1:08x} {nm(c)}')
        strs = dict(strings(segs, '.'))
        for v in ix['consts'].get(str(a), []):
            if v in strs: print(f'str  {v:#010x} {strs[v]}')

def callers_of(ix, a):
    return [int(f) for f, cs in ix['calls'].items() if a in cs or a | 1 in cs]

if __name__ == '__main__':
    main()
