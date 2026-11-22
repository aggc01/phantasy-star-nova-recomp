/* save_backups_test <fs folder>: drives runtime/ui/save_backups.c on a copy of a save (RECOMP_FS = the folder):
 * back up, list, change the save, restore, check the bytes came back, delete. Prints PASS/FAIL per step. */
#include "save_backups.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
static long fsize(const char *p) { FILE *f = fopen(p, "rb"); if (!f) return -1; fseek(f, 0, SEEK_END); long n = ftell(f); fclose(f); return n; }
static int same(const char *a, const char *b) {
	FILE *x = fopen(a, "rb"), *y = fopen(b, "rb"); if (!x || !y) { if (x) fclose(x); if (y) fclose(y); return 0; }
	int ok = 1, c, d; do { c = fgetc(x); d = fgetc(y); if (c != d) { ok = 0; break; } } while (c != EOF);
	fclose(x); fclose(y); return ok;
}
static int fails;
static void check(int cond, const char *what) { printf("%s  %s\n", cond ? "PASS" : "FAIL", what); if (!cond) fails++; }
int main(int argc, char **argv) {
	if (argc < 2) return 2;
	char env[1100]; snprintf(env, sizeof env, "RECOMP_FS=%s", argv[1]); putenv(env);
	char msg[512], p[1200], ref[1200];
	SaveBackup cur; check(save_backups_current(&cur) == 1, "current save found");
	printf("      title '%s' subtitle '%s' detail '%s' %04d-%02d-%02d %02d:%02d, %d files %lld bytes\n", cur.title, cur.subtitle, cur.detail, cur.year, cur.month, cur.day, cur.hour, cur.minute, cur.files, cur.bytes);
	check(save_backups_create("after arena", msg, sizeof msg) == 0, msg);
	check(save_backups_create("weird/..\name:*", msg, sizeof msg) == 0, msg);
	SaveBackup b[16]; int n = save_backups_list(b, 16);
	check(n == 2, "two backups listed");
	for (int i = 0; i < n; i++) printf("      [%d] %s  (%d files, slot %04d-%02d-%02d)\n", i, b[i].name, b[i].files, b[i].year, b[i].month, b[i].day);
	char keep[128]; snprintf(keep, sizeof keep, "%s", strstr(b[0].name, "after") ? b[0].name : b[1].name);
	snprintf(p, sizeof p, "%s/savedata0/savedata0.bin", argv[1]); snprintf(ref, sizeof ref, "%s/../save_backups/%s/savedata0.bin", argv[1], keep);
	check(same(p, ref), "backup bytes equal the save");
	FILE *f = fopen(p, "r+b"); fputs("CHANGED", f); fclose(f);   /* the game saved something else since */
	check(!same(p, ref), "save changed");
	check(save_backups_restore(keep, msg, sizeof msg) == 0, msg);
	check(same(p, ref), "restored bytes equal the backup");
	n = save_backups_list(b, 16); check(n == 3, "a 'before restore' backup was added");
	int found = 0; for (int i = 0; i < n; i++) if (strstr(b[i].name, "before restore")) { found = 1; char q[1200]; snprintf(q, sizeof q, "%s/../save_backups/%s/savedata0.bin", argv[1], b[i].name); check(fsize(q) == fsize(p), "the replaced save kept whole"); }
	check(found, "found the 'before restore' backup");
	check(save_backups_restore("../evil", msg, sizeof msg) != 0, msg);
	check(save_backups_delete("nope", msg, sizeof msg) != 0, msg);
	for (int i = 0; i < n; i++) check(save_backups_delete(b[i].name, msg, sizeof msg) == 0, msg);
	check(save_backups_list(b, 16) == 0, "all deleted");
	/* more backups than the list holds: the newest must still come first (the review's finding, 2026-11-19) */
	{	char root[1200]; snprintf(root, sizeof root, "%s/../save_backups", argv[1]);
		for (int i = 0; i < 70; i++) { char q[1300]; snprintf(q, sizeof q, "%s/2000-01-01 00-%02d-00 old", root, i); mkdir(q, 0755); }
		check(save_backups_create("newest", msg, sizeof msg) == 0, msg);
		SaveBackup big[64]; int k = save_backups_list(big, 64);
		check(k == 64 && strstr(big[0].name, "newest") != 0, "newest first with 71 backups and room for 64");
		check(strstr(big[63].name, "2000-01-01 00-07-00") != 0, "the oldest ones are the ones left out");
		for (int i = 0; i < 70; i++) { char nm[64]; snprintf(nm, sizeof nm, "2000-01-01 00-%02d-00 old", i); save_backups_delete(nm, msg, sizeof msg); }
		save_backups_delete(big[0].name, msg, sizeof msg);
		check(save_backups_list(big, 64) == 0, "cleaned up");
	}
	printf("%s (%d failed)\n", fails ? "FAILED" : "ALL PASS", fails);
	return fails != 0;
}
