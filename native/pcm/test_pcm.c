/* SPDX-License-Identifier: MIT */
#include "pcm.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned long checks;
#define CHECK(x) do {++checks;if(!(x)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint32_t seed=0x2350ca71;
static unsigned rng(void){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
static void equal(const uint8_t*a,const uint8_t*b,size_t n){for(size_t i=0;i<n;++i)CHECK(a[i]==b[i]);}
int main(void){
    uint8_t dst[8194],src[8194],expected[8194],original[8194];
    for(unsigned round=0;round<12000;++round){
        for(size_t i=0;i<sizeof dst;++i){dst[i]=(uint8_t)rng();src[i]=(uint8_t)rng();}
        memcpy(expected,dst,sizeof dst);memcpy(original,src,sizeof src);
        size_t dl=rng()%8193,sl=rng()%8193,offd=rng()%(dl+1),offs=rng()%(sl+1);
        size_t max=dl-offd<sl-offs?dl-offd:sl-offs,count=rng()%(max+1);
        for(size_t i=0;i<count;++i)expected[1+offd+i]=src[1+offs+i];
        CHECK(cf_pcm_copy(dst+1,dl,src+1,sl,offd,offs,count)==0);
        equal(dst,expected,sizeof dst);equal(src,original,sizeof src);
    }
    memcpy(expected,dst,sizeof dst);
#define BAD(D,DL,S,SL,DO,SO,N,E) do{CHECK(cf_pcm_copy(D,DL,S,SL,DO,SO,N)==E);equal(dst,expected,sizeof dst);}while(0)
    BAD(dst,8194,src,8194,SIZE_MAX,0,1,-1);
    BAD(dst,8194,src,8194,0,SIZE_MAX,1,-1);
    BAD(dst,8194,src,8194,0,0,SIZE_MAX,-1);
    BAD(dst,8194,src,8194,8195,0,0,-1);
    BAD(dst,8194,src,8194,0,8195,0,-1);
    BAD(dst,8194,src,8194,8194,0,1,-1);
    BAD(dst,8194,src,8194,0,8194,1,-1);
    BAD(dst,1048577,src,8194,0,0,0,-1);
    BAD(dst,8194,src,1048577,0,0,0,-1);
    BAD(NULL,1,src,8194,0,0,0,-1);
    BAD(dst,8194,NULL,1,0,0,0,-1);
    BAD(dst,8194,dst,8194,0,0,1,-2);
    BAD(dst,8194,dst+8193,1,0,0,1,-2);
    BAD(dst+1,8193,dst,2,0,0,1,-2);
    BAD(dst,8194,dst,8194,0,8193,1,-2);
#undef BAD
    CHECK(cf_pcm_copy(NULL,0,NULL,0,0,0,0)==0);
    CHECK(cf_pcm_copy(dst,8194,dst,8194,8194,8194,0)==0);
    CHECK(cf_pcm_copy(dst,4097,dst+4097,4097,0,0,4097)==0);
    CHECK(cf_pcm_copy(dst+4097,4097,dst,4097,0,0,4097)==0);
    uint8_t *bigdst=malloc(1048578),*bigsrc=malloc(1048578);
    CHECK(bigdst && bigsrc);
    memset(bigdst,0x6a,1048578);for(size_t i=0;i<1048578;++i)bigsrc[i]=(uint8_t)i;
    CHECK(cf_pcm_copy(bigdst+1,1048576,bigsrc+1,1048576,0,0,1048576)==0);
    equal(bigdst+1,bigsrc+1,1048576);CHECK(bigdst[0]==0x6a);CHECK(bigdst[1048577]==0x6a);
    free(bigdst);free(bigsrc);
    printf("PASS %lu checks; 12000 randomized guarded copies, maxima, bounds, aliases, zero-length\n",checks);
    return 0;
}
