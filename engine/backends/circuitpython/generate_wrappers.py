"""Generate transparent include wrappers for unchanged, locally vendored code."""
from pathlib import Path
p = Path(__file__).resolve().parent / 'crankjam'
for name in ('graphics', 'sound'):
    (p / ('core_' + name + '.c')).write_text('#include "../../../src/' + name + '.c"\n')
names = 'lapi lcode lctype ldebug ldo ldump lfunc lgc llex lmem lobject lopcodes lparser lstate lstring ltable ltm lundump lvm lzio lauxlib lbaselib lmathlib lstrlib ltablib lutf8lib'.split()
for name in names:
    prefix = '#include <stdio.h>\n#include <stdlib.h>\n#include "formatter.h"\n#include "floatparse.h"\n#undef snprintf\n#define snprintf cj_snprintf\n#define strtod cj_strtod\n'
    # The local decimal/hex parser avoids target libc allocation paths.
    # The sandbox removes print/warn/file entry points. Never link FILE-backed
    # stdout/stderr warning paths that can allocate an untracked newlib heap.
    prefix += '#define lua_writestring(s,l) ((void)(s), (void)(l))\n#define lua_writeline() ((void)0)\n#define lua_writestringerror(s,p) ((void)(s), (void)(p))\n'
    if name == 'lauxlib':
        # Core always calls lua_newstate with its capped allocator. Make the
        # unused convenience allocator fail closed rather than link libc heap.
        prefix += '#include <stdlib.h>\n#define free(p) ((void)(p))\n#define realloc(p,n) ((void)(p), (void)(n), (void *)0)\n'
    (p / ('lua_' + name + '.c')).write_text(prefix + '#include "../../../vendor/lua-5.4.9/src/' + name + '.c"\n')
