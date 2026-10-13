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
        "  [--board-scale 1|1.5|1.6|1.6s] [--scaled-pbm FINAL640x480.pbm]\n"
        "--board-scale shows the Fruit Jam 640x480 HDMI output (Tab cycles scales in SDL).\n"
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
/* Board scanout emulation: the 400x240 game inside the Fruit Jam's 640x480 HDMI
 * output, scaled num/den with a fixed nearest-neighbour mapping (the pattern a
 * board blit helper would use). 1.5x alternates 2- and 1-pixel columns/rows;
 * 1.6x maps every 5 game pixels to 8 output pixels. Border is black.
 * "1.6x smooth" previews a 2-bit (4 grey level) framebuffer: each output pixel's
 * grey is the exact area coverage of the game pixels under it, rounded to 4 levels. */
#define BOARD_W 640
#define BOARD_H 480
#define BOARD_LEVELS 4
typedef struct { int num, den, smooth; const char *key, *name; } board_scale;
static const board_scale BOARD_SCALES[]={{1,1,0,"1","1x"},{3,2,0,"1.5","1.5x"},{8,5,0,"1.6","1.6x"},
                                         {8,5,1,"1.6s","1.6x smooth"}};
#define BOARD_SCALE_COUNT 4
static int game_bit(const uint8_t *fb,int sx,int sy) {
    return (fb[sy*CJ_STRIDE+sx/8]&(128u>>(unsigned)(sx&7))) ? 1 : 0;
}
/* Grey level 0 (black) .. BOARD_LEVELS-1 (white); -1 = border outside the game. */
static int board_pixel(const uint8_t *fb,const board_scale *s,int x,int y) {
    int w=CJ_WIDTH*s->num/s->den, h=CJ_HEIGHT*s->num/s->den;
    int ox=(BOARD_W-w)/2, oy=(BOARD_H-h)/2;
    if (x<ox || x>=ox+w || y<oy || y>=oy+h) return -1;
    x-=ox; y-=oy;
    if (!s->smooth) return game_bit(fb,x*s->den/s->num,y*s->den/s->num) ? BOARD_LEVELS-1 : 0;
    /* Output pixel spans [x*den, (x+1)*den) in units of 1/num game pixel. */
    int x0=x*s->den, x1=x0+s->den, y0=y*s->den, y1=y0+s->den, covered=0;
    for (int sy=y0/s->num; sy*s->num<y1 && sy<CJ_HEIGHT; ++sy) {
        int oy0=y0>sy*s->num ? y0 : sy*s->num, oy1=y1<(sy+1)*s->num ? y1 : (sy+1)*s->num;
        for (int sx=x0/s->num; sx*s->num<x1 && sx<CJ_WIDTH; ++sx) {
            if (!game_bit(fb,sx,sy)) continue;
            int ox0=x0>sx*s->num ? x0 : sx*s->num, ox1=x1<(sx+1)*s->num ? x1 : (sx+1)*s->num;
            covered+=(ox1-ox0)*(oy1-oy0);
        }
    }
    int area=s->den*s->den; /* round(covered/area * (levels-1)) */
    return (covered*(BOARD_LEVELS-1)*2+area)/(2*area);
}
static int board_pbm_write(const char *path,const uint8_t *fb,const board_scale *s) {
    FILE *f=fopen(path,"wb"); if (!f) return 0;
    int ok;
    if (s->smooth) { /* grey levels need PGM */
        ok=fprintf(f,"P5\n%d %d\n255\n",BOARD_W,BOARD_H)>0;
        for (int y=0;y<BOARD_H && ok;++y) for (int x=0;x<BOARD_W && ok;++x) {
            int level=board_pixel(fb,s,x,y);
            ok=fputc(level<0 ? 0 : level*255/(BOARD_LEVELS-1),f)!=EOF;
        }
    } else {
        ok=fprintf(f,"P4\n%d %d\n",BOARD_W,BOARD_H)>0;
        for (int y=0;y<BOARD_H && ok;++y) for (int x=0;x<BOARD_W && ok;x+=8) {
            unsigned byte=0;
            for (int k=0;k<8;++k) if (board_pixel(fb,s,x+k,y)!=BOARD_LEVELS-1) byte|=128u>>(unsigned)k; /* PBM 1=black */
            ok=fputc((int)byte,f)!=EOF;
        }
    }
    if (fclose(f)) ok=0;
    return ok;
}
static int board_scale_index(const char *s) {
    for (int i=0;i<BOARD_SCALE_COUNT;++i)
        if (!strcmp(s,BOARD_SCALES[i].key) || !strcmp(s,BOARD_SCALES[i].name)) return i;
    fprintf(stderr,"invalid --board-scale: %s (use 1, 1.5, 1.6 or 1.6s)\n",s); exit(2);
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
    const char *source_path=argv[1], *input_path=NULL, *pbm_path=NULL, *wav_path=NULL, *scaled_pbm_path=NULL;
    unsigned long frames=0, heap=HEAP_DEFAULT; unsigned rate=22050; int headless=0, board=-1;
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
        else if (!strcmp(opt,"--board-scale")) board=board_scale_index(value);
        else if (!strcmp(opt,"--scaled-pbm")) scaled_pbm_path=value;
        else { usage(argv[0]); return 2; }
    }
    if (scaled_pbm_path && board<0) { fprintf(stderr,"--scaled-pbm requires --board-scale\n"); return 2; }
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
        int view_w=board<0 ? CJ_WIDTH : BOARD_W, view_h=board<0 ? CJ_HEIGHT : BOARD_H;
        SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY,"nearest");
        /* Board mode: each 640x480 output pixel is a whole 2x2 block of window pixels. */
        window=SDL_CreateWindow("CrankJam — source Lua",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,
                                board<0 ? 800 : 2*BOARD_W,board<0 ? 480 : 2*BOARD_H,SDL_WINDOW_RESIZABLE);
        if (!window) goto sdl_error;
        renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_ACCELERATED);
        if (!renderer) renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_SOFTWARE);
        if (!renderer) goto sdl_error;
        SDL_RenderSetLogicalSize(renderer,view_w,view_h);
        if (board>=0) {
            SDL_RenderSetIntegerScale(renderer,SDL_TRUE);
            char title[96]; snprintf(title,sizeof title,"CrankJam — Fruit Jam HDMI %s (Tab cycles)",BOARD_SCALES[board].name);
            SDL_SetWindowTitle(window,title);
        }
        texture=SDL_CreateTexture(renderer,SDL_PIXELFORMAT_ARGB8888,SDL_TEXTUREACCESS_STREAMING,view_w,view_h);
        pixels=malloc((size_t)view_w*(size_t)view_h*sizeof *pixels); if (!texture || !pixels) goto sdl_error;
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
            while (SDL_PollEvent(&e)) {
                if (e.type==SDL_QUIT || (e.type==SDL_KEYDOWN && e.key.keysym.sym==SDLK_ESCAPE)) running=0;
                else if (board>=0 && e.type==SDL_KEYDOWN && e.key.keysym.sym==SDLK_TAB && !e.key.repeat) {
                    board=(board+1)%BOARD_SCALE_COUNT;
                    char title[96]; snprintf(title,sizeof title,"CrankJam — Fruit Jam HDMI %s (Tab cycles)",BOARD_SCALES[board].name);
                    SDL_SetWindowTitle(window,title);
                }
            }
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
            int pitch_w=CJ_WIDTH;
            if (board<0) {
                for (int y=0;y<CJ_HEIGHT;++y) for (int x=0;x<CJ_WIDTH;++x)
                    pixels[y*CJ_WIDTH+x]=(fb[y*CJ_STRIDE+x/8]&(128u>>(unsigned)(x&7))) ? 0xffeeeeeeu : 0xff101810u;
            } else {
                /* border, then grey levels 0..3 from the host's black to its white */
                static const uint32_t colour[1+BOARD_LEVELS]={0xff000000u,0xff101810u,0xff5a5f5au,0xffa4a6a4u,0xffeeeeeeu};
                for (int y=0;y<BOARD_H;++y) for (int x=0;x<BOARD_W;++x)
                    pixels[y*BOARD_W+x]=colour[board_pixel(fb,&BOARD_SCALES[board],x,y)+1];
                pitch_w=BOARD_W;
            }
            if (SDL_UpdateTexture(texture,NULL,pixels,pitch_w*(int)sizeof *pixels) || SDL_RenderClear(renderer) || SDL_RenderCopy(renderer,texture,NULL,NULL)) goto sdl_error;
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
    if (scaled_pbm_path && !board_pbm_write(scaled_pbm_path,cj_framebuffer(r),&BOARD_SCALES[board])) { perror(scaled_pbm_path); goto done; }
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
