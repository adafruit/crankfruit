# editable startup source, portable native renderer

This directory makes the approved startup independently rebuildable without
the old lab workspace, an image generator, the Playdate SDK or a CircuitPython
UNIX interpreter. The complete editable pixel-span artwork, crank animation,
wordmark and original two-voice jingle are in `boot-splash.lua`.

`render_boot.c` uses only the public `engine/include/crankjam.h` API. It runs
75 source-Lua updates at 30 Hz, with timestamps `i*1000/30` rounded down. Audio
chunks use exact integer 32000/30 sample accounting and total 80,000 samples.
Core 50-byte framebuffer rows are copied into 52-byte rows with zero padding.
Identical padded frames are deduplicated in first-seen order; 75 index bytes
select the result. The current art produces 62 unique frames.

Only startup is pre-rendered. Device games still execute live in the player.
The source is intentionally a host build input, not a live on-board splash:
live boot rendering/mixing previously failed its physical timing budget.

## CMake route

Assume this `boot-source/` and the supplied portable `engine/` are siblings:

```
cmake -S boot-source -B build-boot -DCRANKJAM_ENGINE_DIR=../engine -DCJ_SANITIZE=ON
cmake --build build-boot
ctest --test-dir build-boot --output-on-failure --no-tests=error
mkdir boot-output
build-boot/render-boot boot-source/boot-splash.lua boot-output
python3 -B boot-source/check.py boot-output --renderer build-boot/render-boot
```

The engine includes Lua source. No SDL window or proprietary SDK is required.
Use `-DCJ_SANITIZE=OFF` for a compiler without ASAN/UBSAN support. Choose a C11
compiler and platform SDK normally installed/authorized on the build machine.
The wrapper does not install software or accept licenses.

## link an already-built portable engine

```
python3 -B boot-source/build.py \
  --engine-include engine/include \
  --engine-lib engine/build-core/libcrankjam.a \
  --lua-lib engine/build-core/libcj_lua.a \
  --cc cc --sanitize --output boot-output
python3 -B boot-source/check.py boot-output --reference app/bootclip \
  --renderer boot-output/render-boot
```

`--lua-lib` defaults to `libcj_lua.a` next to the engine library. Omit
`--sanitize` for nonsanitized libraries; linker options must match the chosen
engine build. `--cc` accepts an explicitly selected compiler plus its platform
flags. The equivalent direct C11 link is:

```
cc -std=c11 -O2 -I engine/include boot-source/render_boot.c \
  engine/build-core/libcrankjam.a engine/build-core/libcj_lua.a -lm -o render-boot
```

The Python builder insists on a new output directory. The C executable needs
an existing directory and exclusively creates new files; it refuses overwrite.
Rendering failures create no clip files. An I/O failure while writing can leave
an incomplete new output directory; inspect that result, do not ship it.

## output contract and validation

- `boot.frames`: 773,760 bytes, 62 frames × 12,480 bytes; 400x240, MSB-first, white = 1.
- `boot.index`: 75 unsigned 8-bit frame indices.
- `boot.pcm`: 160,000 bytes, 32 kHz signed PCM16LE mono, exactly 2.5 seconds.

`expected.json` contains the approved hashes without private paths. The native
C render was built and run against the relocated portable engine with
ASAN/UBSAN enabled. All three outputs match the current approved application
clip **byte for byte**, including every PCM sample. No CircuitPython numeric
parser difference was observed for this source. Peak Lua heap was 237,628 bytes
under its 262,144-byte offline limit; this is not board runtime memory usage.

`check.py` also validates geometry, all padding, index bounds, no PCM clipping,
and optional failure cases for empty/binary/oversized source, wrong framerate,
and refusing overwrite. Validation is host evidence, not a new hardware test.

Other compiler/libm/platform combinations should run the same checker rather
than assume exact floating-point raster/audio parity. Editing the art/music
will intentionally change hashes; review a new candidate before replacing the
golden receipt. Never silently update expected hashes just to pass a check.

## authorship and redistribution

The approved monster/wordmark is original generated Crankfruit artwork converted
to exact editable one-bit span records. Its source raster generator is not
needed to reproduce these accepted pixels. Crank movement, composition and
synthesized melody are original authored code; voice envelope settings were
hand-transcribed from an authored Pulp editor voice, not exported Pulp code or
a Pulp runtime. No Panic startup logo, music sample or third-party game audio
is included. Lab-only project identifiers were removed from comments.

Original Crankfruit source and host tooling retain the included MIT notice.
Engine/Lua dependencies retain their own notices in the supplied engine tree.
For a source handoff, include the Lua/C/Python/CMake sources, expected.json,
README and LICENSE. Locally built executables, compiler logs and build folders
are validation artifacts, not required source-package contents.
