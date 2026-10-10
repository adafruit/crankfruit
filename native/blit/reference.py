"""Slow reference/fallback for verification; not an audio deadline guarantee."""
def blit(src, dst):
    if len(src) != 12480 or len(dst) != 38400:
        raise ValueError("blit needs 12480-byte source and 38400-byte destination")
    # This portable reference cannot detect aliasing between distinct views.
    # Callers must supply independent buffers. Native module checks addresses.
    if src is dst:
        raise ValueError("buffers must not overlap")
    for y in range(240):
        for x in range(50):
            value = src[y * 52 + x]
            result = 0
            for bit in range(8):
                result |= ((value >> bit) & 1) << (7 - bit)
            dst[9615 + y * 80 + x] = result
    return 12000
