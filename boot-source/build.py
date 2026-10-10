#!/usr/bin/env python3
"""Build the C boot renderer against chosen portable static engine libraries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--engine-include',type=Path,required=True,help='directory containing crankjam.h')
parser.add_argument('--engine-lib',type=Path,required=True,help='portable libcrankjam.a')
parser.add_argument('--lua-lib',type=Path,help='libcj_lua.a; defaults to engine library sibling')
parser.add_argument('--cc',default=os.environ.get('CC','cc'),help='C11 compiler command')
parser.add_argument('--sanitize',action='store_true',help='match ASAN/UBSAN engine builds')
parser.add_argument('--output',type=Path,required=True,help='new build/output directory')
args=parser.parse_args()
lua=args.lua_lib or args.engine_lib.with_name('libcj_lua.a')
for path in (args.engine_include/'crankjam.h',args.engine_lib,lua):
    if not path.is_file():parser.error('missing required public header/static library: '+path.name)
args.output.mkdir(parents=True,exist_ok=False)
binary=args.output/('render-boot.exe' if os.name=='nt' else 'render-boot')
command=shlex.split(args.cc)+['-std=c11','-O2','-Wall','-Wextra','-Wpedantic',
    '-I',str(args.engine_include),str(HERE/'render_boot.c'),str(args.engine_lib),str(lua),'-lm','-o',str(binary)]
if args.sanitize:command+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
build=subprocess.run(command,capture_output=True,text=True)
(args.output/'compiler-output.txt').write_text(build.stdout+build.stderr)
if build.returncode:raise SystemExit(build.returncode)
render=subprocess.run([str(binary.resolve()),str(HERE/'boot-splash.lua'),str(args.output.resolve())],capture_output=True,text=True)
(args.output/'render-output.txt').write_text(render.stdout+render.stderr)
if render.returncode:raise SystemExit(render.returncode)
receipt=json.loads(render.stdout)
receipt['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (HERE/'render_boot.c',HERE/'boot-splash.lua',args.engine_lib,lua)}
receipt['sanitizers_enabled']=args.sanitize
receipt['files']={name:dict(bytes=(args.output/name).stat().st_size,
    sha256=hashlib.sha256((args.output/name).read_bytes()).hexdigest())
    for name in ('boot.frames','boot.index','boot.pcm')}
(args.output/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('NATIVE_BOOT_RENDER_PASS',json.dumps(receipt,indent=2))
