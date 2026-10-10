"""Independent byte copy reference; distinct-view aliasing is caller checked."""
def copy_into(dst, src, dst_offset, src_offset, count):
    for value in (dst_offset, src_offset, count):
        if type(value) is not int:
            raise TypeError("offsets/count must be integers")
        if not 0 <= value <= 1048576:
            raise ValueError("offset/count exceeds bound")
    dst = memoryview(dst).cast('B')
    src = memoryview(src).cast('B')
    if dst.readonly:
        raise TypeError("destination is read-only")
    if (len(dst) > 1048576 or len(src) > 1048576 or dst_offset > len(dst) or
            src_offset > len(src) or count > len(dst) - dst_offset or count > len(src) - src_offset):
        raise ValueError("buffer/range exceeds bound")
    for i in range(count):
        dst[dst_offset + i] = src[src_offset + i]
    return count
