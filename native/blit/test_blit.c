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
    printf("PASS checks=%lu exhaustive_byte_values=256 patterned_frames=1 invalid_sizes_nulls_overlap=12 guards_and_padding=passed\n", checks);
    return 0;
}
