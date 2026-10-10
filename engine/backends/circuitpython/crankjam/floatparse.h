/* MIT. Module-private C-locale decimal/hex binary64 parser, no heap. */
#ifndef CJ_FLOATPARSE_H
#define CJ_FLOATPARSE_H
#ifdef __cplusplus
extern "C" {
#endif
double cj_strtod(const char *text, char **endptr);
#ifdef __cplusplus
}
#endif
#endif
