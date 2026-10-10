/* The pinned CP port wraps double math but omits this SDK provider because
 * CP itself uses float. Lua needs it. Compile the exact pinned SDK source,
 * without changing CP, its submodule, or linker wrap policy. BSD-3-Clause
 * upstream source retains its own notice. */
#include "src/rp2_common/pico_double/double_math.c"
