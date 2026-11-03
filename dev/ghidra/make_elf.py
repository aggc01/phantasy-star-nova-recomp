#!/usr/bin/env python3
"""A plain ARM ELF of a game's main module for Ghidra, which doesn't load Sony's ELF types (0xfe00): the module's memory
image from its analysis JSON (dump/decrypted/<TITLE>/analysis/eboot.data.json), one PT_LOAD per block, and beside it a
<out>.functions list (hex address, arm|thumb, name) for dev/ghidra/NativSetup.java to mark.

  .venv/bin/python dev/ghidra/make_elf.py <analysis.json> <out.elf>
"""
import json, struct, sys

def main():
    d = json.load(open(sys.argv[1])); out = sys.argv[2]
    blocks = [(b['start'], bytes.fromhex(b['bytes']), b['name']) for b in d['blocks'] if b.get('bytes')]
    ph_off, n = 52, len(blocks)
    off = (ph_off + 32 * n + 0xfff) & ~0xfff
    hdr = bytearray(b'\x7fELF\x01\x01\x01' + bytes(9))
    hdr += struct.pack('<HHIIIIIHHHHHH', 2, 40, 1, blocks[0][0], ph_off, 0, 0x05000000, 52, 32, n, 0, 0, 0)
    body, phs = bytearray(), bytearray()
    for i, (a, by, name) in enumerate(blocks):
        flags = 5 if i == 0 else 6   # (the first block is .text: r-x; the rest rw-)
        phs += struct.pack('<IIIIIIII', 1, off + len(body), a, a, len(by), len(by), flags, 0x1000)
        body += by + bytes(-len(by) & 0xfff)
    img = hdr + phs
    img += bytes(off - len(img))
    open(out, 'wb').write(img + body)
    arm, names = set(d['arm']), {}
    for k, v in d['functions'].items(): names.setdefault(v & ~1, k)
    with open(out + '.functions', 'w') as f:
        for fn in sorted({b[2] for b in d['bodies']}):
            nm = names.get(fn, '')
            if nm.startswith('FUN_'): nm = ''
            f.write(f'{fn:08x} {"arm" if fn in arm else "thumb"} {nm or "fn_%08x" % fn}\n')
    print(f'{out}: {n} blocks; {sum(1 for _ in open(out + ".functions"))} functions listed')

if __name__ == '__main__':
    main()
