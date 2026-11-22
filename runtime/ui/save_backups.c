/*
 * Save backups (the menu's Saves page, overlay.cpp): copies of the game's own save folder, <RECOMP_FS>/savedata0, kept
 * beside the game's file system in <RECOMP_FS>/../save_backups/<name>/, where the game never looks. A backup is a plain
 * copy of every file there: the game's data files and the .slot<N> markers apputil.c writes (SceAppUtilSaveDataSlotParam,
 * whose title, subtitle and detail the page shows). A restore first backs up the save it replaces ("<date> before
 * restore"), so nothing is lost, then empties savedata0 and copies the backup in. The game reads its save only when it
 * loads one, so a restored save is played by loading it: the title screen's Continue, or after restarting the game.
 *
 * Why not save states: a recompiled game runs as the host's own code, on its own threads and call stacks (a guest
 * function is a C function, fn_xxx(c), called on the host stack), so the whole machine can't be frozen to a file and
 * resumed the way an emulator's can. These are the game's own saves, at the points where it saved (asked for by the
 * Phantasy Star Nova player, 2026-11-19, to get back to places more easily).
 *
 * Names are ASCII only (letters, digits, space, '-', '_'; no dots, so a label can't make ".."): the Windows C library
 * opens paths in the ANSI code page.
 * The menu pauses the game while it's up, so the game isn't writing its save while a backup or restore copies it.
 */
#include "save_backups.h"
#include <dirent.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static const char *fs_root(void) { const char *e = getenv("RECOMP_FS"); return e && *e ? e : "fs"; }
void save_backups_dir(char *buf, size_t n) { snprintf(buf, n, "%s/../save_backups", fs_root()); }
static void save_dir(char *buf, size_t n) { snprintf(buf, n, "%s/savedata0", fs_root()); }

static int is_dir(const char *p) { struct stat st; return stat(p, &st) == 0 && S_ISDIR(st.st_mode); }
static int make_dir(const char *p) { return mkdir(p, 0755) == 0 || errno == EEXIST ? 0 : -1; }
static int skip(const char *n) { return !strcmp(n, ".") || !strcmp(n, ".."); }

