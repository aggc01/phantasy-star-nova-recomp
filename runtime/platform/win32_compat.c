/* win32_compat.h's functions, and the C runtime's file mode */
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <sys/time.h>
#include <sys/utime.h>
#include <stdlib.h>
#include <string.h>
#include "win32_compat.h"

/* every open()/fopen() binary unless it asks otherwise: text mode turns CR LF bytes into LF and stops a read at the
 * first 0x1A (Ctrl-Z, end of file) -- Shovel Knight's FMOD read sound.fev in 2 KB reads and the first one ended at its
 * byte 256: "Error loading file" and the game's assert. _CRT_fmode is what mingw-w64's startup reads for msvcrt; the
 * UCRT llvm-mingw links by default ignores it, so the default is set at startup as well (_set_fmode) */
int _CRT_fmode = _O_BINARY;
__attribute__((constructor)) static void binary_files(void) { _set_fmode(_O_BINARY); }

/* positional I/O through the handle with an OVERLAPPED offset -- which on a synchronous handle moves the file
 * pointer too, so it is put back: the descriptor's read()/write() position stays where POSIX leaves it. The save and
 * restore are under a lock picked by the handle, so two threads' pread on one fd can't put back each other's stale
 * position (guest I/O runs on many host threads; fios.c mixes pread and read on one handle). A plain read() racing a
 * pread() on the same fd still sees the moved pointer for the length of the call. */
static SRWLOCK rw_locks[64] = {SRWLOCK_INIT};
static ssize_t rw_at(int fd, void *buf, size_t n, off_t off, int write) {
	HANDLE h = (HANDLE)_get_osfhandle(fd);
	if (h == INVALID_HANDLE_VALUE) { errno = EBADF; return -1; }
	SRWLOCK *lk = &rw_locks[((uintptr_t)h >> 2) % 64];
	AcquireSRWLockExclusive(lk);
	LARGE_INTEGER zero = {0}, cur; if (!SetFilePointerEx(h, zero, &cur, FILE_CURRENT)) { ReleaseSRWLockExclusive(lk); errno = EIO; return -1; }
	size_t total = 0; DWORD err = 0;
	while (total < n) {   /* (a DWORD a call: more than 4 GB in pieces) */
		DWORD part = n - total > 0x40000000u ? 0x40000000u : (DWORD)(n - total), done = 0; uint64_t at = (uint64_t)off + total;
		OVERLAPPED ov; memset(&ov, 0, sizeof ov); ov.Offset = (DWORD)(at & 0xffffffffu); ov.OffsetHigh = (DWORD)(at >> 32);
		BOOL ok = write ? WriteFile(h, (char *)buf + total, part, &done, &ov) : ReadFile(h, (char *)buf + total, part, &done, &ov);
		if (!ok) { err = GetLastError(); break; }
		total += done; if (done < part) break;   /* end of file */
	}
	SetFilePointerEx(h, cur, 0, FILE_BEGIN);
	ReleaseSRWLockExclusive(lk);
	if (err && err != ERROR_HANDLE_EOF && !total) { errno = err == ERROR_ACCESS_DENIED ? EACCES : EIO; return -1; }
	return (ssize_t)total;
}
ssize_t pread(int fd, void *buf, size_t n, off_t off) { return rw_at(fd, buf, n, off, 0); }
ssize_t pwrite(int fd, const void *buf, size_t n, off_t off) { return rw_at(fd, (void *)buf, n, off, 1); }

int win32_nanosleep(const struct timespec *req, struct timespec *rem) {
	if (rem) rem->tv_sec = rem->tv_nsec = 0;
	plat_sleep_ns((uint64_t)req->tv_sec * 1000000000u + (uint64_t)req->tv_nsec);
	return 0;
}
int utimes(const char *path, const struct timeval tv[2]) {
	struct __utimbuf64 u = { tv[0].tv_sec, tv[1].tv_sec };
	return _utime64(path, &u);
}
char *realpath(const char *path, char *resolved) {
	char full[MAX_PATH];
	if (!_fullpath(full, path, sizeof full)) { errno = ENAMETOOLONG; return 0; }
	if (GetFileAttributesA(full) == INVALID_FILE_ATTRIBUTES) { errno = ENOENT; return 0; }
	for (char *p = full; *p; p++) if (*p == '\\') *p = '/';
	size_t n = strlen(full); while (n > 3 && full[n - 1] == '/') full[--n] = 0;   /* (no trailing separator, as POSIX) */
	if (!resolved) return _strdup(full);
	memcpy(resolved, full, n + 1);
	return resolved;
}

#undef rename
int win32_rename(const char *from, const char *to) {
	if (MoveFileExA(from, to, MOVEFILE_REPLACE_EXISTING | MOVEFILE_COPY_ALLOWED)) return 0;
	DWORD e = GetLastError();
	errno = e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND ? ENOENT : e == ERROR_ACCESS_DENIED || e == ERROR_SHARING_VIOLATION ? EACCES : e == ERROR_NOT_SAME_DEVICE ? EXDEV : EIO;
	return -1;
}
