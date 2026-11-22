"""Center the two field-dialogue name casts in the English ui_field.crbpj.

Done by Codex. Pass the original 1.05 project and output file. Appends user
parameter blocks so the existing Priority=60 is retained. CRI must be tested
in game after changing a project; the version and records are checked here.
"""
import argparse
import struct
from pathlib import Path

RECORDS = (0xd92c, 0xee64)  # TextBox__NpcName, TextBox__PlayerName
OLD = bytes.fromhex('01000000100000001400000018000000010000003c000000010001000c000000000000005072696f7269747900000000')

def patch(data):
    b = bytearray(data)
    if b[:4] != b'CRBD' or struct.unpack_from('<I', b, 8)[0] != len(b):
        raise ValueError('not a complete CRBD project')
    if b[0xc7f5:0xc805] != b'TextBox__NpcName' or b[0xe5c6:0xe5d9] != b'TextBox__PlayerName':
        raise ValueError('unexpected ui_field version')
    for record in RECORDS:
        off = struct.unpack_from('<I', b, record + 20)[0]
        block = bytearray(struct.pack('<4I', 2, 16, 20, 28))
        block += bytes((1, 1, 0, 0))
        block += struct.pack('<2I', 60, 2)  # Priority and Align (2 means centre)
        block += struct.pack('<HH3I', 2, 1, 16, 25, 0)
        block += b'Priority\0Align\0'
        block += bytes(-len(block) % 4)
        if b[record + off:record + off + len(block)] == block:
            continue  # Already patched; retain its existing parameter block.
        if off != 0x188 or b[record + off:record + off + len(OLD)] != OLD:
            raise ValueError(f'unexpected parameters at {record:#x}')
        struct.pack_into('<I', b, record + 20, len(b) - record)
        b += block
    struct.pack_into('<I', b, 8, len(b))
    return b

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    if args.source.resolve() == args.output.resolve():
        p.error('source and output must differ')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch(args.source.read_bytes()))
