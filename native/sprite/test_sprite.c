/* SPDX-License-Identifier: MIT */
#include "sprite.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned long checks;
#define CHECK(v) do { ++checks; if (!(v)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #v); exit(1); } } while (0)
static uint32_t rng = 0x267159b3;
static unsigned random32(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }
static void put16(uint8_t *p, unsigned v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void put32(uint8_t *p, uint32_t v) { for (unsigned i = 0; i < 4; ++i) p[i] = (uint8_t)(v >> (8*i)); }
static unsigned get16(const uint8_t *p) { return p[0] + 256u*p[1]; }
static int signed16(const uint8_t *p) { unsigned v = get16(p); return v < 32768 ? (int)v : (int)v - 65536; }
static uint32_t get32(const uint8_t *p) { return p[0] + 256u*p[1] + 65536u*p[2] + 16777216u*p[3]; }
static void descriptor(uint8_t *p, unsigned w, unsigned h, uint32_t pixel, uint32_t mask) {
    put16(p,w); put16(p+2,h); put32(p+4,pixel); put32(p+8,mask);
}
static void command(uint8_t *p, unsigned id, int x, int y, unsigned flags) {
    put16(p,id); put16(p+2,(unsigned)x); put16(p+4,(unsigned)y); put16(p+6,flags);
}
static void fill(uint8_t *p, size_t n) { for (size_t i = 0; i < n; ++i) p[i] = (uint8_t)random32(); }
/* Deliberately simple source-pixel traversal, unlike destination-byte production. */
static void oracle(uint8_t *target, const uint8_t *background, const uint8_t *atlas,
                   const uint8_t *descriptors, const uint8_t *commands, size_t n) {
    for (unsigned y = 0; y < 240; ++y) memcpy(target+y*52, background+y*50, 50);
    for (size_t i = 0; i < n; ++i) {
        const uint8_t *c = commands+i*8, *d = descriptors+get16(c)*12;
        unsigned w = get16(d), h = get16(d+2), stride=(w+7)/8, flags=get16(c+6);
        int x=signed16(c+2), y=signed16(c+4);
        for (unsigned sy=0; sy<h; ++sy) for (unsigned sx=0; sx<w; ++sx) {
            int dx=x+(int)((flags&1)?w-1-sx:sx), dy=y+(int)((flags&2)?h-1-sy:sy);
            if (dx<0 || dx>=400 || dy<0 || dy>=240) continue;
            size_t a=sy*stride+sx/8;
            unsigned sbit=128u>>(sx%8), dbit=128u>>((unsigned)dx%8);
            if (!(atlas[get32(d+8)+a]&sbit)) continue;
            uint8_t *out=target+(unsigned)dy*52+(unsigned)dx/8;
            if (atlas[get32(d+4)+a]&sbit) *out|=(uint8_t)dbit;
            else *out&=(uint8_t)~dbit;
        }
    }
}
static void compare(const uint8_t *a, const uint8_t *b, size_t n) {
    for(size_t i=0;i<n;++i) CHECK(a[i]==b[i]);
}
static void valid_cases(void) {
    uint8_t output_guard[12482], expected[12480], bg_guard[12002], atlas_guard[24004];
    uint8_t desc_guard[3074], commands_guard[2050], input_copy[12002+24004+3074+2050];
    uint8_t *out=output_guard+1, *bg=bg_guard+1, *atlas=atlas_guard+1;
    uint8_t *desc=desc_guard+1, *commands=commands_guard+1;
    for(unsigned iteration=0;iteration<1800;++iteration) {
        fill(output_guard,sizeof output_guard); fill(bg_guard,sizeof bg_guard);
        fill(atlas_guard,sizeof atlas_guard); fill(desc_guard,sizeof desc_guard); fill(commands_guard,sizeof commands_guard);
        unsigned nd=1+random32()%32, nc=random32()%33;
        if(iteration==0) nd=nc=256;
        for(unsigned i=0;i<nd;++i) {
            unsigned w=1+random32()%400, h=1+random32()%240;
            if(iteration<400 && i==0) w=iteration+1;
            if(iteration==0) w=h=1;
            size_t plane=((w+7)/8)*h;
            descriptor(desc+i*12,w,h,(uint32_t)(random32()%(12001-plane)),12001+(uint32_t)(random32()%(12001-plane)));
        }
        for(unsigned i=0;i<nc;++i) {
            int x=(int)(random32()%1100)-500,y=(int)(random32()%700)-350;
            if(i==0 && iteration<400) { x=(int)(iteration%17)-8; y=(int)(iteration%7)-3; }
            if(iteration==0) { x=(int)i;y=100; }
            command(commands+i*8,random32()%nd,x,y,random32()%4);
        }
        if(iteration%29==0) for(unsigned i=0;i<nc;++i) command(commands+i*8,0,32767,-32768,i%4);
        memcpy(expected,out,sizeof expected);
        memcpy(input_copy,bg_guard,sizeof bg_guard);
        memcpy(input_copy+sizeof bg_guard,atlas_guard,sizeof atlas_guard);
        memcpy(input_copy+sizeof bg_guard+sizeof atlas_guard,desc_guard,sizeof desc_guard);
        memcpy(input_copy+sizeof bg_guard+sizeof atlas_guard+sizeof desc_guard,commands_guard,sizeof commands_guard);
        uint8_t guard0=output_guard[0],guard1=output_guard[12481];
        oracle(expected,bg,atlas,desc,commands,nc);
        CHECK(cf_compose(out,12480,bg,12000,atlas,24002,desc,nd*12,commands,nc*8)==0);
        compare(out,expected,sizeof expected);
        CHECK(output_guard[0]==guard0); CHECK(output_guard[12481]==guard1);
        compare(input_copy,bg_guard,sizeof bg_guard);
        compare(input_copy+sizeof bg_guard,atlas_guard,sizeof atlas_guard);
        compare(input_copy+sizeof bg_guard+sizeof atlas_guard,desc_guard,sizeof desc_guard);
        compare(input_copy+sizeof bg_guard+sizeof atlas_guard+sizeof desc_guard,commands_guard,sizeof commands_guard);
    }
}
static void edge_cases(void) {
    uint8_t out[12480],original[12480],bg[12000],atlas[24000],desc[3072],commands[2048];
    fill(out,sizeof out); memcpy(original,out,sizeof out); fill(bg,sizeof bg); fill(atlas,sizeof atlas);
    descriptor(desc,400,240,0,12000); command(commands,0,0,0,0);
    /* Maximal image, every bit value and clipping alignment at every edge. */
    for(unsigned flags=0;flags<4;++flags) for(int x=-9;x<=9;++x) for(int y=-1;y<=1;++y) {
        uint8_t expected[12480]; memcpy(expected,out,sizeof out);
        command(commands,0,x,y,flags); oracle(expected,bg,atlas,desc,commands,1);
        CHECK(cf_compose(out,sizeof out,bg,sizeof bg,atlas,sizeof atlas,desc,12,commands,8)==0);
        compare(out,expected,sizeof out);
    }
    descriptor(desc,1,1,0,1); atlas[0]=0; atlas[1]=128;
    command(commands,0,399,239,0);
    CHECK(cf_compose(out,12480,bg,12000,atlas,2,desc,12,commands,8)==0);
    CHECK(!(out[239*52+49]&1));
    atlas[0]=128;
    CHECK(cf_compose(out,12480,bg,12000,atlas,2,desc,12,commands,8)==0);
    CHECK(out[239*52+49]&1);
    CHECK(cf_compose(out,12480,bg,12000,NULL,0,NULL,0,NULL,0)==0);
    memcpy(original,out,sizeof out);
#define BAD(T,TL,B,BL,A,AL,D,DL,C,CL,RC) do { CHECK(cf_compose(T,TL,B,BL,A,AL,D,DL,C,CL)==RC); compare(out,original,sizeof out); } while(0)
    BAD(out,12479,bg,12000,atlas,2,desc,12,commands,8,-1);
    BAD(out,12481,bg,12000,atlas,2,desc,12,commands,8,-1);
    BAD(out,12480,bg,11999,atlas,2,desc,12,commands,8,-1);
    BAD(out,12480,bg,12001,atlas,2,desc,12,commands,8,-1);
    BAD(NULL,12480,bg,12000,atlas,2,desc,12,commands,8,-1);
    BAD(out,12480,NULL,12000,atlas,2,desc,12,commands,8,-1);
    BAD(out,12480,bg,12000,NULL,2,desc,12,commands,8,-1);
    BAD(out,12480,bg,12000,atlas,2,NULL,12,commands,8,-1);
    BAD(out,12480,bg,12000,atlas,2,desc,12,NULL,8,-1);
    BAD(out,12480,bg,12000,atlas,2,desc,11,commands,8,-1);
    BAD(out,12480,bg,12000,atlas,2,desc,3073,commands,8,-1);
    BAD(out,12480,bg,12000,atlas,2,desc,3084,commands,8,-1);
    BAD(out,12480,bg,12000,atlas,2,desc,12,commands,7,-1);
    BAD(out,12480,bg,12000,atlas,2,desc,12,commands,2056,-1);
    for(unsigned w=0;w<=65535;w=w==0?401:65535) {
        descriptor(desc,w,1,0,1); BAD(out,12480,bg,12000,atlas,2,desc,12,commands,8,-3);
        if(w==65535) break;
    }
    for(unsigned h=0;h<=65535;h=h==0?241:65535) {
        descriptor(desc,1,h,0,1); BAD(out,12480,bg,12000,atlas,2,desc,12,commands,8,-3);
        if(h==65535) break;
    }
    descriptor(desc,1,1,UINT32_MAX,1); BAD(out,12480,bg,12000,atlas,2,desc,12,commands,8,-3);
    descriptor(desc,1,1,0,UINT32_MAX); BAD(out,12480,bg,12000,atlas,2,desc,12,commands,8,-3);
    descriptor(desc,9,1,0,1); BAD(out,12480,bg,12000,atlas,2,desc,12,commands,8,-3);
    descriptor(desc,1,1,0,1); descriptor(desc+12,0,1,0,1);
    BAD(out,12480,bg,12000,atlas,2,desc,24,commands,8,-3); /* Unused bad descriptor. */
    command(commands,1,0,0,0); BAD(out,12480,bg,12000,atlas,2,desc,12,commands,8,-4);
    command(commands,0,0,0,4); BAD(out,12480,bg,12000,atlas,2,desc,12,commands,8,-4);
    command(commands,0,0,0,0); command(commands+8,0,0,0,65535);
    BAD(out,12480,bg,12000,atlas,2,desc,12,commands,16,-4); /* Last command invalid. */
    BAD(out,12480,out,12000,atlas,2,desc,12,commands,8,-2);
    BAD(out,12480,bg,12000,out+12479,1,desc,12,commands,8,-2);
    BAD(out,12480,bg,12000,atlas,2,out,12,commands,8,-2);
    BAD(out,12480,bg,12000,atlas,2,desc,12,out,8,-2);
    /* Adjacent spans allowed; both overlap directions rejected. */
    uint8_t adjacent[24480]; fill(adjacent,sizeof adjacent);
    CHECK(cf_compose(adjacent,12480,adjacent+12480,12000,NULL,0,NULL,0,NULL,0)==0);
    CHECK(cf_compose(adjacent+12000,12480,adjacent,12000,NULL,0,NULL,0,NULL,0)==0);
    CHECK(cf_compose(adjacent+11999,12480,adjacent,12000,NULL,0,NULL,0,NULL,0)==-2);
    CHECK(cf_compose(adjacent,12480,adjacent+12479,12000,NULL,0,NULL,0,NULL,0)==-2);
#undef BAD
}
int main(void) { valid_cases(); edge_cases(); printf("PASS %lu checks; 1800 seeded randomized scenes plus edge/error/alias tests\n",checks); return 0; }
