/* MIT. Static built-in CircuitPython binding, not native .mpy. */
#include "py/runtime.h"
#include "py/objstr.h"
#include "arena.h"
#include <math.h>
#include <string.h>
#include "formatter.h"
#if MICROPY_USE_INTERNAL_PRINTF && !CJ_LOCAL_FORMATTER
#error CrankJam requires its tested local formatter when CP printf is enabled
#endif
#if MICROPY_PY_THREAD && !MICROPY_PY_THREAD_GIL
#error CrankJam requires a single interpreter thread or the GIL
#endif
typedef struct {
    mp_obj_base_t base;
    void *arena; /* Exact GC allocation base; owner is scanned by CP GC. */
    cj_runtime *runtime; /* Interior arena pointer; NOT the only GC root. */
    size_t arena_size, cap;
} runtime_obj;
static runtime_obj *opened(mp_obj_t obj) {
    runtime_obj *self = MP_OBJ_TO_PTR(obj);
    if (!self->runtime) mp_raise_ValueError(MP_ERROR_TEXT("Runtime is closed"));
    return self;
}
static void dispose(runtime_obj *self) {
    if (self->runtime) cj_destroy(self->runtime);
    self->runtime = NULL;
    if (self->arena) m_del(byte, self->arena, self->arena_size);
    self->arena = NULL;
}
static void source_buffer(mp_obj_t obj, mp_buffer_info_t *buf) {
    if (mp_obj_is_str(obj)) mp_raise_TypeError(MP_ERROR_TEXT("source must be bytes-like"));
    mp_get_buffer_raise(obj, buf, MP_BUFFER_READ);
    if (!buf->len || buf->len > 131072) mp_raise_ValueError(MP_ERROR_TEXT("source length must be 1..131072"));
}
static void lua_error(runtime_obj *self) {
    mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("%s"), cj_error(self->runtime));
}
static mp_obj_t runtime_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    enum { ARG_source, ARG_heap_cap };
    static const mp_arg_t allowed[] = {
        {MP_QSTR_source, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}},
        {MP_QSTR_heap_cap, MP_ARG_INT, {.u_int = 262144}},
    };
    mp_arg_val_t values[2];
    mp_arg_parse_all_kw_array(n_args, n_kw, args, 2, allowed, values);
    mp_int_t cap = values[ARG_heap_cap].u_int;
    if (cap < 32768 || cap > 1048576) mp_raise_ValueError(MP_ERROR_TEXT("heap cap must be 32768..1048576"));
    mp_buffer_info_t source; source_buffer(values[ARG_source].u_obj, &source);
    runtime_obj *self = mp_obj_malloc(runtime_obj, type);
    self->arena = NULL; self->runtime = NULL; self->cap = (size_t)cap;
    self->arena_size = cj_arena_bytes(self->cap);
    self->arena = m_new0(byte, self->arena_size);
    self->runtime = cj_arena_create(self->arena, self->arena_size, self->cap);
    if (!self->runtime) { dispose(self); mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("Lua arena exhausted")); }
    if (cj_load_source(self->runtime, "cartridge", source.buf, source.len)) {
        char error[256]; memcpy(error, cj_error(self->runtime), sizeof error); dispose(self);
        mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("%s"), error);
    }
    return MP_OBJ_FROM_PTR(self);
}
static mp_obj_t runtime_close(mp_obj_t obj) { dispose(MP_OBJ_TO_PTR(obj)); return mp_const_none; }
static MP_DEFINE_CONST_FUN_OBJ_1(runtime_close_obj, runtime_close);
static mp_obj_t runtime_load(mp_obj_t obj, mp_obj_t source_obj) {
    runtime_obj *self = opened(obj); mp_buffer_info_t source; source_buffer(source_obj, &source);
    if (cj_load_source(self->runtime, "cartridge", source.buf, source.len)) lua_error(self);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(runtime_load_obj, runtime_load);
static mp_obj_t runtime_step(size_t n_args, const mp_obj_t *args) {
    (void)n_args; runtime_obj *self = opened(args[0]);
    mp_int_t buttons = mp_obj_get_int(args[1]);
    mp_float_t angle = mp_obj_get_float(args[2]), delta = mp_obj_get_float(args[3]);
    /* uint32 maximum is compared before conversion, also on 32-bit MP. */
    mp_int_t elapsed = mp_obj_get_int(args[4]);
    if (buttons < 0 || buttons > 63 || elapsed < 0 || (uint64_t)elapsed > UINT32_MAX || !isfinite(angle) || !isfinite(delta) || fabs((double)angle) > (double)1000000000 || fabs((double)delta) > (double)1000000000)
        mp_raise_ValueError(MP_ERROR_TEXT("input outside supported range"));
    cj_input input = {(uint32_t)buttons, (float)angle, (float)delta, (uint32_t)elapsed};
    if (cj_step(self->runtime, &input)) lua_error(self);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(runtime_step_obj, 5, 5, runtime_step);
static mp_obj_t runtime_copy(size_t n_args, const mp_obj_t *pos, mp_map_t *kw) {
    runtime_obj *self = opened(pos[0]);
    static const mp_arg_t allowed[] = {
        {MP_QSTR_buffer, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}},
        {MP_QSTR_stride, MP_ARG_INT, {.u_int = CJ_STRIDE}},
    };
    mp_arg_val_t a[2]; mp_arg_parse_all(n_args - 1, pos + 1, kw, 2, allowed, a);
    mp_int_t stride = a[1].u_int;
    mp_buffer_info_t buf; mp_get_buffer_raise(a[0].u_obj, &buf, MP_BUFFER_WRITE);
    if (stride < CJ_STRIDE || stride > 4096 || buf.len != (size_t)stride * CJ_HEIGHT)
        mp_raise_ValueError(MP_ERROR_TEXT("framebuffer must be stride*240 bytes; stride 50..4096"));
    const uint8_t *frame = cj_framebuffer(self->runtime);
    for (size_t y = 0; y < CJ_HEIGHT; ++y) memcpy((byte *)buf.buf + y * (size_t)stride, frame + y * CJ_STRIDE, CJ_STRIDE);
    return mp_obj_new_int(CJ_FRAME_BYTES);
}
static MP_DEFINE_CONST_FUN_OBJ_KW(runtime_copy_obj, 2, runtime_copy);
static mp_obj_t runtime_audio(size_t n_args, const mp_obj_t *pos, mp_map_t *kw) {
    runtime_obj *self = opened(pos[0]);
    static const mp_arg_t allowed[] = {
        {MP_QSTR_buffer, MP_ARG_REQUIRED | MP_ARG_OBJ, {.u_obj = MP_OBJ_NULL}},
        {MP_QSTR_rate, MP_ARG_INT, {.u_int = 32000}},
    };
    mp_arg_val_t a[2]; mp_arg_parse_all(n_args - 1, pos + 1, kw, 2, allowed, a);
    if (a[1].u_int < 8000 || a[1].u_int > 192000) mp_raise_ValueError(MP_ERROR_TEXT("rate must be 8000..192000"));
    mp_buffer_info_t buf; mp_get_buffer_raise(a[0].u_obj, &buf, MP_BUFFER_WRITE);
    if (buf.len > 65536 || buf.len % 2) mp_raise_ValueError(MP_ERROR_TEXT("PCM buffer must be even and at most 65536 bytes"));
    /* Aligned native scratch + explicit LE output: arbitrary writable offsets safe. */
    int16_t samples[128]; byte *out = buf.buf;
    for (size_t i = 0; i < buf.len / 2;) {
        size_t n = buf.len / 2 - i; if (n > 128) n = 128;
        cj_audio(self->runtime, samples, n, (unsigned)a[1].u_int);
        for (size_t j = 0; j < n; ++j) { uint16_t v = (uint16_t)samples[j]; out[2*(i+j)] = (byte)v; out[2*(i+j)+1] = (byte)(v >> 8); }
        i += n;
    }
    return mp_obj_new_int_from_uint(buf.len);
}
static MP_DEFINE_CONST_FUN_OBJ_KW(runtime_audio_obj, 2, runtime_audio);
static mp_obj_t runtime_stats(mp_obj_t obj) {
    runtime_obj *s = opened(obj);
    mp_obj_t a[] = {mp_obj_new_int_from_uint(cj_heap_used(s->runtime)), mp_obj_new_int_from_uint(cj_heap_peak(s->runtime)), mp_obj_new_int_from_uint(s->cap), mp_obj_new_int_from_uint(s->arena_size)};
    return mp_obj_new_tuple(4, a);
}
static MP_DEFINE_CONST_FUN_OBJ_1(runtime_stats_obj, runtime_stats);
static mp_obj_t runtime_error(mp_obj_t obj) { const char *s = cj_error(opened(obj)->runtime); return mp_obj_new_str(s, strlen(s)); }
static MP_DEFINE_CONST_FUN_OBJ_1(runtime_error_obj, runtime_error);
static mp_obj_t runtime_refresh(mp_obj_t obj) { return mp_obj_new_int(cj_refresh_rate(opened(obj)->runtime)); }
static MP_DEFINE_CONST_FUN_OBJ_1(runtime_refresh_obj, runtime_refresh);
static const mp_rom_map_elem_t runtime_locals[] = {
    {MP_ROM_QSTR(MP_QSTR_close), MP_ROM_PTR(&runtime_close_obj)},
    {MP_ROM_QSTR(MP_QSTR_load), MP_ROM_PTR(&runtime_load_obj)},
    {MP_ROM_QSTR(MP_QSTR_step), MP_ROM_PTR(&runtime_step_obj)},
    {MP_ROM_QSTR(MP_QSTR_copy_framebuffer_into), MP_ROM_PTR(&runtime_copy_obj)},
    {MP_ROM_QSTR(MP_QSTR_audio_into), MP_ROM_PTR(&runtime_audio_obj)},
    {MP_ROM_QSTR(MP_QSTR_heap_stats), MP_ROM_PTR(&runtime_stats_obj)},
    {MP_ROM_QSTR(MP_QSTR_error), MP_ROM_PTR(&runtime_error_obj)},
    {MP_ROM_QSTR(MP_QSTR_refresh_rate), MP_ROM_PTR(&runtime_refresh_obj)},
};
static MP_DEFINE_CONST_DICT(runtime_locals_dict, runtime_locals);
static MP_DEFINE_CONST_OBJ_TYPE(runtime_type, MP_QSTR_Runtime, MP_TYPE_FLAG_NONE, make_new, runtime_make_new, locals_dict, &runtime_locals_dict);
static const mp_rom_map_elem_t globals[] = {
    {MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_crankjam)},
    {MP_ROM_QSTR(MP_QSTR_Runtime), MP_ROM_PTR(&runtime_type)},
};
static MP_DEFINE_CONST_DICT(globals_dict, globals);
const mp_obj_module_t crankjam_module = {.base = {&mp_type_module}, .globals = (mp_obj_dict_t *)&globals_dict};
MP_REGISTER_MODULE(MP_QSTR_crankjam, crankjam_module);
