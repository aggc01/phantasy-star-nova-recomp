/* For dev/build_replay_win.sh: what gfxreplay.c uses that Windows lacks (setenv), without changing the runtime's own
 * win32_compat.h. */
#include <stdlib.h>
static inline int setenv(const char *k, const char *v, int over) { if (!over && getenv(k)) return 0; return _putenv_s(k, v); }
