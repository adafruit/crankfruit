/* SPDX-License-Identifier: MIT */
#ifndef CF_SPRITE_H
#define CF_SPRITE_H
#include <stddef.h>
#include <stdint.h>
#define CF_TARGET_BYTES 12480u
#define CF_BACKGROUND_BYTES 12000u
#define CF_MAX_RECORDS 256u
/* 0 success; -1 sizes/null; -2 destination overlap; -3 descriptor; -4 command. */
int cf_compose(uint8_t *target, size_t target_len,
    const uint8_t *background, size_t background_len,
    const uint8_t *atlas, size_t atlas_len,
    const uint8_t *descriptors, size_t descriptors_len,
    const uint8_t *commands, size_t commands_len);
#endif
