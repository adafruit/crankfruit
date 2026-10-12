# independent review results

date / tester: 2026-10-09 / JP
board model/revision (keep UID private): Adafruit Fruit Jam RP2350B (revision not recorded)
firmware SHA256/version: `fe3f629d83609e900fe12d5e8f183ab59a6b708918abed26bcc9b506b57f49af`;
`boot_out.txt` reports CircuitPython 10.3.0-55-geb49ac4141-dirty on 2026-09-20
app manifest SHA256: `a78bc9ac625281622a8c8cad4475dc646315d46d7cbd7f5c74a838551a892c71` (42 files)
display/audio sink and power: consumer TV over HDMI (model not recorded), picture and
embedded audio both present; board powered by USB from the host computer
optional crank disabled / hardware + settings: disabled; no `/crank.json` on the board

| check | pass / fail / not tested | notes |
| --- | --- | --- |
| startup picture and sound | pass | library reached on TV; audio heard through TV speakers |
| library selection using physical buttons | pass | real B1/B2/B3 presses, first physical-button run of this kit |
| almost tennis gameplay and sound | pass | tester summary: "everything works" |
| orbit breaker gameplay and sound | pass | tester summary: "everything works" |
| hold B3 returns to library | pass | tester summary: "everything works" |
| sound explorer synthesis | pass | tester summary: "everything works" |
| sound explorer three samples | pass | tester summary: "everything works" |
| independent source-game insertion | pass | Simple Snake port copied by hand to `/games/snake/` (no installer, no launcher edit); appeared in library and played. see Snake section below |
| malformed/unsupported entry disabled | not tested | |
| game error returns to library | not tested | |
| 10-minute play/audio continuity | partial | one scene ran ~36 min (65,857 presentations) before a Ctrl-C: 0 dropped bytes, 0 errors, 0 missed deadlines, but 1 underrun observation; worst service gap 53ms, worst tick 27ms. which scene was not captured |
| optional crank direction/calibration/latency | pass (later) | seesaw STEMMA QT encoder (product 4991) measured and played; see encoder addendum below |
| standalone power, computer unplugged | not tested | board stayed on host USB power |

the five "everything works" rows record the tester's overall report, not separate
per-item notes.

## reproduction steps

1. host checks on macOS (Apple clang, Homebrew CMake, Python 3.14.7), run on a copy
   of the kit: `verify.py` (package hashes, 42-file manifest, 9 installer, 36 loader,
   14 sound, 23 crank, 32 audio-stream, 31 PDI/PDT tests, asset check), engine
   ctest under ASAN/UBSAN (30 tests, 205,092 checks), `native/build.py --cc clang`
   (blit 9,907,985 / sprite 99,735,988 / PCM 197,839,509 checks), and boot-source
   render; rendered `boot.frames`/`boot.index`/`boot.pcm` byte-identical to `app/bootclip/`.
   all passed.
2. optional SDL2 host built (`CJ_BUILD_HOST=ON`); Orbit Breaker and Almost Tennis
   played interactively on the desktop at 30Hz with CoreAudio output, exit 0.
   host evidence only, not Fruit Jam evidence.
3. first firmware attempt did **not** take effect: after copying the UF2,
   `boot_out.txt` still reported stock CircuitPython 11.0.0-alpha.1 and no app files
   were present. the installer wrote nothing to that board, as expected.
4. re-entered the bootloader (BOOT/BUTTON1 + reset), copied
   `firmware/impossible-playdate-fruit-jam.uf2` to RP2350. `boot_out.txt` then
   reported 10.3.0-55-geb49ac4141-dirty. flashing reset the CIRCUITPY filesystem;
   previous board files were removed (not needed by the tester).
5. `python3 install.py --validate-only` passed, then
   `python3 install.py --kit . --port <port> --mount <CIRCUITPY> --uid <UID> --backup-dir <dir> --start`
   reported `INSTALL_READBACK_PASS 42 files`. all 42 installed files were separately
   byte-compared with `app/`: 0 mismatches.
