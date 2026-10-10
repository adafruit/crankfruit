#!/usr/bin/env python3
"""Bounded offline Playdate PDI/PDT conversion. Python stdlib only, never USB.

Original implementation from CC0 cranksters format documentation at commit
e7be3ff0141b7cd3b9f008737eda1f0539aca45c. SPDX-License-Identifier: MIT
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import zlib

PIN = "e7be3ff0141b7cd3b9f008737eda1f0539aca45c"
PDI = b"Playdate IMG"
PDT = b"Playdate IMT"
COMPRESSED = 0x80000000


class AssetError(ValueError):
    """Malformed, unsupported or over-budget asset, without partial decoding."""


@dataclass(frozen=True)
class Limits:
    max_input: int = 16 * 1024 * 1024
    max_raw: int = 16 * 1024 * 1024
    max_side: int = 2048
    max_pixels: int = 4 * 1024 * 1024
    max_total_pixels: int = 8 * 1024 * 1024
    max_cells: int = 1024


DEFAULT_LIMITS = Limits()


def require(condition, message):
    if not condition:
        raise AssetError(message)


def dimensions(width, height, limits=DEFAULT_LIMITS):
    require(type(width) is int and type(height) is int, "dimensions must be integers")
    require(1 <= width <= limits.max_side and 1 <= height <= limits.max_side,
            "dimensions outside allowed range")
    require(width * height <= limits.max_pixels, "image pixel budget exceeded")


def _bit(plane, stride, x, y):
    return (plane[y * stride + x // 8] >> (7 - x % 8)) & 1


def _set(plane, stride, x, y, value):
    if value:
        plane[y * stride + x // 8] |= 128 >> (x % 8)


@dataclass(frozen=True)
class Image:
    """Normalized tight-stride MSB-first planes; white=1, opaque=1.

    Transparent pixel colors and end-of-row padding are canonical zero.
    Stride is ceil(width/8), not the source cell's 4-byte alignment.
    """
    width: int
    height: int
    pixels: bytes
    alpha: bytes

    def __post_init__(self):
        dimensions(self.width, self.height)
        require(type(self.pixels) is bytes and type(self.alpha) is bytes,
                "planes must be immutable bytes")
        size = self.stride * self.height
        require(len(self.pixels) == size and len(self.alpha) == size,
                "plane size does not match dimensions")
        mask = (1 << ((8 - self.width % 8) % 8)) - 1
        for y in range(self.height):
            last = (y + 1) * self.stride - 1
            require((self.pixels[last] | self.alpha[last]) & mask == 0,
                    "nonzero row padding")
        require(all((p & ~a) == 0 for p, a in zip(self.pixels, self.alpha)),
                "transparent pixel colors must be canonical zero")

    @property
    def stride(self):
        return (self.width + 7) // 8

    @property
    def mask(self):
        """Native-compositor terminology for the opacity plane."""
        return self.alpha

    def pixel(self, x, y):
        require(0 <= x < self.width and 0 <= y < self.height, "pixel outside image")
        return (_bit(self.pixels, self.stride, x, y),
                _bit(self.alpha, self.stride, x, y))


@dataclass(frozen=True)
class ImageTable:
    images: tuple[Image, ...]
    columns: int


def from_rows(rows):
    """Create original pixels: '#' black, '.' white, ' ' transparent."""
    require(bool(rows) and bool(rows[0]), "empty rows")
    width, height = len(rows[0]), len(rows)
    dimensions(width, height)
    stride = (width + 7) // 8
    pixels, alpha = bytearray(stride * height), bytearray(stride * height)
    for y, row in enumerate(rows):
        require(len(row) == width, "unequal row widths")
        for x, value in enumerate(row):
            require(value in "#. ", "unknown row character")
            _set(pixels, stride, x, y, value == ".")
            _set(alpha, stride, x, y, value != " ")
    return Image(width, height, bytes(pixels), bytes(alpha))


def _unwrap(data, magic, limits):
    require(isinstance(data, bytes), "input must be bytes")
    require(16 <= len(data) <= limits.max_input, "input size outside budget")
    require(data[:12] == magic, "wrong image signature")
    flags, = struct.unpack_from("<I", data, 12)
    require(flags in (0, COMPRESSED), "unknown file flags")
    if not flags:
        require(len(data) - 16 <= limits.max_raw, "raw size exceeds budget")
        return data[16:], None
    require(len(data) >= 32, "truncated compression header")
    size, width, height, extra = struct.unpack_from("<4I", data, 16)
    require(0 < size <= limits.max_raw, "decompression budget exceeded")
    dimensions(width, height, limits)
    inflater = zlib.decompressobj()
    try:
        raw = inflater.decompress(data[32:], size + 1)
    except zlib.error as error:
        raise AssetError("invalid zlib stream") from error
    require(len(raw) == size, "decompressed size mismatch")
    require(inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail,
            "truncated, overlong or concatenated zlib stream")
    return raw, (width, height, extra)


def _cell_header(cell, limits):
    require(len(cell) >= 16, "truncated cell header")
    cw, ch, stride, left, right, top, bottom, flags = struct.unpack_from("<8H", cell)
    require(flags & ~3 == 0, "unknown cell flags")
    require((cw == 0) == (ch == 0), "inconsistent empty cell")
    require(stride % 4 == 0 and stride >= (cw + 7) // 8,
            "invalid cell row stride")
    if not cw:
        require(stride == 0 and flags != 0, "unsupported empty opaque cell")
    width, height = left + cw + right, top + ch + bottom
    dimensions(width, height, limits)
    expected = 16 + stride * ch * (2 if flags else 1)
    require(expected <= limits.max_raw and len(cell) == expected,
            "cell data length mismatch")
    return cw, ch, stride, left, top, flags, width, height


def _decode_cell(cell, limits):
    cw, ch, stride, left, top, flags, width, height = _cell_header(cell, limits)
    out_stride = (width + 7) // 8
    pixels = bytearray(out_stride * height)
    alpha = bytearray(out_stride * height)
    color = cell[16:16 + stride * ch]
    mask = cell[16 + stride * ch:] if flags else None
    # Match the referenced pdi2png converter: no alpha flag means opaque white
    # outside a cropped color cell; alpha cells have transparent cropped edges.
    if not flags:
        for y in range(height):
            for x in range(width):
                _set(pixels, out_stride, x, y, 1)
                _set(alpha, out_stride, x, y, 1)
    for y in range(ch):
        for x in range(cw):
            opaque = _bit(mask, stride, x, y) if flags else 1
            dx, dy = left + x, top + y
            bit = 128 >> (dx % 8)
            offset = dy * out_stride + dx // 8
            pixels[offset] &= ~bit
            if opaque:
                _set(pixels, out_stride, dx, dy, _bit(color, stride, x, y))
                _set(alpha, out_stride, dx, dy, 1)
    return Image(width, height, bytes(pixels), bytes(alpha))


def decode_pdi(data, limits=DEFAULT_LIMITS):
    raw, header = _unwrap(data, PDI, limits)
    image = _decode_cell(raw, limits)
    if header:
        require(header == (image.width, image.height, 0), "compressed image header mismatch")
    return image


def decode_pdt(data, limits=DEFAULT_LIMITS):
    raw, header = _unwrap(data, PDT, limits)
    require(len(raw) >= 4, "truncated image table header")
    count, columns = struct.unpack_from("<2H", raw)
    require(1 <= count <= limits.max_cells and 1 <= columns <= count,
            "invalid image table count or columns")
    base = 4 + 4 * count
    require(base <= len(raw), "truncated cell offset table")
    offsets = [0] + list(struct.unpack_from("<%dI" % count, raw, 4))
    require(offsets[-1] == len(raw) - base, "table end offset mismatch")
    require(all(b - a >= 16 for a, b in zip(offsets, offsets[1:])),
            "nonmonotonic or overlapping cell offsets")
    headers, total = [], 0
    for a, b in zip(offsets, offsets[1:]):
        require(b <= len(raw) - base, "cell offset outside table")
        h = _cell_header(raw[base + a:base + b], limits)
        total += h[-2] * h[-1]
        require(total <= limits.max_total_pixels, "table pixel budget exceeded")
        headers.append(h)
    # The notes distinguish a sequential row (columns==count) from a matrix.
    if columns != count:
        require(all(h[-2:] == headers[0][-2:] for h in headers), "unequal matrix cell sizes")
    if header:
        require(header == (*headers[0][-2:], count), "compressed table header mismatch")
    return ImageTable(tuple(_decode_cell(raw[base + a:base + b], limits)
                            for a, b in zip(offsets, offsets[1:])), columns)


def _encode_cell(image, crop):
    width, height, row = image.width, image.height, image.stride
    transparent = any(not _bit(image.alpha, row, x, y)
                      for y in range(height) for x in range(width))
    left, top, right, bottom = 0, 0, width, height
    if crop and transparent:
        left, top, right, bottom = width, height, 0, 0
        for y in range(height):
            for x in range(width):
                if _bit(image.alpha, row, x, y):
                    left = min(left, x); right = max(right, x + 1)
                    top = min(top, y); bottom = max(bottom, y + 1)
        if right:
            pass
        else:
            left, top, right, bottom = 0, 0, 1, 1  # portable transparent cell
    cw, ch = right - left, bottom - top
    stride = ((cw + 31) // 32) * 4
    pixels, alpha = bytearray(stride * ch), bytearray(stride * ch)
    for y in range(ch):
        for x in range(cw):
            color, opaque = image.pixel(x + left, y + top)
            _set(pixels, stride, x, y, color)
            _set(alpha, stride, x, y, opaque)
    header = struct.pack("<8H", cw, ch, stride, left, width - right,
                         top, height - bottom, 1 if transparent else 0)
    return header + pixels + (alpha if transparent else b"")


def _wrap(magic, raw, width, height, extra, compressed):
    require(len(raw) <= DEFAULT_LIMITS.max_raw, "encoded raw budget exceeded")
    if compressed:
        return magic + struct.pack("<5I", COMPRESSED, len(raw), width, height, extra) + zlib.compress(raw)
    return magic + struct.pack("<I", 0) + raw


def encode_pdi(image, *, compressed=True, crop=True):
    return _wrap(PDI, _encode_cell(image, crop), image.width, image.height, 0, compressed)


def encode_pdt(images, *, columns=None, compressed=True, crop=True):
    images = tuple(images)
    count = len(images)
    columns = count if columns is None else columns
    require(type(columns) is int and 1 <= count <= DEFAULT_LIMITS.max_cells
            and 1 <= columns <= count, "invalid table size or columns")
    require(sum(i.width * i.height for i in images) <= DEFAULT_LIMITS.max_total_pixels,
            "table pixel budget exceeded")
    if columns != count:
        require(all((i.width, i.height) == (images[0].width, images[0].height) for i in images),
                "unequal matrix cell sizes")
    cells = [_encode_cell(image, crop) for image in images]
    offsets, end = [], 0
    for cell in cells:
        end += len(cell); offsets.append(end)
    raw = struct.pack("<2H", count, columns) + struct.pack("<%dI" % count, *offsets) + b"".join(cells)
    return _wrap(PDT, raw, images[0].width, images[0].height, count, compressed)


def pack_atlas(images, *, columns=4, padding=1):
    """Create an original/authorized sprite atlas plus rectangle metadata."""
    images = tuple(images)
    require(1 <= len(images) <= DEFAULT_LIMITS.max_cells, "invalid atlas count")
    require(type(columns) is int and 1 <= columns <= DEFAULT_LIMITS.max_cells,
            "invalid atlas columns")
    require(type(padding) is int and 0 <= padding <= 64, "invalid atlas padding")
    columns = min(columns, len(images))
    cw, ch = max(i.width for i in images), max(i.height for i in images)
    width = columns * (cw + padding) + padding
    height = ((len(images) + columns - 1) // columns) * (ch + padding) + padding
    dimensions(width, height)
    stride = (width + 7) // 8
    pixels, alpha = bytearray(stride * height), bytearray(stride * height)
    rectangles = []
    for number, image in enumerate(images):
        left = padding + number % columns * (cw + padding)
        top = padding + number // columns * (ch + padding)
        rectangles.append(dict(x=left, y=top, width=image.width, height=image.height))
        for y in range(image.height):
            for x in range(image.width):
                color, opaque = image.pixel(x, y)
                _set(pixels, stride, left + x, top + y, color)
                _set(alpha, stride, left + x, top + y, opaque)
    return Image(width, height, bytes(pixels), bytes(alpha)), rectangles


def pack_native_atlas(images):
    """Return (atlas_bytes, descriptor_bytes) for the Fruit Jam compositor.

    Every descriptor is exactly struct '<HHII': width,height,pixel_offset,
    mask_offset. Offsets refer to the common atlas blob. Tight-stride pixel
    bytes immediately precede each same-sized opacity plane, MSB-first.
    """
    images = tuple(images)
    require(1 <= len(images) <= 256, "native atlas needs 1..256 images")
    require(all(i.width <= 400 and i.height <= 240 for i in images),
            "native sprite exceeds 400x240 compositor bounds")
    require(sum(len(i.pixels) + len(i.alpha) for i in images) <= 262144,
            "native atlas exceeds Canvas 256KiB loading budget")
    require(sum(i.width * i.height for i in images) <= DEFAULT_LIMITS.max_total_pixels,
            "native atlas pixel budget exceeded")
    atlas, descriptors = bytearray(), bytearray()
    for image in images:
        pixel_offset = len(atlas)
        mask_offset = pixel_offset + len(image.pixels)
        descriptors.extend(struct.pack("<HHII", image.width, image.height,
                                       pixel_offset, mask_offset))
        atlas.extend(image.pixels); atlas.extend(image.alpha)
    return bytes(atlas), bytes(descriptors)


def write_png(image, path):
    """Reference preview, 8-bit grayscale+alpha PNG. No external image library."""
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    rows = bytearray()
    for y in range(image.height):
        rows.append(0)
        for x in range(image.width):
            color, opaque = image.pixel(x, y)
            rows.extend((color * 255, opaque * 255))
    header = struct.pack(">2I5B", image.width, image.height, 8, 4, 0, 0, 0)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) +
                           chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def write_bundle(images, directory, *, columns=None, provenance=None, previews=True):
    """New directory only; tight-stride pixel/alpha blobs plus versioned JSON."""
    images = tuple(images)
    require(1 <= len(images) <= DEFAULT_LIMITS.max_cells, "invalid bundle count")
    require(sum(i.width * i.height for i in images) <= DEFAULT_LIMITS.max_total_pixels,
            "bundle pixel budget exceeded")
    columns = len(images) if columns is None else columns
    require(type(columns) is int and 1 <= columns <= len(images), "invalid bundle columns")
    records, offset = [], 0
    for image in images:
        records.append(dict(width=image.width, height=image.height, stride=image.stride,
                            offset=offset, length=len(image.pixels)))
        offset += len(image.pixels)
    pixels = b"".join(i.pixels for i in images)
    alpha = b"".join(i.alpha for i in images)
    manifest = dict(format="crankfruit-1bit-assets", version=1, columns=columns,
                    bit_order="MSB-first", white=1, opaque=1, frames=records,
                    pixels_sha256=hashlib.sha256(pixels).hexdigest(),
                    alpha_sha256=hashlib.sha256(alpha).hexdigest(),
                    source=provenance or {}, format_reference_commit=PIN)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "pixels.bin").write_bytes(pixels)
    (directory / "alpha.bin").write_bytes(alpha)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if previews:
        for number, image in enumerate(images):
            write_png(image, directory / ("frame-%04d.png" % number))
    return manifest


def read_bundle(directory):
    """Read fixed file names only; validate counts, lengths, hashes and pixels."""
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    require(manifest_path.stat().st_size <= 1024 * 1024, "manifest too large")
    try:
        m = json.loads(manifest_path.read_text())
        require(m["format"] == "crankfruit-1bit-assets" and m["version"] == 1,
                "unsupported bundle format")
        require(m["bit_order"] == "MSB-first" and m["white"] == 1 and m["opaque"] == 1,
                "unsupported plane layout")
        require(1 <= len(m["frames"]) <= DEFAULT_LIMITS.max_cells, "invalid frame count")
        blobs = []
        for name in ("pixels", "alpha"):
            path = directory / (name + ".bin")
            require(path.stat().st_size <= DEFAULT_LIMITS.max_raw, "plane blob too large")
            blob = path.read_bytes()
            require(hashlib.sha256(blob).hexdigest() == m[name + "_sha256"], "plane hash mismatch")
            blobs.append(blob)
        images, offset, total = [], 0, 0
        for frame in m["frames"]:
            w, h = frame["width"], frame["height"]
            dimensions(w, h)
            total += w * h
            require(total <= DEFAULT_LIMITS.max_total_pixels, "bundle pixel budget exceeded")
            length = ((w + 7) // 8) * h
            require(frame["stride"] == (w + 7) // 8 and frame["offset"] == offset
                    and frame["length"] == length, "invalid bundle frame layout")
            images.append(Image(w, h, blobs[0][offset:offset + length], blobs[1][offset:offset + length]))
            offset += length
        require(all(len(blob) == offset for blob in blobs), "trailing or truncated plane data")
        require(type(m["columns"]) is int and 1 <= m["columns"] <= len(images), "invalid columns")
        return ImageTable(tuple(images), m["columns"])
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise AssetError("malformed bundle manifest") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    dec = sub.add_parser("decode", help="PDI/PDT -> new normalized asset directory")
    dec.add_argument("source", type=Path); dec.add_argument("output", type=Path)
    enc = sub.add_parser("encode", help="normalized bundle -> new PDI/PDT file")
    enc.add_argument("source", type=Path); enc.add_argument("output", type=Path)
    enc.add_argument("--uncompressed", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "decode":
            require(args.source.stat().st_size <= DEFAULT_LIMITS.max_input, "input too large")
            data = args.source.read_bytes()
            if data.startswith(PDI):
                table = ImageTable((decode_pdi(data),), 1)
            else:
                table = decode_pdt(data)
            write_bundle(table.images, args.output, columns=table.columns,
                         provenance=dict(name=args.source.name, sha256=hashlib.sha256(data).hexdigest()))
        else:
            table = read_bundle(args.source)
            require(args.output.suffix.lower() in (".pdi", ".pdt"), "output must be .pdi or .pdt")
            if args.output.suffix.lower() == ".pdi":
                require(len(table.images) == 1, "PDI needs exactly one image")
                data = encode_pdi(table.images[0], compressed=not args.uncompressed)
            else:
                data = encode_pdt(table.images, columns=table.columns, compressed=not args.uncompressed)
            with args.output.open("xb") as target:
                target.write(data)
    except (AssetError, OSError) as error:
        parser.exit(2, "asset conversion failed: %s\n" % error)


if __name__ == "__main__":
    main()
