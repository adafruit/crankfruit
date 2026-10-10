# removable native helpers

three MIT-licensed bounded helpers, architecture ARMv7EMSP, CircuitPython MPY ABI
`0x1f06`. they do not access hardware themselves. the prebuilt app must use a
custom Fruit Jam firmware with native-module loading enabled.

- `blit`: 400x240 MSB-first stride52 bitmap into centered 640x480 LSB-first scanout.
- `sprite`: background plus packed masked sprites, clipping and both flips.
- `pcm`: bounded allocation-free byte copies between nonoverlapping audio buffers.

source, independently structured Python references and C sanitizer tests accompany
each helper. Python references are verification tools, not deadline-safe fallbacks;
their callers must ensure distinct memoryviews do not alias.

## host checks

```sh
python3 build.py --cc clang
```

ASAN/UBSAN are enabled by default. `--host-cflag=...` can supply host SDK/linker
configuration. `--no-sanitize` is an explicit opt-out and changes the validation
claim. No board is selected or written by this script.
Host-only runs write `HOST-RESULTS.json` and preserve the packaged native-artifact
provenance in `BUILD-RESULTS.json`. Only `--native` updates `BUILD-RESULTS.json`.

## native rebuild

requires Python with `pyelftools==0.32`, Git, and Arm GNU 15.3.Rel1 tools on PATH.
the verified compiler version is GCC 15.3.1 (Arm build arm-15.149).

the native header/linker checkout is intentionally a separate pin from the full
firmware build: both export the measured MPY ABI above. fetch public sources:

```sh
git init circuitpython-native
git -C circuitpython-native remote add origin https://github.com/adafruit/circuitpython.git
git -C circuitpython-native fetch --depth=1 origin 9209e83598cc93b9e5e8ce3fbdcea0b1a2a50e3c
git -C circuitpython-native checkout --detach 9209e83598cc93b9e5e8ce3fbdcea0b1a2a50e3c
python3 -m pip install pyelftools==0.32
python3 build.py --native --circuitpython circuitpython-native --cross-prefix arm-none-eabi- --cc clang
```

`--cross-prefix` and `--cc` can be absolute paths. the build verifies the exact
source pin and unmodified loader/header paths. each `.mpy` is linked with a
relative output filename so source-name metadata contains no build-machine path.
`BUILD-RESULTS.json` records relative source hashes and output hashes without
machine paths. build intermediates, host executables and local logs are not
needed for installation or redistribution.

the packaged sanitized helper build repeated all three host test suites. core
and wrapper object files were byte-identical to the earlier working modules;
only the MPY source filename metadata changed. final package hardware checks
are recorded separately and should identify the final module hashes.
