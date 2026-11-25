#pragma once
/* Interactive SceIme bridge. */
#ifdef __cplusplus
extern "C" {
#endif
typedef struct { int open; unsigned seq, max_utf16; char text[4096]; } ImeView;
int ime_view(ImeView *out);
int ime_active(void);
void ime_submit(unsigned seq, const char *utf8);
void ime_cancel(unsigned seq);
#ifdef __cplusplus
}
#endif
