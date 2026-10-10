/* SPDX-License-Identifier: MIT */
#include "py/dynruntime.h"
#include "sprite.h"

static mp_obj_t compose(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    mp_buffer_info_t b[5];
    mp_get_buffer_raise(args[0], &b[0], MP_BUFFER_WRITE);
    for (size_t i = 1; i < 5; ++i) mp_get_buffer_raise(args[i], &b[i], MP_BUFFER_READ);
    int result = cf_compose(b[0].buf, b[0].len, b[1].buf, b[1].len,
        b[2].buf, b[2].len, b[3].buf, b[3].len, b[4].buf, b[4].len);
    if (result == -1) mp_raise_ValueError("compose: invalid buffer size or record count");
    if (result == -2) mp_raise_ValueError("compose: target overlaps an input");
    if (result == -3) mp_raise_ValueError("compose: invalid sprite descriptor");
    if (result == -4) mp_raise_ValueError("compose: invalid sprite command");
    return MP_OBJ_NEW_SMALL_INT(CF_BACKGROUND_BYTES);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(compose_obj, 5, 5, compose);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    (void)n_args; (void)n_kw; (void)args;
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_compose, MP_OBJ_FROM_PTR(&compose_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
