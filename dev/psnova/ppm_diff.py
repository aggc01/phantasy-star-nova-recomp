"""Compare two PPM (P6) pictures: size, identical bytes, mean and max channel difference, pixels off by more than 8.
Usage: python dev/psnova/ppm_diff.py a.ppm b.ppm"""
import sys

def read_ppm(p):
    d = open(p, "rb").read()
    parts = []; i = 0
    while len(parts) < 4:
        while d[i:i + 1].isspace(): i += 1
        if d[i:i + 1] == b"#":
            while d[i:i + 1] not in (b"\n", b""): i += 1
            continue
        j = i
        while not d[j:j + 1].isspace(): j += 1
        parts.append(d[i:j]); i = j
    i += 1
    w, h = int(parts[1]), int(parts[2])
    return w, h, d[i:i + 3 * w * h]

a, b = read_ppm(sys.argv[1]), read_ppm(sys.argv[2])
if a[:2] != b[:2]: print(f"sizes differ: {a[:2]} vs {b[:2]}"); sys.exit(1)
pa, pb = a[2], b[2]
if pa == pb: print(f"{a[0]}x{a[1]}: identical"); sys.exit(0)
tot = mx = big = 0
for k in range(0, len(pa), 3):
    d = max(abs(pa[k] - pb[k]), abs(pa[k + 1] - pb[k + 1]), abs(pa[k + 2] - pb[k + 2]))
    tot += d; mx = max(mx, d); big += d > 8
n = len(pa) // 3
print(f"{a[0]}x{a[1]}: mean diff {tot / n:.3f}, max {mx}, pixels off by >8: {big} ({100 * big / n:.2f}%)")
