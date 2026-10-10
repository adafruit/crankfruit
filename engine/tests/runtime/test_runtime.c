#include "internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned tests,checks;
#define CHECK(expr) do { ++checks; if (!(expr)) { fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#expr); exit(1); } } while(0)
#define RUN(fn) do { fn(); ++tests; printf("PASS %s\n",#fn); } while(0)
static const char *empty="function playdate.update() end";
static cj_runtime *runtime(void) { cj_runtime *r=cj_create(65536); CHECK(r); return r; }
static int load(cj_runtime *r,const char *s) { return cj_load_source(r,"test",s,strlen(s)); }
static void step(cj_runtime *r,unsigned buttons,float angle,float delta,unsigned ms) {
    cj_input in={buttons,angle,delta,ms}; int code=cj_step(r,&in);
    if (code) fprintf(stderr,"step error: %s\n",cj_error(r)); CHECK(code==0);
}
static int black(cj_runtime *r,int x,int y) { return !(cj_framebuffer(r)[y*CJ_STRIDE+x/8]&(128u>>(unsigned)(x&7))); }
static int all(const int16_t *a,size_t n,int zero) { for(size_t i=0;i<n;++i) if ((a[i]==0)!=zero) return 0; return 1; }
static void test_valid(void) {
    cj_runtime *r=runtime(); CHECK(!load(r,"local g=playdate.graphics; function playdate.update() g.clear();g.fillRect(10,20,4,5) end"));
    step(r,0,0,0,0); CHECK(black(r,10,20)); CHECK(!black(r,9,20)); CHECK(cj_heap_used(r)<=65536); CHECK(cj_heap_peak(r)<=65536);
    printf("METRIC fixture_heap_used=%zu peak=%zu fixed_runtime_bytes=%zu\n",cj_heap_used(r),cj_heap_peak(r),sizeof *r); cj_destroy(r);
}
static void test_corrupt(void) { cj_runtime *r=runtime(); CHECK(load(r,"function ! garbage")!=0); CHECK(strstr(cj_error(r),"test")); cj_destroy(r); }
static void test_binary(void) { cj_runtime *r=runtime(); const char bin[]={27,'L','u','a',0x54,0}; CHECK(cj_load_source(r,"binary",bin,sizeof bin)!=0); CHECK(strstr(cj_error(r),"binary")); cj_destroy(r); }
static void test_source_bound(void) { cj_runtime *r=runtime(); CHECK(cj_load_source(r,"big","x",CJ_SOURCE_LIMIT+1)!=0); CHECK(strstr(cj_error(r),"length")); CHECK(cj_load_source(r,"empty","",0)!=0); cj_destroy(r); }
static void test_heap(void) {
    cj_runtime *r=runtime(); CHECK(load(r,"local x=string.rep('x',200000); function playdate.update() end")!=0);
    CHECK(strstr(cj_error(r),"memory")); CHECK(cj_heap_peak(r)<=65536); CHECK(!load(r,empty)); step(r,0,0,0,0); cj_destroy(r);
    for(size_t cap=1;cap<20000;cap+=173) { r=cj_create(cap); if(r) { CHECK(cj_heap_peak(r)<=cap); cj_destroy(r); } }
}
static void test_infinite_load(void) { cj_runtime *r=runtime(); CHECK(load(r,"while true do end")!=0); CHECK(strstr(cj_error(r),"instruction budget")); cj_destroy(r); }
static void test_infinite_step(void) { cj_runtime *r=runtime(); CHECK(!load(r,"function playdate.update() while true do end end")); cj_input in={0}; CHECK(cj_step(r,&in)!=0); CHECK(strstr(cj_error(r),"instruction budget")); CHECK(cj_step(r,&in)!=0); cj_destroy(r); }
static void test_sandbox(void) {
    cj_runtime *r=runtime(); CHECK(!load(r,"assert(os==nil and io==nil and package==nil and debug==nil and coroutine==nil); assert(load==nil and dofile==nil and loadfile==nil); assert(pcall==nil and xpcall==nil and setmetatable==nil and getmetatable==nil); assert(string.dump==nil and string.match==nil); function playdate.update() end")); cj_destroy(r);
}
static void test_unsupported(void) { cj_runtime *r=runtime(); CHECK(load(r,"playdate.graphics.drawTriangle(1,2,3)")!=0); CHECK(strstr(cj_error(r),"unsupported API: playdate.graphics.drawTriangle")); CHECK(load(r,"local s=playdate.sound.synth.new();s:noteOff()")!=0); CHECK(strstr(cj_error(r),"unsupported API")); cj_destroy(r); }
static void test_rect_clip(void) {
    cj_runtime *r=runtime(); CHECK(!load(r,"local g=playdate.graphics; function playdate.update() g.clear();g.fillRect(-10,-20,15,24);g.fillRect(399,239,1000000000,1000000000) end")); step(r,0,0,0,0);
    for(int y=0;y<CJ_HEIGHT;++y) for(int x=0;x<CJ_WIDTH;++x) CHECK(black(r,x,y)==((x<5&&y<4)||(x==399&&y==239))); cj_destroy(r);
}
static void test_line_huge(void) {
    cj_runtime *r=runtime(); CHECK(!load(r,"local g=playdate.graphics; function playdate.update() g.clear();g.drawLine(-1e9,120,1e9,120);g.drawLine(-1e9,-1e9,-1,-1) end")); step(r,0,0,0,0);
    for(int y=0;y<CJ_HEIGHT;++y) for(int x=0;x<CJ_WIDTH;++x) CHECK(black(r,x,y)==(y==120)); cj_destroy(r);
}
static void test_circle_huge(void) { cj_runtime *r=runtime(); CHECK(!load(r,"local g=playdate.graphics;function playdate.update() g.fillCircleAtPoint(0,0,1e9) end"));step(r,0,0,0,0);for(size_t i=0;i<CJ_FRAME_BYTES;++i)CHECK(cj_framebuffer(r)[i]==0);cj_destroy(r); }
static void test_circle_clip(void) { cj_runtime *r=runtime(); CHECK(!load(r,"local g=playdate.graphics;function playdate.update() g.fillCircleAtPoint(0,0,3) end"));step(r,0,0,0,0);CHECK(black(r,0,0));CHECK(black(r,3,0));CHECK(!black(r,3,3));CHECK(!black(r,399,239));cj_destroy(r); }
static void test_geometry_reject(void) {
    const char *cases[]={"playdate.graphics.drawLine(1e300,0,0,0)","playdate.graphics.fillCircleAtPoint(0,0,-1)","playdate.graphics.fillRect(0,0,0/0,1)","playdate.graphics.fillRect(0,0,1/0,1)","playdate.graphics.drawText('a',0,0,10,10)"};
    cj_runtime *r=runtime();for(size_t i=0;i<sizeof cases/sizeof cases[0];++i)CHECK(load(r,cases[i])!=0);cj_destroy(r);
}
static void test_xor(void) {
    cj_runtime *r=runtime();CHECK(!load(r,"local g=playdate.graphics;function playdate.update() g.clear();g.setColor(g.kColorXOR);g.drawRect(0,0,3,3) end"));step(r,0,0,0,0);
    CHECK(black(r,0,0));CHECK(black(r,2,2));CHECK(black(r,1,0));CHECK(!black(r,1,1));cj_destroy(r);
}
static void test_native_budget(void) { cj_runtime *r=runtime();CHECK(load(r,"for i=1,100 do playdate.graphics.clear() end")!=0);CHECK(strstr(cj_error(r),"drawing work budget"));cj_destroy(r); }
static void test_font(void) { cj_runtime *r=runtime();CHECK(!load(r,"local g=playdate.graphics;function playdate.update() local w,h=g.drawText('Ab',10,10);assert(w==11 and h==7) end"));step(r,0,0,0,0);CHECK(black(r,11,10));CHECK(!black(r,10,10));cj_destroy(r); }
static void test_input_framebuffer(void) {
    cj_runtime *r=runtime();CHECK(!load(r,"local p=playdate;local g=p.graphics;local x=20;function p.update() if p.buttonIsPressed(p.kButtonRight) then x=x+5 end; if p.buttonJustPressed(p.kButtonA) then x=x+10 end;g.clear();g.fillRect(x,100,2,2) end"));
    step(r,0,0,0,0);uint8_t first[CJ_FRAME_BYTES];memcpy(first,cj_framebuffer(r),sizeof first);
    step(r,CJ_RIGHT,0,0,33);CHECK(memcmp(first,cj_framebuffer(r),sizeof first)!=0);CHECK(black(r,25,100));
    step(r,CJ_A,0,0,66);CHECK(black(r,35,100));step(r,CJ_A,0,0,99);CHECK(black(r,35,100));step(r,0,0,0,132);step(r,CJ_A,0,0,165);CHECK(black(r,45,100));cj_destroy(r);
}
static void test_crank_time_refresh(void) {
    cj_runtime *r=runtime();CHECK(!load(r,"local p=playdate;p.display.setRefreshRate(50);assert(p.display.getRefreshRate()==50);function p.update() assert(p.getCurrentTimeMilliseconds()==1234);assert(p.getCrankPosition()==350);local a,b=p.getCrankChange();assert(a==-10 and b==-10);assert(p.getCrankChange()==0) end"));step(r,0,-10,-10,1234);CHECK(cj_refresh_rate(r)==50);cj_destroy(r);
}
static void test_synth_nonzero(void) {
    cj_runtime *r=runtime();int16_t pcm[1024];
    for(int wave=0;wave<3;++wave) {
        char s[256];snprintf(s,sizeof s,"local s=playdate.sound.synth.new(%d);s:setADSR(0,0,1,0);assert(s:playNote(440,1,1));function playdate.update() end",wave);
        CHECK(!load(r,s));cj_audio(r,pcm,1024,22050);CHECK(!all(pcm,1024,1));int positive=0,negative=0;
        for(int i=0;i<1024;++i){if(pcm[i]>0)positive=1;if(pcm[i]<0)negative=1;}CHECK(positive&&negative);
    }
    cj_destroy(r);
}
static void test_mute_stop(void) {
    cj_runtime *r=runtime();int16_t pcm[512];CHECK(!load(r,"local s=playdate.sound.synth.new();s:playNote(440);function playdate.update() if playdate.buttonIsPressed(playdate.kButtonA) then s:setVolume(0) else s:stop() end end"));
    cj_audio(r,pcm,512,22050);CHECK(!all(pcm,512,1));step(r,CJ_A,0,0,0);cj_audio(r,pcm,512,22050);CHECK(all(pcm,512,1));
    CHECK(!load(r,"local s=playdate.sound.synth.new();s:playNote(440);function playdate.update() s:stop() end"));step(r,0,0,0,0);cj_audio(r,pcm,512,22050);CHECK(all(pcm,512,1));cj_destroy(r);
}
static void test_envelope(void) { cj_runtime *r=runtime();int16_t pcm[1024];CHECK(!load(r,"local s=playdate.sound.synth.new();s:setADSR(.002,.002,.5,.01);s:playNote(440,1,.01);function playdate.update() end"));cj_audio(r,pcm,1024,22050);CHECK(!all(pcm,400,1));CHECK(all(pcm+500,524,1));cj_destroy(r); }
static void test_failure_silences(void) { cj_runtime *r=runtime();int16_t pcm[128];CHECK(!load(r,"local s=playdate.sound.synth.new();s:playNote(440);function playdate.update() error('boom') end"));cj_input in={0};CHECK(cj_step(r,&in)!=0);cj_audio(r,pcm,128,22050);CHECK(all(pcm,128,1));cj_destroy(r); }
static void test_restart_lifetime(void) {
    for(int i=0;i<100;++i) {
        cj_runtime *r=runtime();CHECK(!load(r,"local a,b,c=playdate.sound.synth.new(),playdate.sound.synth.new(),playdate.sound.synth.new();a:playNote(440);function playdate.update() playdate.graphics.clear(0) end"));
        step(r,0,0,0,0);CHECK(!load(r,empty));size_t baseline=cj_heap_used(r);CHECK(!load(r,empty));CHECK(cj_heap_used(r)==baseline);CHECK(cj_framebuffer(r)[0]==255);
        int16_t pcm[64];cj_audio(r,pcm,64,22050);CHECK(all(pcm,64,1));CHECK(r->voices[0].allocated==0);cj_destroy(r);
    }
}
static void test_gc_voices(void) { cj_runtime *r=runtime();CHECK(!load(r,"function playdate.update() end"));for(int i=0;i<20;++i){CHECK(!load(r,"local voices={};for i=1,8 do voices[i]=playdate.sound.synth.new() end;function playdate.update() end"));}CHECK(load(r,"local voices={};for i=1,9 do voices[i]=playdate.sound.synth.new() end")!=0);CHECK(strstr(cj_error(r),"synth limit"));cj_destroy(r); }
static void test_mutated_update(void) { cj_runtime *r=runtime();CHECK(!load(r,"function playdate.update() playdate.update=nil end"));step(r,0,0,0,0);cj_input in={0};CHECK(cj_step(r,&in)!=0);CHECK(strstr(cj_error(r),"update must remain"));CHECK(load(r,"playdate={}")!=0);CHECK(strstr(cj_error(r),"must define"));cj_destroy(r); }
static void test_invalid_audio_rate(void) { cj_runtime *r=runtime();CHECK(!load(r,empty));int16_t pcm[16];memset(pcm,127,sizeof pcm);cj_audio(r,pcm,16,0);CHECK(all(pcm,16,1));cj_destroy(r); }
static void test_c_work_escape(void) {
    cj_runtime *r=runtime(); CHECK(load(r,"string.rep('',math.maxinteger)")!=0);
    CHECK(strstr(cj_error(r),"work budget")); CHECK(!load(r,"assert(table.move==nil);function playdate.update() end")); cj_destroy(r);
}
static void test_instance_isolation(void) {
    cj_runtime *a=runtime(), *b=runtime(); CHECK(!load(a,"local s=playdate.sound.synth.new();s:playNote(440);function playdate.update() playdate.graphics.clear(0) end"));
    CHECK(!load(b,empty)); step(a,0,0,0,0); CHECK(cj_framebuffer(a)[0]==0);CHECK(cj_framebuffer(b)[0]==255);
    int16_t pcm[64];cj_audio(b,pcm,64,22050);CHECK(all(pcm,64,1));cj_destroy(a);step(b,0,0,0,0);cj_destroy(b);
}
static void test_button_argument_range(void) {
    cj_runtime *r=runtime();CHECK(load(r,"playdate.buttonIsPressed(4294967297)")!=0);
    CHECK(strstr(cj_error(r),"unsupported button"));CHECK(load(r,"playdate.buttonIsPressed(3)")!=0);cj_destroy(r);
}
int main(void) {
    RUN(test_button_argument_range);
    RUN(test_c_work_escape);RUN(test_instance_isolation);
    RUN(test_valid);RUN(test_corrupt);RUN(test_binary);RUN(test_source_bound);RUN(test_heap);
    RUN(test_infinite_load);RUN(test_infinite_step);RUN(test_sandbox);RUN(test_unsupported);
    RUN(test_rect_clip);RUN(test_line_huge);RUN(test_circle_huge);RUN(test_circle_clip);RUN(test_geometry_reject);
    RUN(test_xor);RUN(test_native_budget);RUN(test_font);RUN(test_input_framebuffer);RUN(test_crank_time_refresh);
    RUN(test_synth_nonzero);RUN(test_mute_stop);RUN(test_envelope);RUN(test_failure_silences);RUN(test_restart_lifetime);
    RUN(test_gc_voices);RUN(test_mutated_update);RUN(test_invalid_audio_rate);
    printf("RESULT tests=%u checks=%u failures=0\n",tests,checks);return 0;
}
