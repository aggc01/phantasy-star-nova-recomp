/*
 * Phantasy Star Nova (PCSG00351): its hooks, built into this game alone (runtime/build.py RECOMP_PACK_SOURCES);
 * packs/PCSG00351/pack.toml's HOOKS= / IHOOKS= place them (1.05 addresses). What every game's hooks share is
 * runtime/core/hooks.h.
 */
#include "hooks.h"

/*
 * Diagnostics for the input thread (RECOMP_PSN_INPUT_TRACE=1), 2026-11-18. The game's controller is read by an Aska
 * worker whose job, fn_81a1f276, loops "while not quit: for each of 3 device slots (+0x18): slot->update() (vtable
 * +0x24); sleep 8 ms". The pad device's update (fn_81b1cd18 -> fn_81b1c958) reads sceCtrlPeekBufferPositive -- yet in
 * play that read happened once, at frame 0, and buttons never reached the game. psn_input_slot (after the slot load at
 * 0x81a1f284): which device each slot holds, as the loop sees it; psn_pad_update (fn_81b1c958's entry): how often the
 * pad's update runs and with what lock state.
 */
static int psn_trace(void) { static int v = -1; if (v < 0) v = getenv("RECOMP_PSN_INPUT_TRACE") != 0; return v; }
void recomp_ihook_psn_input_slot(Cpu *c, int reg) {
	if (!psn_trace()) return;
	static unsigned n;
	if (n++ < 24 || n % 2000 == 0) {
		uint32_t dev = c->r[0], vt = dev ? RD32(dev) : 0, upd = vt ? RD32(vt + 0x24) : 0;
		fprintf(stderr, "    psn input: pass %u slot %#x -> device %#x vtable %#x update %#x quit %u (frame %llu)\n",
		        n, c->r[4], dev, vt, upd, RD8(c->r[5] + 0x24), (unsigned long long)display_frames());
	}
}
void recomp_hook_psn_pad_update(Cpu *c) {
	if (!psn_trace()) return;
	static unsigned n;
	uint32_t o = c->r[0];
	if (n++ < 12 || n % 500 == 0)
		fprintf(stderr, "    psn pad update #%u: device %#x lock %#x waiters %#x (frame %llu)\n", n, o, o ? RD32(o + 4) : 0, o ? RD32(o + 8) : 0,
		        (unsigned long long)display_frames());
}

/*
 * The abort after "Start the Game" (2026-11-18): an Aska worker calls fn_81b2a8bc, a std::map/set insert (MS STL:
 * "if (size >= max_size) _Xlength_error"; max_size 0x071c71c6 = 36-byte nodes), on a tree whose size field (+8) reads
 * >= 0x071c71c6, so the game aborts. psn_tree_insert (its entry) prints the tree and its caller when the size is that
 * large -- which call site (lr), the caller's callee-saved registers (the object the tree belongs to) and the memory
 * around the tree -- then the native chain. Costs one guest read per insert; prints only on the bad one.
 */
void recomp_hook_psn_tree_insert(Cpu *c) {
	uint32_t t = c->r[0];
	if (!t || RD32(t + 8) < 0x071c71c6u) return;
	static int shown;
	if (shown++ >= 2) return;
	fprintf(stderr, "    psn tree insert: tree %#x head %#x size %#x  r1 %#x r2 %#x [sp+0]=%#x lr %#x (frame %llu)\n", t, RD32(t + 4),
	        RD32(t + 8), c->r[1], c->r[2], RD32(c->r[13]), c->r[14], (unsigned long long)display_frames());
	fprintf(stderr, "    psn tree insert: r4 %#x r5 %#x r6 %#x r7 %#x r8 %#x r9 %#x r10 %#x r11 %#x sp %#x\n", c->r[4], c->r[5], c->r[6],
	        c->r[7], c->r[8], c->r[9], c->r[10], c->r[11], c->r[13]);
	for (int k = -0x40; k < 0x40; k += 16)
		fprintf(stderr, "    psn tree insert: %08x: %08x %08x %08x %08x\n", t + k, RD32(t + k), RD32(t + k + 4), RD32(t + k + 8), RD32(t + k + 12));
	plat_backtrace(stderr);
}

