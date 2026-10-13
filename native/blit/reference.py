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


def blit16(src, dst):
    """1.6x: output (x, y) in rows 48..431 shows source (x*5//8, (y-48)*5//8)."""
    if len(src) != 12480 or len(dst) != 38400:
        raise ValueError("blit16 needs 12480-byte source and 38400-byte destination")
    if src is dst:
        raise ValueError("buffers must not overlap")
    for y in range(480):
        for xb in range(80):
            value = 0
            if 48 <= y < 432:
                sy = (y - 48) * 5 // 8
                for bit in range(8):
                    sx = (xb * 8 + bit) * 5 // 8
                    if src[sy * 52 + sx // 8] & (128 >> (sx % 8)):
                        value |= 1 << bit
            dst[y * 80 + xb] = value
    return 38400


def _bit(src, sx, sy):
    return (src[sy * 52 + sx // 8] >> (7 - sx % 8)) & 1


def blit2(src, dst, mode, white=3):
    """2-bit greyscale, 4 pixels per byte (pixel x at bits 2*(x%4)), level `white` = white.

    mode 0: 1x centred; 1: 1.6x sharp; 2: 1.6x smooth (area coverage, levels 0..white).
    white 2 = Playdate-like ~50% grey, 3 = bright ~75%.
    """
    if len(src) != 12480 or len(dst) != 76800 or mode not in (0, 1, 2) or white not in (2, 3):
        raise ValueError("blit2 needs 12480-byte source, 76800-byte destination, mode 0..2")
    if src is dst:
        raise ValueError("buffers must not overlap")
    for i in range(76800):
        dst[i] = 0
    for y in range(480):
        for x in range(640):
            level = 0
            if mode == 0:
                if 120 <= y < 360 and 120 <= x < 520:
                    level = white * _bit(src, x - 120, y - 120)
            elif 48 <= y < 432:
                oy = y - 48
                if mode == 1:
                    level = white * _bit(src, x * 5 // 8, oy * 5 // 8)
                else:
                    x0, y0 = x * 5, oy * 5
                    covered = 0
                    for sy in range(y0 // 8, min((y0 + 4) // 8, 239) + 1):
                        for sx in range(x0 // 8, min((x0 + 4) // 8, 399) + 1):
                            if _bit(src, sx, sy):
                                covered += ((min(x0 + 5, sx * 8 + 8) - max(x0, sx * 8)) *
                                            (min(y0 + 5, sy * 8 + 8) - max(y0, sy * 8)))
                    level = (covered * white * 2 + 25) // 50
            dst[y * 160 + x // 4] |= level << (2 * (x % 4))
    return 76800
