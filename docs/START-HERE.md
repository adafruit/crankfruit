> **historical document:** written for the original Crankfruit review kit (2026-09).
> paths are relative to the repository root. for current setup see the main
> [README](../README.md).

# start here

this review kit is for **adafruit fruit jam RP2350B only**. it includes experimental
custom firmware, not an official CircuitPython release. back up existing board
files/settings before changing firmware. never install it on another board.

## already-running review board

power from USB; connect DVI/HDMI to a display/capture device accepting embedded
audio. after the bad-apple startup, choose almost tennis, orbit breaker, or sound
explorer using B1/B2 and B3. hold B3 to return. gameplay and sound are standalone.
autoreload is deliberately disabled. restart after app edits; return to the library
to re-scan game folders. a computer is not needed during play.

## another fruit jam

1. back up the board; close programs holding its serial connection.
2. deliberately enter RP2350 bootloader mode and copy
   `firmware/crankfruit-fruit-jam.uf2` to RP2350. this replaces firmware
   and may affect filesystem layout. the app installer never performs this step.
3. wait for CIRCUITPY. confirm its serial port and UID using both `boot_out.txt`
   and the serial device descriptor.
4. run `python3 install.py --validate-only` from this extracted kit.
5. install `pyserial==3.5` in a Python environment, then run:

```sh
python3 install.py --port SERIAL_PORT --mount CIRCUITPY_VOLUME --uid BOARD_UID --backup-dir HOST_BACKUP_DIRECTORY --start
```

replace placeholders with the selected board and a host backup folder. the
installer verifies firmware APIs, backs up changed files, installs `code.py` last,
and reads back every byte. no auto-selection, deletion or flashing. see
`TOOLS-README.md`. on a Courier-era board, preserve/move unwanted legacy game
folders outside `/games/`, otherwise they appear as unsupported entries.

Adafruit's [board guide](https://learn.adafruit.com/adafruit-fruit-jam?view=all)
documents bootloader entry: hold BOOT/BUTTON1 while resetting, wait for RP2350,
then release. its stock CircuitPython download is **not** this custom runtime.

## review checklist

watch startup/library animation; listen to navigation and games; play both games;
change sound explorer wave/pitch/decay/sample; add another source-game folder;
check malformed/unsupported entries; hold B3 to return. read `RESULTS.md`,
`AUTHORING.md`, source/licenses and `SHA256SUMS`. record independent findings in
`TEST-RESULTS-TEMPLATE.md`.

read `tools/crank/README.md` before wiring a crank. no crank is enabled by default.
copy/edit its disabled JSON template as `/crank.json` only after confirming the
bus/pin and calibration. this physical input path is not yet hardware-qualified.

video is400x240 logical monochrome centered in640x480 scanout. direct-buffer
presentation is not an atomic swap or a tear-free guarantee. audio is32kHz mono
PCM over HDMI. display/capture routing matters; a DVI-only sink may show video
without sound. the analog audio codec is not used as a fallback in this build.

## recovery

interrupt a failed app with Ctrl-C in a serial console and inspect the error.
remove/disable invalid crank configuration or restore installer backups. a game
error normally returns to the library; failure to stop native audio is fatal.
keep install logs/backups private because they contain local paths/device IDs.
standard BOOT/RESET recovery remains available; no flash-nuke tool is included.

## rebuild boundaries

editable app source is in `app/`; `engine/` builds without a proprietary SDK;
`native/` contains removable Turbo helpers. full firmware base:
`adafruit/circuitpython@eb49ac414192f75a81316906e78937e654f3f56e`.
native loading flag: `CIRCUITPY_ENABLE_MPY_NATIVE = 1`. C/Lua runtime inclusion:
`USER_C_MODULES`. helper ABI:`0x1f06`, ARMv7EMSP. no Viper compiler or cloud service
runs on the board.

portable engine/native host checks were rerun. the relocated full firmware
reconstruction launcher was plan checked, not used for a fresh complete firmware
cross-build. that rebuild limit is separate from recorded on-device app tests.
