/* Original CrankJam bounded source-Lua runtime. */
#include "internal.h"
#include "lualib.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void *vm_alloc(void *ud, void *ptr, size_t old, size_t size) {
    cj_runtime *r = ud;
    if (!ptr) old = 0;
    if (!size) { free(ptr); r->heap_used -= old; return NULL; }
    if (size > r->heap_limit - (r->heap_used - old)) return NULL;
    void *p = realloc(ptr, size);
    if (!p) return NULL;
    r->heap_used = r->heap_used - old + size;
    if (r->heap_used > r->heap_peak) r->heap_peak = r->heap_used;
    return p;
}
cj_runtime *cj_from_lua(lua_State *L) { return *(cj_runtime **)lua_getextraspace(L); }
void cj_args(lua_State *L, int low, int high) {
    int n = lua_gettop(L);
    if (n < low || n > high) luaL_error(L, "unsupported argument count (expected %d..%d)", low, high);
}
double cj_number(lua_State *L, int index, double low, double high) {
    double n = luaL_checknumber(L, index);
    if (!isfinite(n) || n < low || n > high)
        luaL_error(L, "argument %d outside supported finite range", index);
    return n;
}
void cj_charge(lua_State *L, int work) {
    cj_runtime *r = cj_from_lua(L);
    if (work > r->native_work) luaL_error(L, "native drawing work budget exceeded");
    r->native_work -= work;
}
static int unsupported(lua_State *L) {
    const char *key = lua_tostring(L, 2);
    return luaL_error(L, "unsupported API: %s.%s", lua_tostring(L, lua_upvalueindex(1)), key ? key : "<non-string>");
}
void cj_strict_table(lua_State *L, const char *name) {
    lua_newtable(L);
    lua_pushstring(L, name); lua_pushcclosure(L, unsupported, 1); lua_setfield(L, -2, "__index");
    lua_pushboolean(L, 0); lua_setfield(L, -2, "__metatable");
    lua_setmetatable(L, -2);
}
static void budget_hook(lua_State *L, lua_Debug *ar) {
    (void)ar;
    cj_runtime *r = cj_from_lua(L);
    r->instructions -= 1000;
    if (r->instructions <= 0) luaL_error(L, "instruction budget exceeded");
}
static void budget_start(cj_runtime *r) {
    r->instructions = CJ_INSTRUCTION_LIMIT;
    r->native_work = CJ_NATIVE_LIMIT;
    lua_sethook(r->L, budget_hook, LUA_MASKCOUNT, 1000);
}
static int l_pressed(lua_State *L) {
    cj_args(L, 1, 1);
    lua_Integer value = luaL_checkinteger(L, 1);
    if (value < 1 || value > CJ_A) return luaL_error(L, "unsupported button constant");
    unsigned mask = (unsigned)value;
    if (mask & (mask - 1)) return luaL_error(L, "unsupported button constant");
    lua_pushboolean(L, (cj_from_lua(L)->input.buttons & mask) != 0); return 1;
}
static int l_just_pressed(lua_State *L) {
    l_pressed(L); lua_pop(L, 1);
    cj_runtime *r = cj_from_lua(L);
    unsigned mask = (unsigned)lua_tointeger(L, 1);
    lua_pushboolean(L, ((r->input.buttons & ~r->previous_buttons) & mask) != 0); return 1;
}
static int l_crank(lua_State *L) {
    cj_args(L, 0, 0);
    double angle = fmod((double)cj_from_lua(L)->input.crank_degrees, 360.0);
    lua_pushnumber(L, angle < 0 ? angle + 360 : angle); return 1;
}
static int l_delta(lua_State *L) {
    cj_args(L, 0, 0); cj_runtime *r = cj_from_lua(L);
    lua_pushnumber(L, r->crank_pending); lua_pushnumber(L, r->crank_pending);
    r->crank_pending = 0; return 2;
}
static int l_time(lua_State *L) {
    cj_args(L, 0, 0); lua_pushinteger(L, cj_from_lua(L)->input.elapsed_ms); return 1;
}
static int l_set_refresh(lua_State *L) {
    cj_args(L, 1, 1); lua_Integer rate = luaL_checkinteger(L, 1);
    if (rate < 1 || rate > 50) return luaL_error(L, "supported refresh rate is integer 1..50 (unlimited unsupported)");
    cj_from_lua(L)->refresh = (unsigned)rate; return 0;
}
static int l_get_refresh(lua_State *L) {
    cj_args(L, 0, 0); lua_pushinteger(L, cj_from_lua(L)->refresh); return 1;
}
static void remove_fields(lua_State *L, const char *const *names) {
    for (; *names; ++names) { lua_pushnil(L); lua_setfield(L, -2, *names); }
}
static int bounded_rep(lua_State *L) {
    lua_Integer n = luaL_checkinteger(L, 2);
    if (n > CJ_NATIVE_LIMIT) return luaL_error(L, "string.rep work budget exceeded");
    if (n > 0) cj_charge(L, (int)n);
    int count = lua_gettop(L);
    lua_pushvalue(L, lua_upvalueindex(1)); lua_insert(L, 1);
    lua_call(L, count, 1); return 1;
}
static int init_vm(lua_State *L) {
    /* No package/io/os/debug/coroutine: never call luaL_openlibs. */
    luaL_requiref(L, "_G", luaopen_base, 1);
    const char *const removed[] = {"dofile", "loadfile", "load", "collectgarbage", "print", "warn", "pcall", "xpcall", "setmetatable", "getmetatable", "rawset", NULL};
    remove_fields(L, removed); lua_pop(L, 1);
    luaL_requiref(L, "math", luaopen_math, 1); lua_pop(L, 1);
    luaL_requiref(L, "string", luaopen_string, 1);
    /* Pattern matching may run for unbounded C time outside instruction hooks. */
    const char *const strings[] = {"dump", "find", "match", "gmatch", "gsub", NULL};
    remove_fields(L, strings);
    lua_getfield(L, -1, "rep"); lua_pushcclosure(L, bounded_rep, 1); lua_setfield(L, -2, "rep");
    lua_pop(L, 1);
    luaL_requiref(L, "table", luaopen_table, 1);
    /* Moving arbitrarily many nil entries evades both heap and VM budgets. */
    lua_pushnil(L); lua_setfield(L, -2, "move"); lua_pop(L, 1);
    luaL_requiref(L, "utf8", luaopen_utf8, 1); lua_pop(L, 1);
    const luaL_Reg system_api[] = {
        {"buttonIsPressed", l_pressed}, {"buttonJustPressed", l_just_pressed},
        {"getCrankPosition", l_crank}, {"getCrankChange", l_delta},
        {"getCurrentTimeMilliseconds", l_time}, {NULL, NULL}
    };
    lua_newtable(L); luaL_setfuncs(L, system_api, 0);
    const char *names[] = {"kButtonLeft", "kButtonRight", "kButtonUp", "kButtonDown", "kButtonB", "kButtonA"};
    for (unsigned i = 0; i < 6; ++i) { lua_pushinteger(L, 1u << i); lua_setfield(L, -2, names[i]); }
    lua_newtable(L);
    lua_pushcfunction(L, l_set_refresh); lua_setfield(L, -2, "setRefreshRate");
    lua_pushcfunction(L, l_get_refresh); lua_setfield(L, -2, "getRefreshRate");
    cj_strict_table(L, "playdate.display"); lua_setfield(L, -2, "display");
    cj_graphics_bind(L); lua_setfield(L, -2, "graphics");
    cj_sound_bind(L); lua_setfield(L, -2, "sound");
    cj_strict_table(L, "playdate"); lua_setglobal(L, "playdate");
    return 0;
}
static void silence(cj_runtime *r) {
    for (int i = 0; i < CJ_VOICES; ++i) r->voices[i].active = 0;
}
static int fail(cj_runtime *r, const char *message) {
    snprintf(r->error, sizeof r->error, "%s", message ? message : "unknown Lua error");
    r->loaded = 0; silence(r); return -1;
}
static int lua_failure(cj_runtime *r) {
    fail(r, lua_tostring(r->L, -1)); lua_settop(r->L, 0); return -1;
}
static int reset_vm(cj_runtime *r) {
    if (r->L) { lua_close(r->L); r->L = NULL; }
    memset(r->voices, 0, sizeof r->voices);
    memset(&r->input, 0, sizeof r->input);
    memset(r->framebuffer, 255, sizeof r->framebuffer);
    r->previous_buttons = 0; r->crank_pending = 0;
    r->refresh = 30; r->color = 0; r->loaded = 0; r->error[0] = 0;
    r->heap_peak = 0;
    r->L = lua_newstate(vm_alloc, r);
    if (!r->L) return fail(r, "Lua heap limit too small to create VM");
    *(cj_runtime **)lua_getextraspace(r->L) = r;
    lua_pushcfunction(r->L, init_vm);
    if (lua_pcall(r->L, 0, 0, 0) != LUA_OK) return lua_failure(r);
    return 0;
}
cj_runtime *cj_create(size_t heap_limit) {
    cj_runtime *r = calloc(1, sizeof *r);
    if (!r) return NULL;
    r->heap_limit = heap_limit ? heap_limit : CJ_DEFAULT_HEAP;
    if (reset_vm(r)) { cj_destroy(r); return NULL; }
    return r;
}
void cj_destroy(cj_runtime *r) {
    if (!r) return;
    if (r->L) lua_close(r->L);
    free(r);
}
static int validate_vm(lua_State *L) {
    lua_getglobal(L, "playdate");
    if (!lua_istable(L, -1)) return luaL_error(L, "playdate must remain a table");
    lua_pushliteral(L, "update"); lua_rawget(L, -2);
    if (!lua_isfunction(L, -1)) return luaL_error(L, "cartridge must define playdate.update function");
    return 0;
}
int cj_load_source(cj_runtime *r, const char *name, const char *source, size_t length) {
    if (!r) return -1;
    if (reset_vm(r)) return -1;
    if (!source || !length || length > CJ_SOURCE_LIMIT) return fail(r, "source length must be 1..131072 bytes");
    if ((unsigned char)source[0] == 0x1b) return fail(r, "binary chunks are unsupported; source Lua required");
    char chunk_name[96]; snprintf(chunk_name, sizeof chunk_name, "%.90s", name ? name : "cartridge");
    if (luaL_loadbufferx(r->L, source, length, chunk_name, "t") != LUA_OK) return lua_failure(r);
    budget_start(r);
    if (lua_pcall(r->L, 0, 0, 0) != LUA_OK) return lua_failure(r);
    /* Validation is protected too: even an exhausted heap must not panic. */
    lua_pushcfunction(r->L, validate_vm);
    if (lua_pcall(r->L, 0, 0, 0) != LUA_OK) return lua_failure(r);
    r->loaded = 1; return 0;
}
static int update_vm(lua_State *L) {
    lua_getglobal(L, "playdate");
    if (!lua_istable(L, -1)) return luaL_error(L, "playdate must remain a table");
    lua_pushliteral(L, "update"); lua_rawget(L, -2);
    if (!lua_isfunction(L, -1)) return luaL_error(L, "playdate.update must remain a function");
    lua_call(L, 0, 0); return 0;
}
int cj_step(cj_runtime *r, const cj_input *input) {
    if (!r || !input) return -1;
    if (!r->loaded) { if (!r->error[0]) fail(r, "no loaded cartridge"); return -1; }
    if (!isfinite(input->crank_degrees) || !isfinite(input->crank_delta)) return fail(r, "nonfinite crank input");
    r->previous_buttons = r->input.buttons; r->input = *input;
    r->crank_pending += input->crank_delta;
    budget_start(r); lua_pushcfunction(r->L, update_vm);
    if (lua_pcall(r->L, 0, 0, 0) != LUA_OK) return lua_failure(r);
    return 0;
}
const uint8_t *cj_framebuffer(const cj_runtime *r) { return r ? r->framebuffer : NULL; }
const char *cj_error(const cj_runtime *r) { return r ? r->error : "null runtime"; }
size_t cj_heap_used(const cj_runtime *r) { return r ? r->heap_used : 0; }
size_t cj_heap_peak(const cj_runtime *r) { return r ? r->heap_peak : 0; }
unsigned cj_refresh_rate(const cj_runtime *r) { return r ? r->refresh : 0; }
