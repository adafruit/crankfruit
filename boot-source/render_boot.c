/* Offline source-complete startup renderer using only the public engine API.
 * Copyright (c) 2026 Crankfruit contributors. SPDX-License-Identifier: MIT.
 * This is host tooling, not code to execute on the Fruit Jam during startup.
 */
#include "crankjam.h"
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BOOT_FRAMES 75u
#define BOOT_RATE 30u
#define AUDIO_RATE 32000u
#define PADDED_STRIDE 52u
#define PADDED_BYTES (PADDED_STRIDE * CJ_HEIGHT)
#define SOURCE_LIMIT 131072u
#define LUA_HEAP 262144u

static FILE *new_output(const char *directory, const char *name) {
    size_t n = strlen(directory) + strlen(name) + 2u;
    char *path = malloc(n);
    if (!path) return NULL;
    (void)snprintf(path, n, "%s/%s", directory, name);
    /* C11 exclusive-create mode refuses to overwrite a previous candidate. */
    FILE *file = fopen(path, "wbx");
    if (!file) fprintf(stderr, "cannot create %s: %s\n", name, strerror(errno));
    free(path);
    return file;
}

static int write_all(FILE *file, const void *bytes, size_t length) {
    return fwrite(bytes, 1, length, file) == length;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: render-boot SOURCE.lua NEW_OUTPUT_DIRECTORY\n"
                        "output directory must exist, output files must not\n");
        return 2;
    }
    if (CJ_WIDTH != 400 || CJ_HEIGHT != 240 || CJ_STRIDE != 50) {
        fprintf(stderr, "unsupported engine framebuffer geometry\n");
        return 2;
    }
    int status = 1;
    FILE *input = NULL, *frames_file = NULL, *index_file = NULL, *pcm_file = NULL;
    char *source = NULL;
    uint8_t *unique = NULL, *pcm = NULL;
    cj_runtime *runtime = NULL;
    uint8_t indices[BOOT_FRAMES], padded[PADDED_BYTES] = {0};
    size_t unique_count = 0, total_samples = 0;
    int16_t samples[1067];

    input = fopen(argv[1], "rb");
    if (!input) { fprintf(stderr, "cannot open Lua source\n"); goto done; }
    source = malloc(SOURCE_LIMIT + 1u);
    unique = calloc(BOOT_FRAMES, PADDED_BYTES);
    pcm = malloc((size_t)AUDIO_RATE * 5u); /* 2.5 seconds * 2 bytes/sample. */
    if (!source || !unique || !pcm) { fprintf(stderr, "host allocation failed\n"); goto done; }
    size_t source_length = fread(source, 1, SOURCE_LIMIT + 1u, input);
    if (ferror(input) || source_length == 0 || source_length > SOURCE_LIMIT) {
        fprintf(stderr, "source must contain 1..131072 readable bytes\n"); goto done;
    }
    if (fclose(input)) { input = NULL; fprintf(stderr, "source close failed\n"); goto done; }
    input = NULL;
    runtime = cj_create(LUA_HEAP);
    if (!runtime) { fprintf(stderr, "engine allocation failed\n"); goto done; }
    if (cj_load_source(runtime, "boot-splash.lua", source, source_length)) {
        fprintf(stderr, "Lua load failed: %s\n", cj_error(runtime)); goto done;
    }
    for (uint32_t i = 0; i < BOOT_FRAMES; ++i) {
        const cj_input controls = {0, 0.0f, 0.0f, i * 1000u / BOOT_RATE};
        if (cj_step(runtime, &controls)) {
            fprintf(stderr, "frame %u failed: %s\n", (unsigned)i, cj_error(runtime)); goto done;
        }
        if (cj_refresh_rate(runtime) != BOOT_RATE) {
            fprintf(stderr, "boot source must request30Hz\n"); goto done;
        }
        const uint8_t *frame = cj_framebuffer(runtime);
        if (!frame) { fprintf(stderr, "missing engine framebuffer\n"); goto done; }
        for (size_t row = 0; row < CJ_HEIGHT; ++row) {
            memcpy(padded + row * PADDED_STRIDE, frame + row * CJ_STRIDE, CJ_STRIDE);
        }
        size_t selected = 0;
        for (; selected < unique_count; ++selected) {
            if (memcmp(padded, unique + selected * PADDED_BYTES, PADDED_BYTES) == 0) break;
        }
        if (selected == unique_count) {
            if (unique_count >= 255u || unique_count >= BOOT_FRAMES) {
                fprintf(stderr, "unique frame limit exceeded\n"); goto done;
            }
            memcpy(unique + unique_count * PADDED_BYTES, padded, PADDED_BYTES);
            ++unique_count;
        }
        indices[i] = (uint8_t)selected;
        size_t count = ((size_t)(i + 1u) * AUDIO_RATE / BOOT_RATE) -
                       ((size_t)i * AUDIO_RATE / BOOT_RATE);
        if (count > sizeof samples / sizeof samples[0] || total_samples + count > 80000u) {
            fprintf(stderr, "audio sample count exceeded\n"); goto done;
        }
        cj_audio(runtime, samples, count, AUDIO_RATE);
        for (size_t j = 0; j < count; ++j) {
            uint16_t value = (uint16_t)samples[j];
            pcm[(total_samples + j) * 2u] = (uint8_t)(value & 255u);
            pcm[(total_samples + j) * 2u + 1u] = (uint8_t)(value >> 8);
        }
        total_samples += count;
    }
    if (total_samples != 80000u) { fprintf(stderr, "wrong final sample count\n"); goto done; }
    /* Finish rendering before opening output files. A write failure may leave
       an incomplete NEW directory; do not replace or delete previous builds. */
    frames_file = new_output(argv[2], "boot.frames");
    if (!frames_file) goto done;
    index_file = new_output(argv[2], "boot.index");
    if (!index_file) goto done;
    pcm_file = new_output(argv[2], "boot.pcm");
    if (!pcm_file) goto done;
    if (!write_all(frames_file, unique, unique_count * PADDED_BYTES) ||
        !write_all(index_file, indices, BOOT_FRAMES) ||
        !write_all(pcm_file, pcm, total_samples * 2u)) {
        fprintf(stderr, "output write failed\n"); goto done;
    }
    printf("{\"frames\":75,\"unique_frames\":%zu,\"stride\":52,"
           "\"frame_bytes\":12480,\"samples\":80000,\"pcm_bytes\":160000,"
           "\"rate\":32000,\"heap_peak\":%zu,\"hardware_tested\":false}\n",
           unique_count, cj_heap_peak(runtime));
    status = 0;
done:
    if (input && fclose(input)) status = 1;
    if (frames_file && fclose(frames_file)) status = 1;
    if (index_file && fclose(index_file)) status = 1;
    if (pcm_file && fclose(pcm_file)) status = 1;
    if (runtime) cj_destroy(runtime);
    free(source); free(unique); free(pcm);
    return status;
}
