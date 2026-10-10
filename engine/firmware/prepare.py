#!/usr/bin/env python3
"""Fetch exact public firmware sources and apply integrity-pinned patches.

No device operations. Writes only the selected source destination and its
submodules. Use an empty dedicated destination, not a working source checkout.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
F=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination',type=Path,default=F/'circuitpython')
    p.add_argument('--git',default='git')
    p.add_argument('--plan',action='store_true')
    a=p.parse_args();cp=a.destination.resolve();patches=F/'patches'
    receipt=json.loads((patches/'receipt.json').read_text())
    def call(args,cwd=None):subprocess.run(list(map(str,args)),cwd=cwd,check=True)
    def git(*args,cwd=None):return subprocess.check_output([a.git,*map(str,args)],cwd=cwd,text=True).strip()
    for name,info in receipt['patches'].items():
        data=(patches/name).read_bytes()
        assert len(data)==info['bytes'] and hashlib.sha256(data).hexdigest()==info['sha256'],name
    if a.plan:
        print('PLAN ONLY: fetch https://github.com/adafruit/circuitpython.git at',receipt['source_head'])
        print('fetch board-selected exact gitlinks; apply 3 pinned patches; verify 28 outputs; apply link integration patch')
        print('no files fetched or modified; no devices accessed')
        return
    if not (cp/'.git').exists():
        if cp.exists() and any(cp.iterdir()):raise SystemExit('source destination must be empty or the exact prepared checkout')
        call([a.git,'init',cp])
        call([a.git,'-C',cp,'remote','add','origin','https://github.com/adafruit/circuitpython.git'])
        call([a.git,'-C',cp,'fetch','--depth=1','origin',receipt['source_head']])
        call([a.git,'-C',cp,'checkout','--detach',receipt['source_head']])
    if git('rev-parse','HEAD',cwd=cp)!=receipt['source_head']:raise SystemExit('source commit differs from pinned firmware')
    call([sys.executable,'tools/ci_fetch_deps.py','adafruit_fruit_jam'],cwd=cp)
    roots={g['name']:cp/g['root'] for g in receipt['groups']}
    def apply(root,patch):
        already=subprocess.run([a.git,'apply','--reverse','--check',str(patch)],cwd=root,capture_output=True)
        if already.returncode:
            call([a.git,'apply','--check',patch],cwd=root)
            call([a.git,'apply',patch],cwd=root)
    for group in receipt['groups']:
        root=roots[group['name']]
        if git('rev-parse','HEAD',cwd=root)!=group['commit']:raise SystemExit('dependency commit mismatch: '+group['name'])
        apply(root,patches/(group['name']+'.patch'))
    for rec in receipt['records']:
        data=(roots[rec['root']]/rec['path']).read_bytes()
        assert len(data)==rec['bytes'] and hashlib.sha256(data).hexdigest()==rec['sha256'],rec['path']
    assert len(receipt['records'])==28
    apply(cp,F/'build-integration.patch')
    print('FIRMWARE_SOURCE_PASS exact public pin, 3 complete patches, 28 byte-verified outputs, link integration')
if __name__=='__main__':main()
