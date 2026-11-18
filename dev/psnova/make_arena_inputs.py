"""make_arena_inputs.py <buttons out> <sticks out> [--jump-every 40] [--phase-b 23720] [--end 28800]

The scripted play's input for `vitarecomp test` (TEST_INPUT) and its sticks (EXTRA_ENV RECOMP_INPUT_STICKS): the presses up
to the training arena as proven by the take-4/5 recordings (inputs/to-arena.txt: title, NEW GAME, character creation with
the name typed by SceIme, Yes on "will be saved", the story's dialogue -- Circle every 150 frames, margin-based so the
real clock's drift doesn't matter), then the arena.

The arena (from frame 21,800; the HUD comes up around 21,500-22,000 on this PC): the quest "Move to the arrows!" puts
the arrows straight ahead of the spawn point, beyond a field of crates. The real player (reference footage, part 1,
14:29-14:42) jumps onto the crates and runs over them; holding forward and pressing jump at different moments (takes 4
and 5) only ran into the first row. So:
  phase A (21,800 to --phase-b): cycles of 240 frames -- 120 with the left stick forward and Cross (jump; it also
          closes the help windows) tapped every --jump-every frames, 50 stepping back (stick down), 50 walking forward
          again without jumping, 20 standing still. Take 6 reached the cyan area under the arrows at ~21,960 and stayed
          there for the rest of the take -- bouncing, then attacking and resting in phase B -- without the quest
          completing, while test52 completed it: most likely the quest counts ENTERING the area and take 6 got there
          before the quest had begun (the jump taps close the help windows and the stick moves at once). Stepping out
          and back in each cycle, and standing still, covers both that and a "must be on the ground" rule.
  phase B (to --end): the next quests (attacks, enemies): cycles of 360 frames -- 200 running forward with jumps, then
          Square (attack) tapped every 20 frames for 130, a short rest.
Masks (hex, as RECOMP_INPUT reads them): Cross 4000, Circle 2000, Square 8000, Triangle 1000. Sticks: lx,ly,rx,ry bytes,
128 centred, ly 0 = forward.
"""
import argparse
import os

ap = argparse.ArgumentParser()
ap.add_argument("buttons"); ap.add_argument("sticks")
ap.add_argument("--start", type=int, default=21800)
ap.add_argument("--jump-every", type=int, default=40)
ap.add_argument("--phase-b", type=int, default=23720)
ap.add_argument("--end", type=int, default=28800)
a = ap.parse_args()

here = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(here, "inputs", "to-arena.txt")).read().strip().split(",")
base = [b for b in base if b and int(b.split("-")[0].split(":")[0]) < a.start]
btn, stk = list(base), []
CROSS, SQUARE = "4000", "8000"
FWD = "128,0,128,128"

# phase A: cycles of jumps forward, a step back out, a walk forward in, a stand
BACK = "128,255,128,128"
for f in range(a.start, a.phase_b, 240):
    stk.append(f"{f}-{f + 119}:{FWD}")
    stk.append(f"{f + 120}-{f + 169}:{BACK}")
    stk.append(f"{f + 170}-{f + 219}:{FWD}")   # (frames 220-239 of the cycle: sticks centred)
    for g in range(f, f + 120, a.jump_every):
        btn.append(f"{g}-{g + 5}:{CROSS}")
# phase B: run and jump, then attack
for f in range(a.phase_b, a.end, 360):
    stk.append(f"{f}-{f + 199}:{FWD}")
    for g in range(f, f + 200, a.jump_every):
        btn.append(f"{g}-{g + 5}:{CROSS}")
    for g in range(f + 200, f + 330, 20):
        btn.append(f"{g}-{g + 5}:{SQUARE}")

open(a.buttons, "w").write(",".join(btn) + "\n")
open(a.sticks, "w").write(";".join(stk) + "\n")
print(f"{len(btn)} button ranges, {len(stk)} stick ranges; arena from {a.start}, phase B from {a.phase_b}, to {a.end}")
