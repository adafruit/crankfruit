/* SPDX-License-Identifier: MIT */
#include "blit.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned long checks;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); exit(1); } } while (0)
static uint8_t reference(uint8_t v) {
    uint8_t r = 0;
    for (unsigned bit = 0; bit < 8; ++bit) r |= ((v >> bit) & 1u) << (7u - bit);
    return r;
}
int main(void) {
    uint8_t source[CF_SOURCE_BYTES + 2], before[CF_SOURCE_BYTES + 2];
    uint8_t output[CF_DEST_BYTES + 2];
    uint8_t *src = source + 1, *dst = output + 1; /* deliberately unaligned */
    for (unsigned value = 0; value < 257; ++value) {
        memset(source, 0x97, sizeof source);
        for (unsigned y = 0; y < 240; ++y)
            for (unsigned x = 0; x < 50; ++x)
                src[y * 52 + x] = value < 256 ? value : (y * 31 + x * 17) & 255;
        memcpy(before, source, sizeof source);
        memset(output, 0xa5, sizeof output);
        CHECK(cf_blit(src, CF_SOURCE_BYTES, dst, CF_DEST_BYTES) == CF_COPIED_BYTES);
        CHECK(memcmp(before, source, sizeof source) == 0);
        CHECK(output[0] == 0xa5 && output[sizeof output - 1] == 0xa5);
        for (unsigned y = 0; y < 480; ++y) {
            for (unsigned x = 0; x < 80; ++x) {
                uint8_t expected = 0xa5;
                if (y >= 120 && y < 360 && x >= 15 && x < 65)
                    expected = reference(src[(y - 120) * 52 + x - 15]);
                CHECK(dst[y * 80 + x] == expected);
            }
        }
    }
    memset(output, 0xa5, sizeof output);
    CHECK(cf_blit(src, 0, dst, CF_DEST_BYTES) == -1);
    CHECK(cf_blit(src, CF_SOURCE_BYTES - 1, dst, CF_DEST_BYTES) == -1);
    CHECK(cf_blit(src, CF_SOURCE_BYTES + 1, dst, CF_DEST_BYTES) == -1);
    CHECK(cf_blit(src, CF_SOURCE_BYTES, dst, CF_DEST_BYTES - 1) == -1);
    CHECK(cf_blit(src, CF_SOURCE_BYTES, dst, CF_DEST_BYTES + 1) == -1);
    CHECK(cf_blit(NULL, CF_SOURCE_BYTES, dst, CF_DEST_BYTES) == -1);
    CHECK(cf_blit(src, CF_SOURCE_BYTES, NULL, CF_DEST_BYTES) == -1);
    for (size_t i = 0; i < sizeof output; ++i) CHECK(output[i] == 0xa5);
    uint8_t joined[CF_SOURCE_BYTES + CF_DEST_BYTES + 1];
    memset(joined, 0, sizeof joined);
    CHECK(cf_blit(joined, CF_SOURCE_BYTES, joined, CF_DEST_BYTES) == -2);
    CHECK(cf_blit(joined, CF_SOURCE_BYTES, joined + CF_SOURCE_BYTES - 1, CF_DEST_BYTES) == -2);
    CHECK(cf_blit(joined + CF_DEST_BYTES - 1, CF_SOURCE_BYTES, joined, CF_DEST_BYTES) == -2);
    CHECK(cf_blit(joined, CF_SOURCE_BYTES, joined + CF_SOURCE_BYTES, CF_DEST_BYTES) == CF_COPIED_BYTES);
    CHECK(cf_blit(joined + CF_DEST_BYTES, CF_SOURCE_BYTES, joined, CF_DEST_BYTES) == CF_COPIED_BYTES);
    /* cf_blit16: per-pixel independent reference over every byte value, a
     * patterned frame and seeded random frames; whole destination is written. */
    unsigned long seed = 12345;
    for (unsigned frame = 0; frame < 256 + 1 + 40; ++frame) {
        memset(source, 0x97, sizeof source);
        for (unsigned y = 0; y < 240; ++y)
            for (unsigned x = 0; x < 50; ++x) {
                seed = seed * 1103515245ul + 12345ul;
                src[y * 52 + x] = frame < 256 ? (uint8_t)frame
                                : frame == 256 ? (uint8_t)((y * 31 + x * 17) & 255)
                                : (uint8_t)(seed >> 16);
            }
        memcpy(before, source, sizeof source);
        memset(output, 0xa5, sizeof output);
        CHECK(cf_blit16(src, CF_SOURCE_BYTES, dst, CF_DEST_BYTES) == CF_DEST_BYTES);
        CHECK(memcmp(before, source, sizeof source) == 0);
        CHECK(output[0] == 0xa5 && output[sizeof output - 1] == 0xa5);
        for (unsigned y = 0; y < 480; ++y)
            for (unsigned x = 0; x < 640; ++x) {
                unsigned expected = 0;
                if (y >= 48 && y < 432) {
                    unsigned sx = x * 5 / 8, sy = (y - 48) * 5 / 8;
                    expected = (src[sy * 52 + sx / 8] >> (7 - sx % 8)) & 1u;
                }
                CHECK(((dst[y * 80 + x / 8] >> (x % 8)) & 1u) == expected);
            }
    }
    memset(output, 0xa5, sizeof output);
    CHECK(cf_blit16(src, CF_SOURCE_BYTES - 1, dst, CF_DEST_BYTES) == -1);
    CHECK(cf_blit16(src, CF_SOURCE_BYTES, dst, CF_DEST_BYTES + 1) == -1);
    CHECK(cf_blit16(NULL, CF_SOURCE_BYTES, dst, CF_DEST_BYTES) == -1);
    CHECK(cf_blit16(src, CF_SOURCE_BYTES, NULL, CF_DEST_BYTES) == -1);
    for (size_t i = 0; i < sizeof output; ++i) CHECK(output[i] == 0xa5);
    CHECK(cf_blit16(joined, CF_SOURCE_BYTES, joined + CF_SOURCE_BYTES - 1, CF_DEST_BYTES) == -2);
    CHECK(cf_blit16(joined + CF_DEST_BYTES - 1, CF_SOURCE_BYTES, joined, CF_DEST_BYTES) == -2);
    CHECK(cf_blit16(joined, CF_SOURCE_BYTES, joined + CF_SOURCE_BYTES, CF_DEST_BYTES) == CF_DEST_BYTES);
    /* cf_blit2: independent per-pixel reference for all three modes (same
     * formulas as the desktop host's --board-scale preview). */
    static uint8_t output2[CF_DEST2_BYTES + 2];
    uint8_t *dst2 = output2 + 1;
    unsigned frames2 = 0;
    for (unsigned frame = 0; frame < 32 + 1 + 12; ++frame) {
        for (unsigned y = 0; y < 240; ++y)
            for (unsigned x = 0; x < 52; ++x) {
                seed = seed * 1103515245ul + 12345ul;
                src[y * 52 + x] = frame < 32 ? (uint8_t)(frame * 8 + 1)
                                : frame == 32 ? (uint8_t)((y * 31 + x * 17) & 255)
                                : (uint8_t)(seed >> 16);
            }
        memcpy(before, source, sizeof source);
        for (int combo = 0; combo < 6; ++combo) {
            int mode = combo % 3, white = combo < 3 ? 3 : 2;
            memset(output2, 0xa5, sizeof output2);
            CHECK(cf_blit2(src, CF_SOURCE_BYTES, dst2, CF_DEST2_BYTES, mode, white) == CF_DEST2_BYTES);
            CHECK(memcmp(before, source, sizeof source) == 0);
            CHECK(output2[0] == 0xa5 && output2[sizeof output2 - 1] == 0xa5);
            for (unsigned y = 0; y < 480; ++y)
                for (unsigned x = 0; x < 640; ++x) {
                    unsigned expected = 0;
                    if (mode == 0) {
                        if (y >= 120 && y < 360 && x >= 120 && x < 520) {
                            unsigned sx = x - 120, sy = y - 120;
                            expected = (src[sy * 52 + sx / 8] >> (7 - sx % 8)) & 1u ? (unsigned)white : 0u;
                        }
                    } else if (y >= 48 && y < 432) {
                        unsigned ox = x, oy = y - 48;
                        if (mode == 1) {
                            unsigned sx = ox * 5 / 8, sy = oy * 5 / 8;
                            expected = (src[sy * 52 + sx / 8] >> (7 - sx % 8)) & 1u ? (unsigned)white : 0u;
                        } else {
                            unsigned x0 = ox * 5, x1 = x0 + 5, y0 = oy * 5, y1 = y0 + 5, covered = 0;
                            for (unsigned sy = y0 / 8; sy * 8 < y1 && sy < 240; ++sy)
                                for (unsigned sx = x0 / 8; sx * 8 < x1 && sx < 400; ++sx) {
                                    if (!((src[sy * 52 + sx / 8] >> (7 - sx % 8)) & 1u)) continue;
                                    unsigned a0 = x0 > sx * 8 ? x0 : sx * 8, a1 = x1 < sx * 8 + 8 ? x1 : sx * 8 + 8;
                                    unsigned b0 = y0 > sy * 8 ? y0 : sy * 8, b1 = y1 < sy * 8 + 8 ? y1 : sy * 8 + 8;
                                    covered += (a1 - a0) * (b1 - b0);
                                }
                            expected = (covered * (unsigned)white * 2 + 25) / 50;
                        }
                    }
                    CHECK(((dst2[y * 160 + x / 4] >> (2 * (x % 4))) & 3u) == expected);
                }
        }
        ++frames2;
    }
    CHECK(cf_blit2(src, CF_SOURCE_BYTES, dst2, CF_DEST2_BYTES, 3, 3) == -1);
    CHECK(cf_blit2(src, CF_SOURCE_BYTES, dst2, CF_DEST2_BYTES, -1, 3) == -1);
    CHECK(cf_blit2(src, CF_SOURCE_BYTES, dst2, CF_DEST2_BYTES, 0, 1) == -1);
    CHECK(cf_blit2(src, CF_SOURCE_BYTES, dst2, CF_DEST2_BYTES, 0, 4) == -1);
    CHECK(cf_blit2(src, CF_SOURCE_BYTES, dst2, CF_DEST_BYTES, 0, 3) == -1);
    CHECK(cf_blit2(NULL, CF_SOURCE_BYTES, dst2, CF_DEST2_BYTES, 0, 3) == -1);
    static uint8_t joined2[CF_SOURCE_BYTES + CF_DEST2_BYTES + 1];
    CHECK(cf_blit2(joined2, CF_SOURCE_BYTES, joined2 + CF_SOURCE_BYTES - 1, CF_DEST2_BYTES, 2, 3) == -2);
    CHECK(cf_blit2(joined2, CF_SOURCE_BYTES, joined2 + CF_SOURCE_BYTES, CF_DEST2_BYTES, 2, 2) == CF_DEST2_BYTES);
    /* cf_frame_changed: identical, first/last/middle byte differences, copy-back. */
    {
        static uint8_t a[CF_SOURCE_BYTES + 2], b[CF_SOURCE_BYTES + 2];
        uint8_t *fa = a + 1, *fb = b + 1;
        for (unsigned i = 0; i < CF_SOURCE_BYTES; ++i) fa[i] = fb[i] = (uint8_t)(i * 7);
        CHECK(cf_frame_changed(fa, CF_SOURCE_BYTES, fb, CF_SOURCE_BYTES) == 0);
        unsigned positions[] = {0, 1, 6239, CF_SOURCE_BYTES - 1};
        for (unsigned p = 0; p < 4; ++p) {
            fa[positions[p]] ^= 0x10;
            CHECK(cf_frame_changed(fa, CF_SOURCE_BYTES, fb, CF_SOURCE_BYTES) == 1);
            CHECK(memcmp(fa, fb, CF_SOURCE_BYTES) == 0);            /* prev now equals src */
            CHECK(cf_frame_changed(fa, CF_SOURCE_BYTES, fb, CF_SOURCE_BYTES) == 0);
        }
        /* aligned buffers take the word path */
        static _Alignas(4) uint8_t wa[CF_SOURCE_BYTES], wb[CF_SOURCE_BYTES];
        for (unsigned i = 0; i < CF_SOURCE_BYTES; ++i) wa[i] = wb[i] = (uint8_t)(i * 13);
        CHECK(cf_frame_changed(wa, CF_SOURCE_BYTES, wb, CF_SOURCE_BYTES) == 0);
        for (unsigned p = 0; p < 4; ++p) {
            wa[positions[p]] ^= 0x22;
            CHECK(cf_frame_changed(wa, CF_SOURCE_BYTES, wb, CF_SOURCE_BYTES) == 1);
            CHECK(memcmp(wa, wb, CF_SOURCE_BYTES) == 0);
            CHECK(cf_frame_changed(wa, CF_SOURCE_BYTES, wb, CF_SOURCE_BYTES) == 0);
        }
        CHECK(cf_frame_changed(fa, CF_SOURCE_BYTES - 1, fb, CF_SOURCE_BYTES) == -1);
        CHECK(cf_frame_changed(NULL, CF_SOURCE_BYTES, fb, CF_SOURCE_BYTES) == -1);
        CHECK(cf_frame_changed(fa, CF_SOURCE_BYTES, fa + 1, CF_SOURCE_BYTES) == -2);
    }
    printf("PASS checks=%lu exhaustive_byte_values=256 patterned_frames=1 invalid_sizes_nulls_overlap=12 guards_and_padding=passed; blit16 frames=297 per_pixel_reference invalid=7; blit2 frames=%u modes=3 whites=2 per_pixel_reference invalid=8; frame_changed positions=4 aligned_and_unaligned invalid=3\n", checks, frames2);
    return 0;
}
