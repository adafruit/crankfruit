#!/usr/bin/env python3
"""Compare trusted authored assets with a pinned, unchanged Cranksters reader.

PDI uses the upstream command-line converter. PDT uses our small framing glue
and upstream read_cell, because that converter does not implement a PDT CLI.
Dependency: Pillow. No device access, network calls, or source-asset writes.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib
from PIL import Image

HERE = Path(__file__).resolve().parent
PIN = "e7be3ff0141b7cd3b9f008737eda1f0539aca45c"
SCRIPT_SHA256 = "977f2627075c481a9dcdba64ad13fef68749b1eba14c20103b042898446b4de2"
TOOL = HERE / "upstream" / "pdi2png.py"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--assets", type=Path, default=HERE / "assets",
                    help="trusted authored asset directory, defaults to sibling assets/")
parser.add_argument("--receipt", type=Path, default=HERE / "UPSTREAM-ORACLE.json",
                    help="verification receipt destination")
args = parser.parse_args()
assets = args.assets.resolve()
assert hashlib.sha256(TOOL.read_bytes()).hexdigest() == SCRIPT_SHA256, "upstream script changed"
spec = importlib.util.spec_from_file_location("pinned_upstream_pdi", TOOL)
upstream = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upstream)
manifest = json.loads((assets / "manifest.json").read_text())
before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
          for path in sorted(assets.iterdir()) if path.is_file()}

checked = []
checked_files = set()
aliases = {}
with tempfile.TemporaryDirectory(prefix="crankfruit-pdi-check-") as temporary:
    for name, filename in manifest["backgrounds"].items():
        assert Path(filename).name == filename and filename.endswith(".bin")
        if filename in checked_files:
            aliases[name] = filename
            continue
        checked_files.add(filename)
        pdi = assets / (Path(filename).stem + ".pdi")
        png = Path(temporary) / (Path(filename).stem + ".png")
        result = subprocess.run([sys.executable, str(TOOL), str(pdi), "-o", str(png)],
                                capture_output=True, text=True)
        assert result.returncode == 0, "upstream PDI conversion failed for " + pdi.name
        with Image.open(png) as image:
            assert image.size == (400, 240), "background dimensions changed"
            assert image.convert("1").tobytes() == (assets / filename).read_bytes(), "PDI pixel mismatch"
            assert image.convert("RGBA").getchannel("A").getextrema() == (255, 255), "PDI alpha mismatch"
        checked.append(pdi.name)
    result = subprocess.run([sys.executable, str(TOOL), str(assets / "sprites.pdt"),
                             "-o", str(Path(temporary) / "unsupported.png")],
                            capture_output=True, text=True)
    assert result.returncode != 0 and "Not a valid PDI file" in result.stderr

# This framing is deliberately separate from tools/pd_assets.py. Cell pixels and
# alpha are decoded by the exact pinned upstream read_cell implementation.
data = (assets / "sprites.pdt").read_bytes()
assert data[:12] == b"Playdate IMT", "invalid PDT signature"
flags, = struct.unpack_from("<I", data, 12)
if flags & 0x80000000:
    expected_size, = struct.unpack_from("<I", data, 16)
    assert expected_size <= 16 * 1024 * 1024, "PDT verification size budget"
    raw = zlib.decompress(data[32:])
    assert len(raw) == expected_size, "PDT decompressed size mismatch"
else:
    raw = data[16:]
count, columns = struct.unpack_from("<HH", raw)
assert 1 <= count <= 256 and 0 <= columns <= count
base = 4 + 4 * count
offsets = (0,) + struct.unpack_from("<%dI" % count, raw, 4)
assert all(offsets[i] < offsets[i+1] for i in range(count))
assert base + offsets[-1] == len(raw), "PDT framing length mismatch"
atlas = (assets / "sprites.bin").read_bytes()
descriptors = (assets / "sprites.desc").read_bytes()
assert len(descriptors) == count * 12 and count == len(manifest["sprites"])
pixel_checks = 0
for number in range(count):
    width, height, rows, has_alpha = upstream.read_cell(raw, base + offsets[number])
    w, h, pixel_offset, alpha_offset = struct.unpack_from("<HHII", descriptors, number * 12)
    assert (w, h) == (width, height)
    stride = (w + 7) // 8
    for y, row in enumerate(rows):
        for x in range(w):
            color = row[x*2] if has_alpha else row[x]
            alpha = row[x*2+1] if has_alpha else 255
            at = y * stride + x // 8
            shift = 7 - x % 8
            native_color = (atlas[pixel_offset + at] >> shift) & 1
            native_alpha = (atlas[alpha_offset + at] >> shift) & 1
            assert alpha == native_alpha * 255, "PDT alpha mismatch"
            assert color == native_color * 255, "PDT pixel mismatch, including transparent color"
            pixel_checks += 1

after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
         for path in sorted(assets.iterdir()) if path.is_file()}
assert before == after, "source assets changed during verification"
receipt = {"upstream_commit": PIN, "upstream_script_sha256": SCRIPT_SHA256,
           "pdi_cli_exact_backgrounds": checked, "background_aliases": aliases,
           "pdi_cli_checked_pixels": len(checked) * 400 * 240,
           "pdt_cli_supported": False,
           "pdt_limitation": "Unchanged upstream CLI rejects PDT. Table framing is local glue; every cell pixel and alpha value uses unchanged upstream read_cell, not a complete upstream PDT reader.",
           "pdt_upstream_cell_decoder_exact_sprites": count,
           "pdt_upstream_cell_decoder_pixel_checks": pixel_checks,
           "transparent_colors_compared_exactly": True,
           "hardware_touched": False, "source_assets_changed": False,
           "asset_hashes": before}
args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
print("UPSTREAM_ORACLE_PASS", len(checked), "PDI backgrounds", count,
      "PDT cells", pixel_checks, "cell pixels + alpha exact; PDT CLI unsupported")
