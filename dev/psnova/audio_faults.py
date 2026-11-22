"""Find faults in a recording of the game's sound (dev/psnova/video_review.sh writes sound.wav).

The game's own sound is band-limited (Phantasy Star Nova's streams stop near 15 kHz), so a burst of energy
at 16.5-20.5 kHz is a discontinuity in the waveform: a click from a buffer that ran dry, was cut, or was
joined out of step. Also finds short silences inside loud passages (dropouts) and repeats.

usage: python -I dev/psnova/audio_faults.py <sound.wav> [<out.txt>]
Prints a summary: clicks per second over time, the spacing between clicks (periodic spacing points at a
buffer size), dropouts, and the level/channel balance.
"""
import sys, wave
import numpy as np

def load(path):
	with wave.open(path, 'rb') as w:
		n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
		a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
	return a.reshape(-1, ch), sr

def main():
	path = sys.argv[1]
	out = open(sys.argv[2], 'w', encoding='utf-8') if len(sys.argv) > 2 else sys.stdout
	a, sr = load(path)
	mono = a.mean(axis=1)
	hop, win = 128, 512
	nwin = (len(mono) - win) // hop
	idx = np.arange(win)[None, :] + hop * np.arange(nwin)[:, None]
	frames = mono[idx] * np.hanning(win)[None, :]
	spec = np.abs(np.fft.rfft(frames, axis=1)) ** 2
	freqs = np.fft.rfftfreq(win, 1.0 / sr)
	hf = spec[:, (freqs >= 16500) & (freqs <= 20500)].sum(axis=1)
	mid = spec[:, (freqs >= 2000) & (freqs <= 12000)].sum(axis=1)
	rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-20)
	hf_db = 10 * np.log10(hf + 1e-20)
	t = (np.arange(nwin) * hop + win / 2) / sr
	floor = np.median(hf_db[rms > 1e-4]) if (rms > 1e-4).any() else -200
	# a click: the HF band jumps >= 20 dB over its running floor and stands above the 2-12 kHz content's spillover
	thr = floor + 20
	peaks = []
	for i in range(1, nwin - 1):
		if hf_db[i] >= thr and hf_db[i] >= hf_db[i - 1] and hf_db[i] > hf_db[i + 1] and hf[i] > 1e-3 * mid[i]:
			if not peaks or t[i] - peaks[-1] > 0.004: peaks.append(t[i])
	peaks = np.array(peaks)
	dur = len(mono) / sr
	print(f'{path}', file=out)
	print(f'  length {dur:.1f} s, {sr} Hz, {a.shape[1]} ch; HF floor {floor:.1f} dB, click threshold {thr:.1f} dB', file=out)
	print(f'  clicks: {len(peaks)} ({len(peaks) / dur:.1f}/s)', file=out)
	if len(peaks) > 2:
		d = np.diff(peaks) * 1000
		h, e = np.histogram(d, bins=[0, 5, 8, 10, 12, 15, 18, 20, 22, 25, 30, 35, 40, 45, 50, 60, 80, 100, 150, 200, 500, 1e9])
		print('  spacing between clicks (ms): ' + ', '.join(f'{e[k]:.0f}-{e[k + 1]:.0f}:{h[k]}' for k in range(len(h)) if h[k]), file=out)
		print(f'  median spacing {np.median(d):.1f} ms', file=out)
	# per-second table: clicks, level
	print('  second: clicks level(dBFS)', file=out)
	row = []
	for s in range(int(dur) + 1):
		m = (t >= s) & (t < s + 1)
		c = int(((peaks >= s) & (peaks < s + 1)).sum())
		lv = 20 * np.log10(rms[m].mean() + 1e-9) if m.any() else -180
		row.append(f'{s:4d}:{c:3d} {lv:6.1f}')
		if len(row) == 6:
			print('   ' + ' | '.join(row), file=out); row = []
	if row: print('   ' + ' | '.join(row), file=out)
	# dropouts: >= 8 ms below -70 dBFS with >= -35 dBFS within 50 ms on both sides
	q = 20 * np.log10(rms + 1e-9)
	drops = []
	i = 0
	while i < nwin:
		if q[i] < -70:
			j = i
			while j < nwin and q[j] < -70: j += 1
			ln = (j - i) * hop / sr
			k = int(0.05 * sr / hop)
			if 0.008 <= ln <= 0.5 and i - k >= 0 and j + k < nwin and q[i - k:i].max() > -35 and q[j:j + k].max() > -35:
				drops.append((t[i], ln))
			i = j
		else: i += 1
	print(f'  dropouts (short silences inside sound): {len(drops)}', file=out)
	for s, ln in drops[:40]: print(f'    {s:8.3f} s  {ln * 1000:6.1f} ms', file=out)
	# channel balance
	l, r = a[:, 0], a[:, 1] if a.shape[1] > 1 else a[:, 0]
	cor = float(np.corrcoef(l[::7], r[::7])[0, 1]) if l.std() > 0 and r.std() > 0 else 1.0
	print(f'  L rms {20 * np.log10(np.sqrt((l ** 2).mean()) + 1e-9):.1f} dB, R rms {20 * np.log10(np.sqrt((r ** 2).mean()) + 1e-9):.1f} dB, L/R correlation {cor:.2f}', file=out)
	print(f'  peak {20 * np.log10(np.abs(a).max() + 1e-9):.1f} dBFS, samples at full scale: {int((np.abs(a) >= 0.999).sum())}', file=out)
	np.save(path.replace('.wav', '_clicks.npy'), peaks)

if __name__ == '__main__':
	main()
