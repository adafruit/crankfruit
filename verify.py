#!/usr/bin/env python3
"""Local, no-device host verification from an extracted review kit."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CRANKFRUIT_APP_DIR=str(ROOT/'app'))
env['PYTHONPATH']=os.pathsep.join((str(ROOT/'app'),str(ROOT/'tests/audio')))
for line in (ROOT/'SHA256SUMS').read_text().splitlines():
    expected,name=line.split('  ',1)
    path=ROOT/name
    assert path.is_file() and not path.is_symlink(),name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,name
print('PACKAGE_HASHES_PASS',flush=True)
def run(*args):
    result=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,env=env,capture_output=True,text=True)
    print(result.stdout+result.stderr,flush=True)
    assert result.returncode==0,args
    assert 'Ran 0 tests' not in result.stdout+result.stderr,'empty test discovery'
run('install.py','--validate-only')
run('test_installer.py')
for folder in ('tools/cartridges','tools/sound','tools/crank','tools/gamepad','tests/audio','tools/art/tools'):
    run('-m','unittest','discover','-s',folder,'-v')
run('tools/art/test_assets.py')
print('PORTABLE_HOST_CHECKS_PASS; no hardware was accessed',flush=True)
