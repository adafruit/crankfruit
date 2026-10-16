# Crankfruit

Crankfruit turns an Adafruit Fruit Jam into a tiny Playdate-inspired game console.
Copy an open-source, Playdate-style Lua game into a folder, plug the board into a TV,
and play with a USB gamepad and a real crank. Everything runs on the Fruit Jam's
RP2350: no computer, network or account is needed while playing. Games draw the
Playdate's 400x240 one-bit screen over HDMI, with synth sound over HDMI audio.

Crankfruit is a **source-game player, not an emulator**: it runs compatible Lua
games from source, not `.pdx`/`.pdz` bundles or catalog games. It is an independent
project and is not affiliated with or endorsed by Panic, makers of the Playdate.

## what's included

- **Crankfruit player:** startup animation, a game library that finds games
  automatically, per-game error recovery, HDMI video and audio.
- **Games:** Orbit Breaker (original), Almost Tennis (a source adaptation of
  SquidGod's MIT game) and Simple Snake (a port of Mocchi Mochi's MIT game, in
  `examples/snake/`). Sound Explorer is a built-in synth and sample toy.
- **Controls:** the Fruit Jam's three buttons, an optional wired PlayStation 4
  (DualShock 4) USB controller, and an optional crank: a STEMMA QT rotary encoder,
  a quadrature encoder such as a 100-pulse CNC handwheel, or the controller's right
  stick.
- **Display modes:** 1x, or 1.6x (640x384, full width, exact aspect ratio) sharp or
  antialiased, switchable while playing.
- **Source and tools:** the portable C/Lua engine (with a desktop player), native
  helpers, the custom CircuitPython firmware build recipe, cartridge, art and sound
  tools, and tests.

## hardware

- Adafruit Fruit Jam (RP2350B)
- HDMI display that plays HDMI audio (a TV or monitor with speakers; DVI-only
  monitors show the picture without sound)
- USB-C power: the computer, or a supply of at least 2A for standalone play
- optional: wired Sony DualShock 4 controller (USB-A host port)
- optional crank:
  - Adafruit I2C STEMMA QT Rotary Encoder breakout (product 4991), or
  - a quadrature encoder on two consecutive GPIOs, e.g. a 100-pulse CNC handwheel
    powered at 3.3V from the STEMMA QT port (see [crank notes](tools/crank/README.md))

## setup

1. **Back up the board.** Flashing replaces CircuitPython and may reset the
   CIRCUITPY drive.
2. **Flash the firmware.** Hold BOOT/BUTTON1 while pressing reset, wait for the
   `RP2350` drive, then copy `firmware/crankfruit-fruit-jam.uf2` onto it. This is a
   custom CircuitPython 10 build with the Lua engine and HDMI audio built in; stock
   CircuitPython will not run Crankfruit. Check that `boot_out.txt` on CIRCUITPY
   reports `10.3.0-55-geb49ac4141`.
3. **Install the app.** With Python 3.9+ and `pyserial==3.5`:

   ```sh
   python3 install.py --validate-only
   python3 install.py --kit . --port SERIAL_PORT --mount /Volumes/CIRCUITPY \
     --uid BOARD_UID --backup-dir ~/fruitjam-backup --start
   ```

   The board's UID is in `boot_out.txt`. The installer verifies the board and
   firmware, backs up every file it replaces, writes `code.py` last and reads every
   byte back. It never deletes files or flashes firmware. See
   [TOOLS-README.md](TOOLS-README.md).
4. **Add Snake (optional):** copy `examples/snake/` to `/games/snake/` on CIRCUITPY.
5. Connect HDMI, then restart. The startup animation plays, then the library.

Autoreload is off: restart the board after changing files. Don't keep files on
CIRCUITPY open in an editor while playing (see known limitations).

## controls

| action | Fruit Jam buttons | DualShock 4 |
| --- | --- | --- |
| move / choose a game | B1 / B2 | d-pad or left stick (all four directions) |
| A: open, start, swing, restart | B3 | cross |
| B: pause, dash | B1 + B2 | circle |
| back to the library | hold B3 for 1.2s | options |
| crank | - | crank hardware, or the right stick if enabled |

While the controller is connected, the Fruit Jam buttons become **settings
buttons**: B1 cycles the display mode (B2 and B3 are reserved). Unplug the
controller and they are game controls again.

The crank moves the library highlight, steers Orbit Breaker's paddle, swings in
Almost Tennis (a quick flick), turns the snake in Simple Snake, and changes values
in Sound Explorer.

## optional configuration files

Copy these to the root of CIRCUITPY. A missing file selects the default; an invalid
one stops startup with an error so mistakes are visible.

