"""contact_sheet.py <out.png> <cols> <scale_div> <ppm...>: tile PPM (P6) shots into one PNG, each shrunk by scale_div,
with its file name's frame number burned in as a simple bar code-free label (top-left, 5x7 digits). No PIL needed."""
import sys, zlib, struct, os
DIG = {'0':"01110100011001110101110011000101110",'1':"00100011000010000100001000010001110",'2':"01110100010000100010001000100011111",
'3':"11110000010000101110000010000111110",'4':"00010001100101010010111110001000010",'5':"11111100001111000001000011000101110",
'6':"00110010001000011110100011000101110",'7':"11111000010001000100010000100001000",'8':"01110100011000101110100011000101110",'9':"01110100011000101111000010001001100"}
def read_ppm(p):
    d = open(p, 'rb').read(); parts = []; i = 0
    while len(parts) < 4:
        while d[i:i+1].isspace(): i += 1
        if d[i:i+1] == b'#':
            while d[i:i+1] != b'\n': i += 1
            continue
        j = i
        while not d[j:j+1].isspace(): j += 1
        parts.append(d[i:j]); i = j
    return int(parts[1]), int(parts[2]), d[i+1:]
out, cols, div = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); files = sys.argv[4:]
w0, h0, _ = read_ppm(files[0]); tw, th = w0 // div, h0 // div; rows = (len(files) + cols - 1) // cols
W, H = cols * tw, rows * th; img = bytearray(W * H * 3)
for n, f in enumerate(files):
    w, h, px = read_ppm(f); ox, oy = (n % cols) * tw, (n // cols) * th
    for y in range(th):
        sy = y * div; row = px[sy * w * 3:(sy + 1) * w * 3]
        o = ((oy + y) * W + ox) * 3
        for x in range(tw):
            s = x * div * 3; img[o + x*3:o + x*3 + 3] = row[s:s+3]
    label = ''.join(c for c in os.path.basename(f) if c.isdigit()).lstrip('0') or '0'
    for k, c in enumerate(label):
        for r in range(7):
            for q in range(5):
                on = DIG[c][r*5+q] == '1'
                for yy in range(2):
                    for xx in range(2):
                        p = ((oy + 2 + r*2 + yy) * W + ox + 2 + k*12 + q*2 + xx) * 3
                        img[p:p+3] = b'\xff\xff\x00' if on else b'\x00\x00\x00'
raw = b''.join(b'\x00' + bytes(img[y*W*3:(y+1)*W*3]) for y in range(H))
def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
open(out, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))
print(out, W, H, len(files))
