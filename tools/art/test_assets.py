"""Stdlib-only assertions against the checked-in binary build output."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import pd_assets as pd

OUT = ROOT / "assets"
manifest = json.loads((OUT / "manifest.json").read_text())
receipt = json.loads((ROOT / "asset-build.json").read_text())
assert set(manifest["backgrounds"]) == {"game", "library", "explorer", "error"}
assert manifest["backgrounds"]["game"] == manifest["backgrounds"]["library"]
for name in ("library", "explorer", "error"):
    decoded = pd.decode_pdi((OUT / (name + ".pdi")).read_bytes())
    assert decoded.width == 400 and decoded.height == 240
    assert decoded.pixels == (OUT / manifest["backgrounds"][name]).read_bytes()
    assert all(v == 255 for v in decoded.alpha)

table = pd.decode_pdt((OUT / "sprites.pdt").read_bytes()).images
atlas = (OUT / "sprites.bin").read_bytes()
descriptors = (OUT / "sprites.desc").read_bytes()
assert len(table) == len(manifest["sprites"]) <= 256
assert len(descriptors) == 12 * len(table) <= 3072
assert len(atlas) <= 262144
for name, info in manifest["sprites"].items():
    index = info["id"]
    sprite = table[index]
    w, h, pixel_offset, alpha_offset = struct.unpack_from("<HHII", descriptors, index * 12)
    assert (w, h) == (sprite.width, sprite.height) == (info["width"], info["height"])
    size = ((w + 7) // 8) * h
    assert atlas[pixel_offset:pixel_offset + size] == sprite.pixels
    assert atlas[alpha_offset:alpha_offset + size] == sprite.alpha
    assert all(not (pixel & ~alpha) for pixel, alpha in zip(sprite.pixels, sprite.alpha))
for scale in (1, 2):
    for code in range(32, 96):
        assert "glyph%d_%d" % (scale, code) in manifest["sprites"]
mascot_planes = []
for frame in range(4):
    sprite = table[manifest["sprites"]["crank_badapple%d" % frame]["id"]]
    assert (sprite.width, sprite.height) == (64, 32)
    assert all(value == 255 for value in sprite.alpha), "mascot must replace whole frame"
    mascot_planes.append(sprite.pixels)
assert len(set(mascot_planes)) == 4, "crank animation needs four distinct poses"
for filename, info in receipt["assets"].items():
    data = (OUT / filename).read_bytes()
    assert len(data) == info["bytes"]
    assert hashlib.sha256(data).hexdigest() == info["sha256"]
print("ASSET_TEST_PASS: 3 opaque PDI backgrounds, game alias, %d exact masked PDT/atlas sprites, hashes" % len(table))
