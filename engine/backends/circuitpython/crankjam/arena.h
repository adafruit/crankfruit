/* MIT: bounded, coalescing arena owned by one Python Runtime. */
#pragma once
#include <stddef.h>
#include "crankjam.h"
size_t cj_arena_bytes(size_t heap_cap);
cj_runtime *cj_arena_create(void *storage, size_t bytes, size_t heap_cap);
