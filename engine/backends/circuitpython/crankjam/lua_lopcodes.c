#include <stdio.h>
#include <stdlib.h>
#include "formatter.h"
#include "floatparse.h"
#undef snprintf
#define snprintf cj_snprintf
#define strtod cj_strtod
#define lua_writestring(s,l) ((void)(s), (void)(l))
#define lua_writeline() ((void)0)
#define lua_writestringerror(s,p) ((void)(s), (void)(p))
#include "../../../vendor/lua-5.4.9/src/lopcodes.c"