6. startup, library, both games and Sound Explorer then checked on the TV with
   physical buttons.

no code changes were made to the kit for the results above.

## addendum: USB gamepad support (kit modified)

after the review above, optional USB gamepad input was added. this is a local
change, not part of the reviewed kit; the unmodified kit is the first commit of
the git repository (all 344 files match the original `SHA256SUMS`).

- new `app/gamepad_input.py`, opt-in via `/gamepad.json`; wired Sony DualShock 4
  (`054c:05c4` tested) on the Fruit Jam USB-A host port. d-pad/left stick = directions,
  cross = A, circle = B, options = return to library. onboard buttons still work.
- `app/hardware.py` merges pad bits into `read_buttons()`; `app/crankfruit.py` loads
  the config, masks the return bit before cartridges, routes options to the library.
- new `tools/gamepad/` (README, template config, MIT license, 19 host tests); `verify.py`
  runs them. `app-manifest.json` (now 43 files,
  `1989f31b8b317e68f72106dc7ba319e3e6cc4165903ef1a4ca0d3a9a994556c2`), `MANIFEST.json`
  and `SHA256SUMS` regenerated; full `verify.py` passes.
- installed with `install.py` (`INSTALL_READBACK_PASS 43 files`), template copied to
  `/gamepad.json`.

| check | pass / fail / not tested | notes |
| --- | --- | --- |
| every DS4 control decoded on board | pass | raw REPL capture; all buttons, d-pad, stick |
| unplug / replug | pass | `USBError` caught, buttons released, auto-reconnect; twice during gameplay too |
| library and games with gamepad | pass | tester: "both games feel good with the controller" |
| options returns to library | pass | every game scene exited cleanly to the library |
| audio continuity with gamepad | pass (~6 min) | 0 underruns, 0 dropped bytes, 0 missed deadlines, 0 errors |
| 10-minute play with gamepad | not tested | logged gameplay totalled ~6 minutes |

player metrics with the gamepad enabled (serial log, same board and TV):

| mode | play time | worst step | kit baseline worst step | worst tick | underruns / dropped |
| --- | --- | --- | --- | --- | --- |
| almost tennis | 61s + 10s + 30s | 18 / 19 / 18ms | 18ms | 39ms | 0 / 0 |
| orbit breaker | 36s + 60s | 13 / 13ms | 14ms | 33ms | 0 / 0 |
| sound explorer | 49s | 11ms | 11ms | 31ms | 0 / 0 |
| library (5 visits) | ~3min | 4ms | 4ms | 24ms | 0 / 0 |

pad reads cost ~0.94ms each, at most once per 25ms; the connect step costs ~8.6ms
once per (re)connect. worst tick (31-39ms in games) exceeds the single pre-gamepad
snapshot seen (27ms, scene unknown); it did not cause underruns here, but it is the
first metric to watch in longer sessions. `poll_ms` can be raised to reduce pad reads.

## future possibility: larger picture (display stays 1x for now)

the game is drawn 1x (400x240) centred in the 640x480 HDMI output. a clean 2x
(800x480) is not possible with this firmware. REPL probe of `picodvi.Framebuffer`
on 2026-10-09:

| mode | accepted colour depths |
| --- | --- |
| 640x480 | 1, 2, 8 (current; HDMI audio confirmed at exactly 32 kHz) |
| 720x400 | 1, 2, 8 |
| 320x240, 360x200 | 8 only (hardware-doubled to 640x480 / 720x400) |
| 400x240, 640x240, 720x480, 800x480, 800x600, 1280x720 | rejected: "Invalid width and height" |

2x does not fit either full mode (800 > 640 wide; 480 > 400 tall).

