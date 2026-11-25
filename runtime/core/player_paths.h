/* The portable player directory survives updates to game assets. */
#ifndef NOVA_PLAYER_PATHS_H
#define NOVA_PLAYER_PATHS_H

#include <stddef.h>
#include <stdlib.h>

static inline const char *player_save_override(void) {
    const char *root = getenv("RECOMP_SAVE_ROOT");
    return root && *root ? root : NULL;
}

static inline const char *player_save_root(void) {
    const char *root = player_save_override();
    if (!root) root = getenv("RECOMP_FS");
    return root && *root ? root : "fs";
}

const char *host_path_s(const char *path, char *buffer, size_t size);

#endif
