"""Select a local crankjam-enabled host interpreter explicitly, never auto-fetch it."""
import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--interpreter", required=True, help="crankjam-enabled MicroPython executable")
parser.add_argument("--frames", type=Path, help="optional directory for five native host PBM previews")
args = parser.parse_args()
base = Path(__file__).resolve().parent
manifest = json.loads((base / "manifest.json").read_text())
assert manifest["kind"] == "lua"
assert manifest["profile"] == "crankfruit-lua-v1"
assert manifest["target_fps"] == 30 and manifest["heap_cap"] == 65536
assert manifest["entry"] == "main.lua"
assert len(manifest["title"]) <= 48 and len(manifest["author"]) <= 64
assert len(manifest["description"]) <= 160 and len(manifest["controls"]) <= 160
command = [args.interpreter, str(base / "native_check.py"), str(base / "main.lua")]
if args.frames:
    args.frames.mkdir(parents=True, exist_ok=True)
    command.append(str(args.frames.resolve()))
subprocess.run(command, check=True)
