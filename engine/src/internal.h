/* CrankJam original implementation; no SDK code or assets. */
#ifndef CJ_INTERNAL_H
#define CJ_INTERNAL_H
#include "crankjam.h"
#include "lua.h"
#include "lauxlib.h"
#include <math.h>
#define CJ_SOURCE_LIMIT (128u * 1024u)
#define CJ_DEFAULT_HEAP (256u * 1024u)
#define CJ_INSTRUCTION_LIMIT 100000
#define CJ_NATIVE_LIMIT 2000000
#define CJ_VOICES 8
#define CJ_COORD_LIMIT 1000000000.0
#define CJ_SYNTH_META "CrankJam.synth"
typedef struct {
    int allocated, active, waveform;
    double volume, velocity, frequency, phase, age, length;
    double attack, decay, sustain, release;
} cj_voice;
struct cj_runtime {
    lua_State *L;
    size_t heap_limit, heap_used, heap_peak;
    uint8_t framebuffer[CJ_FRAME_BYTES];
    char error[256];
    cj_input input;
    uint32_t previous_buttons;
    double crank_pending;
    unsigned refresh;
    int color, loaded, instructions, native_work;
    cj_voice voices[CJ_VOICES];
};
cj_runtime *cj_from_lua(lua_State *L);
double cj_number(lua_State *L, int index, double low, double high);
void cj_args(lua_State *L, int low, int high);
void cj_charge(lua_State *L, int work);
void cj_strict_table(lua_State *L, const char *name);
void cj_graphics_bind(lua_State *L);
void cj_sound_bind(lua_State *L);
#endif
