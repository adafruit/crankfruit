#ifndef CRANKJAM_H
#define CRANKJAM_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define CJ_WIDTH 400
#define CJ_HEIGHT 240
#define CJ_STRIDE ((CJ_WIDTH + 7) / 8)
#define CJ_FRAME_BYTES (CJ_STRIDE * CJ_HEIGHT)
enum { CJ_LEFT=1u, CJ_RIGHT=2u, CJ_UP=4u, CJ_DOWN=8u, CJ_B=16u, CJ_A=32u };
typedef struct cj_runtime cj_runtime;
typedef struct {
    uint32_t buttons;
    float crank_degrees;
    float crank_delta;
    uint32_t elapsed_ms;
} cj_input;
/* Single-threaded API. Each instance owns its VM, framebuffer and sound state.
 * Heap cap is for VM allocations, not this instance's fixed C storage.
 * Framebuffer is MSB-first with 1=white, 0=black; no per-row padding.
 * Source-only loader rejects binary bytecode and keeps host IO unavailable.
 * A nonzero status is failure; cj_error provides a bounded human-readable cause.
 */
cj_runtime *cj_create(size_t lua_heap_limit);
void cj_destroy(cj_runtime *runtime);
int cj_load_source(cj_runtime *runtime, const char *name, const char *source, size_t length);
int cj_step(cj_runtime *runtime, const cj_input *input);
const uint8_t *cj_framebuffer(const cj_runtime *runtime);
const char *cj_error(const cj_runtime *runtime);
size_t cj_heap_used(const cj_runtime *runtime);
size_t cj_heap_peak(const cj_runtime *runtime);
unsigned cj_refresh_rate(const cj_runtime *runtime);
/* Produce signed16-bit mono PCM. Caller chooses/validates rate, queues output,
 * and duplicates channels if its device expects stereo. No Lua calls in ISR.
 */
void cj_audio(cj_runtime *runtime, int16_t *samples, size_t frames, unsigned sample_rate);
#ifdef __cplusplus
}
#endif
#endif
