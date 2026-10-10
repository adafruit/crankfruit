"""SPDX-License-Identifier: MIT
Independent pixel-by-pixel oracle. Not a real-time performance promise.

Distinct memoryview aliasing cannot be detected portably. Callers must provide
independent buffers; the native implementation checks complete address spans.
"""
import struct


def compose(target, background, atlas, descriptors, commands):
    if any(target is value for value in (background, atlas, descriptors, commands)):
        raise ValueError("target overlaps input")
    target = memoryview(target).cast("B")
    background = memoryview(background).cast("B")
    atlas = memoryview(atlas).cast("B")
    descriptors = memoryview(descriptors).cast("B")
    commands = memoryview(commands).cast("B")
    if target.readonly:
        raise TypeError("target must be writable")
    if (len(target) != 12480 or len(background) != 12000 or
            len(descriptors) % 12 or len(descriptors) > 256 * 12 or
            len(commands) % 8 or len(commands) > 256 * 8):
        raise ValueError("invalid sizes")
    sprites = list(struct.iter_unpack("<HHII", descriptors))
    draws = list(struct.iter_unpack("<HhhH", commands))
    for w, h, p, m in sprites:
        if not (1 <= w <= 400 and 1 <= h <= 240):
            raise ValueError("invalid dimensions")
        plane = ((w + 7) // 8) * h
        if p + plane > len(atlas) or m + plane > len(atlas):
            raise ValueError("invalid plane offset")
    for sprite_id, x, y, flags in draws:
        if sprite_id >= len(sprites) or flags & ~3:
            raise ValueError("invalid command")
    for y in range(240):
        target[y * 52:y * 52 + 50] = background[y * 50:y * 50 + 50]
    for sprite_id, x, y, flags in draws:
        w, h, p, m = sprites[sprite_id]
        stride = (w + 7) // 8
        for sy in range(h):
            dy = y + (h - 1 - sy if flags & 2 else sy)
            if not 0 <= dy < 240:
                continue
            for sx in range(w):
                dx = x + (w - 1 - sx if flags & 1 else sx)
                if not 0 <= dx < 400:
                    continue
                bit = 128 >> (sx & 7)
                offset = sy * stride + sx // 8
                if atlas[m + offset] & bit:
                    dest = dy * 52 + dx // 8
                    dest_bit = 128 >> (dx & 7)
                    if atlas[p + offset] & bit:
                        target[dest] |= dest_bit
                    else:
                        target[dest] &= 255 ^ dest_bit
    return 12000
