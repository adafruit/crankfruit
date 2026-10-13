# optional display scaling: 1x, 1.6x sharp, 1.6x smooth

by default the 400x240 game is drawn 1x in a 1-bit (black/white) 640x480 HDMI
picture. copying `display-config.json` to the board as `/display.json` switches
the HDMI framebuffer to **2-bit greyscale** (4 levels, 76,800 bytes) and offers
three modes; `"scale"` picks the one used at startup (and `"white"` the grey
used for white, below):

| scale | picture |
| --- | --- |
| `"1"` | 1x, centred (400x240 at 120,120) |
| `"1.6"` | 1.6x sharp: 640x384 at rows 48..431, exact 5:3, black bars above/below |
| `"1.6s"` | 1.6x smooth: same area; each output pixel's grey is the exact area coverage of the game pixels under it, rounded to 4 levels |

**switching live:** while the USB gamepad is connected, the Fruit Jam's onboard
buttons are settings buttons instead of game controls. B1 cycles 1x -> 1.6x ->
1.6x smooth (without `/display.json`: 1x <-> 1.6x sharp at 1-bit). B2 and B3 are
reserved. the choice lasts until restart (the app cannot write `/display.json`
while the drive is mounted on a computer). unplug the gamepad and B1/B2/B3 are
game controls again, so the board always stays playable. delete `/display.json`
to return to the kit's original 1-bit output.

**white level** (2-bit only): `"white": "playdate"` (default) draws game white at
level 2, about 50% grey, the same as the kit's 1-bit output and close to the light
grey of the Playdate's Sharp Memory LCD; smooth mode then has 3 levels (black, one
grey, white). `"white": "bright"` uses level 3, about 75%, with 4 levels for
smoothing. the HDMI encoder places pixel bits at the top of each 8-bit channel,
which is why 1-bit white is only about 50% (0x80) and 2-bit level 3 about 75% (0xC0).

the scaling is the native `blit16` function in `native/blit` (part of
`_crankfruit_blit.mpy`). output pixel (x, y) shows source pixel (x*5/8,
(y-48)*5/8): every 5 game pixels become 8 output pixels (one output byte), so game
pixels are 2 or 1 output pixels wide in a fixed pattern. preview any scale on a
computer with the desktop player's `--board-scale` option (`engine/README.md`).

measured on the Fruit Jam (2026-10-13): 1-bit `blit16` 2.43ms per frame vs 1.57ms
for the 1x `blit`; 2-bit `blit2` 1.1ms (1x), 3.2ms (1.6x sharp), 6.0ms (1.6x smooth),
all pixel-exact in on-board samples; 3,000 sampled output pixels matched the mapping. host checks:
`native/build.py` (C sanitizer suite against a per-pixel reference) and
`python3 -m unittest discover -s tools/display` (config, selection, Python reference).

**unchanged frames are skipped:** each presented frame is compared with the last
one drawn (native `frame_changed`, word-wise; ~0.23ms on the board for an identical
frame, as the Python buffers sit in PSRAM). if nothing changed, the scaler is not
run; a redraw is forced at startup and after each B1 mode switch. games that draw
at 20Hz (Almost Tennis) and static screens save most of the scaling cost. each
scene logs `DISPLAY_DONE <scene> skipped_unchanged_presents N`.

for correct proportions, set the TV's picture size for this input to 4:3 /
"Original" / "Just Scan"; many TVs stretch 640x480 to 16:9 by default.
