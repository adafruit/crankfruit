> **historical document:** written for the original Crankfruit review kit (2026-09).
> paths are relative to the repository root. for current setup see the main
> [README](../README.md).

# review evidence and limits

qualification date:2026-09-20. target: one Adafruit Fruit Jam RP2350B.
observed firmware: CircuitPython10.3.0-55-geb49ac4141-dirty, custom crankjam and
HDMI audio APIs. no firmware was flashed during this player integration pass.
the included UF2 has SHA256
`fe3f629d83609e900fe12d5e8f183ab59a6b708918abed26bcc9b506b57f49af`.
its structure and strings were audited. the installed firmware was identified by
boot/runtime APIs, not by a new full flash-memory hash readback.

## measured on the board

final app files are recorded in `app-manifest.json`; each installed file was
read back. the three privacy-rebuilt native helpers were imported and exercised
on the board, not just compiled on a host. source discovery found both games.
all automated gameplay used injected button states, not physical button presses.

| three-minute mode run | updates | mixed samples | worst step | worst mix | missed deadlines | audio starvation / dropped bytes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| almost tennis | 5,403 | 5,763,200 | 18ms | 14ms | 0 | 0 / 0 |
| orbit breaker | 5,403 | 5,763,200 | 14ms | 10ms | 0 | 0 / 0 |
| sound explorer | 5,403 | 5,763,200 | 11ms | 9ms | 0 | 0 / 0 |

each mode also recorded zero runtime/stream errors. startup, dynamic-library
selection and hold-to-return completed with clean native-audio teardown.
counts include three prefill updates, not three extra displayed frames. logical
updates are30Hz; game drawing deliberately uses a20Hz quota where applicable.
audio prefill puts simulation about66ms ahead of wall time. timing jitter was
measured, so this is not a zero-latency or tear-free claim. `late_frames` counts
late polling observations and can exceed actual update count.

the first smoke test failed in the library: repeated glyph command construction
took25ms and caused one starvation observation. library pages are now prepared
before playback; live animation redraws one mascot sprite. the repeated smoke
test measured4ms worst library step and zero starvation/dropped bytes/errors.
the failed candidate is not the delivered app. raw logs stay private; structured
metrics without board identifiers are in `physical-results.json`.

the long run preceded one cleanup-only change: `hardware.close()` now runs even
if optional-crank cleanup throws. subsequent final-app qualification is recorded
in `physical-results.json`; no drawing/audio algorithm changed after the long run.

real-device recovery checks passed10 assertions: deliberately broken source was
rejected at load and during active playback, native audio was stopped, the real
library rendered again, and Orbit Breaker played afterward. aborting the faulty
game intentionally discarded3,202 queued PCM bytes and waited for the active
bank tail; this is separate from zero-loss normal-play results above.

`media/hardware-demo.mp4` is58.6 seconds of real HDMI capture, trimmed to remove
signal acquisition/teardown, cropped and nearest-neighbor enlarged. all modes
and the library were visually inspected. digital capture audio is nonzero in
startup, tennis, Orbit Breaker and Sound Explorer. whites look gray through this
capture path; levels were not corrected. capture audio packet timestamps are
irregular, so the clip is output evidence, not a calibrated end-to-end audio-clock
or subjective listening test. board queue metrics above are a separate measurement.
the final42-file payload was read back and normal startup reached the library.

## host/source checks

- 36 loader/library/lifecycle checks, including an independent inserted game,
  disabled malformed entries, strict manifests, and cached 33-item pagination.
- 14 sound/PDA checks; real crankjam runtime additionally exercised64 synth
  configurations, stop-to-zero and cached sample parity.
- 23 optional-crank/scheduler policy checks. these are not physical crank tests.
- 32 audio-stream policy tests, including25 nested native-copy fixture cases.
- 9 installer policy tests; the installer was also used on the actual board.
- 30 C/Lua engine tests,205,092 checks under ASAN/UBSAN.
- native helper C sanitizer suites: blit9,907,985 checks; sprite99,735,988;
  PCM197,839,509. final helper bytes match the installed artifacts.
- 31 PDI/PDT codec tests plus exact artwork/atlas checks for138 masked sprites.
- independent pinned Cranksters decoder: all288,000 background pixels and54,307
  sprite pixels/alpha match. its CLI does not read PDT, so our table-framing glue
  invokes its unchanged cell decoder for each of the138 cells.
- startup rebuilt with the public C API:75 indexed frames,62 unique frames,
  80,000 PCM samples. all three outputs match installed startup assets byte-for-byte.
  five renderer failure/overwrite checks also passed.

`verify.py` repeats portable Python checks without accessing hardware. engine,
native and boot renderer builds are separately documented. fixture tests are
not presented as real Lua, video, audio, or hardware proof.

## compatibility and unverified items

read `COMPATIBILITY.md`: this is a bounded compatible-source player, not an
arbitrary PDX/PDZ/native-game emulator. Almost Tennis is an adapted MIT source
game; Orbit Breaker is original. PDI/PDT and PCM PDA conversion are offline tools;
general Playdate image/sample-player APIs are not exposed to cartridges yet.

not demonstrated: physical button presses, standalone-power unplug test,
physical STEMMA QT encoder or potentiometer, arbitrary commercial games, complete
SDK compatibility, analog audio-codec output, all HDMI monitors, or tear-free
scanout. software contains no host/network dependency for normal play. crank
backends are disabled by default and need wiring/calibration/timing qualification.

full firmware reconstruction has pinned public source, patches and configurable
launchers. those relocated launchers were plan checked; a new complete firmware
cross-build was not performed during this packaging pass. native helpers and
the portable C/Lua engine were actually rebuilt and tested.

## scrub scope

fresh allowlist packaging excludes local device IDs, home/workspace paths,
accounts, backups, raw logs, research, VCS and build caches. native helpers were
rebuilt to remove absolute source-name metadata; binary bytes were not patched.
PNG timestamp/text metadata was removed from the staged source copy without
changing image data. required copyright, licenses and public source provenance
remain. bounded scans and extraction checks are evidence, not a universal promise
that arbitrary downstream additions are safe to redistribute.
