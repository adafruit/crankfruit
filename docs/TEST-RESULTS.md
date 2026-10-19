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
| malformed/unsupported entry disabled | pass (later) | 2026-10-16 on the board: invalid JSON, an unknown manifest key and a bytecode main.lua were each listed but disabled with a reason; A on one showed the reason instead of launching; real games stayed enabled (12/12 checks) |
| game error returns to library | pass (later) | 2026-10-16 `tests/hardware/003_recovery.py`: load-time and mid-game (during audio) failures rejected, audio stopped, library rendered, Orbit Breaker played afterwards (10/10, `~~END~~`); test folders removed |
| 10-minute play/audio continuity | partial | one scene ran ~36 min (65,857 presentations) before a Ctrl-C: 0 dropped bytes, 0 errors, 0 missed deadlines, but 1 underrun observation; worst service gap 53ms, worst tick 27ms. which scene was not captured |
| optional crank direction/calibration/latency | pass (later) | seesaw STEMMA QT encoder (product 4991) measured and played; see encoder addendum below |
| standalone power, computer unplugged | pass (later) | 2026-10-15 demo on a power supply with no computer: app, gamepad and handwheel crank all worked; see handwheel addendum |

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
   `firmware/crankfruit-fruit-jam.uf2` to RP2350. `boot_out.txt` then
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

## addendum: crank in the library, Almost Tennis, Simple Snake and Sound Explorer (2026-10-12)

with the STEMMA QT encoder as the crank (20 counts/turn, so one click = 18 degrees):

- library: crank moves the highlight, one game per 18 degrees, clockwise = next,
  with the navigation beep; at most 3 moves per frame, leftover of a fast spin
  dropped; never launches a game.
- Almost Tennis: a crank flick of 10 degrees or more in one frame swings, as in
  upstream `player.lua` ("med" `CRANK_SENSE`), during play only. the crank change
  is read every frame so stale movement cannot swing later.
- Simple Snake (addition, not upstream): one click turns the snake right
  (clockwise) or left relative to its heading; one turn per snake step, one early
  click buffered.
- Sound Explorer: one click acts like B2 (clockwise) or B1 on the selected field.
- `crankfruit.py` now passes the crank to the library and Sound Explorer as well as
  Lua games (not the splash).

| check | pass / fail / not tested | notes |
| --- | --- | --- |
| library highlight by crank | pass | tester: "works well" |
| Almost Tennis, Snake, Sound Explorer crank | pass | tester: "they felt good" |
| Snake steering in the desktop host | pass | clockwise click at frame 40 turned down, counter-clockwise at 100 turned right; head positions matched |
| Almost Tennis flick in the desktop host | pass | 12-degree flick produced the swing sound; no flick, no sound |
| Snake / Sound Explorer timing | pass | Snake 83s, Sound Explorer 35s: 0 underruns, 0 dropped bytes, 0 missed deadlines |

two problems found and fixed during this work:

1. **Almost Tennis redraws.** the first version forced an immediate redraw on any
   frame with a crank flick, defeating the port's 20Hz redraw budget while the
   knob turned: 54s, 3 underruns, worst tick 45ms, worst service gap 86ms. now a
   redraw is forced only when a swing actually starts.
2. **encoder read glitch.** one Almost Tennis run ended after ~4s with
   `CARTRIDGE_ERROR almost-tennis OSError(19,)`: a single I2C read got no answer
   (cable checked, seated). the zero-delay encoder read now retries once, then
   holds the last position (no movement) for that frame, and only fails after 30
   consecutive failed frames (~1s) or on the very first read. each scene logs
   `CRANK_DONE {retries_ok, held_frames, max_consecutive}`.

after both fixes, Almost Tennis ran 298s: 0 errors, 1 underrun, 1 missed deadline,
0 dropped bytes, worst step 18ms; encoder 0 retries / 0 held frames; gamepad max
poll 3ms. the one underrun came from a single 73ms tick stall that matches the
70-85ms stalls seen in idle library sessions; it is not the game step, gamepad or
encoder. unconfirmed hypothesis: host (macOS) access to the mounted CIRCUITPY
drive stalling flash. suggested test: eject CIRCUITPY and log a long idle session.

## addendum: display scaling and smoothing (2026-10-13)

firmware HDMI modes accepted by `picodvi.Framebuffer` (probe): 640x480 and 720x400
at 1/2/8-bit; 320x240 and 360x200 at 8-bit only; 400x240, 800x480, 720x480,
800x600 and 1280x720 rejected. a clean 2x of 400x240 is therefore impossible.

