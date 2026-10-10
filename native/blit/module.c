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

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    (void)n_args; (void)n_kw; (void)args;
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_blit, MP_OBJ_FROM_PTR(&blit_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
