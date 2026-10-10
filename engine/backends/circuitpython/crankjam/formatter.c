/* MIT. Bounded, heap-free, private formatter. C99-sized adapter to stb.
 * stb_sprintf v1.10, nothings/stb 2c980bb59875b0d32144a71867fbdebb2f77cd20.
 * The upstream dual MIT/public-domain license is retained in the header.
 * Floating least-significant digits and %a spelling can differ from libc;
 * this is not a claim of universally bit-identical libc formatting. */
#include "formatter.h"
#include <limits.h>
#define STB_SPRINTF_DECORATE(name) cj_stb_##name
#define STB_SPRINTF_NOUNALIGNED
#define STB_SPRINTF_IMPLEMENTATION
#include "stb_sprintf.h"
int cj_vsnprintf(char *buf, size_t cap, const char *fmt, va_list args) {
    if (cap > INT_MAX) { if (buf && cap) buf[0] = 0; return -1; }
    return cj_stb_vsnprintf(cap ? buf : NULL, (int)cap, fmt, args);
}
int cj_snprintf(char *buf, size_t cap, const char *fmt, ...) {
    va_list args; va_start(args, fmt);
    int n = cj_vsnprintf(buf, cap, fmt, args);
    va_end(args); return n;
}
