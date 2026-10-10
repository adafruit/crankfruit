/* SPDX-License-Identifier: MIT */
#ifndef CRANKFRUIT_BLIT_H
#define CRANKFRUIT_BLIT_H
#include <stddef.h>
#include <stdint.h>
enum { CF_SOURCE_BYTES = 12480, CF_DEST_BYTES = 38400, CF_COPIED_BYTES = 12000 };
/* Returns 12000 on success, -1 for size/null, -2 for overlapping buffers.
 * Buffers are borrowed only for this synchronous call. No allocation or IO. */
int cf_blit(const uint8_t *src, size_t src_len, uint8_t *dst, size_t dst_len);
#endif
