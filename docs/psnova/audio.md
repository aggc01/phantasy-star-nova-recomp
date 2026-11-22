# Chopped sound (2026-11-19)

The user: "the audio is messed up", with nine screen recordings (Desktop, `Recording 2026-11-19 1..9.mp4`, 16 minutes).

## What the recordings showed

`dev/psnova/video_review.sh <out> <videos>` wrote each recording's sound as a WAV (and contact sheets, a spectrogram) to
`dump/user-videos-2026-11-19/`. `dev/psnova/audio_faults.py <sound.wav>` counts clicks: the game's sound stops near
15 kHz, so a burst at 16.5-20.5 kHz is a break in the waveform.

- Every recording: 12-27 clicks a second, spaced in steps of ~21 ms (median spacing 21-40 ms).
- The waveform (recording 1 at 40 s): the sound drops to flat silence for 4-5 ms about every 21 ms, in both channels.

## The cause: the A/V delay's silence top-up

Phantasy Star Nova's sound engine (CRI Atom, thread "CRI Atom AudioOut") outputs **256-sample buffers** (5.3 ms) on port 0;
movies use 1024-sample buffers on port 1.

`runtime/ui/window.c` `audio_output` holds each port's sound back by the measured A/V delay (about 49 ms here): that much
audio waits in the port's SDL stream beyond the pacing depth. It topped the stream up with silence **whenever it held
less than the delay** when a buffer arrived. But the pacing wait just below returns as soon as the stream is down to
exactly delay + one buffer, so a 256-sample port has 5.3 ms of slack. The device takes its data in larger pieces (the
longest wait between two buffers was 10.6 ms = 512 frames), so nearly every few buffers the stream dipped under the
delay and got a piece of silence in the middle of the sound, while the delay's own ~45 ms of real sound still waited.
The silence also counts toward the pacing, so the game was held back: it produced its sound at 80 % of real time.

`RECOMP_AUDIO_LOG=1` (new) prints each port's handover every 5 s. Title screen, 60 fps, windowed
(`dev/psn-logs/run_audio_check.sh`):

| | buffers / 5 s (port 0) | silence put in | sound rate |
|---|---|---|---|
| old top-up (`RECOMP_AUDIO_PAD=dip`, test92) | 750 x 256 | 250 top-ups, 1000 ms per 5 s | 38,400 / s (80 %) |
| fixed (test93) | 939 x 256 | 0 | 48,077 / s (real time) |

Port 1 (1024-sample buffers) never got a top-up in either run: with 21 ms buffers the slack was large enough.

## The fix

The top-up now happens only when the port **ran dry** (it found the stream empty: the speakers are getting silence
already, and the delay is set up again so the next late buffer doesn't run dry too) or **the delay rose** (by the rise).
A lower delay still drains through the pacing wait. With the fix: 0 top-ups, 0 times empty, the queue stays at the
delay (45-49 ms), so the picture/sound sync is unchanged.

`RECOMP_AUDIO_PAD=dip` brings the old behaviour back (for comparison only).

An earlier recording that morning (`Recording 2026-11-19 072124.mp4`, before the movie) had no chop; its clicks were the
warp movie's own broadband sound (no flat gaps in the waveform). The chop depends on how the sound device takes its data
(here in 512-frame pieces against the port's 256-frame buffers); that can change with the output device or Windows'
audio settings. The fix doesn't depend on it.

## Not covered

- The movies' sound (port 1) was not chopped by this; the movies' own playback at 60 fps (CPU decode, ~48 fps) is a
  separate open item (frame-rate.md).
- Checked on the title screen's music at 60 fps; gameplay uses the same port and buffer size.
