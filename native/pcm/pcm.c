/* SPDX-License-Identifier: MIT */
#include "pcm.h"
int cf_pcm_copy(uint8_t *dst, size_t dst_len, const uint8_t *src, size_t src_len,
                size_t dst_offset, size_t src_offset, size_t count) {
    if ((!dst && dst_len) || (!src && src_len) ||
        dst_len > CF_PCM_MAX_BYTES || src_len > CF_PCM_MAX_BYTES ||
        dst_offset > dst_len || src_offset > src_len ||
        count > dst_len - dst_offset || count > src_len - src_offset) return -1;
    if (!count) return 0;
    uintptr_t d = (uintptr_t)dst, s = (uintptr_t)src;
    /* Reject aliasing across the full supplied spans, even disjoint subranges. */
    if (d <= s ? s - d < dst_len : d - s < src_len) return -2;
    for (size_t i = 0; i < count; ++i) dst[dst_offset + i] = src[src_offset + i];
    return 0;
}
