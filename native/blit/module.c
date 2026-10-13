/* SPDX-License-Identifier: MIT */
#include "py/dynruntime.h"
#include "blit.h"

static mp_obj_t blit(mp_obj_t src_obj, mp_obj_t dst_obj) {
    mp_buffer_info_t src, dst;
    mp_get_buffer_raise(src_obj, &src, MP_BUFFER_READ);
    mp_get_buffer_raise(dst_obj, &dst, MP_BUFFER_WRITE);
    int result = cf_blit(src.buf, src.len, dst.buf, dst.len);
    if (result == -1) mp_raise_ValueError("blit needs 12480-byte source and 38400-byte destination");
    if (result == -2) mp_raise_ValueError("blit buffers must not overlap");
    return MP_OBJ_NEW_SMALL_INT(CF_COPIED_BYTES);
}
static MP_DEFINE_CONST_FUN_OBJ_2(blit_obj, blit);

static mp_obj_t blit16(mp_obj_t src_obj, mp_obj_t dst_obj) {
    mp_buffer_info_t src, dst;
    mp_get_buffer_raise(src_obj, &src, MP_BUFFER_READ);
    mp_get_buffer_raise(dst_obj, &dst, MP_BUFFER_WRITE);
    int result = cf_blit16(src.buf, src.len, dst.buf, dst.len);
    if (result == -1) mp_raise_ValueError("blit16 needs 12480-byte source and 38400-byte destination");
    if (result == -2) mp_raise_ValueError("blit16 buffers must not overlap");
    return MP_OBJ_NEW_SMALL_INT(CF_DEST_BYTES);
}
static MP_DEFINE_CONST_FUN_OBJ_2(blit16_obj, blit16);

static mp_obj_t blit2(size_t n_args, const mp_obj_t *args) {
    mp_buffer_info_t src, dst;
    mp_get_buffer_raise(args[0], &src, MP_BUFFER_READ);
    mp_get_buffer_raise(args[1], &dst, MP_BUFFER_WRITE);
    int white = n_args > 3 ? (int)mp_obj_get_int(args[3]) : 3;  /* 2 Playdate-like, 3 bright */
    int result = cf_blit2(src.buf, src.len, dst.buf, dst.len, (int)mp_obj_get_int(args[2]), white);
    if (result == -1) mp_raise_ValueError("blit2 needs 12480-byte source, 76800-byte destination, mode 0..2, white 2..3");
    if (result == -2) mp_raise_ValueError("blit2 buffers must not overlap");
    return MP_OBJ_NEW_SMALL_INT(CF_DEST2_BYTES);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(blit2_obj, 3, 4, blit2);

static mp_obj_t frame_changed(mp_obj_t src_obj, mp_obj_t prev_obj) {
    mp_buffer_info_t src, prev;
    mp_get_buffer_raise(src_obj, &src, MP_BUFFER_READ);
    mp_get_buffer_raise(prev_obj, &prev, MP_BUFFER_WRITE);
    int result = cf_frame_changed(src.buf, src.len, prev.buf, prev.len);
    if (result == -1) mp_raise_ValueError("frame_changed needs two 12480-byte buffers");
    if (result == -2) mp_raise_ValueError("frame_changed buffers must not overlap");
    return mp_obj_new_bool(result);
}
static MP_DEFINE_CONST_FUN_OBJ_2(frame_changed_obj, frame_changed);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    (void)n_args; (void)n_kw; (void)args;
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_blit, MP_OBJ_FROM_PTR(&blit_obj));
    mp_store_global(MP_QSTR_blit16, MP_OBJ_FROM_PTR(&blit16_obj));
    mp_store_global(MP_QSTR_blit2, MP_OBJ_FROM_PTR(&blit2_obj));
    mp_store_global(MP_QSTR_frame_changed, MP_OBJ_FROM_PTR(&frame_changed_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
