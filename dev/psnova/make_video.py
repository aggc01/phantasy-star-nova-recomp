"""make_video.py <recording dir> <out.mp4> [--ffmpeg path] [--fps 30] [--scale WxH]

Turns a gameplay recording (RECOMP_VIDEO_DIR=<dir> on a run: runtime/gfx/gfx_gpu.c video_* and runtime/gfx/display.c
audio recording) into an MP4 (H.264 + AAC):
  frames.txt   "<frame> <host us> <file>"          one line per presented frame, its JPEG beside it
  audio.txt    "<port> <host us> <offset> <bytes> <rate> <channels> <volL> <volR>"   one line per sceAudioOutOutput
  audio_<port>.raw                                  that port's 16-bit PCM, buffer after buffer
Both clocks are the host's monotonic microseconds, so the picture and the sound line up: every frame lasts until the
next one's time (the game's own pacing, slow frames included) and every audio buffer is mixed in at the time the game
handed it over (sceAudioOutOutput blocks until the buffer before has played, so that is when it starts to sound).

ffmpeg: the first that exists of --ffmpeg, $FFMPEG, the copies Subtitle Edit and Stremio keep on this PC.
Run with any Python 3 that has numpy (the system one here: C:\\Python314\\python.exe).
"""
import argparse
import os
import subprocess
import sys
import wave

import numpy as np

RATE = 48000


def find_ffmpeg(arg):
    cands = [arg, os.environ.get("FFMPEG"),
             os.path.expandvars(r"%LOCALAPPDATA%\Programs\SubtitleEdit\ffmpeg\ffmpeg.exe"),
             os.path.expandvars(r"%LOCALAPPDATA%\Programs\Stremio\ffmpeg.exe")]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    sys.exit("no ffmpeg found (pass --ffmpeg)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("out")
    ap.add_argument("--ffmpeg"); ap.add_argument("--fps", type=int, default=30); ap.add_argument("--scale", default="")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--max-frames", type=int, default=0, help="only the first N frames (a quick check of a recording)")
    ap.add_argument("--preset", default="medium")
    a = ap.parse_args()
    d = a.dir
    frames = []
    for line in open(os.path.join(d, "frames.txt")):
        p = line.split()
        if len(p) >= 3 and os.path.isfile(os.path.join(d, p[2])):
            frames.append((int(p[1]), p[2]))
    if len(frames) < 2:
        sys.exit("fewer than 2 frames recorded")
    frames.sort()
    if a.max_frames:
        frames = frames[:a.max_frames]
    # a recording with several RECOMP_VIDEO_RANGES has gaps between them (minutes of an unrecorded intro): each pause of
    # over a second between two frames becomes a cut -- the time after it moves back by the gap, picture and sound alike
    # (a first version held the frame before a gap for the whole gap: 1,800 frames came out as 348 s)
    frame_us = 1_000_000 // a.fps
    gaps, shift, adj, prev = [], 0, [], None
    for t, name in frames:
        if prev is not None and t - prev > 1_000_000:
            removed = (t - prev) - frame_us
            gaps.append((prev, t, removed)); shift += removed
        adj.append((t - shift, name)); prev = t
    def adj_time(t):   # an audio buffer's time on the cut timeline; None inside a gap
        s = 0
        for g0, g1, rem in gaps:
            if t >= g1: s += rem
            elif t > g0: return None
        return t - s
    frames = adj
    if gaps:
        print(f"{len(gaps)} gap(s) cut: " + ", ".join(f"{rem / 1e6:.0f} s" for _, _, rem in gaps))
    t0, t_end = frames[0][0], frames[-1][0] + frame_us
    # the picture: ffmpeg's concat list, each frame shown until the next one's time
    lst = os.path.join(d, "frames_concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for k, (t, name) in enumerate(frames):
            nxt = frames[k + 1][0] if k + 1 < len(frames) else t_end
            f.write(f"file '{name}'\nduration {max(nxt - t, 1000) / 1e6:.6f}\n")
        f.write(f"file '{frames[-1][1]}'\n")   # (the concat demuxer drops the last entry's duration otherwise)
    # the sound: every port's buffers mixed onto one 48 kHz stereo timeline from the first frame's time
    mix = np.zeros((int((t_end - t0) / 1e6 * RATE) + RATE, 2), np.float32)
    raws, n_buf, n_late = {}, 0, 0
    at = os.path.join(d, "audio.txt")
    for line in open(at) if os.path.isfile(at) else []:
        p = line.split()
        if len(p) < 8:
            continue
        port, t, off, nbytes, rate, ch = (int(x) for x in p[:6])
        t = adj_time(t)
        if t is None:
            continue
        vol = np.array([int(p[6]), int(p[7])], np.float32) / 0x8000
        if port not in raws:
            raws[port] = np.memmap(os.path.join(d, f"audio_{port}.raw"), np.int16, "r")
        pcm = np.asarray(raws[port][off // 2:(off + nbytes) // 2], np.float32) / 32768.0
        pcm = pcm.reshape(-1, ch) if ch > 1 else np.repeat(pcm[:, None], 2, axis=1)
        if rate != RATE:   # (linear resampling: the game's ports are 48 kHz; a movie's may not be)
            n = int(len(pcm) * RATE / rate)
            x = np.linspace(0, len(pcm) - 1, n)
            pcm = np.stack([np.interp(x, np.arange(len(pcm)), pcm[:, c]) for c in range(2)], 1).astype(np.float32)
        i = int((t - t0) / 1e6 * RATE)
        if i < 0:
            pcm = pcm[-i:]; i = 0; n_late += 1
        j = min(i + len(pcm), len(mix))
        if j > i:
            mix[i:j] += pcm[:j - i] * vol
        n_buf += 1
    peak = float(np.abs(mix).max()) if n_buf else 0.0
    wav = os.path.join(d, "audio_mix.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
    print(f"{len(frames)} frames over {(t_end - t0) / 1e6:.1f} s ({len(frames) / ((t_end - t0) / 1e6):.1f} fps on average); "
          f"{n_buf} audio buffers from {len(raws)} port(s), peak {peak:.2f}{' (clipped)' if peak > 1 else ''}")
    # the JPEGs are full range; players expect video (limited) range in yuv420p (ffmpeg otherwise kept yuvj420p)
    vf = ["-vf", (f"scale={a.scale.replace('x', ':')}:flags=lanczos:" if a.scale else "scale=") + "in_range=full:out_range=tv,format=yuv420p"]
    cmd = [find_ffmpeg(a.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
           *vf, "-r", str(a.fps), "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", a.out]
    r = subprocess.run(cmd)
    if r.returncode:
        sys.exit(f"ffmpeg failed ({r.returncode})")
    print(f"-> {a.out} ({os.path.getsize(a.out) / (1 << 20):.1f} MB)")


if __name__ == "__main__":
    main()
