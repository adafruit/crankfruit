#!/usr/bin/env python3
"""Host-only read-only inspector and explicit allowlist source packer. MIT."""
import argparse
import json
from pathlib import Path
import zipfile

import cartridge_loader as loader


def pack(folder, destination):
    item = loader.inspect_folder(str(folder))
    if not item["enabled"]:
        raise loader.CartridgeError(item["reason"])
    source = loader.load(item)
    manifest = {key: item[key] for key in loader._ALLOWED}
    files = [("manifest.json", (json.dumps(manifest, indent=2) + "\n").encode("ascii")),
             ("main.lua", source)]
    for name in ("LICENSE", "LICENSE.txt", "COPYING", "README.md"):
        path = Path(folder) / name
        if path.exists():
            files.append((name, loader._read(str(path), 65536)))
    # Revalidate after gathering documentation, before creating the archive.
    if loader.load(item) != source:
        raise loader.CartridgeError("source changed during packaging")
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files:
            info = zipfile.ZipInfo(item["slug"] + "/" + name)
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return dict(file=str(destination), slug=item["slug"], files=len(files),
                compatibility="source candidate", execution_performed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="inspect one cartridge folder or a game library")
    check.add_argument("path")
    check.add_argument("--single", action="store_true", help="force one-folder inspection")
    package = sub.add_parser("pack", help="validate then create a new allowlist ZIP")
    package.add_argument("folder")
    package.add_argument("output")
    args = parser.parse_args()
    try:
        if args.command == "pack":
            output = pack(args.folder, args.output)
            print(json.dumps(output, indent=2))
            return 0
        path = Path(args.path)
        single = (args.single or path.is_file() or
                  path.name.lower().endswith(loader._UNSUPPORTED) or
                  (path / "manifest.json").exists() or (path / "main.lua").exists())
        items = [loader.inspect_folder(args.path)] if single else loader.discover(args.path)
        print(json.dumps(dict(items=items, execution_performed=False,
                              compatibility_claim="source candidates only"), indent=2))
        return 0 if all(item["enabled"] for item in items) else 1
    except (loader.CartridgeError, OSError) as error:
        print(json.dumps(dict(error=str(error), execution_performed=False), indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
