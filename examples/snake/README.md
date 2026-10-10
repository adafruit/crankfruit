# Simple Snake

A source adaptation of Mocchi Mochi's (TauchMe) MIT-licensed Playdate snake game
for the experimental Impossible Playdate player on Fruit Jam. This is **not the
original PDX**; it is a port to the `crankfruit-lua-v1` source profile.

upstream: https://gitlab.com/mocchimochi/playdate/playdate-snake-game at
`c9cc2a924dcbe31156529ae37326940360865530` (v1.3.4). the archived GitHub copy
(Mocchi-Mochi/playdate-snake-game) is an older, different version.

## controls

- d-pad or left stick: steer up / down / left / right (needs the optional USB
  gamepad; see `tools/gamepad/README.md`). the Fruit Jam's onboard buttons only
  provide left / right, so the snake cannot be steered up or down without a pad.
- A (gamepad cross, or B3): restart after game over.
- gamepad options, or hold B3: return to the library.

## what changed from upstream

gameplay logic, speeds (move every 5 frames at 30Hz, faster every 5 segments down
to every 2 frames), 10px grid, collision rules, turn-blocking and game-over panel
layout are kept. changes are limited to what the source profile requires:

- `snake.lua` inlined into `main.lua`; `CoreLibs`, `saveddata` and `music` imports removed.
- Playdate-only `+=` / `-=` rewritten as standard Lua 5.4 assignments.
- the `eat.wav` sample is replaced by a short synth blip (no sample-player API).
- the background music (credited upstream to 8 Bit And Chill, not covered by the
  repo's MIT notice) is not included; system-menu Music/Inverted items are removed.
- the high score lives in memory only (no game filesystem access); it resets when
  you leave the game.
- rounded rectangles are drawn as plain rectangles; text widths use the 6px
  built-in font; `*bold*` markup is dropped; text is drawn in all caps by the
  built-in font. the FillWhite image draw mode is emulated by drawing the
  game-over text in white.

## licence

upstream copyright and MIT notice are in `LICENSE`. adaptation changes are MIT.

## checks

- `tools/cartridges/cartridge_cli.py check examples/snake`: enabled source candidate.
- desktop headless run (900 frames, scripted d-pad turns): moved, ate, scored,
  reached game over; eat blip audible in output; peak Lua heap ~32KB of 64KB.
