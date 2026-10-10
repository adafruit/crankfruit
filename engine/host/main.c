/* Desktop transport only. Core never includes SDL or performs file IO. */
#include "crankjam.h"
#ifndef CJ_NO_SDL
#include <SDL.h>
#endif
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define SOURCE_MAX 131072u
#define HEAP_DEFAULT 262144u

typedef struct { unsigned long frame; uint32_t buttons; float angle,delta; } event;
static void usage(const char *exe) {
    fprintf(stderr,"Usage: %s SOURCE.lua [--headless] [--frames N] [--heap BYTES]\n"
        "  [--input-script FILE] [--pbm FINAL.pbm] [--wav AUDIO.wav] [--sample-rate HZ]\n"
        "Input rows: frame buttons crank_degrees crank_delta; # comments allowed.\n"
        "Rows strictly increasing, zero-based; buttons/angle held, delta per event only.\n"
        "Buttons: Left=1 Right=2 Up=4 Down=8 B=16 A=32 (sum for combinations).\n"
        "SDL controls: arrows, Z/Space=A, X=B, Q/E crank, Esc quits.\n",exe);
}
static unsigned long number(const char *s,unsigned long min,unsigned long max) {
    char *end; errno=0; unsigned long v=strtoul(s,&end,10);
    if (errno || !s[0] || *end || s[0]=='-' || v<min || v>max) { fprintf(stderr,"invalid numeric option: %s\n",s); exit(2); }
    return v;
}
static int le16(FILE *f,uint16_t n) { return fputc(n&255,f)!=EOF && fputc(n>>8,f)!=EOF; }
static int le32(FILE *f,uint32_t n) { return le16(f,(uint16_t)n) && le16(f,(uint16_t)(n>>16)); }
static int wav_header(FILE *f,uint32_t count,unsigned rate) {
    return fseek(f,0,SEEK_SET)==0 && fwrite("RIFF",1,4,f)==4 && le32(f,36+count*2) &&
        fwrite("WAVEfmt ",1,8,f)==8 && le32(f,16) && le16(f,1) && le16(f,1) &&
        le32(f,rate) && le32(f,rate*2) && le16(f,2) && le16(f,16) &&
        fwrite("data",1,4,f)==4 && le32(f,count*2);
}
static int pbm_write(const char *path,const uint8_t *fb) {
    FILE *f=fopen(path,"wb"); if (!f) return 0;
    int ok=fprintf(f,"P4\n%d %d\n",CJ_WIDTH,CJ_HEIGHT)>0;
    for (size_t i=0;i<CJ_FRAME_BYTES && ok;++i) ok=fputc(fb[i]^255,f)!=EOF; /* PBM 1=black */
    if (fclose(f)) ok=0;
    return ok;
}
static event *read_events(const char *path,size_t *count) {
    *count=0; if (!path) return NULL;
    FILE *f=fopen(path,"r"); if (!f) { perror(path); exit(2); }
    size_t cap=64; event *events=malloc(cap*sizeof *events); if (!events) exit(2);
    char row[256]; unsigned line=0;
    while (fgets(row,sizeof row,f)) {
        ++line; char *p=row; while (*p==' ' || *p=='\t') ++p;
        if (!*p || *p=='#' || *p=='\n') continue;
        event e; unsigned buttons; char extra;
        int n=sscanf(p,"%lu %u %f %f %c",&e.frame,&buttons,&e.angle,&e.delta,&extra);
        if (n!=4 || buttons>63 || !isfinite(e.angle) || !isfinite(e.delta) || e.frame>1000000 ||
            (*count && e.frame<=events[*count-1].frame) || *count>=100000) {
            fprintf(stderr,"invalid input row %u in %s\n",line,path); fclose(f); free(events); exit(2);
        }
        e.buttons=buttons;
        if (*count==cap) { cap*=2; event *next=realloc(events,cap*sizeof *events); if (!next) exit(2); events=next; }
        events[(*count)++]=e;
    }
    if (ferror(f)) { perror(path); exit(2); }
    fclose(f); return events;
}
int main(int argc,char **argv) {
    if (argc<2 || !strcmp(argv[1],"--help")) { usage(argv[0]); return argc<2 ? 2 : 0; }
    const char *source_path=argv[1], *input_path=NULL, *pbm_path=NULL, *wav_path=NULL;
    unsigned long frames=0, heap=HEAP_DEFAULT; unsigned rate=22050; int headless=0;
    for (int i=2;i<argc;++i) {
        if (!strcmp(argv[i],"--headless")) { headless=1; continue; }
        if (i+1>=argc) { usage(argv[0]); return 2; }
        const char *opt=argv[i], *value=argv[++i];
        if (!strcmp(opt,"--frames")) frames=number(value,1,1000000);
        else if (!strcmp(opt,"--heap")) heap=number(value,32768,64u*1024u*1024u);
        else if (!strcmp(opt,"--sample-rate")) rate=(unsigned)number(value,8000,192000);
        else if (!strcmp(opt,"--input-script")) input_path=value;
        else if (!strcmp(opt,"--pbm")) pbm_path=value;
        else if (!strcmp(opt,"--wav")) wav_path=value;
        else { usage(argv[0]); return 2; }
    }
#ifdef CJ_NO_SDL
    headless=1;
#endif
    if (headless && !frames) frames=300;
    FILE *source=fopen(source_path,"rb"); if (!source) { perror(source_path); return 2; }
    char *text=malloc(SOURCE_MAX+1); if (!text) { fclose(source); return 2; }
    size_t length=fread(text,1,SOURCE_MAX+1,source); int read_ok=!ferror(source); fclose(source);
    if (!read_ok || !length || length>SOURCE_MAX) { fprintf(stderr,"source unreadable/empty/over 131072 bytes\n"); free(text); return 2; }
    cj_runtime *r=cj_create(heap); if (!r) { fprintf(stderr,"cannot create VM under heap cap\n"); free(text); return 1; }
    if (cj_load_source(r,source_path,text,length)) { fprintf(stderr,"load: %s\n",cj_error(r)); free(text); cj_destroy(r); return 1; }
    free(text); size_t event_count=0, next_event=0; event *events=read_events(input_path,&event_count);
#ifndef CJ_NO_SDL
    SDL_Window *window=NULL; SDL_Renderer *renderer=NULL; SDL_Texture *texture=NULL; SDL_AudioDeviceID device=0;
#endif
    uint32_t *pixels=NULL; int16_t *pcm=malloc((size_t)rate*sizeof *pcm); FILE *wav=NULL; int status=1;
    if (!pcm) goto done;
#ifndef CJ_NO_SDL
    if (!headless) {
        if (SDL_Init(SDL_INIT_VIDEO|SDL_INIT_AUDIO|SDL_INIT_EVENTS)) { fprintf(stderr,"SDL init: %s\n",SDL_GetError()); goto done; }
        window=SDL_CreateWindow("CrankJam — source Lua",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,800,480,SDL_WINDOW_RESIZABLE);
        if (!window) goto sdl_error;
        renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_ACCELERATED);
        if (!renderer) renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_SOFTWARE);
        if (!renderer) goto sdl_error;
        SDL_RenderSetLogicalSize(renderer,CJ_WIDTH,CJ_HEIGHT);
        texture=SDL_CreateTexture(renderer,SDL_PIXELFORMAT_ARGB8888,SDL_TEXTUREACCESS_STREAMING,CJ_WIDTH,CJ_HEIGHT);
        pixels=malloc(CJ_WIDTH*CJ_HEIGHT*sizeof *pixels); if (!texture || !pixels) goto sdl_error;
        SDL_AudioSpec wanted, obtained; SDL_zero(wanted);
        wanted.freq=(int)rate; wanted.format=AUDIO_S16SYS; wanted.channels=1; wanted.samples=1024; wanted.callback=NULL;
        device=SDL_OpenAudioDevice(NULL,0,&wanted,&obtained,0); if (!device) goto sdl_error;
        SDL_PauseAudioDevice(device,0);
        printf("SDL video_driver=%s audio_driver=%s mono_s16 rate=%u queue_mode=1\n",SDL_GetCurrentVideoDriver(),SDL_GetCurrentAudioDriver(),rate);
    }
