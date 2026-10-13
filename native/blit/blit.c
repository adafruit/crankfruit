/* SPDX-License-Identifier: MIT */
#include "blit.h"

static uint8_t reverse_byte(uint8_t value) {
    unsigned v = value;
    v = ((v & 0x55u) << 1) | ((v >> 1) & 0x55u);
    v = ((v & 0x33u) << 2) | ((v >> 2) & 0x33u);
    return (uint8_t)((v << 4) | (v >> 4));
}

int cf_blit(const uint8_t *src, size_t src_len, uint8_t *dst, size_t dst_len) {
    if (!src || !dst || src_len != CF_SOURCE_BYTES || dst_len != CF_DEST_BYTES) return -1;
    uintptr_t s = (uintptr_t)src, d = (uintptr_t)dst;
    /* Subtract ordered addresses instead of adding lengths to pointers. */
    if (s <= d ? d - s < src_len : s - d < dst_len) return -2;
    for (size_t y = 0; y < 240; ++y) {
        const uint8_t *row = src + y * 52;
        uint8_t *out = dst + 9615 + y * 80;
        for (size_t x = 0; x < 50; ++x) out[x] = reverse_byte(row[x]);
    }
    return CF_COPIED_BYTES;
}

/* Five source pixels (bit 4 = leftmost, MSB-first order) -> one LSB-first output
 * byte of eight pixels. Output pixel j shows source pixel j*5/8 of the group. */
static uint8_t widen5(unsigned group) {
    unsigned out = 0;
    for (unsigned j = 0; j < 8; ++j)
        if (group & (16u >> ((j * 5u) >> 3))) out |= 1u << j;
    return (uint8_t)out;
}

int cf_blit16(const uint8_t *src, size_t src_len, uint8_t *dst, size_t dst_len) {
    if (!src || !dst || src_len != CF_SOURCE_BYTES || dst_len != CF_DEST_BYTES) return -1;
    uintptr_t s = (uintptr_t)src, d = (uintptr_t)dst;
    if (s <= d ? d - s < src_len : s - d < dst_len) return -2;
    uint8_t table[32];
    for (unsigned g = 0; g < 32; ++g) table[g] = widen5(g);
    for (size_t i = 0; i < 48 * 80; ++i) dst[i] = 0;               /* top border */
    for (size_t i = 432 * 80; i < CF_DEST_BYTES; ++i) dst[i] = 0;  /* bottom border */
    size_t previous = (size_t)-1;
    for (size_t y = 0; y < 384; ++y) {
        size_t sy = y * 5 / 8;
        uint8_t *out = dst + (48 + y) * 80;
        if (sy == previous) {                                       /* repeated row */
            const uint8_t *above = out - 80;
            for (size_t x = 0; x < 80; ++x) out[x] = above[x];
            continue;
        }
        previous = sy;
        const uint8_t *row = src + sy * 52;
        for (size_t k = 0; k < 80; ++k) {
            size_t bit = k * 5, byte = bit >> 3;
            /* 16-bit window; byte+1 stays inside the 52-byte stride (max index 50). */
            unsigned window = ((unsigned)row[byte] << 8) | row[byte + 1];
            out[k] = table[(window >> (11 - (bit & 7))) & 31u];
        }
    }
    return CF_DEST_BYTES;
}

/* Five source pixels starting at source bit `bit` of an MSB-first row (bit 4 =
 * leftmost). Reads row[byte+1], which stays inside the 52-byte stride. */
static unsigned group5(const uint8_t *row, size_t k) {
    size_t bit = k * 5, byte = bit >> 3;
    unsigned window = ((unsigned)row[byte] << 8) | row[byte + 1];
    return (window >> (11 - (bit & 7))) & 31u;
}

/* Horizontal coverage (0..5 eighths) of output pixel j (0..7) by a 5-pixel group. */
static unsigned cover5(unsigned group, unsigned j) {
    unsigned lo = j * 5, hi = lo + 5, total = 0;
    for (unsigned i = 0; i < 5; ++i) {
        if (!(group & (16u >> i))) continue;
        unsigned a = lo > i * 8 ? lo : i * 8, b = hi < i * 8 + 8 ? hi : i * 8 + 8;
        if (b > a) total += b - a;
    }
    return total;
}

