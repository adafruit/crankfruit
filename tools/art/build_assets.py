"""Portable code-native one-bit player UI, with exact PDI/PDT roundtrips.

Copyright (c) 2026 Adafruit Industries. SPDX-License-Identifier: MIT
Build dependency: Pillow. All inputs and outputs are relative to this file.
"""
from pathlib import Path
import ast
import hashlib
import json
import math
import re
import sys
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import pd_assets as pd

OUT, PREVIEW = ROOT / "assets", ROOT / "previews"
OUT.mkdir(exist_ok=True)
PREVIEW.mkdir(exist_ok=True)
font_source = (ROOT / "vendor" / "font.h").read_text()
FONT = {ast.literal_eval("'" + char + "'"): [int(n) for n in rows.split(",")]
        for char, rows in re.findall(r"\{'((?:\\.|[^'])*)',\s*\{([^}]+)\}\}", font_source)}
approved_lockup = Image.open(ROOT / "raster_source" / "approved-startup-lockup.png").convert("1")
wordmark = approved_lockup.crop((8, 171, 392, 222)).resize((258, 34), Image.Resampling.NEAREST)


def mascot(frame):
    """Original bold pixel silhouette: clear face first, only crank moves."""
    im = Image.new("1", (64, 32), 1)
    d = ImageDraw.Draw(im)
    d.polygon(((13, 5), (19, 4), (24, 6), (28, 4), (34, 5), (38, 9),
               (39, 16), (36, 24), (31, 28), (23, 27), (17, 28), (11, 24),
               (8, 17), (9, 10)), fill=0)
    d.polygon(((12, 10), (16, 7), (21, 7), (24, 9), (28, 7), (33, 7),
               (36, 11), (36, 18), (32, 24), (25, 24), (18, 25), (13, 21)), fill=1)
    # Small rim texture only; no stipple inside expression or letter counters.
    for x, y in ((11, 13), (12, 18), (15, 22), (31, 7), (34, 10), (35, 21)):
        d.point((x, y), fill=0)
    d.polygon(((21, 5), (22, 1), (25, 0), (25, 3), (24, 6)), fill=0)
    d.polygon(((26, 4), (28, 0), (35, 0), (32, 3)), fill=0)
    # Slanted brows and narrow white pupils make the tiny apple recognizably mean.
    d.polygon(((13, 10), (22, 14), (21, 17), (15, 16)), fill=0)
    d.polygon(((26, 14), (35, 10), (33, 16), (27, 17)), fill=0)
    d.point((19, 15), fill=1);d.point((28, 15), fill=1)
    d.polygon(((15, 19), (20, 21), (29, 21), (33, 18), (30, 24), (20, 24)), fill=0)
    for x in (19, 23, 27):
        d.rectangle((x, 21, x+1, 22), fill=1)
    d.rectangle((14, 28, 19, 30), fill=0);d.rectangle((29, 28, 34, 30), fill=0)
    # Outboard gearbox and a four-pose arm, drawn on an opaque white replacement.
    d.rectangle((38, 13, 44, 20), fill=0)
    d.rectangle((40, 15, 42, 18), fill=1)
    d.line((43, 16, 47, 16), fill=0, width=2)
    cx, cy = 47, 16
    hx, hy = ((55, 16), (47, 24), (39, 16), (47, 8))[frame]
    d.line((cx, cy, hx, hy), fill=0, width=3)
    d.rounded_rectangle((hx-2, hy-4, hx+2, hy+4), radius=1, fill=0)
    d.line((hx, hy-2, hx, hy), fill=1)
    return im


mascots = tuple(mascot(frame) for frame in range(4))


def text(im, value, x, y, scale=1, ink=0):
    draw = ImageDraw.Draw(im)
    for char in value.upper():
        rows = FONT.get(char, FONT["?"])
        for yy, row in enumerate(rows):
            for xx in range(5):
                if row & (16 >> xx):
                    draw.rectangle((x + xx * scale, y + yy * scale,
                                    x + (xx + 1) * scale - 1,
                                    y + (yy + 1) * scale - 1), fill=ink)
        x += 6 * scale


def normalized(im, mask=None):
    im = im.convert("1")
    w, h = im.size
    if mask is None:
        mask = Image.new("1", (w, h), 1)
    return pd.from_rows(["".join(" " if not mask.getpixel((x, y)) else
                                "." if im.getpixel((x, y)) else "#"
                                for x in range(w)) for y in range(h)])


