"""even_pointers.py <title dir> <out seeds>: every even word in the main program that points into .text, classified against the analysis (known ARM, known Thumb whose bytes also decode as ARM -- all 500 were import stubs on 2026-11-18 --, inside a body, uncovered and clean ARM, uncovered junk). Written to check analyze.py's arm_pointer_targets; run with the .venv Python."""
import json, struct, bisect, sys, re
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
W = sys.argv[1]
d = json.load(open(W + "/analysis/eboot.data.json"))
elf = open(W + "/elf/eboot.bin.elf", "rb").read()
phoff = struct.unpack_from("<I", elf, 0x1c)[0]; phnum = struct.unpack_from("<H", elf, 0x2c)[0]
segs = [struct.unpack_from("<8I", elf, phoff + 32 * i) for i in range(phnum)]
def off(va):
    for t, o, v, p, fs, ms, fl, al in segs:
        if t == 1 and v <= va < v + fs: return o + va - v
T0, T1 = 0x81000000, 0x8246bf90
bodies = sorted((b[0], b[1]) for b in d["bodies"]); los = [b[0] for b in bodies]
funcs = {v & ~1 for v in d["functions"].values()}
armset = set(d.get("arm", []))
# ARM-mode functions the recompiler decided on: from the generated code's recomp_is_arm table
gen = open(W + "/recomp/game.c", encoding="utf-8", errors="replace").read()
m = re.search(r"int recomp_is_arm\(uint32_t a\) \{(.*?)\n\}", gen, re.S)
rec_arm = {int(x, 16) for x in re.findall(r"case 0x([0-9a-f]+)u:", m.group(1))} if m else set()
def covered(a):
    i = bisect.bisect_right(los, a) - 1
    return i >= 0 and bodies[i][0] <= a <= bodies[i][1]
arm = Cs(CS_ARCH_ARM, CS_MODE_ARM); arm.detail = True
def clean_arm(v):
    ins = list(arm.disasm(elf[off(v): off(v) + 0x400], v))
    if not ins or ins[0].address != v: return 0
    if any(c in ins[0].mnemonic for c in ()) : return 0
    for k, i in enumerate(ins[:256]):
        mn = i.mnemonic
        cond = i.cc if hasattr(i, "cc") else 15
        if k < 2 and cond not in (0, 15) and cond != 14: return 0   # entries start unconditionally (AL)
        if mn.startswith(("stc", "ldc", "cdp", "mcr", "mrc", "udf", "svc", "bkpt")) and not re.search(r"p1[01]|p1[45]", i.op_str): return 0
        if "^" in i.op_str: return 0
        if (mn == "bx" and i.op_str == "lr") or (mn.startswith("pop") and "pc" in i.op_str) or (mn.startswith("ldm") and "pc" in i.op_str) or mn == "b":
            return k + 1
    return 0
stats = {"known_arm": 0, "known_thumb_ARMclean": [], "known_thumb_other": 0, "uncovered_clean": [], "uncovered_junk": 0, "inside_body": 0}
seen = set()
for t, o, v0, p, fs, ms, fl, al in segs:
    if t != 1 or fs == 0: continue
    for k in range(0, fs - 3, 4):
        v = struct.unpack_from("<I", elf, o + k)[0]
        if v & 3 or not (T0 <= v < T1) or v in seen: continue
        seen.add(v)
        if v in funcs:
            if v in rec_arm or v in armset: stats["known_arm"] += 1
            elif clean_arm(v): stats["known_thumb_ARMclean"].append(v)
            else: stats["known_thumb_other"] += 1
        elif covered(v): stats["inside_body"] += 1
        elif clean_arm(v): stats["uncovered_clean"].append(v)
        else: stats["uncovered_junk"] += 1
for k, x in stats.items(): print(k, len(x) if isinstance(x, list) else x)
print("known-Thumb targets of even pointers that decode cleanly as ARM (first 20):", " ".join(hex(a) for a in stats["known_thumb_ARMclean"][:20]))
print("uncovered, clean ARM (first 30):", " ".join(hex(a) for a in stats["uncovered_clean"][:30]))
open(sys.argv[2], "w").write("".join(f"{a:#x} arm\n" for a in stats["uncovered_clean"]))
open(sys.argv[2] + ".thumb_suspects", "w").write("".join(f"{a:#x}\n" for a in stats["known_thumb_ARMclean"]))
