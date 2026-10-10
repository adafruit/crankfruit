# optional crank input

`CrankInput(config=None)` is disabled by default. disabled construction and reads
do not import hardware modules, open files, select pins or open an I2C bus.
`read()` returns `(angle_degrees, signed_delta_degrees)`; `close()` is idempotent.
closed instances reject reads. all source is MIT; no device was accessed here.

## parent integration

construct once before audio playback. the parent may explicitly load
`load_config('/crank.json')`; a missing optional file should select disabled mode,
while invalid JSON/configuration must fail visibly. the helper never discovers or
loads a file automatically. it accepts only a JSON object, bounded to4096
characters. alternatively import `CRANK_CONFIG` from a user-edited settings module
and pass that dict to the constructor.

the parent GamePlayer must call `read()` only after the frame's deadline and PCM
capacity admission, immediately before the frame. do not consume crank movement
on every fast outer-loop iteration. optional `read(frame_id)` memoizes a sample
for a repeated nonnegative frame token; if using tokens, advance the token only
after actual frame consumption. a held sample must not be applied to two frames.
the parent's admission-time no-argument integration needs no token.

the staged player now loads `/crank.json` after hardware initialization and before
playback; only missing-file errno2 selects the disabled default. malformed JSON,
permission errors and invalid settings are not silently ignored. input is passed
to loaded Lua games only, not the splash, library or Sound Explorer. the app owns
the shared crank object and closes it after scene cleanup; individual scenes
must not close it.

`crank_settings.py` contains disabled placeholder templates. `crank-config.json`
is also disabled; it may be installed as `/crank.json`. no guessed board pin or
I2C address is active in either file.

## seesaw STEMMA QT rotary encoder

required enabled settings: `kind='seesaw'`, explicit `bus_factory` naming a
verified public board I2C factory, integer I2C `address`, and positive integer
`counts_per_revolution`. optional encoder channel0-3 defaults0, direction+1/-1
defaults+1, and zero_degrees0-359 defaults0. counts are the driver's position
units per mechanical revolution, not assumed detents. measure/verify them for
the chosen hardware; multiple quadrature counts can correspond to one detent.

the driver opens `Seesaw(bus, addr=address, reset=False)` and
`IncrementalEncoder(seesaw, encoder=channel)`, reading `.position` once per frame.
it never writes the encoder position, reads the destructive delta register, or
resets the seesaw. first read establishes a software baseline with zero delta.
subsequent count differences preserve direction and rotations over180 degrees;
angle alone wraps into [0,360). signed32 counter rollover is handled, assuming
less than2^31 counts between observations. sensor reset/hotplug is not inferred
or silently corrected; restart/reinitialize the input if its counter resets.

install `adafruit_seesaw` and `adafruit_bus_device` from the bundle matching the
device's CircuitPython version only when enabling this backend. they are not
vendored here. board I2C factories commonly return shared bus objects, so close
drops references without deinitializing the bus or disrupting other devices.

APIs verified against Adafruit's current
[rotaryio source](https://docs.circuitpython.org/projects/seesaw/en/latest/_modules/adafruit_seesaw/rotaryio.html)
and [Seesaw source](https://docs.circuitpython.org/projects/seesaw/en/latest/_modules/adafruit_seesaw/seesaw.html),
with upstream main revision `13ba8ba2a2cecb9df5a41390f991ce6c0cd76e14` recorded.

## analog potentiometer

required enabled settings: `kind='analog'`, explicit ADC-capable board `pin`
name, measured `adc_min`/`adc_max` in0..65535 with min<max, and integer
`travel_degrees` in1..360. deadband defaults128 ADC units and must be less than
the calibrated range. direction and zero_degrees work as above.

uses `analogio.AnalogIn(pin).value` and deinitializes only that owned ADC on close.
the official [AnalogIn API](https://docs.circuitpython.org/en/stable/shared-bindings/analogio/)
returns16-bit-scaled values even when underlying conversion resolution is lower.
reads are clamped to the calibrated endpoints. changes at or inside the deadband
hold the last accepted position; slow motion accumulates relative to that held
baseline and is eventually emitted. the first absolute position has zero delta.

a pot has stops and represents bounded absolute travel, not an endless crank.
delta follows its signed physical travel, not the shortest path around a circle:
a full270-degree sweep reports+270 even though displayed angle is wrapped. do
not wire an unverified pin or apply voltage beyond the selected board's analog
input limits. verify pin conflicts with DVI/audio/storage before enabling.

## timing and evidence limits

I2C polling and the seesaw library's temporary four-byte buffer/unpack result
consume time and allocations. `read()` also returns a tuple. neither this module
nor Turbo makes bus transfers instantaneous. the Turbo/workflow skill review
keeps acquisition in CircuitPython; no acceleration is proposed for this tiny
mapping. measure the complete input+game+audio path before enabling a crank in a
qualified real-time build. do not add GC disabling or unbounded polling.

13 host tests passed: disabled no-import/no-I/O behavior, positive/negative
detents, multi-turn accounting, signed32 wrap, duplicate frame-token reads,
ADC clamp/calibration/noise/slow motion, reversed travel, invalid settings,
read-error baseline preservation, resource ownership, and bounded JSON loading.
the real CircuitPython UNIX build also passed disabled construction/read/close
and JSON load. these are not hardware, electrical, input-latency, audio, or
physical-direction verification. no pins/buses were touched by this lane.

## staged scheduler/lifecycle policy tests

run `python3 -B -m unittest -v test_scheduler.py` from this folder. to review a
copied package, set `CRANKFRUIT_APP_DIR` to its actual app directory. tests load
that staged `player.py`, `stream.py` and `crankfruit.py`; bytecode writes are
disabled, so no app cache files are generated.

10 additional policy checks passed with explicit runtime/hardware/crank stubs:
prefill and before-deadline loops do not sample; queue backpressure does not
consume movement; each admitted frame receives the exact angle/delta once;
explicit angle/delta still works with no hardware crank; input exceptions stop
audio before runtime close; config handling is ENOENT-only; only Lua games
receive crank input. this is scheduler/lifecycle evidence, not sensor/native
runtime or audio-output verification.