**desktop preview** (`engine/host`, `--board-scale 1|1.5|1.6|1.6s`, Tab cycles):
reproduces the board's 640x480 output and mappings; saved frames place the game
exactly at 400x240@(120,120), 600x360@(20,60), 640x384@(0,48). tester chose 1.6x,
then liked the smooth preview.

**native scalers** (`native/blit`, reproducible toolchain: rebuilding the original
helpers first gave byte-identical blit/sprite/pcm; sprite and pcm unchanged since):

| function | output | board time / frame | verification |
| --- | --- | --- | --- |
| `blit` (kit) | 1-bit 1x | 1.57ms | kit suite |
| `blit16` | 1-bit 1.6x | 2.43ms | per-pixel reference (297 frames); 3,000 on-board samples, 0 mismatches |
| `blit2` mode 0 | 2-bit 1x | 1.1ms | per-pixel reference, both white levels |
| `blit2` mode 1 | 2-bit 1.6x sharp | 3.2ms | per-pixel reference; 1,500 on-board samples, 0 mismatches |
| `blit2` mode 2 | 2-bit 1.6x smooth | 6.0ms (from 8.1 before optimisation) | per-pixel reference; 1,500 on-board samples, 0 mismatches |

host blit suite: 184,130,503 checks under ASAN/UBSAN (and `-Wshadow`).

**2-bit probe on the TV:** 76,800-byte framebuffer allocated in SRAM; four bars
black / dark grey / light grey / white as expected; HDMI audio accepted at exactly
32kHz (1,281,064 bytes in 20s vs ~1,280,064) and the tone was heard throughout.
the 2-bit level-3 white was visibly brighter than the 1-bit white: the HDMI encoder
puts pixel bits at the top of each channel, so 1-bit white is ~50% (0x80), which
the tester notes approximates the light grey of the Playdate's Sharp Memory LCD.
hence `"white": "playdate"` (level 2, default) vs `"bright"` (level 3).

| check | pass / fail / not tested | notes |
| --- | --- | --- |
| 1.6x (1-bit) on the TV | pass | tester: "it looks good"; Orbit Breaker 57s: 0 underruns, worst tick 36ms, worst present 4ms |
| B1 live toggle (1-bit) | pass | 16 toggles incl. mid-game and across gamepad unplug/replug; 0 underruns |
| onboard buttons as settings only while a pad is connected | pass | tester: "it all worked" |
| 2-bit three-mode B1 cycle | pass | 9 presses cycled 1x / 1.6x / 1.6x smooth three times, no errors |
| Playdate-like white default | pass | startup log `white 2` |
| smooth-mode in-game timing | pass (tight) | Almost Tennis, 2-bit, modes cycled during play: see frame-skip section below; 0 dropped bytes, but heaviest frames exceed 33ms |

**freeze and recovery:** one idle library session (2-bit) ended with
`game scheduling deadline exceeded (100ms)`: worst tick 384ms, worst pump and
present both 68ms, service gap 136ms, 1,072 dropped bytes. it coincided with the
tester closing `code.py` (open from CIRCUITPY) in a text editor, which writes to
the drive; flash writes stall code running from flash. this is the most likely
cause of the earlier 70-89ms library stalls too. the library now reopens after
such a failure with a "RECOVERED" footer (3 failures within 60s still stop the
app; audio-stop failures stay fatal). after the fix the tester opened and closed
`code.py` again: no crash. advice: don't keep CIRCUITPY files open while playing.

### unchanged-frame skipping (2026-10-13)

first Almost Tennis session in 2-bit (modes cycled 1x / 1.6x / 1.6x smooth during
play, 93s): worst step 18ms, mix 14ms, present 8ms, tick 46ms; 1,572 late frames,
6 missed deadlines, 1 underrun, 0 dropped bytes. the scaler ran on every frame
although Almost Tennis draws at 20Hz.

new native `frame_changed` (word-wise compare-and-copy; 0.23ms on the board for an
identical frame, 0.11ms when changed; the Python buffers are in PSRAM, so a
byte-wise version took 0.88ms) lets `present()` skip the scaler for unchanged
frames, forcing a redraw at startup and after each B1 mode switch.

| scene (2-bit, mostly smooth) | play | presents skipped | late frames | missed | underruns / dropped | worst tick / gap |
| --- | --- | --- | --- | --- | --- | --- |
| library | 33s | 828 of 997 (83%) | 770 | 0 | 0 / 0 | 30 / 31ms |
| Almost Tennis (B1 cycled twice) | 87s | 970 of 2,617 (37%) | 303 | 5 | 0 / 0 | 46 / 94ms |

