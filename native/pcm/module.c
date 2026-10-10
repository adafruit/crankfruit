/* SPDX-License-Identifier: MIT */
#include "py/dynruntime.h"
#include "pcm.h"
static mp_obj_t copy_into(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    /* All admissible offsets/counts fit a tagged small int on this ABI. Reject
       floats, arbitrary __int__ objects and oversized integers without calls. */
    mp_int_t offsets[3];
    for (size_t i = 0; i < 3; ++i) {
        if (!MP_OBJ_IS_SMALL_INT(args[i + 2])) mp_raise_TypeError("copy offsets/count must be bounded integers");
        offsets[i] = MP_OBJ_SMALL_INT_VALUE(args[i + 2]);
        if (offsets[i] < 0 || offsets[i] > (mp_int_t)CF_PCM_MAX_BYTES) mp_raise_ValueError("copy offsets/count out of range");
    }
    mp_buffer_info_t dst, src;
    mp_get_buffer_raise(args[0], &dst, MP_BUFFER_WRITE);
    mp_get_buffer_raise(args[1], &src, MP_BUFFER_READ);
    int result = cf_pcm_copy(dst.buf, dst.len, src.buf, src.len,
        (size_t)offsets[0], (size_t)offsets[1], (size_t)offsets[2]);
    if (result == -1) mp_raise_ValueError("copy buffer size or range invalid");
    if (result == -2) mp_raise_ValueError("copy buffers overlap");
    return MP_OBJ_NEW_SMALL_INT(offsets[2]);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(copy_into_obj, 5, 5, copy_into);
mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    (void)n_args; (void)n_kw; (void)args;
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_copy_into, MP_OBJ_FROM_PTR(&copy_into_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
