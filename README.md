# impossible playdate / crankfruit

an open-source, standalone game player for adafruit fruit jam. copy a compatible
source game into `/games/<slug>/`, restart, and it appears in the library. no
computer, network, account or cloud service is needed during play.

this is a **source-compatible subset**, not a universal playdate emulator.
it does not run arbitrary `.pdx`/`.pdz` bundles, compiled lua, native playdate
binaries, catalog games, the playdate operating system, or SDK/CoreLibs unchanged.
it is an independent experiment, not endorsed by panic or cranksters.

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
QT encoder and analog-pot backends are included, disabled by default. no USB
controller or touch-input support is claimed.

almost tennis: B1/B2 move, B3 start/swing/restart, B1+B2 dash when available.
orbit breaker: B1/B2 move, B3 start/restart, B1+B2 pause.
sound explorer: B1/B2 change, short B3 next field, B1+B2 replay.

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
format research: https://github.com/cranksters/playdate-reverse-engineering
at revision `e7be3ff0141b7cd3b9f008737eda1f0539aca45c`.
format references are community documentation, not an SDK compatibility guarantee.
required third-party notices remain in their source directories.
