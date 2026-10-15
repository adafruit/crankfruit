# impossible playdate / crankfruit

an open-source, standalone game player for adafruit fruit jam. copy a compatible
source game into `/games/<slug>/`, restart, and it appears in the library. no
computer, network, account or cloud service is needed during play.

this is a **source-compatible subset**, not a universal playdate emulator.
it does not run arbitrary `.pdx`/`.pdz` bundles, compiled lua, native playdate
binaries, catalog games, the playdate operating system, or SDK/CoreLibs unchanged.
it is an independent experiment, not endorsed by panic or cranksters.

## what this repo adds

the first commit is the original review kit, unmodified (all files match its
`SHA256SUMS`). later commits add:

- **optional USB gamepad:** a wired Sony DualShock 4 on the fruit jam USB-A host
  port. d-pad/left stick move in all four directions, cross = A, circle = B,
  options = back to the library. onboard buttons keep working. off unless
  `/gamepad.json` exists: copy `tools/gamepad/gamepad-config.json` there and
  restart. mapping, timing measurements and tests: `tools/gamepad/README.md`.
- **right-stick crank (proof of concept):** with `"crank": true` in
  `/gamepad.json` (on in the template), rotating the right stick drives the
  playdate crank for lua games; orbit breaker's paddle follows it. speed is set by
  `crank_scale` (template: 70%).
- **STEMMA QT rotary encoder crank:** the kit's seesaw crank backend, tested with
  adafruit's I2C rotary encoder breakout (product 4991). new optional
  `read_delay_ms` makes each read ~1ms instead of ~9ms; working `/crank.json` and
  measurements are in `tools/crank/README.md`. needs `adafruit_seesaw` (10.x
  bundle) in `/lib`. a hardware crank takes priority over the stick crank.
- **4-frame audio prefill:** the player pre-mixes 4 frames (was 3), giving ~33ms
  more buffer against heavy game frames at the cost of ~33ms more latency. the
  gamepad also logs its slowest poll per scene (`GAMEPAD_DONE`).
- **bigger, smoother picture:** with `/display.json` the HDMI framebuffer runs at
  2-bit greyscale and B1 cycles 1x, 1.6x sharp (640x384, exact 5:3, full width)
  and 1.6x smooth (area-coverage antialiasing). white defaults to the kit's
  Playdate-like grey (`"white": "bright"` for brighter). the desktop player
  previews 1x/1.5x/1.6x/1.6x smooth with `--board-scale`. see
  `tools/display/README.md`.
- **100-pulse CNC handwheel crank:** `"kind": "rotaryio"` reads a quadrature
  encoder in hardware (3.6 degrees per click on a 100-pulse handwheel at 3.3V on
  STEMMA QT); per-crank `step_degrees` sets library/Sound Explorer steps, and
  Simple Snake turns on one click. on SDA/SCL, `settings.toml` needs
  `CIRCUITPY_PICODVI_ENABLE = "never"` (see `tools/crank/README.md`).
- **library survives a system freeze:** a >100ms stall (for example the computer
  writing to CIRCUITPY) reopens the library instead of stopping the app.
- **crank everywhere it fits:** the crank (stick or encoder) moves the library
  highlight, swings in almost tennis (upstream's flick rule), turns the snake in
  simple snake, and changes values in sound explorer. encoder reads retry and
  hold through brief I2C glitches (`CRANK_DONE` log line).
- **simple snake:** a source adaptation of Mocchi Mochi's MIT playdate snake game,
  in `examples/snake/`. copy that folder to `/games/snake/` on the board and
  restart. up/down steering needs the gamepad. changes from upstream are listed
  in `examples/snake/README.md`.
- **`TEST-RESULTS.md`:** independent results on one fruit jam and a TV over HDMI:
  physical buttons, both games, HDMI audio, gamepad timing, unplug/replug, the
  snake port, and which HDMI modes this firmware accepts.

`app-manifest.json`, `MANIFEST.json` and `SHA256SUMS` are regenerated for these
changes; `python3 verify.py` passes and `install.py` installs the gamepad code.

## what's included

- crankfruit player: bad-apple startup animation, dynamic game library, per-game
  error recovery, standalone 400x240 monochrome graphics inside 640x480 HDMI.
- almost tennis: a source adaptation of SquidGod's MIT game, with ten opponents.
  its original external art/audio/libraries are not included. this is a port,
  not a binary compatibility demonstration.
- orbit breaker: original 16-brick paddle game, loaded by exactly the same
  manifest/source path, with no special launcher branch.
- sound explorer: square/triangle synthesizers and three original samples decoded
  from playdate PDA files on the development computer, then played locally.
- cranksters-format tools: PDI images and PDT image tables roundtrip into bounded
  native sprite assets; PDA PCM audio converts to cached 32kHz mono PCM16.

## controls

fruit jam B1/B2 select a game; B3 opens it. hold B3 for 1.2 seconds to return.
the library re-scans on entry, so new source folders do not need launcher edits.
games describe their controls in their manifests. the three onboard buttons are
input path, exercised with injected states during automated tests. physical
button presses and a physical crank are separate manual checks. optional STEMMA
QT encoder and analog-pot backends are included, disabled by default. an optional
wired DualShock 4 USB gamepad is supported (see above); other USB controllers
and touch input are not.

almost tennis: B1/B2 move, B3 start/swing/restart, B1+B2 dash when available;
crank flick (10 degrees in a frame) swings, as in the original.
orbit breaker: B1/B2 move, B3 start/restart, B1+B2 pause; crank moves the paddle.
sound explorer: B1/B2 change, short B3 next field, B1+B2 replay; crank click changes.
simple snake: gamepad d-pad/stick steer, A restart (B1/B2 can only steer left/right);
crank click turns left/right.
library: crank click (18 degrees) moves the highlight; it never launches a game.

with the gamepad: d-pad = B1/B2 directions (plus up/down), cross = B3, circle =
B1+B2, options = immediate return to the library. while the gamepad is connected,
the onboard buttons become settings buttons: B1 cycles the display modes (1x,
1.6x sharp, 1.6x smooth with `/display.json`; B2/B3 reserved). unplug the gamepad and they are game controls again.

## start and review

read `START-HERE.md` before installation and `RESULTS.md` for the exact observed
tests and remaining limits. `app/` contains the application payload, not firmware.
`firmware/` contains the reviewed custom Fruit Jam UF2. stock CircuitPython lacks
the built-in crankjam engine and this HDMI-audio extension.

`AUTHORING.md` defines the bounded source profile and loading workflow.
`engine/`, `native/`, and the format tools contain editable source and licenses.
all tools run locally. optional host tests require the documented build tools.

## attribution

almost tennis upstream: https://github.com/SquidGodDev/almost-tennis
at revision `69172662a659849c8b452e257c1f41f8cd240ad8`.
simple snake upstream: https://gitlab.com/mocchimochi/playdate/playdate-snake-game
at revision `c9cc2a924dcbe31156529ae37326940360865530` (MIT, Mocchi Mochi).
format research: https://github.com/cranksters/playdate-reverse-engineering
at revision `e7be3ff0141b7cd3b9f008737eda1f0539aca45c`.
format references are community documentation, not an SDK compatibility guarantee.
required third-party notices remain in their source directories.
