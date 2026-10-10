/* SPDX-License-Identifier: MIT */
#ifndef CF_PCM_H
#define CF_PCM_H
#include <stddef.h>
#include <stdint.h>
#define CF_PCM_MAX_BYTES 1048576u
/* 0 success, -1 length/null/bounds, -2 nonzero copy with overlapping buffers. */
int cf_pcm_copy(uint8_t *dst, size_t dst_len, const uint8_t *src, size_t src_len,
                size_t dst_offset, size_t src_offset, size_t count);
#endif
