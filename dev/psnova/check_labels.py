"""check_labels.py <recomp dir> [base]: before a long build, every `goto L_x` in the generated C has its `L_x:` label in
the same function (the recompiler's inner-entry goto once pointed at a label its ARM decode never wrote: three parts of
Phantasy Star Nova failed to compile after 25 minutes). Prints each missing label with its function; exit 1 if any.
"""
import glob
import os
import re
import sys

d = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else "game"
FN = re.compile(r"^(?:static )?void (fn_[0-9a-f]+)\(Cpu \*c\) \{")
GOTO = re.compile(r"goto (L_[0-9a-f]{8});")
LABEL = re.compile(r"^(L_[0-9a-f]{8}):")
bad = 0
files = sorted(glob.glob(os.path.join(glob.escape(d), base + "_part*.c")) + glob.glob(os.path.join(glob.escape(d), "mod_*.c")))
for path in files:
    name, gotos, labels = None, set(), set()

    def flush():
        global bad
        for t in sorted(gotos - labels):
            print(f"{os.path.basename(path)}: {name}: goto {t} has no label")
            bad += 1
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = FN.match(line)
            if m:
                if name: flush()
                name, gotos, labels = m.group(1), set(), set()
                continue
            if name is None:
                continue
            m = LABEL.match(line)
            if m:
                labels.add(m.group(1))
            for t in GOTO.findall(line):
                gotos.add(t)
        if name: flush()
print(f"{len(files)} files checked, {bad} missing labels")
sys.exit(1 if bad else 0)
