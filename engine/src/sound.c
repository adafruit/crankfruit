#include "internal.h"
#include <string.h>

typedef struct { int index; } synth_handle;
static cj_voice *voice(lua_State *L) {
    synth_handle *h=luaL_checkudata(L,1,CJ_SYNTH_META);
    return &cj_from_lua(L)->voices[h->index];
}
static int l_gc(lua_State *L) { memset(voice(L),0,sizeof(cj_voice)); return 0; }
static int l_new(lua_State *L) {
    cj_args(L,0,1); int wave=0;
    if (lua_gettop(L)) { lua_Integer w=luaL_checkinteger(L,1); if (w<0 || w>2) return luaL_error(L,"unsupported synth waveform"); wave=(int)w; }
    cj_runtime *r=cj_from_lua(L); int index;
    for (index=0;index<CJ_VOICES;++index) if (!r->voices[index].allocated) break;
    if (index==CJ_VOICES) return luaL_error(L,"synth limit exceeded (8 live objects)");
    synth_handle *h=lua_newuserdatauv(L,sizeof *h,0); h->index=index;
    luaL_setmetatable(L,CJ_SYNTH_META);
    cj_voice *v=&r->voices[index]; memset(v,0,sizeof *v);
    v->allocated=1; v->waveform=wave; v->volume=1; v->sustain=1; v->length=-1;
    return 1;
}
static int l_volume(lua_State *L) {
    cj_args(L,2,3); cj_voice *v=voice(L);
    double left=cj_number(L,2,0,1), right=lua_gettop(L)==3 ? cj_number(L,3,0,1) : left;
    v->volume=(left+right)*0.5; return 0;
}
static int l_adsr(lua_State *L) {
    cj_args(L,5,5); cj_voice *v=voice(L);
    double a=cj_number(L,2,0,10), d=cj_number(L,3,0,10), s=cj_number(L,4,0,1), r=cj_number(L,5,0,10);
    v->attack=a; v->decay=d; v->sustain=s; v->release=r; return 0;
}
static int l_play(lua_State *L) {
    cj_args(L,2,4); cj_voice *v=voice(L);
    if (lua_type(L,2)!=LUA_TNUMBER) return luaL_error(L,"playNote supports numeric Hertz only, not note names/MIDI");
    double hz=cj_number(L,2,0,20000);
    double vol=lua_isnoneornil(L,3) ? 1 : cj_number(L,3,0,1);
    double len=lua_isnoneornil(L,4) ? -1 : cj_number(L,4,0,60);
    if (hz==0) { v->length=v->age; lua_pushboolean(L,1); return 1; }
    v->frequency=hz; v->velocity=vol; v->length=len; v->age=0; v->phase=0; v->active=1;
    lua_pushboolean(L,1); return 1;
}
static int l_stop(lua_State *L) { cj_args(L,1,1); voice(L)->active=0; return 0; }
void cj_sound_bind(lua_State *L) {
    luaL_newmetatable(L,CJ_SYNTH_META);
    lua_pushcfunction(L,l_gc); lua_setfield(L,-2,"__gc");
    lua_pushboolean(L,0); lua_setfield(L,-2,"__metatable");
    lua_newtable(L);
    const luaL_Reg api[]={{"setVolume",l_volume},{"setADSR",l_adsr},{"playNote",l_play},{"stop",l_stop},{NULL,NULL}};
    luaL_setfuncs(L,api,0); cj_strict_table(L,"playdate.sound.synth"); lua_setfield(L,-2,"__index"); lua_pop(L,1);
    lua_newtable(L);
    const char *names[]={"kWaveSine","kWaveSquare","kWaveTriangle"};
    for (int i=0;i<3;++i) { lua_pushinteger(L,i); lua_setfield(L,-2,names[i]); }
    lua_newtable(L); lua_pushcfunction(L,l_new); lua_setfield(L,-2,"new");
    cj_strict_table(L,"playdate.sound.synth"); lua_setfield(L,-2,"synth");
    cj_strict_table(L,"playdate.sound");
}
static double held_envelope(const cj_voice *v,double t) {
    if (v->attack>0 && t<v->attack) return t/v->attack;
    t-=v->attack;
    if (v->decay>0 && t<v->decay) return 1-(1-v->sustain)*t/v->decay;
    return v->sustain;
}
void cj_audio(cj_runtime *r,int16_t *samples,size_t frames,unsigned rate) {
    if (!samples) return;
    /* No Lua calls, allocation, blocking IO, or background thread. */
    for (size_t i=0;i<frames;++i) {
        double mix=0;
        if (r && r->loaded && rate>=8000 && rate<=192000) {
            for (int k=0;k<CJ_VOICES;++k) {
                cj_voice *v=&r->voices[k]; if (!v->active) continue;
                double env=held_envelope(v,v->age);
                if (v->length>=0 && v->age>=v->length) {
                    double release_age=v->age-v->length;
                    if (v->release<=0 || release_age>=v->release) { v->active=0; continue; }
                    env=held_envelope(v,v->length)*(1-release_age/v->release);
                }
                double wave;
                if (v->waveform==0) wave=sin(6.2831853071795864769*v->phase);
                else if (v->waveform==1) wave=v->phase<0.5 ? 1 : -1;
                else wave=1-4*fabs(v->phase-0.5);
                /* Fixed mix headroom; final saturation is explicit. */
                mix+=wave*env*v->volume*v->velocity*0.25;
                v->phase+=v->frequency/rate; v->phase-=floor(v->phase);
                v->age+=1.0/rate;
            }
        }
        mix=fmax(-1,fmin(1,mix)); samples[i]=(int16_t)lround(mix*32767);
    }
}