static int copy_file(const char *src, const char *dst) {
	FILE *in = fopen(src, "rb"); if (!in) return -1;
	FILE *out = fopen(dst, "wb"); if (!out) { fclose(in); return -1; }
	char buf[65536]; size_t k; int err = 0;
	while ((k = fread(buf, 1, sizeof buf, in)) > 0) if (fwrite(buf, 1, k, out) != k) { err = 1; break; }
	if (ferror(in)) err = 1;
	fclose(in); if (fclose(out)) err = 1;
	return err ? -1 : 0;
}
static int copy_tree(const char *src, const char *dst) {   /* every file and folder in src into dst (made if missing) */
	if (make_dir(dst)) return -1;
	DIR *d = opendir(src); if (!d) return -1;
	struct dirent *e; int rc = 0;
	while ((e = readdir(d))) {
		if (skip(e->d_name)) continue;
		char s[2048], t[2048]; snprintf(s, sizeof s, "%s/%s", src, e->d_name); snprintf(t, sizeof t, "%s/%s", dst, e->d_name);
		if (is_dir(s) ? copy_tree(s, t) : copy_file(s, t)) rc = -1;
	}
	closedir(d); return rc;
}
static int empty_tree(const char *dir, int remove_self) {   /* dir's contents removed (and dir, if remove_self) */
	DIR *d = opendir(dir); if (!d) return is_dir(dir) ? -1 : 0;
	struct dirent *e; int rc = 0;
	while ((e = readdir(d))) {
		if (skip(e->d_name)) continue;
		char p[2048]; snprintf(p, sizeof p, "%s/%s", dir, e->d_name);
		if (is_dir(p) ? empty_tree(p, 1) : unlink(p)) rc = -1;
	}
	closedir(d);
	if (remove_self && rmdir(dir)) rc = -1;
	return rc;
}
static void tree_size(const char *dir, int *files, long long *bytes) {
	DIR *d = opendir(dir); if (!d) return;
	struct dirent *e;
	while ((e = readdir(d))) {
		if (skip(e->d_name)) continue;
		char p[2048]; struct stat st; snprintf(p, sizeof p, "%s/%s", dir, e->d_name);
		if (stat(p, &st)) continue;
		if (S_ISDIR(st.st_mode)) tree_size(p, files, bytes); else { (*files)++; *bytes += (long long)st.st_size; }
	}
	closedir(d);
}
static void field(char *out, size_t n, const uint8_t *p, size_t len) {   /* a NUL-padded UTF-8 field of the slot param */
	size_t k = 0; while (k < len && p[k]) k++;
	if (k >= n) k = n - 1;
	memcpy(out, p, k); out[k] = 0;
}
static void read_info(const char *dir, SaveBackup *b) {   /* the newest .slot<N> marker's texts and time, and the file count */
	tree_size(dir, &b->files, &b->bytes);
	DIR *d = opendir(dir); if (!d) return;
	struct dirent *e; long long best = -1;
	while ((e = readdir(d))) {
		if (strncmp(e->d_name, ".slot", 5)) continue;
		char p[2048]; snprintf(p, sizeof p, "%s/%s", dir, e->d_name);
		uint8_t s[0x34c]; memset(s, 0, sizeof s);
		FILE *f = fopen(p, "rb"); if (!f) continue;
		size_t got = fread(s, 1, sizeof s, f); fclose(f);
		if (got < 0x318) continue;
		uint16_t t[6]; memcpy(t, s + 0x30c, sizeof t);   /* modifiedTime: year, month, day, hour, minute, second */
		const long long key = ((((long long)t[0] * 13 + t[1]) * 32 + t[2]) * 24 + t[3]) * 3600LL + t[4] * 60LL + t[5];   /* (64-bit: a Windows long is 32) */
		if (key <= best) continue;
		best = key;
		field(b->title, sizeof b->title, s + 0x4, 64); field(b->subtitle, sizeof b->subtitle, s + 0x44, 128); field(b->detail, sizeof b->detail, s + 0xc4, 512);
		b->year = t[0]; b->month = t[1]; b->day = t[2]; b->hour = t[3]; b->minute = t[4];
	}
	closedir(d);
}
static int name_ok(const char *name) {   /* one plain folder name of ours: no path in it */
	if (!name || !*name || strlen(name) >= 128 || strstr(name, "..")) return 0;
	for (const char *c = name; *c; c++) if (*c == '/' || *c == '\\' || *c == ':') return 0;
	return 1;
}

