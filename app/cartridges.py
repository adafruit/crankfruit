"""Read-only CircuitPython-compatible source-cartridge discovery/preflight.

Original code, copyright 2026 Adafruit Industries. SPDX-License-Identifier: MIT.
No Python import/eval from cartridges, no Lua execution, no filesystem writes.
Passing this check means source candidate, NOT verified API compatibility.
"""
import os
import json

PROFILE = "crankfruit-lua-v1"
MAX_FILES = 32
MAX_MANIFEST = 4096
MAX_SOURCE = 131072
DEFAULT_HEAP = 65536
_ALLOWED = ("kind", "profile", "title", "author", "description", "controls",
            "target_fps", "heap_cap", "entry")
_COMPARE = ("slug", "title", "author", "description", "controls", "kind",
            "profile", "target_fps", "heap_cap", "entry", "folder", "root",
            "manifest_fingerprint", "source_fingerprint")
_UNSUPPORTED = (".pdx", ".pdz", ".luac", ".elf", ".bin", ".uf2", ".zip")
_LSTAT = getattr(os, "lstat", None)


class CartridgeError(ValueError):
    pass


def _require(value, message):
    if not value:
        raise CartridgeError(message)


def _printable(value, limit):
    return "".join(c if 32 <= ord(c) <= 126 else "?" for c in str(value))[:limit]


def _root_path(root):
    _require(isinstance(root, str) and bool(root), "library path must be a nonempty string")
    _require("\x00" not in root and "\\" not in root, "invalid library path")
    _require(all(part != ".." for part in root.split("/")), "parent traversal is not allowed")
    root = root.rstrip("/")
    return root or "/"


def _join(root, name):
    return root + ("" if root.endswith("/") else "/") + name


def _slug(name):
    return (isinstance(name, str) and 1 <= len(name) <= 48 and
            name[0] in "abcdefghijklmnopqrstuvwxyz0123456789" and
            all(c in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in name))


def _safe_stat(path):
    # CircuitPython FAT filesystems do not expose symlinks. On hosts where
    # lstat exists, reject symlinks in EVERY path component, including root.
    if _LSTAT is not None:
        current = "/" if path.startswith("/") else "."
        for part in path.split("/"):
            if part in ("", "."):
                continue
            _require(part != "..", "parent traversal is not allowed")
            current = _join(current, part)
            _require((_LSTAT(current)[0] & 0o170000) != 0o120000,
                     "symlinks are not accepted")
        return _LSTAT(path)
    return os.stat(path)


def _directory(path):
    _require((_safe_stat(path)[0] & 0o170000) == 0o040000, "not a cartridge directory")
    names = os.listdir(path)
    _require(len(names) <= MAX_FILES, "more than 32 directory entries; split this library")
    return sorted(names)


def _read(path, maximum):
    before = _safe_stat(path)
    _require((before[0] & 0o170000) == 0o100000, "entry must be a regular file")
    _require(before[6] <= maximum, "file exceeds allowed size")
    with open(path, "rb") as source:
        data = source.read(maximum + 1)
    after = _safe_stat(path)
    _require(len(data) <= maximum and len(data) == before[6], "file size changed while reading")
    _require(all(before[i] == after[i] for i in (0, 1, 2, 6, 8, 9)
                 if i < len(before) and i < len(after)), "file changed while reading")
    return data


def _fingerprint(data):
    # Portable bounded change detection, NOT a signature/authentication hash.
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return "%d:%08x" % (len(data), value)


def _unique_keys(text):
    # json.loads() on CircuitPython has no object_pairs_hook. The schema is
    # flat, so separately identify quoted strings followed by ':' and reject
    # duplicate decoded keys, including differently escaped spellings.
    keys, i = [], 0
    while i < len(text):
        if text[i] != '"':
            i += 1
            continue
        start = i
        i += 1
        while i < len(text):
            if text[i] == "\\":
                i += 2
            elif text[i] == '"':
                i += 1
                break
            else:
                i += 1
        end = i
        while i < len(text) and text[i] in " \t\r\n":
            i += 1
        if i < len(text) and text[i] == ":":
            key = json.loads(text[start:end])
            _require(key not in keys, "duplicate manifest key")
            keys.append(key)


def _manifest(data):
    _require(bool(data), "manifest is empty")
    try:
        text = data.decode("utf-8")
        obj = json.loads(text)
    except Exception:
        raise CartridgeError("manifest is not valid UTF-8 JSON")
    _require(isinstance(obj, dict), "manifest must be a JSON object")
    _require(all(key in _ALLOWED for key in obj), "unknown manifest field")
    _unique_keys(text)
    _require(obj.get("kind") == "lua", "unsupported kind; only source Lua is accepted")
    _require(obj.get("profile") == PROFILE, "unsupported runtime profile")
    _require(type(obj.get("target_fps")) is int and obj["target_fps"] == 30,
             "target_fps must be integer 30")
    entry = obj.get("entry", "main.lua")
    _require(entry == "main.lua", "entry must be literal main.lua; no alternate paths")
    heap = obj.get("heap_cap", DEFAULT_HEAP)
    _require(type(heap) is int and 32768 <= heap <= 262144,
             "heap_cap must be an integer from 32768 to 262144")
    for key, limit, nonempty in (("title", 48, True), ("author", 64, True),
                                  ("description", 160, False), ("controls", 160, False)):
        value = obj.get(key)
        _require(isinstance(value, str), key + " must be a string")
        _require(len(value) <= limit and all(32 <= ord(c) <= 126 for c in value),
                 key + " must be short printable ASCII")
        _require(not nonempty or bool(value.strip()), key + " must not be empty")
    return dict(kind="lua", profile=PROFILE, title=obj["title"], author=obj["author"],
                description=obj["description"], controls=obj["controls"],
                target_fps=30, heap_cap=heap, entry="main.lua")