| file | template | what it does |
| --- | --- | --- |
| `/gamepad.json` | `tools/gamepad/gamepad-config.json` | enables the DualShock 4; `"crank": true` makes the right stick a crank (`crank_scale` sets its speed) |
| `/crank.json` | see `tools/crank/README.md` | a hardware crank: `seesaw` (I2C breakout), `rotaryio` (quadrature encoder) or `analog`; `step_degrees` sets degrees per library/Sound Explorer step. A hardware crank takes priority over the stick |
| `/display.json` | `tools/display/display-config.json` | 2-bit greyscale output with three modes (1x, 1.6x sharp, 1.6x smooth); `"white": "playdate"` (default, the Playdate-like light grey) or `"bright"` |
| `/settings.toml` | - | **required for an encoder on STEMMA QT SDA/SCL:** `CIRCUITPY_PICODVI_ENABLE = "never"` (see known limitations) |

Example for a 100-pulse handwheel on STEMMA QT:

```json
{"enabled": true, "kind": "rotaryio", "pin_a": "SDA", "pin_b": "SCL",
 "counts_per_revolution": 100, "direction": -1, "step_degrees": 3.6}
```

## adding games

Make `/games/<name>/manifest.json` and `/games/<name>/main.lua`, then return to the
library or restart: new games appear automatically. Games use a bounded,
Playdate-style Lua 5.4 API (drawing primitives, text, buttons, crank, time and a
small synth). Imports, CoreLibs, sprites and image loading are not available, so
existing Playdate games need porting. See [AUTHORING.md](AUTHORING.md) and
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md); `examples/snake/README.md` shows a
real port.

## desktop player and tests

The engine builds on a computer with CMake and a C11 compiler (`engine/README.md`).
The optional SDL2 player runs games in a window, and `--board-scale 1|1.5|1.6|1.6s`
previews the Fruit Jam's HDMI output (Tab cycles the modes).

`python3 verify.py` runs the portable checks (package hashes, installer, loader,
sound, crank, gamepad, display, audio stream and art tests) without hardware. The
engine, native helpers and boot animation have their own test suites; see their
READMEs. Hardware results are in [docs/TEST-RESULTS.md](docs/TEST-RESULTS.md).

## known limitations

- **Not an emulator.** Only compatible Lua source games run; compiled Playdate
  games, CoreLibs, sprites, images, timers and sample playback are not supported.
- **Brief freezes when the computer writes to CIRCUITPY.** Writing to the board's
  flash (for example an editor closing a file on the drive) pauses the board for
  up to a few hundred ms, which can cause an audio dropout. The library recovers by
  itself. For play, eject the drive or use standalone power.
- **Encoder on STEMMA QT needs `settings.toml`.** At power-on the firmware probes
  the TV over I2C on the STEMMA QT pins (shared with HDMI's data lines). An encoder
  holding a line low then sends the board into safe mode (blinking yellow). Add
  `CIRCUITPY_PICODVI_ENABLE = "never"` to `settings.toml`.
- **Only 3.3V devices on STEMMA QT.** Never power a 5V encoder there: its outputs
  would put 5V on the shared bus. Use D6/D7 with resistor dividers instead (not yet
  tested).
- **Heavy games are close to the frame budget in 1.6x smooth.** Almost Tennis's
  busiest frames can run late; the audio buffer has absorbed it in testing. Use
  1.6x sharp for the most headroom.
- **Fixed 30 fps, 64KB Lua heap by default (256KB maximum), no save data.**
- **Wired DualShock 4 only.** Other USB controllers, Bluetooth and touch are not
  supported.
- **Untested:** the analog potentiometer crank and D6/D7 encoder wiring.
- **The 1.6x and 2-bit modes and HDMI audio** are tested on one TV; other displays
  may differ. The firmware is a patched CircuitPython 10.3 build; a clean rebuild
  from the pinned public sources reproduces the shipped UF2 except for its build
  date (see `engine/firmware/REBUILD-RESULTS.json`).

## credits and license

Crankfruit is MIT licensed, copyright 2026 Adafruit Industries (see `LICENSE`).
Third-party code keeps its own notices:

- Almost Tennis: adapted from https://github.com/SquidGodDev/almost-tennis
  (`69172662a659849c8b452e257c1f41f8cd240ad8`), MIT, SquidGod.
- Simple Snake: adapted from https://gitlab.com/mocchimochi/playdate/playdate-snake-game
  (`c9cc2a924dcbe31156529ae37326940360865530`), MIT, Mocchi Mochi.
- Playdate file-format research: https://github.com/cranksters/playdate-reverse-engineering
  (`e7be3ff0141b7cd3b9f008737eda1f0539aca45c`), CC0. Format notes are community
  documentation, not an SDK compatibility guarantee.
- CircuitPython, Lua 5.4.9, TinyUSB, Pico-PIO-USB, fast_float, stb_sprintf and
  other components: see `engine/licenses/` and the notices in their source folders.

Playdate is a trademark of Panic Inc.
