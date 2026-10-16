# optional full firmware rebuild

installing the included prebuilt UF2 does not require a build or network access.
the source reconstruction recipe below uses only public pinned upstream sources
and included patches. it never selects, flashes, erases or writes a device.

## dependencies

- CircuitPython: `https://github.com/adafruit/circuitpython.git`, commit
  `eb49ac414192f75a81316906e78937e654f3f56e`.
- every root gitlink is recorded in `source-pins.json`; the upstream dependency
  fetcher selects the Fruit Jam dependencies and follows their pinned submodules.
- patched TinyUSB: `5453ed09f19af010b6a361562d967cfa30aaadc6`.
- patched Pico-PIO-USB: `a5a2f5ae91988449ba576ec9d237e806d5cd4416`.
- Lua 5.4.9 source is included. original official archive:
  `https://www.lua.org/ftp/lua-5.4.9.tar.gz`, SHA-256
  `2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6`.
- fast_float v8.0.2 at `50a80a73ab2ab256ba1c3bf86923ddd8b4202bc7` is included,
  with upstream license options and `fast-float-provenance.json`.
- stb_sprintf v1.10 from `nothings/stb` commit
  `2c980bb59875b0d32144a71867fbdebb2f77cd20`, original SHA-256
  `e0b8c56e1084602290b9a17ef59f429b5293deb8cb9d8b0f20a14abc39b56520`.
  the included modified header retains its notices; `stb-local.patch` documents
  the formatter fixes. no proprietary SDK is required.
- Arm GNU Toolchain 15.3.Rel1, GCC 15.3.1, build arm-15.149.
- Python, Git, GNU Make and the pinned Python packages in `requirements-lock.txt`.

the historical validated compiler host was macOS Apple Silicon. its official
archive URL is:
`https://gitlab.arm.com/api/v4/projects/tooling%2Fgnu-toolchains-for-arm/packages/generic/gnu-toolchain/15.3.rel1/arm-gnu-toolchain-15.3.rel1-darwin-arm64-arm-none-eabi.tar.xz`

expected SHA-256:
`376808a59ca209c1413236f1c6a509e33da4b29857ab28642b9927cf3048af55`.
the compiler is not redistributed. other supported host packages may be chosen
from Arm, but their output needs independent qualification.

## commands

from this directory, in an activated dedicated Python virtual environment:

```sh
python3 -m pip install -r requirements-lock.txt
python3 prepare.py --plan
python3 prepare.py
python3 build.py --cross-prefix arm-none-eabi- --jobs 1
```

`--destination`/`--circuitpython`, `--git`, `--make` and `--cross-prefix` allow
explicit tool/source selection. use a dedicated source checkout; the preparer
applies patches in that checkout. the three patches are byte-hash checked and
all 28 resulting files are verified before the link integration patch is applied.
the board configuration enables native MPY loading, reserves 2MiB firmware in
16MiB external flash, and includes the patched HDMI audio methods plus static
`crankjam` runtime. stock CircuitPython is not a substitute.

output: `circuitpython/ports/raspberrypi/build-crankfruit/firmware.uf2`.
path-remapping flags reduce accidental local build metadata. re-audit the actual
output, validate UF2 target/ranges, and rerun hardware checks before using it.
version strings/build timestamps can change hashes. a rebuilt image is not
automatically identical to the prebuilt, physically tested image.

**fresh rebuild, 2026-10-16:** these launchers were used for a full build from the
pinned public sources on macOS arm64 with the recorded Arm GNU Toolchain
15.3.Rel1. `prepare.py` now also fetches CircuitPython's release tags (the build
stamps its version with `git describe`; without tags it stops with "Cannot
determine version"). the rebuilt UF2 matches the shipped
`firmware/crankfruit-fruit-jam.uf2` in size, layout and every code byte: only 12
bytes differ, the build date in three copies of the version banner. details and
hashes: `REBUILD-RESULTS.json`. the shipped, hardware-tested image is kept.
