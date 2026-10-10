/* MIT. Exact binary64 decimal conversion without newlib's hidden heap.
 * fast_float v8.0.2, 50a80a73ab2ab256ba1c3bf86923ddd8b4202bc7, MIT option.
 * Hex parsing uses bounded integer accumulation and IEEE rounding below.
 * This is a module-private C-locale seam, not a general libc replacement. */
#include "floatparse.h"
#include "fast_float/fast_float.h"
#include <cstring>
#include <cstdint>
static int hex_digit(char c) {
    if (c >= '0' && c <= '9') return c-'0';
    if (c >= 'a' && c <= 'f') return c-'a'+10;
    if (c >= 'A' && c <= 'F') return c-'A'+10;
    return -1;
}
static uint64_t rounded(uint64_t x, int shift, bool sticky) {
    if (shift <= 0) return x << -shift;
    if (shift > 64) return 0;
    uint64_t half=UINT64_C(1) << (shift-1);
    uint64_t q=shift==64 ? 0 : x>>shift;
    uint64_t rem=shift==64 ? x : x & ((UINT64_C(1)<<shift)-1);
    return q + (rem>half || (rem==half && (sticky || (q&1))));
}
/* IEEE binary64 round-to-nearest/even, including subnormal single rounding.
 * Numeric tokens are source-bounded. Saturate exponents before integer overflow.
 * Avoid SDK ldexp, whose RP2350 implementation flushes subnormal results. */
static double parse_hex(const char *p, const char *original, char **endptr) {
    (void)original;
    bool neg=*p=='-'; if (*p=='-' || *p=='+') ++p;
    const char *zero=p; p+=2; uint64_t sig=0; int bits=0, dropped=0, fractional=0;
    bool dot=false, any=false, sticky=false;
    for (;;) {
        int d=hex_digit(*p);
        if (d>=0) {
            any=true; if(dot) ++fractional;
            if(bits<=60) { sig=(sig<<4)|(unsigned)d; if(bits) bits+=4; else { unsigned t=d; while(t) {++bits;t>>=1;} } }
            else { ++dropped; sticky=sticky || d!=0; }
            ++p;
        } else if (*p=='.' && !dot) { dot=true; ++p; }
        else break;
    }
    if(!any) { if(endptr) *endptr=const_cast<char *>(zero+1); return neg ? -0.0 : 0.0; }
    int e=4*(dropped-fractional);
    if(*p=='p' || *p=='P') {
        const char *mark=p++; bool minus=*p=='-'; if(*p=='+' || *p=='-') ++p;
        if(*p<'0' || *p>'9') p=mark;
        else { int n=0; while(*p>='0' && *p<='9') { if(n<100000) n=n*10+(*p-'0'); ++p; } e+=minus ? -n : n; }
    }
    if(endptr) *endptr=const_cast<char *>(p);
    uint64_t out=0; int exponent=bits-1+e;
    if(!sig) out=0;
    else if(exponent>1023) out=UINT64_C(0x7ff0000000000000);
    else if(exponent < -1022) out=rounded(sig,-(e+1074),sticky);
    else {
        uint64_t mant=rounded(sig,bits-53,sticky);
        if(mant==UINT64_C(0x20000000000000)) { mant>>=1; ++exponent; }
        out=exponent>1023 ? UINT64_C(0x7ff0000000000000) : ((uint64_t)(exponent+1023)<<52) | (mant & UINT64_C(0xfffffffffffff));
    }
    out |= (uint64_t)neg<<63; double value; std::memcpy(&value,&out,sizeof value); return value;
}
extern "C" double cj_strtod(const char *text, char **endptr) {
    const char *p = text;
    while (*p == ' ' || (*p >= '\t' && *p <= '\r')) ++p;
    if (*p == '+') {
        ++p;
        if (*p == '+' || *p == '-') {
            if (endptr) *endptr = const_cast<char *>(text);
            return 0;
        }
    }
    double value = 0;
    const char *q=*p=='-' ? p+1 : p;
    if(q[0]=='0' && (q[1]=='x' || q[1]=='X')) return parse_hex(p,text,endptr);
    auto result = fast_float::from_chars(p, p + std::strlen(p), value);
    if (result.ec == std::errc::invalid_argument) {
        if (endptr) *endptr = const_cast<char *>(text);
        return 0;
    }
    if (endptr) *endptr = const_cast<char *>(result.ptr);
    return value;
}
