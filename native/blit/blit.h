/* SPDX-License-Identifier: MIT */
#ifndef CRANKFRUIT_BLIT_H
#define CRANKFRUIT_BLIT_H
#include <stddef.h>
#include <stdint.h>
enum { CF_SOURCE_BYTES = 12480, CF_DEST_BYTES = 38400, CF_COPIED_BYTES = 12000 };
/* Returns 12000 on success, -1 for size/null, -2 for overlapping buffers.
 * Buffers are borrowed only for this synchronous call. No allocation or IO. */
int cf_blit(const uint8_t *src, size_t src_len, uint8_t *dst, size_t dst_len);
/* 1.6x nearest-neighbour: the 400x240 frame becomes 640x384 at rows 48..431 of
 * the 640x480 LSB-first scanout; rows outside are written black (0). Output
 * pixel (x, y) shows source pixel (x*5/8, (y-48)*5/8). Returns 38400 on success,
 * -1 for size/null, -2 for overlap. Writes the whole destination. */
int cf_blit16(const uint8_t *src, size_t src_len, uint8_t *dst, size_t dst_len);
/* 2-bit greyscale scanout (640x480, 4 pixels per byte, pixel x at bits 2*(x%4),
 * level 0 black .. `white` (2 = Playdate-like ~50% grey, 3 = bright ~75%)).
 * mode 0: 1x centred at (120,120); mode 1: 1.6x sharp (same mapping as
 * cf_blit16); mode 2: 1.6x smooth, each output pixel's level is
 * round(white * covered area / 25) in 1/8-source-pixel units. Writes the whole
 * destination. Returns 76800, -1 for size/null/mode/white, -2 for overlap. */
enum { CF_DEST2_BYTES = 76800 };
int cf_blit2(const uint8_t *src, size_t src_len, uint8_t *dst, size_t dst_len, int mode, int white);
#endif
