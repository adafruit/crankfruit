# player interface assets

Original deterministic one-bit UI for Crankfruit / Impossible Playdate.
The existing visual system is extended directly: its previously approved
beveled startup wordmark is compiled into the header, while a new tiny mean-apple
mascot and turning crank are authored as deterministic pixel code. No new image
model call, Courier art, or Blinka asset is required here.

## build and check

```sh
python3 -m pip install Pillow
python3 build_assets.py
python3 test_assets.py
python3 verify_upstream.py
```

All input and output paths are relative to these scripts. `vendor/font.h` is the
original MIT CrankJam font, with its license in `vendor/LICENSE-CrankJam`.
`tools/pd_assets.py` is the original bounded offline codec from the player work,
based on Cranksters' CC0 format notes at the commit named in that file. The
remaining UI drawing code and art are MIT, copyright 2026 Crankfruit contributors.
The portable `raster_source/approved-startup-lockup.png` retains the previously
approved original generated artwork used for the startup. Its wordmark is
compiled with nearest-neighbor scaling; the build receipt records its source
hash. No external trademark art or platform logo is used.

The builder saves compressed PDI backgrounds and one masked PDT sprite table,
decodes them, compares all pixels and alpha exactly, then emits native packed
planes. It records SHA-256 hashes in `asset-build.json`. The independent output
check compares PDI/native bytes, PDT/atlas descriptors, canonical transparency,
canvas budgets, glyph coverage and receipt hashes. Build previews are host
artwork, not physical Fruit Jam captures.

`verify_upstream.py` adds an independent format check using the unchanged
Cranksters `pdi2png.py` at commit `e7be3ff0141b7cd3b9f008737eda1f0539aca45c`,
bundled with its CC0 license under `upstream/`. It checks the converter's SHA-256
before running it. Its command-line PDI reader validates all three backgrounds.
The upstream CLI does **not** support PDT and that rejection is explicitly
checked. Small local table-framing glue therefore feeds all sprite cells into
the unchanged upstream `read_cell()` decoder. Both color and alpha must match
the native atlas exactly, including transparent pixel colors. This is independent
cell decoding, not a claim of a complete upstream PDT command-line conversion.

The optional `--assets directory` selects another trusted local authored bundle;
`--receipt filename` changes the JSON receipt destination. Pillow is needed for
the independent PDI-to-PNG comparison. Neither verification script accesses
hardware or changes source assets.

## geometry contract

400 x 240 logical pixels, white=1. No antialiasing or grayscale palette.

- `library`: branding in y0..54; body x20..379, y60..207. Three recommended
  row origins are y62,108,154. Titles at x43,y+7, scale2; descriptions at x43,y+27,
  scale1. Keep titles to 27 characters and descriptions to 55 characters. Footer
  is baked at y214..239. Sparse separators sit at y107 and153, outside row text.
- `game`: alias of the same `library.bin`, required by Canvas initialization.
- `explorer`: shared branding, "SOUND" page label; blank body y60..213. Suggested
  field labels x36 and values x144 at y66/90/114; wave sprite x32,y144; envelope
  x238,y144; labels y189. Footer controls are baked at y220 and232. Do not draw
  another header or footer over this background.
- `error`: shared branding and error panel. Title is baked at y79. Parent may
  write the actual reason from x38,y116 through y184. Footer: B3 back to library.

Sprites: `selection`364x43, `cursor`7x9, `wave_square`128x40,
`wave_triangle`128x40, `wave_sample`128x40, `envelope`96x40, plus ASCII32..95
glyphs at scales1 and2. The atlas has138 entries. `selection` has an opaque white
interior and rounded masked edges: compose it before its row text. Place it at
x18 and the selected row origin. Waveforms and envelope have opaque white
interiors. These schematic waveforms illustrate signal shape, not a live scope.

`crank_badapple0` through `crank_badapple3` are opaque64x32 replacement frames.
Place at x300,y8; frame0 is already baked into every background. Advance the
frame at5Hz for a complete crank revolution every0.8seconds. The header page
label starts x300,y43 and leaves x350,y43 available for a short counter. Main
wordmark occupies x18..275,y5..38; subtitle starts x20,y43. Body layout is
unchanged by the mascot animation. Fine ordered texture stays in the margins.

`assets/` is device-ready input for the existing Canvas API. Only native `.bin`,
`.desc` and `manifest.json` files are needed at runtime; `.pdi`/`.pdt` preserve
the authoring interchange format for review and rebuilding.