#endif
    if (wav_path) { wav=fopen(wav_path,"wb"); if (!wav || !wav_header(wav,0,rate)) { perror(wav_path); goto done; } }
    unsigned long completed=0; uint64_t sample_count=0, nonzero=0; int peak=0;
    double square_sum=0, elapsed=0, sample_fraction=0; uint32_t buttons=0; float angle=0;
    int running=1;
    while (running && (!frames || completed<frames)) {
#ifndef CJ_NO_SDL
        uint64_t begin=headless ? 0 : SDL_GetPerformanceCounter();
#endif
        float delta=0;
#ifndef CJ_NO_SDL
        if (!headless) {
            SDL_Event e;
            while (SDL_PollEvent(&e)) if (e.type==SDL_QUIT || (e.type==SDL_KEYDOWN && e.key.keysym.sym==SDLK_ESCAPE)) running=0;
            if (!running) break;
            const Uint8 *keys=SDL_GetKeyboardState(NULL);
            buttons=(keys[SDL_SCANCODE_LEFT]?CJ_LEFT:0u)|(keys[SDL_SCANCODE_RIGHT]?CJ_RIGHT:0u)|
                (keys[SDL_SCANCODE_UP]?CJ_UP:0u)|(keys[SDL_SCANCODE_DOWN]?CJ_DOWN:0u)|
                (keys[SDL_SCANCODE_X]?CJ_B:0u)|((keys[SDL_SCANCODE_Z]||keys[SDL_SCANCODE_SPACE])?CJ_A:0u);
            delta=(keys[SDL_SCANCODE_E]?6.0f:0)-(keys[SDL_SCANCODE_Q]?6.0f:0);
            angle=fmodf(angle+delta+360,360);
        }
#endif
        if (input_path) {
            if (next_event<event_count && events[next_event].frame==completed) {
                event e=events[next_event++]; buttons=e.buttons; angle=e.angle; delta=e.delta;
            } else if (next_event) { buttons=events[next_event-1].buttons; angle=events[next_event-1].angle; delta=0; }
        }
        cj_input in={buttons,angle,delta,(uint32_t)elapsed};
        if (cj_step(r,&in)) { fprintf(stderr,"frame %lu: %s\n",completed,cj_error(r)); goto done; }
        double dt=1.0/cj_refresh_rate(r); elapsed+=dt*1000;
        sample_fraction+=dt*rate; size_t count=(size_t)floor(sample_fraction+1e-9); sample_fraction-=(double)count;
        cj_audio(r,pcm,count,rate); /* Only main thread executes core/audio. */
        if (sample_count+count>(UINT32_MAX-36u)/2u) { fprintf(stderr,"WAV duration limit exceeded\n"); goto done; }
        for (size_t i=0;i<count;++i) {
            int a=abs((int)pcm[i]); if (a>peak) peak=a; if (a) ++nonzero; square_sum+=(double)pcm[i]*pcm[i];
            if (wav && !le16(wav,(uint16_t)pcm[i])) { fprintf(stderr,"WAV write failed\n"); goto done; }
        }
        sample_count+=count;
#ifndef CJ_NO_SDL
        if (!headless) {
            if (SDL_QueueAudio(device,pcm,(Uint32)(count*sizeof *pcm))) goto sdl_error;
            const uint8_t *fb=cj_framebuffer(r);
            for (int y=0;y<CJ_HEIGHT;++y) for (int x=0;x<CJ_WIDTH;++x)
                pixels[y*CJ_WIDTH+x]=(fb[y*CJ_STRIDE+x/8]&(128u>>(unsigned)(x&7))) ? 0xffeeeeeeu : 0xff101810u;
            if (SDL_UpdateTexture(texture,NULL,pixels,CJ_WIDTH*(int)sizeof *pixels) || SDL_RenderClear(renderer) || SDL_RenderCopy(renderer,texture,NULL,NULL)) goto sdl_error;
            SDL_RenderPresent(renderer);
            double used=(double)(SDL_GetPerformanceCounter()-begin)/(double)SDL_GetPerformanceFrequency();
            if (used<dt) SDL_Delay((Uint32)((dt-used)*1000));
            /* Bounded latency; SDL consumes queued PCM, never calls Lua. */
            while (SDL_GetQueuedAudioSize(device)>rate) SDL_Delay(1);
        }
#endif
        ++completed;
    }
    if (pbm_path && !pbm_write(pbm_path,cj_framebuffer(r))) { perror(pbm_path); goto done; }
    if (wav) {
        int ok=wav_header(wav,(uint32_t)sample_count,rate); if (fclose(wav)) ok=0; wav=NULL;
        if (!ok) { fprintf(stderr,"WAV finalize failed\n"); goto done; }
    }
    printf("frames=%lu elapsed_ms=%.3f refresh=%u heap_used=%zu heap_peak=%zu heap_cap=%lu\n",completed,elapsed,cj_refresh_rate(r),cj_heap_used(r),cj_heap_peak(r),heap);
    printf("audio_samples=%" PRIu64 " nonzero=%" PRIu64 " peak=%d rms=%.3f rate=%u\n",sample_count,nonzero,peak,sample_count?sqrt(square_sum/(double)sample_count):0,rate);
    status=0; goto done;
#ifndef CJ_NO_SDL
sdl_error:
    fprintf(stderr,"SDL: %s\n",SDL_GetError());
#endif
done:
    if (wav) fclose(wav);
#ifndef CJ_NO_SDL
    if (device) SDL_CloseAudioDevice(device);
    if (texture) SDL_DestroyTexture(texture);
    if (renderer) SDL_DestroyRenderer(renderer);
    if (window) SDL_DestroyWindow(window);
    if (!headless) SDL_Quit();
#endif
    free(pcm); free(pixels); free(events); cj_destroy(r); return status;
}
