#!/usr/bin/env bash
# Prepare the user's screen recordings for review without watching them in real time:
#   contact sheets (one frame every 2 s, 4x4 per sheet = 32 s), a sound spectrogram, and the sound as a WAV
#   for dev/psnova/audio_faults.py.
# usage: dev/psnova/video_review.sh <out dir> <video>...
# Outputs stay under dump/ (the game's imagery is never committed).
set -euo pipefail
here="$(cd "$(dirname "$0")/../.." && pwd)"
ff="$here/tools/ffmpeg.exe"
out="$1"; shift
mkdir -p "$out"
for v in "$@"; do
	base="$(basename "$v" .mp4)"; base="${base// /_}"
	d="$out/$base"; mkdir -p "$d"
	"$ff" -hide_banner -loglevel error -y -i "$v" -vf "fps=1/2,scale=480:-2,drawtext=text='%{pts\:hms}':x=6:y=6:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=4x4" -q:v 4 "$d/sheet_%02d.jpg"
	"$ff" -hide_banner -loglevel error -y -i "$v" -vn -ac 2 -ar 48000 -c:a pcm_s16le "$d/sound.wav"
	"$ff" -hide_banner -loglevel error -y -i "$v" -lavfi "showspectrumpic=s=1800x500:legend=1:scale=log" "$d/spectrum.png"
	echo "$base: $(ls "$d"/sheet_*.jpg | wc -l) sheets"
done
