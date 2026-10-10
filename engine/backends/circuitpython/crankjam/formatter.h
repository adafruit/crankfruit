/* MIT. Module-local formatting; never interpose CircuitPython libc symbols. */
#ifndef CJ_FORMATTER_H
#define CJ_FORMATTER_H
#include <stddef.h>
#include <stdarg.h>
#define CJ_LOCAL_FORMATTER 1
int cj_snprintf(char *buf, size_t cap, const char *fmt, ...);
int cj_vsnprintf(char *buf, size_t cap, const char *fmt, va_list args);
#endif