def _source(data):
    _require(1 <= len(data) <= MAX_SOURCE, "main.lua must contain 1..131072 bytes")
    _require(data[:1] != b"\x1b" and not data.startswith(b"\x7fELF"),
             "compiled or native binary input is unsupported")
    try:
        text = data.decode("utf-8")
    except Exception:
        raise CartridgeError("main.lua must be UTF-8 source, not binary/encrypted data")
    _require(all(ord(c) >= 32 or c in "\t\r\n" for c in text) and "\x7f" not in text,
             "binary control bytes are not accepted in Lua source")


def _disabled(root, name, reason):
    return dict(slug=name, root=root, folder=_join(root, name) if name else root,
                title=_printable(name or "game library", 48), author="", description="",
                controls="", kind="lua", profile=PROFILE, target_fps=30,
                heap_cap=DEFAULT_HEAP, entry="main.lua", enabled=False,
                reason=_printable(reason, 160), compatibility="disabled",
                manifest_fingerprint="", source_fingerprint="",
                symlink_checks_available=_LSTAT is not None)


def _check(root, name):
    root = _root_path(root)
    _require(isinstance(name, str), "folder name must be text")
    lower = name.lower()
    _require(not any(lower.endswith(suffix) for suffix in _UNSUPPORTED),
             "PDX/PDZ, compiled/native games and archives are unsupported; use a source folder")
    _require(_slug(name), "folder name must be a lowercase source-cartridge slug")
    folder = _join(root, name)
    entries = _directory(folder)
    for entry in entries:
        info = _safe_stat(_join(folder, entry))
        _require((info[0] & 0o170000) in (0o100000, 0o040000),
                 "special filesystem entries are not accepted")
        # Extra real directories (art/docs/host tests) are not traversed. The
        # sole loadable entry remains the top-level literal main.lua.
    _require("manifest.json" in entries, "missing manifest.json")
    _require("main.lua" in entries, "missing main.lua")
    raw_manifest = _read(_join(folder, "manifest.json"), MAX_MANIFEST)
    obj = _manifest(raw_manifest)
    source = _read(_join(folder, "main.lua"), MAX_SOURCE)
    _source(source)
    _require(_read(_join(folder, "manifest.json"), MAX_MANIFEST) == raw_manifest,
             "manifest changed during preflight")
    _require(_directory(folder) == entries, "directory changed during preflight")
    obj.update(slug=name, root=root, folder=folder, enabled=True, reason="",
               compatibility="source candidate",
               manifest_fingerprint=_fingerprint(raw_manifest),
               source_fingerprint=_fingerprint(source),
               symlink_checks_available=_LSTAT is not None)
    return obj, source


def inspect_folder(folder):
    """Inspect one folder; always return an item, including a disabled reason."""
    root, name = ".", ""
    try:
        folder = _root_path(folder)
        parts = folder.rsplit("/", 1)
        root, name = (parts[0] or "/", parts[1]) if len(parts) == 2 else (".", parts[0])
        item, unused = _check(root, name)
        return item
    except Exception as error:
        return _disabled(root, name, str(error) if isinstance(error, CartridgeError) else "cartridge files could not be read")


def discover(root="/games"):
    """Return source candidates and disabled rows; never execute game content.

    Unknown plain files are ignored; recognized game binaries/archives appear
    as disabled rows. Any per-folder error leaves the rest of the library usable.
    """
    try:
        root = _root_path(root)
        names = _directory(root)
    except Exception as error:
        return [_disabled(root if isinstance(root, str) else ".", "",
                          str(error) if isinstance(error, CartridgeError) else "game library could not be read")]
    result = []
    for name in names:
        try:
            is_unsupported = any(name.lower().endswith(suffix) for suffix in _UNSUPPORTED)
            info = _safe_stat(_join(root, name))
            if (info[0] & 0o170000) != 0o040000 and not is_unsupported:
                continue
            item, unused = _check(root, name)
            result.append(item)
        except Exception as error:
            result.append(_disabled(root, name, str(error) if isinstance(error, CartridgeError)
                                    else "cartridge files could not be read"))
    return result


def load(item):
    """Recheck and return source bytes immediately before Runtime construction.

    Refuse changed metadata/source since discovery. Re-scan to accept deliberate
    edits. Change fingerprints are not signatures and do not authenticate games.
    """
    _require(isinstance(item, dict) and item.get("enabled") is True,
             "cannot load a disabled or malformed cartridge item")
    try:
        current, source = _check(item["root"], item["slug"])
        _require(all(current[key] == item.get(key) for key in _COMPARE),
                 "cartridge changed since discovery; refresh the library")
        return source
    except CartridgeError:
        raise
    except Exception:
        raise CartridgeError("cartridge could not be revalidated")
