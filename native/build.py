#!/usr/bin/env python3
"""Portable native helper build. Never connects to or writes a device.

Requires Python with pyelftools==0.32, pinned CircuitPython source and Arm GCC.
Default invocation runs host ASAN/UBSAN tests; --native also builds the modules.
Source paths in generated MPY metadata are relative output basenames.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
CP_PIN='9209e83598cc93b9e5e8ce3fbdcea0b1a2a50e3c'
MODULES=('blit','sprite','pcm')

def run(args,cwd):
    print('+',Path(str(args[0])).name,' '.join(str(a) for a in args[1:] if not str(a).startswith('/')),flush=True)
    subprocess.run(list(map(str,args)),cwd=cwd,check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native',action='store_true')
    p.add_argument('--circuitpython',type=Path)
    p.add_argument('--cross-prefix',default=os.environ.get('CROSS_COMPILE','arm-none-eabi-'))
    p.add_argument('--cc',default=os.environ.get('CC','cc'))
    p.add_argument('--host-cflag',action='append',default=[])
    p.add_argument('--no-sanitize',action='store_true',help='Explicitly opt out for a host without ASAN/UBSAN')
    p.add_argument('--git',default='git')
    a=p.parse_args()
    cp=a.circuitpython.resolve() if a.circuitpython else None
    if a.native:
        if cp is None:p.error('--native requires --circuitpython')
        head=subprocess.check_output([a.git,'-C',str(cp),'rev-parse','HEAD'],text=True).strip()
        if head!=CP_PIN:raise SystemExit('CircuitPython native header/linker commit does not match pinned revision')
        if subprocess.check_output([a.git,'-C',str(cp),'status','--porcelain','tools/mpy_ld.py','tools/mpy-tool.py','py'],text=True).strip():
            raise SystemExit('native header/linker paths must be unmodified')
    receipts=[]
    for name in MODULES:
        path=ROOT/name
        build=path/'build';build.mkdir(exist_ok=True)
        flags=['-std=c11','-O2','-Wall','-Wextra','-Werror',*a.host_cflag]
        if not a.no_sanitize:flags+=['-fsanitize=address,undefined']
        run([a.cc,*flags,name+'.c','test_'+name+'.c','-o','build/test_'+name],path)
        result=subprocess.check_output([str(build/('test_'+name))],text=True).strip()
        print(result,flush=True)
        record=dict(module=name,host_result=result,host_sanitizers=None if a.no_sanitize else 'address,undefined')
        if a.native:
            flags=['-mthumb','-mcpu=cortex-m33','-mfpu=fpv5-sp-d16','-mfloat-abi=hard','-std=gnu99','-O3','-fpic','-fno-common','-fno-builtin','-ffunction-sections','-fdata-sections','-fno-section-anchors','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror','-ffile-prefix-map='+str(ROOT)+'=native','-fmacro-prefix-map='+str(cp)+'=circuitpython']
            run([sys.executable,cp/'tools/mpy_ld.py','--arch','armv7emsp','--preprocess','-o','build/module.config.h','module.c'],path)
            run([a.cross_prefix+'gcc',*flags,'-c',name+'.c','-o','build/'+name+'.o'],path)
            run([a.cross_prefix+'gcc',*flags,'-DNO_QSTR','-DMICROPY_ENABLE_DYNRUNTIME','-DMP_CONFIGFILE="build/module.config.h"','-I.','-isystem',cp,'-DMICROPY_FLOAT_IMPL=MICROPY_FLOAT_IMPL_FLOAT','-c','module.c','-o','build/module.o'],path)
            artifact='_crankfruit_'+name+'.mpy'
            run([sys.executable,cp/'tools/mpy_ld.py','--arch','armv7emsp','--qstrs','build/module.config.h','-o',artifact,'build/module.o','build/'+name+'.o'],path)
            # Metadata must contain a basename, not any parent directory.
            data=(path/artifact).read_bytes()
            assert data[:3]==b'C\x06\x1f'
            for marker in (str(ROOT).encode(),b'/Users/',b'/home/',b'C:\\Users\\'):
                assert marker not in data,'nonportable native metadata'
            run([sys.executable,cp/'tools/mpy-tool.py','-d',artifact],path)
            record.update(artifact=artifact,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),header_hex=data[:4].hex(),abi='0x1f06',target_arch='armv7emsp',circuitpython_pin=CP_PIN)
        record['source_sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(path.iterdir()) if f.suffix in ('.c','.h','.py')}
        receipts.append(record)
    receipt_name='BUILD-RESULTS.json' if a.native else 'HOST-RESULTS.json'
    (ROOT/receipt_name).write_text(json.dumps(receipts,indent=2)+'\n')
    print('NATIVE_HELPERS_PASS',json.dumps([{k:r[k] for k in ('module','bytes','sha256') if k in r} for r in receipts]))
if __name__=='__main__':main()
