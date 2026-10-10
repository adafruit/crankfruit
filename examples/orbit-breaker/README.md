# Orbit Breaker

An original, MIT-licensed compatible-source game for the experimental Impossible
Playdate player on Fruit Jam. This is **not an unmodified Playdate game or PDX**.
Its supported surface is `crankfruit-lua-v1`: single-file source Lua, basic
one-bit drawing and square/triangle synthesized sound. No external assets,
imports, SDK, network, sample player, or host computer is used by the game.

Clear the sixteen satellites without losing your three ships. Hits award 25
points. Rebounds become slightly quicker; the paddle's impact position controls
the angle. The title leads into an automatic demonstration after three seconds.
The demonstration returns to the title after 24 seconds, or after its result card.

## controls

- B1 / B2: move left / right.
- B3: start or restart your game.
- B1 + B2: pause or resume.
- Hold B3: exit through the player's own navigation.
- Crank delta is accepted when the player supplies it; no physical crank is
  assumed to exist on an unmodified Fruit Jam.

## install

Copy this directory, keeping `manifest.json` and `main.lua` together, into the
player's configured games directory. The folder name is the implicit game id.
The loader discovers the manifest; no application code change should be needed.
The manifest requests 30 Hz logic and a 65536-byte Lua heap. Drawing is gated by
20 Hz time slots, uses fixed brick storage, and retains the static playfield
between hits. Actual HDMI/audio qualification belongs to the complete player
and target firmware, not to this source package alone.

## portable host verification

Use a compatible, crankjam-enabled MicroPython host interpreter that you built
or received with the player. The test runner does not download or execute a
guessed runtime:

```sh
python3 verify.py --interpreter /path/to/crankjam-micropython
```

Optionally add `--frames /path/to/previews` for five native-host PBM images.
Tests cover boundary movement, wall and paddle bounces, loss/restart, brick hits,
win/loss transitions, fixed-slot accounting, score/ship limits, record retention,
and the 20 Hz drawing quota. Two real runtime instances compare every framebuffer
and PCM block across 1,800 deterministic scripted updates. One instance includes
the assertion harness; its output must still match the uninstrumented game.

Observed host result: 1,800 matching frames, 1,920,600 matching PCM samples,
799 changing frames, 176 nonzero PCM blocks. Instrumented heap peak 46,011 of 65,536
bytes. These are host results, not proof of physical video or audible sound.

Copyright (c) 2026 Crankfruit contributors. See `LICENSE`.
