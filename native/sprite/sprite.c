/* SPDX-License-Identifier: MIT */
#include "sprite.h"

static unsigned u16(const uint8_t *p) { return (unsigned)p[0] | ((unsigned)p[1] << 8); }
static uint32_t u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static int s16(const uint8_t *p) {
    unsigned v = u16(p);
    return v < 32768u ? (int)v : (int)v - 65536;
}
static int overlaps(const uint8_t *a, size_t an, const uint8_t *b, size_t bn) {
    if (!an || !bn) return 0;
    uintptr_t av = (uintptr_t)a, bv = (uintptr_t)b;
    return av <= bv ? bv - av < an : av - bv < bn;
}
static unsigned reverse8(unsigned v) {
    v = ((v & 0x55u) << 1) | ((v >> 1) & 0x55u);
    v = ((v & 0x33u) << 2) | ((v >> 2) & 0x33u);
    return ((v << 4) | (v >> 4)) & 255u;
}
/* Return 1..8 valid consecutive source bits, right-aligned. No padding read. */
static unsigned bits(const uint8_t *row, unsigned x, unsigned count) {
    unsigned shift = x & 7u;
    unsigned value = (unsigned)row[x >> 3] << 8;
    if (shift + count > 8) value |= row[(x >> 3) + 1];
    return (value >> (16 - shift - count)) & ((1u << count) - 1u);
}

int cf_compose(uint8_t *target, size_t target_len,
    const uint8_t *background, size_t background_len,
    const uint8_t *atlas, size_t atlas_len,
    const uint8_t *descriptors, size_t descriptors_len,
    const uint8_t *commands, size_t commands_len) {
    if (!target || !background || target_len != CF_TARGET_BYTES || background_len != CF_BACKGROUND_BYTES ||
        (!atlas && atlas_len) || (!descriptors && descriptors_len) || (!commands && commands_len) ||
        descriptors_len % 12 || descriptors_len / 12 > CF_MAX_RECORDS ||
        commands_len % 8 || commands_len / 8 > CF_MAX_RECORDS) return -1;
    if (overlaps(target, target_len, background, background_len) ||
        overlaps(target, target_len, atlas, atlas_len) ||
        overlaps(target, target_len, descriptors, descriptors_len) ||
        overlaps(target, target_len, commands, commands_len)) return -2;
    /* Validate every record before the first write. Subtraction avoids offset overflow. */
    for (size_t at = 0; at < descriptors_len; at += 12) {
        const uint8_t *d = descriptors + at;
        unsigned w = u16(d), h = u16(d + 2);
        size_t pixels = u32(d + 4), mask = u32(d + 8);
        if (!w || w > 400 || !h || h > 240) return -3;
        size_t plane = (size_t)((w + 7) / 8) * h;
        if (pixels > atlas_len || plane > atlas_len - pixels ||
            mask > atlas_len || plane > atlas_len - mask) return -3;
    }
    for (size_t at = 0; at < commands_len; at += 8) {
        const uint8_t *c = commands + at;
        if (u16(c) >= descriptors_len / 12 || (u16(c + 6) & ~3u)) return -4;
    }
    for (unsigned y = 0; y < 240; ++y)
        for (unsigned x = 0; x < 50; ++x) target[y * 52 + x] = background[y * 50 + x];
    for (size_t at = 0; at < commands_len; at += 8) {
        const uint8_t *c = commands + at;
        const uint8_t *d = descriptors + (size_t)u16(c) * 12;
        int w = (int)u16(d), h = (int)u16(d + 2);
        int left = s16(c + 2), top = s16(c + 4);
        unsigned flags = u16(c + 6), stride = ((unsigned)w + 7) / 8;
        int x0 = left < 0 ? 0 : left, y0 = top < 0 ? 0 : top;
        int x1 = left + w > 400 ? 400 : left + w;
        int y1 = top + h > 240 ? 240 : top + h;
        if (x0 >= x1 || y0 >= y1) continue;
        const uint8_t *pixels = atlas + u32(d + 4), *masks = atlas + u32(d + 8);
        for (int y = y0; y < y1; ++y) {
            unsigned sy = (unsigned)(y - top);
            if (flags & 2) sy = (unsigned)h - 1 - sy;
            const uint8_t *pr = pixels + sy * stride, *mr = masks + sy * stride;
            uint8_t *out = target + (unsigned)y * 52;
            for (int x = x0; x < x1;) {
                unsigned count = 8u - ((unsigned)x & 7u);
                if (count > (unsigned)(x1 - x)) count = (unsigned)(x1 - x);
                unsigned sx = (unsigned)(x - left);
                if (flags & 1) sx = (unsigned)w - sx - count;
                unsigned p = bits(pr, sx, count), m = bits(mr, sx, count);
                if (flags & 1) { p = reverse8(p) >> (8 - count); m = reverse8(m) >> (8 - count); }
                unsigned shift = 8 - ((unsigned)x & 7u) - count;
                p <<= shift; m <<= shift;
                unsigned index = (unsigned)x >> 3;
                out[index] = (uint8_t)((out[index] & ~m) | (p & m));
                x += (int)count;
            }
        }
    }
    return 0;
}
