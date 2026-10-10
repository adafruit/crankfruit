/* MIT. Compile the real core unchanged with a bounded allocator seam.
 * No CP allocation, GC, callback, background task or IRQ occurs inside Lua.
 * All dynamic core/Lua storage lives in one CP-owned arena. */
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stddef.h>
#include "arena.h"
#include "internal.h"
#include <stdio.h>
#include "formatter.h"
#undef snprintf
#define snprintf cj_snprintf
typedef union block block;
union block {
    struct { size_t size; block *next, *prev; int used; } h;
    max_align_t align;
};
static block *creating_arena;
static size_t aligned(size_t n) { return (n + sizeof(max_align_t) - 1) / sizeof(max_align_t) * sizeof(max_align_t); }
static void merge(block *b);
static void split(block *b, size_t n) {
    if (b->h.size < n + sizeof(block) + sizeof(max_align_t)) return;
    block *q = (block *)((unsigned char *)(b + 1) + n);
    *q = (block){0}; q->h.size = b->h.size - n - sizeof(block);
    q->h.next = b->h.next; q->h.prev = b;
    if (q->h.next) q->h.next->h.prev = q;
    b->h.next = q; b->h.size = n;
    merge(q); /* q is newly free; never absorb space into a used neighbor. */
}
static void merge(block *b) {
    block *q;
    while ((q = b->h.next) && !q->h.used) {
        b->h.size += sizeof(block) + q->h.size;
        b->h.next = q->h.next;
        if (b->h.next) b->h.next->h.prev = b;
    }
}
static void *arena_malloc_from(block *first, size_t n) {
    if (n > SIZE_MAX - sizeof(max_align_t)) return NULL;
    n = aligned(n);
    for (block *b = first; b; b = b->h.next) {
        if (!b->h.used && b->h.size >= n) {
            split(b, n); b->h.used = 1; return b + 1;
        }
    }
    return NULL;
}
static void arena_free(void *p) {
    if (!p) return;
    block *b = (block *)p - 1; b->h.used = 0;
    merge(b);
    if (b->h.prev && !b->h.prev->h.used) merge(b->h.prev);
}
static void *arena_calloc(size_t count, size_t size) {
    if (size && count > SIZE_MAX / size) return NULL;
    size *= count;
    void *p = arena_malloc_from(creating_arena, size);
    if (p) memset(p, 0, size);
    return p;
}
static void *arena_realloc(void *p, size_t n) {
    if (!p) return arena_malloc_from(creating_arena, n);
    if (!n) { arena_free(p); return NULL; }
    block *b = (block *)p - 1;
    if (n > SIZE_MAX - sizeof(max_align_t)) return NULL;
    size_t need = aligned(n);
    if (b->h.size >= need) { split(b, need); return p; }
    if (b->h.next && !b->h.next->h.used && b->h.size + sizeof(block) + b->h.next->h.size >= need) {
        merge(b); split(b, need); return p;
    }
    block *first = b;
    while (first->h.prev) first = first->h.prev;
    void *q = arena_malloc_from(first, n);
    if (!q) return NULL;
    memcpy(q, p, b->h.size); arena_free(p); return q;
}
/* For realloc(NULL), identify the arena through the actual core's allocator
 * userdata instead of a persistent global pointer. */
static void *arena_realloc_for(cj_runtime *r, void *p, size_t n) {
    if (p) return arena_realloc(p, n);
    block *first = (block *)r - 1;
    while (first->h.prev) first = first->h.prev;
    return arena_malloc_from(first, n);
}
#define calloc arena_calloc
#define free arena_free
#define realloc(ptr, size) arena_realloc_for(r, ptr, size)
#include "../../../src/runtime.c"
#undef calloc
#undef free
#undef realloc
size_t cj_arena_bytes(size_t cap) {
    /* Metadata/alignment and fragmentation reserve; hard physical cap too. */
    return aligned(cap + cap / 2 + sizeof(cj_runtime) + 4096) + sizeof(block);
}
cj_runtime *cj_arena_create(void *storage, size_t bytes, size_t cap) {
    block *first = storage;
    memset(first, 0, sizeof *first); first->h.size = bytes - sizeof *first;
    creating_arena = first;
    cj_runtime *r = cj_create(cap);
    creating_arena = NULL;
    return r;
}