def base(page):
    im = Image.new("1", (400, 240), 1)
    d = ImageDraw.Draw(im)
    im.paste(wordmark, (18, 5))
    text(im, "GAMES FOR FRUIT JAM", 20, 43)
    im.paste(mascots[0], (300, 8))
    text(im, page, 300, 43)
    d.line((18, 52, 381, 52), fill=0)
    d.line((18, 54, 85, 54), fill=0)
    # Fine edge ticks are outside all editable rows and waveform panels.
    for y in range(66, 197, 13):
        d.line((9, y, 11, y), fill=0)
        d.line((388, y, 390, y), fill=0)
    # Sparse ordered one-bit texture is confined to the outer frame, not content.
    for y in range(59, 208, 2):
        for x in range(0, 6):
            if (x + 2*(y//2)) % 4 == 0:
                d.point((x, y), fill=0)
                d.point((399-x, y), fill=0)
    return im


backgrounds = {}
im = base("LIBRARY")
d = ImageDraw.Draw(im)
for y in (107, 153):
    for x in range(43, 380, 4):
        d.point((x, y), fill=0)
d.line((18, 214, 381, 214), fill=0)
text(im, "B1/B2 SELECT", 20, 225)
text(im, "B3 OPEN", 180, 225)
text(im, "SOURCE PLAYER", 304, 225)
backgrounds["library"] = im

im = base("SOUND")
d = ImageDraw.Draw(im)
d.line((18, 215, 381, 215), fill=0)
text(im, "B1/B2 CHANGE  B3 NEXT", 20, 220)
text(im, "B1+B2 REPLAY  HOLD B3 LIBRARY", 20, 232)
backgrounds["explorer"] = im

im = base("CHECK")
d = ImageDraw.Draw(im)
d.rounded_rectangle((20, 66, 379, 200), radius=5, outline=0)
text(im, "CARTRIDGE NOT LOADED", 38, 79, 2)
d.line((38, 104, 361, 104), fill=0)
# Error detail remains clear from y116 through y184; parent owns actual reason.
d.line((18, 215, 381, 215), fill=0)
text(im, "B3 BACK TO LIBRARY", 20, 227)
text(im, "NO GAME EXECUTED", 286, 227)
backgrounds["error"] = im

sprites = {}
for frame, im in enumerate(mascots):
    sprites["crank_badapple%d" % frame] = normalized(im)


def icon(name, width, height, painter):
    im = Image.new("1", (width, height), 1)
    mask = Image.new("1", (width, height), 0)
    painter(ImageDraw.Draw(im), ImageDraw.Draw(mask))
    sprites[name] = normalized(im, mask)


def selection(d, m):
    m.rounded_rectangle((0, 0, 363, 42), radius=4, fill=1)
    d.rounded_rectangle((0, 0, 363, 42), radius=4, outline=0, width=2)
    d.rectangle((6, 7, 8, 35), fill=0)


icon("selection", 364, 43, selection)
sprites["cursor"] = pd.from_rows(["#      ", "##     ", "###    ", "####   ",
                                  "#####  ", "####   ", "###    ", "##     ", "#      "])


def wave(kind):
    def painter(d, m):
        m.rectangle((0, 0, 127, 39), fill=1)
        # Sparse reference axis, solid signal, no gray fills or antialiasing.
        for x in range(0, 128, 4):
            d.point((x, 20), fill=0)
        points = []
        for x in range(4, 124):
            phase = (x - 4) % 32
            if kind == "square":
                y = 7 if phase < 16 else 32
            elif kind == "triangle":
                y = 7 + round((phase if phase < 16 else 32 - phase) * 25 / 16)
            else:
                amplitude = 14 * math.exp(-(x - 4) / 52)
                y = round(20 - amplitude * math.sin((x - 4) * .48))
            points.append((x, y))
        d.line(points, fill=0, width=2)
    return painter


for kind in ("square", "triangle", "sample"):
    icon("wave_" + kind, 128, 40, wave(kind))


def envelope(d, m):
    m.rectangle((0, 0, 95, 39), fill=1)
    d.line((3, 36, 93, 36), fill=0)
    d.line((3, 36, 3, 4), fill=0)
    d.line((4, 35, 13, 5, 30, 19, 69, 19, 91, 35), fill=0, width=2)
    for x in (13, 30, 69):
        for y in range(25, 36, 3):
            d.point((x, y), fill=0)


icon("envelope", 96, 40, envelope)

# Canvas uppercases letters. Unsupported ASCII punctuation renders '?', matching
# CrankJam's fallback. Include all 32..95 keys so no character silently vanishes.
for scale in (1, 2):
    for value in range(32, 96):
        im = Image.new("1", (5 * scale, 7 * scale), 0)
        mask = Image.new("1", im.size, 0)
        text(mask, chr(value), 0, 0, scale, 1)
        sprites["glyph%d_%d" % (scale, value)] = normalized(im, mask)
assert len(sprites) <= 256

manifest = {"version": 1, "width": 400, "height": 240, "backgrounds": {},
            "sprites": {}, "labels": {},
            "provenance": "Original MIT Crankfruit player UI; MIT CrankJam glyphs; exact Cranksters PDI/PDT format roundtrips."}
for name, im in backgrounds.items():
    original = normalized(im)
    encoded = pd.encode_pdi(original, compressed=True)
    decoded = pd.decode_pdi(encoded)
    assert decoded == original
    (OUT / (name + ".pdi")).write_bytes(encoded)
    (OUT / (name + ".bin")).write_bytes(decoded.pixels)
    assert len(decoded.pixels) == 12000
    manifest["backgrounds"][name] = name + ".bin"
    im.save(PREVIEW / (name + ".png"))
manifest["backgrounds"]["game"] = "library.bin"

table = tuple(sprites.values())
encoded = pd.encode_pdt(table, compressed=True)
decoded = pd.decode_pdt(encoded)
assert decoded.images == table
atlas, descriptors = pd.pack_native_atlas(decoded.images)
assert len(descriptors) == len(table) * 12 and len(descriptors) <= 3072
(OUT / "sprites.pdt").write_bytes(encoded)
(OUT / "sprites.bin").write_bytes(atlas)
(OUT / "sprites.desc").write_bytes(descriptors)
for index, (name, sprite) in enumerate(sprites.items()):
    manifest["sprites"][name] = {"id": index, "width": sprite.width, "height": sprite.height}
(OUT / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")) + "\n")


def paste(im, sprite, x, y):
    for yy in range(sprite.height):
        for xx in range(sprite.width):
            value, opaque = sprite.pixel(xx, yy)
            if opaque:
                im.putpixel((x + xx, y + yy), value)


# Review-only populated layouts. Device uses the blank backgrounds plus commands.
im = backgrounds["library"].copy()
paste(im, sprites["selection"], 18, 62)
for y, title, desc in ((62, "ALMOST TENNIS", "A RALLY ON THE SMALL SCREEN."),
                       (108, "ORBIT BREAKER", "16 SATELLITES. ONE SHIP."),
                       (154, "SOUND EXPLORER", "SYNTHS, ENVELOPES AND PDA SAMPLES.")):
    text(im, title, 43, y + 7, 2)
    text(im, desc, 43, y + 27)
im.save(PREVIEW / "library-populated.png")
animated = []
for frame in range(4):
    preview = im.copy()
    preview.paste(mascots[frame], (300, 8))
    animated.append(preview)
animated[0].save(PREVIEW / "library-crank.gif", save_all=True,
                 append_images=animated[1:], duration=200, loop=0)
im = backgrounds["explorer"].copy()
for y, label, value in ((66, "WAVE", "SQUARE"), (90, "PITCH", "440 HZ"), (114, "DECAY", "200 MS")):
    text(im, label, 36, y)
    text(im, value, 144, y)
paste(im, sprites["cursor"], 22, 65)
paste(im, sprites["wave_square"], 32, 144)
paste(im, sprites["envelope"], 238, 144)
text(im, "WAVEFORM", 44, 189)
text(im, "LEVEL ENVELOPE", 230, 189)
im.save(PREVIEW / "explorer-populated.png")
receipt = {"backgrounds": len(backgrounds), "background_aliases": {"game": "library"},
           "sprites": len(sprites), "roundtrips": "all pixel and alpha planes exact",
           "width": 400, "height": 240, "hardware_tested": False,
           "wordmark_source_sha256": hashlib.sha256((ROOT / "raster_source" / "approved-startup-lockup.png").read_bytes()).hexdigest(),
           "assets": {p.name: {"bytes": p.stat().st_size,
                               "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                      for p in sorted(OUT.iterdir()) if p.is_file()}}
(ROOT / "asset-build.json").write_text(json.dumps(receipt, indent=2) + "\n")
print("ASSET_BUILD_PASS", len(backgrounds), "backgrounds + game alias", len(sprites), "sprites")