int save_backups_current(SaveBackup *out) {
	memset(out, 0, sizeof *out);
	char d[1024]; save_dir(d, sizeof d);
	if (!is_dir(d)) return 0;
	read_info(d, out); snprintf(out->name, sizeof out->name, "savedata0");
	return out->files > 0;
}
static int newest_name_first(const void *a, const void *b) { return strcmp(*(const char *const *)b, *(const char *const *)a); }
int save_backups_list(SaveBackup *out, int max) {   /* every folder's name read first, sorted newest first, then the first `max` (a cut in
                                                     * listing order kept the oldest: NTFS lists by name, and the names start with the date) */
	char root[1024]; save_backups_dir(root, sizeof root);
	DIR *d = opendir(root); if (!d) return 0;
	char **names = 0; int nn = 0, cap = 0; struct dirent *e;
	while ((e = readdir(d))) {
		if (skip(e->d_name) || !name_ok(e->d_name)) continue;
		char p[2048]; snprintf(p, sizeof p, "%s/%s", root, e->d_name);
		if (!is_dir(p)) continue;
		if (nn == cap) { cap = cap ? cap * 2 : 64; char **g = realloc(names, (size_t)cap * sizeof *names); if (!g) break; names = g; }
		if (!(names[nn] = strdup(e->d_name))) break;
		nn++;
	}
	closedir(d);
	qsort(names, (size_t)nn, sizeof *names, newest_name_first);
	int n = 0;
	for (int i = 0; i < nn; i++) {
		if (n < max) { char p[2048]; snprintf(p, sizeof p, "%s/%s", root, names[i]); memset(&out[n], 0, sizeof out[n]); snprintf(out[n].name, sizeof out[n].name, "%s", names[i]); read_info(p, &out[n]); n++; }
		free(names[i]);
	}
	free(names);
	return n;
}
static int backup_as(const char *label, char *made, size_t made_n, char *msg, size_t n) {
	char src[1024]; save_dir(src, sizeof src);
	SaveBackup cur; if (!save_backups_current(&cur)) { snprintf(msg, n, "There is no save yet: save in the game first."); return -1; }
	char root[1024]; save_backups_dir(root, sizeof root);
	if (make_dir(root)) { snprintf(msg, n, "Couldn't make the folder %s.", root); return -1; }
	char clean[64] = {0}; size_t k = 0;   /* the label, ASCII only (see the top) */
	for (const char *c = label ? label : ""; *c && k < sizeof clean - 1; c++) {
		const unsigned char u = (unsigned char)*c;
		clean[k++] = (u < 0x80 && (u == ' ' || u == '-' || u == '_' || (u >= '0' && u <= '9') || (u >= 'A' && u <= 'Z') || (u >= 'a' && u <= 'z'))) ? (char)u : '_';
	}
	while (k && clean[k - 1] == ' ') clean[--k] = 0;   /* (Windows drops trailing spaces) */
	time_t now = time(0); struct tm tm; localtime_r(&now, &tm);
	char base[128]; snprintf(base, sizeof base, "%04d-%02d-%02d %02d-%02d-%02d%s%s", tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec, k ? " " : "", clean);
	char name[128], dst[2048];
	for (int i = 1; i < 100; i++) {   /* a free name: " (2)", " (3)"... after the first */
		if (i == 1) snprintf(name, sizeof name, "%s", base); else snprintf(name, sizeof name, "%.110s (%d)", base, i);
		snprintf(dst, sizeof dst, "%s/%s", root, name);
		if (!is_dir(dst)) break;
	}
	if (copy_tree(src, dst)) { empty_tree(dst, 1); snprintf(msg, n, "The backup failed (copying to %s).", dst); return -1; }
	if (made) snprintf(made, made_n, "%s", name);
	snprintf(msg, n, "Backed up as \"%s\" (%d files).", name, cur.files);
	return 0;
}
int save_backups_create(const char *label, char *msg, size_t n) { return backup_as(label, 0, 0, msg, n); }
int save_backups_restore(const char *name, char *msg, size_t n) {
	if (!name_ok(name)) { snprintf(msg, n, "Not a backup name: %s", name ? name : "(none)"); return -1; }
	char root[1024], src[2048], dst[1024]; save_backups_dir(root, sizeof root); snprintf(src, sizeof src, "%s/%s", root, name); save_dir(dst, sizeof dst);
	if (!is_dir(src)) { snprintf(msg, n, "The backup \"%s\" isn't there any more.", name); return -1; }
	char kept[128] = "", m2[256] = "";
	SaveBackup cur;
	if (save_backups_current(&cur) && backup_as("before restore", kept, sizeof kept, m2, sizeof m2)) {   /* the save being replaced, kept first */
		snprintf(msg, n, "Not restored: the current save couldn't be backed up first (%s).", m2); return -1;
	}
	if (make_dir(dst) || empty_tree(dst, 0) || copy_tree(src, dst)) {
		snprintf(msg, n, "The restore failed while copying.%s%s%s", kept[0] ? " The save that was there is in \"" : "", kept, kept[0] ? "\"." : ""); return -1;
	}
	snprintf(msg, n, "Restored \"%s\". Load it in the game: the title screen's Continue (restart the game first if you're in play).%s%s%s", name,
	         kept[0] ? " The save it replaced is kept as \"" : "", kept, kept[0] ? "\"." : "");
	return 0;
}
int save_backups_delete(const char *name, char *msg, size_t n) {
	if (!name_ok(name)) { snprintf(msg, n, "Not a backup name: %s", name ? name : "(none)"); return -1; }
	char root[1024], p[2048]; save_backups_dir(root, sizeof root); snprintf(p, sizeof p, "%s/%s", root, name);
	if (!is_dir(p)) { snprintf(msg, n, "The backup \"%s\" isn't there any more.", name); return -1; }
	if (empty_tree(p, 1)) { snprintf(msg, n, "Couldn't delete all of \"%s\".", name); return -1; }
	snprintf(msg, n, "Deleted \"%s\".", name);
	return 0;
}
