# application installation and source tools

the installer does not flash firmware. first install the included custom Fruit
Jam UF2 deliberately, following the package's board instructions, and back up
any existing device work. stock CircuitPython lacks the required custom runtime
and HDMI-audio interfaces. a plain DVI monitor does not guarantee audible output.

## validate before touching the device

from the extracted kit root:

```sh
python3 install.py --validate-only
python3 test_installer.py
```

these commands need only Python 3.9+ and do not open serial ports. the installer
requires an exact manifest inventory under `app/`, verifies every length/hash,
and syntax-checks Python files before opening a selected device.

## explicit-target installation

install `pyserial==3.5` in a dedicated virtual environment. identify the intended
board's serial port, mounted CIRCUITPY volume and UID, then supply all three:

```sh
python3 install.py --kit . --port SERIAL_PORT --mount CIRCUITPY_VOLUME --uid BOARD_UID --backup-dir HOST_BACKUP_DIRECTORY
```

replace the placeholders with the selected device's actual values. the script
checks the serial descriptor, mounted volume's boot identity, and the running
board's UID/model/MPY ABI/custom audio methods. it regains a confirmed REPL,
disables autoreload with an execution acknowledgment, backs up every file being
replaced, writes only manifest-listed files, writes `code.py` last and reads back
all installed bytes. unrelated files are preserved. nothing is deleted or flashed.

the default successful end state is stopped at REPL with autoreload disabled.
add `--start` to request normal startup after verified installation. requesting
startup is not a performance/audio qualification. installer receipts and backups
contain local device/path details: keep them private, outside the shared ZIP.

if a write or control check fails, the installer does not guess at recovery or
delete files. it preserves backups and a per-file progress receipt. regain a
controlled REPL and inspect that receipt before choosing recovery actions.

## source development

- `engine/README.md`: portable C/Lua host tests and command-line player; optional SDL2 window.
- `engine/firmware/README.md`: full firmware public pins, patches, configurable rebuild recipe and licenses.
- `native/README.md`: removable helper source/reference/sanitizer tests and clean metadata rebuild.

the prebuilt firmware is included for installation without network or compiler.
its original full build was verified historically. packaging did not rerun a full
firmware cross-build; neutral source-reconstruction launchers were plan checked.
the relocated engine host tests and clean native helper builds were rerun.
the final application/hardware verification belongs to the package's main report.

the integration lead also used this installer on the explicitly selected Fruit
Jam and reported successful readback of 42 application files. that receipt is
separate from the nine host-only installer tests; it is not a sustained playback
result. later application revisions must be identified by their own manifests.
