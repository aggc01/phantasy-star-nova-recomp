"""List a capture's text draws: the draws that sample a message file's glyph atlas (DXT3, a power-of-two size up to 512),
with each draw's quads (position and texture coordinates per corner), so the main letters and their shadow can be compared.

usage: python -I dev/psnova/text_draws.py <draw dump.txt> <verts log> [atlas WxH ...]
  draw dump.txt : gfxreplay's RECOMP_REPLAY_DUMP=1 output (one "draw N: ..." line per draw)
  verts log     : gfxreplay's stderr with RECOMP_REPLAY_VERTS=<the draws listed by --list>
Run with --list <draw dump.txt> first: prints the draw numbers to pass to RECOMP_REPLAY_VERTS.
(2026-11-19, docs/psnova/text-render-faults.md)
"""
import re, sys

def atlas_draws(dump):
	out = []
	for line in open(dump, encoding='utf-8', errors='replace'):
		m = re.match(r'draw (\d+):', line)
		if not m: continue
		tex = re.findall(r' (\d+)=(0x[0-9a-f]+) f(0x[0-9a-f]+) (\d+)x(\d+)', line.split('  tex', 1)[1].split('  blend')[0]) if '  tex' in line else []
		for unit, addr, fmt, w, h in tex:
			w, h = int(w), int(h)
			if w in (128, 256, 512) and h in (32, 64, 128, 256, 512):
				out.append((int(m.group(1)), unit, addr, fmt, w, h, line.strip()))
	return out

def main():
	if sys.argv[1] == '--list':
		ds = atlas_draws(sys.argv[2])
		for d in ds: print(f'draw {d[0]}: tex unit {d[1]} {d[2]} fmt {d[3]} {d[4]}x{d[5]}')
		print('RECOMP_REPLAY_VERTS=' + ','.join(str(d[0]) for d in ds))
		return
	dump, verts = sys.argv[1], sys.argv[2]
	ds = {d[0]: d for d in atlas_draws(dump)}
	cur = None
	for line in open(verts, encoding='utf-8', errors='replace'):
		m = re.match(r'verts draw (\d+):', line)
		if m:
			cur = int(m.group(1)); d = ds.get(cur)
			print(f'\n== draw {cur}: atlas {d[2] if d else "?"} {d[4] if d else "?"}x{d[5] if d else "?"}  {line.strip()[len(m.group(0)):]}')
			continue
		if cur is None: continue
		if line.startswith('   v') or line.startswith('   indices') or 'uniforms' in line or line.startswith('     '):
			print(line.rstrip())

if __name__ == '__main__':
	main()