remaining: Almost Tennis's heaviest frames (step 18 + mix 14 + smooth present 8ms)
still exceed the 33ms frame; the 4-frame audio buffer absorbed them in this run.
possible next step: cache each source row's 5-pixel groups to cut smooth from ~6
to ~4ms.

## addendum: 100-pulse handwheel crank, step sizes, safe-mode fix (2026-10-13..15)

hardware: MBL600/800-100P line-driver handwheel (datasheet: 5V +/-5%, 100 pulses,
A/B/A-/B-), powered at 3.3V from the Fruit Jam STEMMA QT port, A/B on SDA/SCL
(GPIO20/21, consecutive as rotaryio needs). powered at 3.3V its outputs cannot
exceed 3.3V; it is not to be powered at 5V on these pins (shared bus with the
onboard audio chip and HDMI DDC).

| check | pass / fail / not tested | notes |
| --- | --- | --- |
| counts per click / per turn | pass | 10 clicks -10, 10 back +10, one turn -100 (repeated 2026-10-15: -10 / +10) |
| signal quality | pass | 587 changes while spinning fast, never more than 1 count between 5ms reads |
| `kind: "rotaryio"` crank | pass | `direction: -1` so clockwise is positive; reads are a PIO counter, no bus traffic |
| Orbit Breaker with handwheel (2-bit) | pass | 63s: 0 underruns, 0 missed deadlines, worst tick 43ms |
| per-crank `step_degrees` | pass | handwheel set to 3.6 = one click per library highlight / Sound Explorer value |
| Simple Snake one-click turns | pass (host) | step 3.6 degrees; one 3.6 or one 18 degree click each give exactly one turn |
| standalone power-on with handwheel | pass (after fix) | first attempt fell into safe mode (see below); with the `settings.toml` fix the 2026-10-15 standalone demo worked (tester report) |

**safe mode at power-on:** powered from a supply (not the computer) with the
handwheel connected, the board blinked yellow and did not start. on the computer:
`safe_mode_reason = GC_ALLOC_OUTSIDE_VM`. cause: at boot the firmware's
`picodvi_autoconstruct()` opens I2C on SDA/SCL to probe the TV's EDID (0x50); with
the encoder holding a line low (depends on wheel rest position) the I2C setup fails
outside the VM. earlier, opening `board.I2C()` with the encoder attached had raised
"No pull up found on SDA or SCL". fix: `CIRCUITPY_PICODVI_ENABLE = "never"` in the
board's `settings.toml` (string present in the installed firmware). after a hard
reset with the setting, the app started on its own and the encoder read correctly.
this also confirms the STEMMA QT I2C bus is shared with the HDMI DDC lines.

## addendum: clean firmware rebuild from pinned sources (2026-10-16)

`engine/firmware/prepare.py` fetched CircuitPython `eb49ac414192f75a81316906e78937e654f3f56e`
and the Fruit Jam dependencies, applied the three byte-checked patches (28 outputs
verified) and the link integration (`FIRMWARE_SOURCE_PASS`). the first build stopped
at "Cannot determine version": the one-commit shallow clone has no release tags.
after CircuitPython's `make fetch-tags` (now built into `prepare.py`), `build.py`
completed with Arm GNU Toolchain 15.3.Rel1 (arm-15.149) on macOS arm64.

result: 2,380,800-byte UF2, 4,650 blocks, family 0xe48bff59, flash 0x10000000 to
0x10122a00, identical to the shipped image in every byte except 12: the build date
in three copies of the version banner (`... on 2026-09-20` vs `... on 2026-10-16`).
version banner, crankjam, HDMI audio methods and the CIRCUITPY_PICODVI_ENABLE
setting all present; no local paths in the image. the shipped, hardware-tested UF2
is kept; `engine/firmware/REBUILD-RESULTS.json` records hashes. not flashed, as
the code is byte-identical.

## addendum: handwheel moved to A1/A2 (2026-10-19)

the 100-pulse handwheel was rewired to the 3V, GND, A1 and A2 header pins (A1/A2 =
GPIO41/42), off the shared STEMMA QT I2C bus. `rotaryio` opened the pins without
issue (PIO on the RP2350B's upper GPIO range). calibration: 10 clockwise clicks -10,
10 back +10, same direction as on SDA/SCL. `/crank.json` now uses `pin_a: "A1"`,
`pin_b: "A2"`; the `CIRCUITPY_PICODVI_ENABLE` workaround was removed from
`settings.toml`, and after a hard reset the app started on its own with the crank
enabled. A1/A2 is now the recommended wiring.

