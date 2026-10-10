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

almost tennis: B1/B2 move, B3 start/swing/restart, B1+B2 dash when available.
orbit breaker: B1/B2 move, B3 start/restart, B1+B2 pause.
sound explorer: B1/B2 change, short B3 next field, B1+B2 replay.
simple snake: gamepad d-pad/stick steer, A restart (B1/B2 can only steer left/right).

with the gamepad: d-pad = B1/B2 directions (plus up/down), cross = B3, circle =
B1+B2, options = immediate return to the library.

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