int cf_blit2(const uint8_t *src, size_t src_len, uint8_t *dst, size_t dst_len, int mode, int white) {
    if (!src || !dst || src_len != CF_SOURCE_BYTES || dst_len != CF_DEST2_BYTES || mode < 0 || mode > 2 ||
        white < 2 || white > 3) return -1;
    unsigned wl = (unsigned)white; /* white level */
    uintptr_t s = (uintptr_t)src, d = (uintptr_t)dst;
    if (s <= d ? d - s < src_len : s - d < dst_len) return -2;
    if (mode == 0) {
        uint16_t table[256]; /* one source byte (MSB-first) -> 8 two-bit pixels */
        for (unsigned v = 0; v < 256; ++v) {
            unsigned out = 0;
            for (unsigned j = 0; j < 8; ++j) if (v & (128u >> j)) out |= wl << (2 * j);
            table[v] = (uint16_t)out;
        }
        for (size_t i = 0; i < 120 * 160; ++i) dst[i] = 0;               /* top border */
        for (size_t i = 360 * 160; i < CF_DEST2_BYTES; ++i) dst[i] = 0;  /* bottom border */
        for (size_t y = 0; y < 240; ++y) {
            const uint8_t *row = src + y * 52;
            uint8_t *line = dst + (120 + y) * 160;
            for (size_t x = 0; x < 30; ++x) { line[x] = 0; line[130 + x] = 0; } /* side borders */
            uint8_t *out = line + 30;
            for (size_t x = 0; x < 50; ++x) {
                unsigned w = table[row[x]];
                out[2 * x] = (uint8_t)w; out[2 * x + 1] = (uint8_t)(w >> 8);
            }
        }
        return CF_DEST2_BYTES;
    }
    for (size_t i = 0; i < 48 * 160; ++i) dst[i] = 0;                    /* top border */
    for (size_t i = 432 * 160; i < CF_DEST2_BYTES; ++i) dst[i] = 0;      /* bottom border */
    if (mode == 1) {
        uint16_t table[32]; /* sharp: same mapping as cf_blit16, white = 3 */
        for (unsigned g = 0; g < 32; ++g) {
            unsigned out = 0;
            for (unsigned j = 0; j < 8; ++j) if (g & (16u >> ((j * 5u) >> 3))) out |= wl << (2 * j);
            table[g] = (uint16_t)out;
        }
        size_t previous = (size_t)-1;
        for (size_t y = 0; y < 384; ++y) {
            size_t sy = y * 5 / 8;
            uint8_t *out = dst + (48 + y) * 160;
            if (sy == previous) {                                       /* repeated row */
                const uint8_t *above = out - 160;
                for (size_t x = 0; x < 160; ++x) out[x] = above[x];
                continue;
            }
            previous = sy;
            const uint8_t *row = src + sy * 52;
            for (size_t k = 0; k < 80; ++k) {
                unsigned w = table[group5(row, k)];
                out[2 * k] = (uint8_t)w; out[2 * k + 1] = (uint8_t)(w >> 8);
            }
        }
        return CF_DEST2_BYTES;
    }
    /* Smooth. Output row y (0..383) spans source eighths [5y, 5y+5). The span
     * pattern repeats every 8 output rows (a "phase"); rows of one phase blend
     * source rows (y*5/8, +1) with the same weights (wa, wb), wa + wb = 5.
     * Output pixels 0..3 of a group only touch source pixels 0..2 (eighths
     * 0..20) and pixels 4..7 only touch source pixels 2..4 (eighths 20..40), so
     * each half is a 64-entry table indexed by 3 bits from each source row. */
    uint8_t level[26], cover[32][8], lo[64], hi[64];
    for (unsigned c = 0; c < 26; ++c) level[c] = (uint8_t)((c * wl * 2 + 25) / 50); /* round(white*c/25) */
    for (unsigned g = 0; g < 32; ++g) for (unsigned j = 0; j < 8; ++j) cover[g][j] = (uint8_t)cover5(g, j);
    for (unsigned phase = 0; phase < 8; ++phase) {
        unsigned start = phase * 5, wa = 8 - (start & 7);
        if (wa > 5) wa = 5;
        unsigned wb = 5 - wa;
        for (unsigned a = 0; a < 8; ++a) for (unsigned b = 0; b < 8; ++b) {
            unsigned left = 0, right = 0, al = a << 2, bl = b << 2; /* bits 4..2 = source pixels 0..2 */
            for (unsigned j = 0; j < 4; ++j) {
                left |= (unsigned)level[wa * cover[al][j] + wb * cover[bl][j]] << (2 * j);
                right |= (unsigned)level[wa * cover[a][j + 4] + wb * cover[b][j + 4]] << (2 * j);
            }
            lo[(a << 3) | b] = (uint8_t)left;
            hi[(a << 3) | b] = (uint8_t)right;
        }
        for (size_t y = phase; y < 384; y += 8) {
            size_t sy = y * 5 / 8;
            const uint8_t *ra = src + sy * 52, *rb = src + (sy + 1 < 240 ? sy + 1 : sy) * 52;
            uint8_t *out = dst + (48 + y) * 160;
            for (size_t k = 0; k < 80; ++k) {
                unsigned ga = group5(ra, k), gb = wb ? group5(rb, k) : 0u;
                out[2 * k] = lo[((ga >> 2) << 3) | (gb >> 2)];
                out[2 * k + 1] = hi[((ga & 7u) << 3) | (gb & 7u)];
            }
        }
    }
    return CF_DEST2_BYTES;
}

int cf_frame_changed(const uint8_t *src, size_t src_len, uint8_t *prev, size_t prev_len) {
    if (!src || !prev || src_len != CF_SOURCE_BYTES || prev_len != CF_SOURCE_BYTES) return -1;
    uintptr_t s = (uintptr_t)src, d = (uintptr_t)prev;
    if (s <= d ? d - s < src_len : s - d < prev_len) return -2;
    size_t i = 0;
    if (((s | d) & 3u) == 0) {
        /* Word path: Python buffers on the board sit in slower PSRAM, so fewer,
         * wider accesses matter. may_alias keeps the byte views well-defined. */
        typedef uint32_t __attribute__((__may_alias__)) word_t;
        const word_t *sw = (const word_t *)(const void *)src;
        word_t *pw = (word_t *)(void *)prev;
        size_t w = 0, words = CF_SOURCE_BYTES / 4;
        while (w < words && sw[w] == pw[w]) ++w;
        if (w == words) return 0;
        for (; w < words; ++w) pw[w] = sw[w];
        return 1;
    }
    while (i < CF_SOURCE_BYTES && src[i] == prev[i]) ++i;
    if (i == CF_SOURCE_BYTES) return 0;
    for (; i < CF_SOURCE_BYTES; ++i) prev[i] = src[i];  /* bytes before i already match */
    return 1;
}
