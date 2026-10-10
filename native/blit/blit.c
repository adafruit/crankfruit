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
