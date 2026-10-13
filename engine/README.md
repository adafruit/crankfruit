# source-Lua engine development

the included C runtime implements a bounded Playdate-style source-Lua subset,
not arbitrary compiled PDX files, the complete SDK or Playdate OS. the current
Fruit Jam application layer is supplied separately; this directory lets a
developer build, test and experiment with the underlying Lua API on a computer.

required: CMake 3.20+, a C11 compiler and a build tool. Lua sources are included,
so no system Lua or proprietary SDK is required.

## tests and command-line player

from this directory:

```sh
cmake -S . -B build-core -DCJ_BUILD_HOST=OFF -DCJ_BUILD_TESTS=ON -DCJ_SANITIZE=ON
cmake --build build-core
ctest --test-dir build-core --output-on-failure --no-tests=error
build-core/crankjam-headless examples/hello.lua --headless --frames 90 --sample-rate 32000 --pbm hello.pbm --wav hello.wav
```

`CJ_SANITIZE` enables ASAN/UBSAN for a compatible compiler. set it OFF explicitly
for a compiler without those sanitizers. command-line framebuffer/audio files are
host-generated outputs, not physical Fruit Jam evidence.

the freshly relocated source tree passed all 30 runtime tests and 205,092 checks
under ASAN/UBSAN. the command-line sample additionally exercises native drawing
and synthesis. the sanitizer suite covers bounded source/heap/instruction work,
sandbox behavior, clipping, input, numeric ranges, synth lifetimes and PCM.

## optional desktop window

install SDL2 development files and make `sdl2-config` available on PATH:

```sh
cmake -S . -B build-host -DCJ_BUILD_HOST=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build-host
build-host/crankjam-host examples/hello.lua --sample-rate 32000
```

controls for source games: arrows; Z/Space=A; X=B; Q/E=simulated crank; Esc=quit.
the graphical SDL host is optional and is not required to build the headless
player or run engine tests. no native host executables are redistributed.

### Fruit Jam output preview: `--board-scale 1|1.5|1.6|1.6s`

shows the game inside the Fruit Jam's 640x480 HDMI output with a black border,
using the fixed nearest-neighbour mapping a board blit helper would use. the
window is 1280x960 and integer-scaled, so each output pixel is a whole block.
press Tab to cycle 1x / 1.5x / 1.6x / 1.6x smooth while playing.

| scale | game area in 640x480 | pixel pattern |
| --- | --- | --- |
| 1x | 400x240 at (120,120) | exact (current board output) |
| 1.5x | 600x360 at (20,60) | game pixels alternate 2 and 1 output pixels |
| 1.6x | 640x384 at (0,48) | every 5 game pixels become 8 output pixels |
| 1.6x smooth (`1.6s`) | 640x384 at (0,48) | 4 grey levels (a 2-bit framebuffer): each output pixel's exact area coverage, rounded |

`--scaled-pbm FILE` (with `--board-scale`, works headless) writes the final frame
as a 640x480 PBM (PGM greyscale for `1.6s`). this is a preview only: the board still outputs 1x.

```sh
build-host/crankjam-host game.lua --board-scale 1.5
build-core/crankjam-headless game.lua --headless --board-scale 1.6 --scaled-pbm out.pbm
```

the firmware statically embeds the binding in `backends/circuitpython/`, including
module-local formatter/numeric-parser fixes. full firmware rebuild details and
public source pins are in `firmware/README.md`. those relocated full cross-build
launchers were syntax/plan checked, not freshly cross-built during packaging.

original engine code retains `src/LICENSE`. Lua licensing is preserved in
`vendor/lua-5.4.9/src/lua.h`; fast_float and stb_sprintf retain their notices in
the binding tree. collected CircuitPython/dependency notices are in `licenses/`.
