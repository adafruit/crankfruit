# make and load a game

make `/games/my-game/manifest.json` and `/games/my-game/main.lua`.
folder names use lowercase letters, digits, hyphens and underscores, 1..48
characters, starting with a letter or digit. keep at most32 directory entries in
the game root and in each cartridge, including hidden filesystem files.

```json
{
  "kind": "lua",
  "profile": "crankfruit-lua-v1",
  "title": "My Game",
  "author": "Your name",
  "description": "A small original game",
  "controls": "B1/B2 move; B3 start; hold B3 library",
  "target_fps": 30,
  "heap_cap": 65536,
  "entry": "main.lua"
}
```

title/author/description/controls must be printable ASCII with limits48/64/160/160.
title and author must be nonempty. unknown or duplicate manifest keys are rejected.
`heap_cap` is optional, defaults65536, allowed32768..262144. `entry` is optional
but can only be `main.lua`. target_fps must be integer30.

`main.lua` must be UTF-8 source, 1..131072 bytes. a passing preflight is a **source
candidate**, not proof that its APIs are implemented. unsupported calls produce
a game error; the app stops the game and returns to the library. game changes
between discovery and launch are rejected until the library is re-scanned.

```lua
local p = playdate
local g = p.graphics
p.display.setRefreshRate(30)
function p.update()
    g.clear(g.kColorWhite)
    g.setColor(g.kColorBlack)
    g.drawText("HELLO FRUIT JAM", 130, 115)
end
```

start from either bundled `main.lua`, not from an arbitrary commercial bundle.
the runtime exposes primitive drawing, text, button/crank/time queries, and a
small sound synth API. consult `engine/src/graphics.c`, `sound.c`, `runtime.c`
for the exact registered methods. the bundled examples are executable references.
the runtime uses standard Lua5.4.9 source syntax. playdate-specific syntax and
SDK modules need porting first.

not implemented: imports/CoreLibs, Playdate classes, sprite/collision APIs,
timers, general game filesystem access, network, arbitrary sample-player APIs,
Playdate native ARM loading, PDZ decryption/bytecode execution. the player passes
zero crank angle/delta by default. explicit `/crank.json` configuration can enable
a seesaw STEMMA QT encoder or calibrated analog pot, sampled once per admitted
game update. see `tools/crank/README.md`; physical input is not hardware-qualified.
orbit breaker already consumes crank deltas. the sound explorer
uses an internal synthetic crank value as a synth control signal, not crank hardware.

30Hz is the simulation/audio scheduler rate. heavy scenes may deliberately redraw
at20Hz, as the bundled games do. audio is32kHz mono PCM16; three-frame prefill puts
simulation about66ms ahead of output. measure whole-frame performance on the board.

games have a bounded Lua heap, instruction and drawing budgets. this is experimental
software, not a hardened adversarial-game sandbox. review unknown source before
running it. cartridges cannot supply executable Python to the loader.

## cranksters-format integration

PDI/PDT tools validate and decode images on the computer, then export fixed native
bitplanes and transparency masks. PDA tools decode supported PCM modes on the
computer. sample playback uses cached PCM and native buffer copying on Fruit Jam.
these are real file-format integrations, not a claim that Cranksters provides a
ready-made emulator. conversion is a development step; playback is standalone.

to add another game, copy its source folder into `/games/`, return to the library
or restart, and select it. no edit to `crankfruit.py` is required.