**possible later: 1.5x inside 640x480.** game becomes 600x360, centred, using fixed
nearest-neighbour mapping (destination x -> source (2*x)//3, same for y), so game
pixels alternate 2 and 1 screen pixels. keeps the tested 640x480 video/audio mode;
needs a 1.5x variant of the native `blit` helper (similar cost to the current one).
a still-frame mockup looked clearly bigger with readable text, but 1-px lines and
glyph strokes come out 1 or 2 px wide, and moving sprites may ripple slightly; this
was not seen in motion. suggested next step if revisited: add a 1.5x option to the
SDL desktop host to judge motion before touching the board.

true 2x would need an 800x480 mode patched into the firmware's HDMI driver, a check
that HDMI audio fits that timing, a full firmware rebuild, and a sink that accepts
800x480 (non-standard for TVs).

## addendum: community game port (Simple Snake)

source: Mocchi Mochi's (TauchMe) MIT Playdate snake game,
gitlab.com/mocchimochi/playdate/playdate-snake-game at
`c9cc2a924dcbe31156529ae37326940360865530` (v1.3.4). ported to the
`crankfruit-lua-v1` profile in `examples/snake/` (upstream LICENSE kept; every
change listed in `examples/snake/README.md`). gameplay, speeds, grid, collisions
and game-over layout unchanged; imports, `+=`, sample/music playback, datastore,
system menu and rounded rects adapted or removed. background music (third-party)
not included. up/down steering requires the USB gamepad.

- host: `cartridge_cli.py check` reports an enabled source candidate; headless run
  moved, ate, scored and reached game over; `verify.py` passes with Snake added to
  `MANIFEST.json` / `SHA256SUMS`.
- board: folder copied by hand to `/games/snake/` (byte-compared, no AppleDouble
  files) and the app restarted; Snake appeared in the library with no player change.

| check | pass / fail / not tested | notes |
| --- | --- | --- |
| appears in library after manual copy | pass | independent source-game insertion |
| 4-way steering with gamepad | pass | tester: "everything worked great" |
| eat sound, game over, restart with A | pass | tester: "everything worked great" |
| options returns to library | pass | scene exited cleanly to the library |
| Snake audio/timing (127s) | pass | 0 underruns, 0 dropped bytes, 0 missed deadlines, 0 errors; worst step 20ms, worst tick 34ms; peak Lua heap 27.5KB of 64KB |

### observation: long idle library session

the library had been left idle ~3.2 hours (11,501s) before Snake was opened,
with the gamepad enabled. that scene recorded 2 underrun observations and 2 missed
deadlines, worst step 70ms, worst tick 87ms, worst service gap 73ms (normal
library step is ~4ms); 0 dropped bytes, 0 errors. cause not determined from
summary metrics: the gamepad is one candidate; a pre-gamepad ~36-minute run also
showed 1 underrun. suggested follow-up: a comparable idle run with `/gamepad.json`
removed.

### board incident: CIRCUITPY read-only

before copying Snake, the Mac saw CIRCUITPY as read-only ("Media Read-Only: Yes")
even after remounting, while CircuitPython also reported its own mount read-only.
cause not found. `microcontroller.reset()` (equivalent to the reset button)
restored host write access.

## addendum: right-stick crank (proof of concept, 2026-10-12)

the DS4 right stick can drive the Playdate crank (`"crank": true` in
`/gamepad.json`); details in `tools/gamepad/README.md`. no crank hardware was used.

| check | pass / fail / not tested | notes |
| --- | --- | --- |
| angle maths on board (up 0, right 90, down 180, left 270; wrap across 0) | pass | REPL check on CircuitPython |
| crank cost | pass | ~69us per pad report, ~21us per frame read |
| Orbit Breaker paddle follows stick rotation, clockwise = right | pass | tester confirmed |
| speed | pass at 70% | 100% (one-to-one) felt a little fast; `crank_scale` 70 adopted |
| Orbit Breaker timing with stick crank (42s) | pass | 0 underruns, 0 dropped bytes, 0 missed deadlines, 0 errors; worst step 14ms, worst tick 32ms |
| hardware crank (`/crank.json` seesaw/analog) | seesaw: pass | see encoder addendum below; analog pot still not tested |

31 gamepad host tests (11 stick-crank) pass; `verify.py` passes.

## addendum: STEMMA QT rotary encoder crank and 4-frame audio prefill (2026-10-12)

hardware: Adafruit I2C STEMMA QT rotary encoder breakout (seesaw chip id 0x55,
product 4991) on the Fruit Jam STEMMA QT port, address 0x36. `board.STEMMA_I2C`
exists; the bus also shows the onboard audio chip (0x18) and what appear to be the
TV's HDMI DDC devices (0x3a, 0x50-0x57). `adafruit_seesaw` 1.18.2 from the
CircuitPython 10.x bundle (20261010) copied to `/lib`; `adafruit_bus_device` is
built into this firmware.

`/crank.json`: `{"enabled": true, "kind": "seesaw", "bus_factory": "STEMMA_I2C",
"address": 54, "counts_per_revolution": 20, "read_delay_ms": 0}`.

code changes: `crank_input.py` gains optional `read_delay_ms` (0..8, default 8 =
the library's original `IncrementalEncoder.position` path; 0..7 reads the position
register directly with that delay). `player.py` accepts `prefill_frames=4` with a
12,288-byte queue (2 and 3 keep 8,192); `crankfruit.py` uses 4. the gamepad records
its slowest poll and slow-poll count per scene (`GAMEPAD_DONE` log line).

| check | pass / fail / not tested | notes |
| --- | --- | --- |
| encoder identified and read | pass | chip 0x55, product 4991 |
| read cost | pass with `read_delay_ms` 0 | library default 9.1ms per read; 0ms delay 1.0-1.1ms |
| fast-read accuracy | pass | 3,711 zero-delay reads vs default-delay reads: 0 mismatches, 0 jumps, incl. fast spinning |
| counts per revolution / direction | pass | 20 (tester confirmed), clockwise counts up |
| Orbit Breaker paddle follows knob | pass | tester: clockwise right, "clicky but fine" |
| priority over stick crank | pass | log: `GAMEPAD_CRANK ignored: /crank.json hardware crank takes priority` |

timing investigation (Orbit Breaker with the encoder):

| run | prefill | play | worst tick | underruns | dropped | notes |
| --- | --- | --- | --- | --- | --- | --- |
| first encoder run | 3 | 61s | 45ms | 1 | 0 | stick-crank run was 32ms / 0 |
| instrumented (in-memory wrappers) | 3 | ~52s | 37ms | - | 0 | encoder read max 1.9ms (99% <1.5ms); slow ticks are slow game frames |
| instrumented, heap sampling | 3 | ~53s | 41ms | - | 0 | timing inflated by 16-22ms `gc.mem_free()` probes |
| after change | 4 | 48s | 35ms | 0 | 0 | 0 missed deadlines, 1 late frame, gamepad max poll 2ms |

findings: the encoder read is not the spike. slow frames (20-35ms) are Orbit
Breaker's own heavy frames: Lua step 4-14ms + synth mix 6-13ms + present 2-3ms +
in-frame audio servicing 3-9ms. automatic garbage collection is rare (app allocates
~25KB/s; one collection every ~29s, ~12.6ms each with a game loaded), so scheduled
collection was not pursued. one 40.7ms gamepad poll was seen once and not
reproduced in ~1.7h of later polling (max 3ms). the 4-frame prefill adds ~33ms
audio/scene-start latency and removed the observed underrun.

library idle stalls narrowed: a ~1.7h idle library session (prefill 4) again had 2
underruns, 2 missed deadlines, worst library step 60ms, worst tick 77ms, 0 dropped
bytes, while the gamepad's slowest poll was 3ms. the stall is in the library
scene's own update step, not the gamepad or the encoder. not yet fixed.
