#include "internal.h"
#include "font.h"
#include <stdlib.h>
#include <string.h>
static double coord(lua_State *L, int i) { return cj_number(L, i, -CJ_COORD_LIMIT, CJ_COORD_LIMIT); }
static void pixel(cj_runtime *r, int x, int y) {
    if (x < 0 || x >= CJ_WIDTH || y < 0 || y >= CJ_HEIGHT) return;
    uint8_t *p = &r->framebuffer[y * CJ_STRIDE + x / 8];
    uint8_t bit = (uint8_t)(128u >> (unsigned)(x & 7));
    if (r->color == 2) *p ^= bit;
    else if (r->color == 1) *p |= bit;
    else *p &= (uint8_t)~bit;
}
static int color_arg(lua_State *L, int i) {
    lua_Integer c = luaL_checkinteger(L, i);
    if (c < 0 || c > 2) luaL_error(L, "unsupported graphics color");
    return (int)c;
}
static int l_color(lua_State *L) { cj_args(L, 1, 1); cj_from_lua(L)->color = color_arg(L, 1); return 0; }
static int l_clear(lua_State *L) {
    cj_args(L, 0, 1); int c = lua_gettop(L) ? color_arg(L, 1) : 1;
    cj_charge(L, CJ_WIDTH * CJ_HEIGHT); cj_runtime *r = cj_from_lua(L);
    if (c == 2) for (size_t i = 0; i < CJ_FRAME_BYTES; ++i) r->framebuffer[i] ^= 255;
    else memset(r->framebuffer, c ? 255 : 0, CJ_FRAME_BYTES);
    return 0;
}
/* Liang-Barsky clip first: even enormous lines do bounded raster work. */
static int clip(double p, double q, double *a, double *b) {
    if (p == 0) return q >= 0;
    double t = q / p;
    if (p < 0) { if (t > *b) return 0; if (t > *a) *a = t; }
    else { if (t < *a) return 0; if (t < *b) *b = t; }
    return 1;
}
static void line(lua_State *L, double x0, double y0, double x1, double y1) {
    cj_charge(L, 1);
    double dx = x1-x0, dy = y1-y0, a = 0, b = 1;
    if (!clip(-dx,x0,&a,&b) || !clip(dx,CJ_WIDTH-1-x0,&a,&b) ||
        !clip(-dy,y0,&a,&b) || !clip(dy,CJ_HEIGHT-1-y0,&a,&b)) return;
    int x = (int)lround(x0+a*dx), y = (int)lround(y0+a*dy);
    int ex = (int)lround(x0+b*dx), ey = (int)lround(y0+b*dy);
    int ax = abs(ex-x), ay = -abs(ey-y), sx = x < ex ? 1 : -1, sy = y < ey ? 1 : -1;
    int error = ax+ay;
    cj_charge(L, ax > -ay ? ax+1 : -ay+1);
    for (;;) {
        pixel(cj_from_lua(L),x,y); if (x == ex && y == ey) break;
        int e = error*2;
        if (e >= ay) { error += ay; x += sx; }
        if (e <= ax) { error += ax; y += sy; }
    }
}
static int l_line(lua_State *L) {
    cj_args(L,4,4); double x0=coord(L,1), y0=coord(L,2), x1=coord(L,3), y1=coord(L,4);
    line(L,x0,y0,x1,y1); return 0;
}
static void rect(lua_State *L, int filled) {
    cj_args(L,4,4);
    double x=floor(coord(L,1)), y=floor(coord(L,2));
    double w=floor(cj_number(L,3,0,CJ_COORD_LIMIT)), h=floor(cj_number(L,4,0,CJ_COORD_LIMIT));
    cj_charge(L,1); if (w < 1 || h < 1) return;
    if (!filled) {
        line(L,x,y,x+w-1,y);
        if (h > 1) line(L,x,y+h-1,x+w-1,y+h-1);
        if (h > 2) {
            line(L,x,y+1,x,y+h-2);
            if (w > 1) line(L,x+w-1,y+1,x+w-1,y+h-2);
        }
        return;
    }
    int x0=(int)fmin(CJ_WIDTH,fmax(0,x)), y0=(int)fmin(CJ_HEIGHT,fmax(0,y));
    int x1=(int)fmin(CJ_WIDTH,fmax(0,x+w)), y1=(int)fmin(CJ_HEIGHT,fmax(0,y+h));
    cj_charge(L,(x1-x0)*(y1-y0));
    for (int j=y0;j<y1;++j) for (int i=x0;i<x1;++i) pixel(cj_from_lua(L),i,j);
}
static int l_rect(lua_State *L) { rect(L,0); return 0; }
static int l_fill_rect(lua_State *L) { rect(L,1); return 0; }
static void circle(lua_State *L, int filled) {
    cj_args(L,3,3);
    double x=coord(L,1), y=coord(L,2), rad=cj_number(L,3,0,CJ_COORD_LIMIT);
    int x0=(int)fmin(CJ_WIDTH,fmax(0,ceil(x-rad-0.5))), y0=(int)fmin(CJ_HEIGHT,fmax(0,ceil(y-rad-0.5)));
    int x1=(int)fmin(CJ_WIDTH-1,fmax(-1,floor(x+rad+0.5))), y1=(int)fmin(CJ_HEIGHT-1,fmax(-1,floor(y+rad+0.5)));
    cj_charge(L,1); if (x1 < x0 || y1 < y0) return;
    cj_charge(L,(x1-x0+1)*(y1-y0+1));
    double outer=(rad+0.5)*(rad+0.5), inner=fmax(0,rad-0.5); inner*=inner;
    for (int j=y0;j<=y1;++j) for (int i=x0;i<=x1;++i) {
        double d=((double)i-x)*((double)i-x)+((double)j-y)*((double)j-y);
        if (d <= outer && (filled || d >= inner)) pixel(cj_from_lua(L),i,j);
    }
}
static int l_circle(lua_State *L) { circle(L,0); return 0; }
static int l_fill_circle(lua_State *L) { circle(L,1); return 0; }
static int l_text(lua_State *L) {
    cj_args(L,3,3); size_t n; const unsigned char *text=(const unsigned char *)luaL_checklstring(L,1,&n);
    if (n > 1024) return luaL_error(L,"drawText supports at most 1024 bytes");
    int x=(int)floor(coord(L,2)), y=(int)floor(coord(L,3)), origin=x, maxw=0, lines=1;
    cj_charge(L,(int)n*35+1);
    for (size_t i=0;i<n;++i) {
        unsigned char c=text[i];
        if (c=='\n') { if (x-origin > maxw) maxw=x-origin; x=origin; y+=8; ++lines; continue; }
        if (c>='a' && c<='z') c=(unsigned char)(c-'a'+'A');
        const uint8_t unknown[7]={31,17,1,6,4,0,4}; const uint8_t *rows=unknown;
        for (size_t k=0;k<sizeof cj_font/sizeof cj_font[0];++k) if ((unsigned char)cj_font[k].c==c) { rows=cj_font[k].row; break; }
        for (int j=0;j<7;++j) for (int k=0;k<5;++k) if (rows[j] & (16u>>(unsigned)k)) pixel(cj_from_lua(L),x+k,y+j);
        x+=6;
    }
    if (x-origin > maxw) maxw=x-origin;
    lua_pushinteger(L,maxw ? maxw-1 : 0); lua_pushinteger(L,lines*8-1); return 2;
}
void cj_graphics_bind(lua_State *L) {
    const luaL_Reg api[]={{"clear",l_clear},{"setColor",l_color},{"drawLine",l_line},{"drawRect",l_rect},
        {"fillRect",l_fill_rect},{"drawText",l_text},{"drawCircleAtPoint",l_circle},{"fillCircleAtPoint",l_fill_circle},{NULL,NULL}};
    lua_newtable(L); luaL_setfuncs(L,api,0);
    lua_pushinteger(L,0); lua_setfield(L,-2,"kColorBlack");
    lua_pushinteger(L,1); lua_setfield(L,-2,"kColorWhite");
    lua_pushinteger(L,2); lua_setfield(L,-2,"kColorXOR");
    cj_strict_table(L,"playdate.graphics");
}
