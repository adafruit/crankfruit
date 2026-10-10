# source-cartridge loader and host inspector

`cartridge_loader.py` uses only `os` and `json` and can be installed on the
board as **`cartridges.py`**. It has no filename-dependent imports. The host
CLI/tests use its original development filename. Original MIT code; no device
UID, private path, credentials or network service is built in.

## runtime API

```
from cartridges import discover, load

items = discover('/games')
item = items[selected]
if item['enabled']:
    source = load(item)
    # Only the application's explicit launch path may execute this source:
    runtime = crankjam.Runtime(source, heap_cap=item['heap_cap'])
```

`discover()` never executes Lua or Python and never writes files. It returns
eligible **source candidates**, not verified compatible games. Unsupported
API calls, syntax, excessive runtime allocation or work quota failures must be
handled by the parent's launch/update exception path. Preflight is not a
compiler, interpreter, security sandbox, signature verifier or trust judgment.

Items have: `slug,root,folder,title,author,description,controls,kind,profile,
target_fps,heap_cap,entry,enabled,reason,compatibility,manifest_fingerprint,
source_fingerprint,symlink_checks_available`. `reason` is printable ASCII,
at most160 characters. Disabled rows retain all UI-required keys. Individual
bad folders do not crash the library. Root errors become one disabled row.
An empty valid library returns `[]`; the parent adds its built-in Sound Explorer.

`load(item)` revalidates the manifest, directory, source bytes and chosen
paths, then compares metadata and change fingerprints with discovery. A changed
cartridge requires a fresh scan. It returns the validated bytes, not a Python
module or file handle. Stat/read/stat and repeated manifest reads narrow the
change window but do not claim race-proof filesystem transactions. Portable
FNV-1a32 fingerprints detect ordinary changes; they are **not authentication**.

## exact manifest schema

Each `/games/<slug>/` contains `manifest.json` and `main.lua`:

```
{
  "kind": "lua",
  "profile": "crankfruit-lua-v1",
  "title": "An Independent Game",
  "author": "Game Author",
  "description": "A short description.",
  "controls": "B1/B2 move; B3 play; hold B3 library.",
  "target_fps": 30,
  "heap_cap": 65536,
  "entry": "main.lua"
}
```

Required:kind,profile,title,author,description,controls,target_fps. title is1..48
printable ASCII characters,author1..64,description/controls0..160. title/author
cannot be whitespace-only. heap_cap defaults65,536 and must be an integer in
32,768..262,144. target_fps must be integer30, not a bool,float or other rate.
entry defaults main.lua and no other path is accepted. Unknown fields and
duplicate keys (including alternate JSON escapes) are rejected. There is no
`id`,URL,license or version field in this minimal v1 schema; keep attribution
and licensing in LICENSE/README files until a future profile defines more.

Slug:1..48 lowercase ASCII letters/digits/hyphen/underscore, beginning with a
letter or digit. Roots can be absolute or relative but cannot contain `..`.
Choose the root directly or resolve a trusted host path before invoking the
CLI. Entries cannot escape their chosen folder.

## bounded filesystem behavior

- at most32 immediate entries in the library root and in each cartridge folder.
  **macOS `._` sidecar files count toward this bound**, even though unknown
  regular root files are not shown. More than32 root entries disables scanning
  with a clear message rather than silently omitting an arbitrary game.
- at most4,096 manifest bytes and1..131,072 UTF-8 source bytes; binary escape,
  ELF, invalid UTF-8 and binary control bytes reject. There is no general way
  to identify encrypted text; text passing these checks remains only a source
  candidate and can still fail the real Lua loader.
- `.pdx`,`.pdz`,`.luac`,`.elf`,`.bin`,`.uf2`,`.zip` files/folders produce clear
  disabled rows. This tool does not unpack archives or load compiled games.
- host `lstat`, when available, rejects links in every accessed path component
  and immediate cartridge entry. Extra real subdirectories are ignored, not
  traversed. Only top-level manifest/main.lua are read for launch.
- CircuitPython FAT has no symlinks; on interpreters without `lstat` the item
  reports `symlink_checks_available=False`. Do not treat that fallback as a
  symlink security boundary on a link-capable host filesystem.

## host CLI

```
python3 cartridge_cli.py check games
python3 cartridge_cli.py check games/my-game --single
python3 cartridge_cli.py pack games/my-game my-game.zip
```

`check` prints JSON and performs no execution/writes. Exit0 means no disabled
rows,1 means disabled rows,2 means a CLI/read/pack error. The explicit `pack`
command validates before creating a new archive, refuses overwrite, and copies
only normalized manifest, source and existing LICENSE,LICENSE.txt,COPYING,
README.md (each documentation file <=64KiB). It does not copy Python scripts,
unknown assets, nested folders, absolute paths or private scan metadata.
Packaging is not a privacy scan of the game's own source/docs; review those
before sharing. Existing notices should not be discarded.

## evidence

```
python3 -B run_checks.py
python3 -B run_checks.py --cp-unix /path/to/qualified/circuitpython-unix
```

27 loader/packer tests cover schema, duplicate keys, limits, binary rejection,
paths/symlinks, independent-game insertion, changes before launch, no Python
execution and ZIP allowlisting.9 parent integration policy tests cover dynamic
4+item discovery, pagination/wrap/disabled launch, maximum metadata command
budget and scene constructor/update failure plus successful cleanup. Integration
uses real parent Library/run_scene/GamePlayer/PcmStream with **stub Canvas,
runtime and hardware**. It is not Lua execution or physical evidence. Configure
`CRANKFRUIT_APP_DIR` when testing a copied package's app directory.

The cached-page regressions check33 selectable items (including a built-in),
396,000 bytes of packed page pixels plus an optional12,000-byte error page,
prebuilt disabled/error messages, and no text/glyph/page construction during
150 live-step calls. At most one animation sprite command is issued per live
redraw. Stub framebuffer bytes identify cached pages only; they are not native
glyph/compositor output, total RAM measurements or physical timing proof.

The real CircuitPython UNIX smoke imports the exact module, discovers two new
source candidates plus two disabled examples, and revalidates both sources.
It does not execute them. Current results and source fingerprints are retained
in TEST-RESULTS.json. Actual Fruit Jam qualification remains the parent's lane.
