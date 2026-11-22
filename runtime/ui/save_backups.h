/* Save backups: copies of the game's own save folder for the menu's Saves page (overlay.cpp). save_backups.c has the why. */
#ifndef SAVE_BACKUPS_H
#define SAVE_BACKUPS_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
	char name[128];       /* the backup's folder name in save_backups/ (its date, then the label) */
	char title[64];       /* the newest save slot's texts, as the game wrote them (UTF-8): title, subtitle, detail */
	char subtitle[128];
	char detail[256];
	int year, month, day, hour, minute;   /* when the game last wrote that slot (0: no slot marker) */
	int files;            /* how many files the backup holds */
	long long bytes;      /* and their size */
} SaveBackup;

int save_backups_current(SaveBackup *out);   /* the save the game has now (fs/savedata0): 1, or 0 when it has none */
int save_backups_list(SaveBackup *out, int max);   /* the backups, newest first; how many */
int save_backups_create(const char *label, char *msg, size_t n);   /* back up the current save (label: optional); 0 ok, -1 failed; msg says what happened */
int save_backups_restore(const char *name, char *msg, size_t n);   /* put backup `name` in place of the current save, which is backed up first */
int save_backups_delete(const char *name, char *msg, size_t n);
void save_backups_dir(char *buf, size_t n);   /* where the backups are kept */

#ifdef __cplusplus
}
#endif
#endif
