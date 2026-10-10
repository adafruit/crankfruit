#!/usr/bin/env python3
"""Validate render layout/audio and approved hashes; optionally byte-compare a clip."""
import argparse
import array
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path)
parser.add_argument('--reference',type=Path,help='optional existing clip for exact byte comparison')
parser.add_argument('--renderer',type=Path,help='optional executable for bounded failure tests')
args=parser.parse_args()
golden=json.loads((HERE/'expected.json').read_text())
data={name:(args.output/name).read_bytes() for name in ('boot.frames','boot.index','boot.pcm')}
matches={}
for name,blob in data.items():
    assert len(blob)==golden[name]['bytes'],name+' length mismatch'
    digest=hashlib.sha256(blob).hexdigest()
    assert digest==golden[name]['sha256'],name+' approved hash mismatch'
    matches[name]=dict(bytes=len(blob),sha256=digest,approved_hash_match=True)
    if args.reference:
        assert blob==(args.reference/name).read_bytes(),name+' reference bytes differ'
        matches[name]['reference_byte_identical']=True
frames,index,pcm=data['boot.frames'],data['boot.index'],data['boot.pcm']
assert len(frames)%12480==0 and len(frames)//12480==62
assert len(index)==75 and max(index)<62 and set(index)==set(range(62))
assert all(frames[i+50:i+52]==b'\0\0' for i in range(0,len(frames),52))
samples=array.array('h',pcm)
if sys.byteorder!='little':samples.byteswap()
assert len(samples)==80000 and max(abs(x) for x in samples)<32767
failure_checks=[]
if args.renderer:
    exe=str(args.renderer.resolve())
    with tempfile.TemporaryDirectory(prefix='boot-render-check-') as temp:
        root=Path(temp)
        for name,source in [('empty',b''),('binary',b'\x1bLua'),('oversize',b' '*131073),
                            ('bad-rate',b'playdate.display.setRefreshRate(20); function playdate.update() end')]:
            path=root/(name+'.lua');path.write_bytes(source)
            output=root/name;output.mkdir()
            result=subprocess.run([exe,str(path),str(output)],capture_output=True,timeout=20)
            assert result.returncode!=0,name+' unexpectedly passed'
            assert list(output.iterdir())==[],name+' wrote output despite failure'
            failure_checks.append(name)
        # Reusing an output folder must refuse overwrite of the approved bytes.
        existing=root/'existing';existing.mkdir()
        for name,blob in data.items():(existing/name).write_bytes(blob)
        result=subprocess.run([exe,str(HERE/'boot-splash.lua'),str(existing)],capture_output=True,timeout=20)
        assert result.returncode!=0
        assert all((existing/name).read_bytes()==blob for name,blob in data.items())
        failure_checks.append('refuses-overwrite')
receipt=dict(public_c_api_only=True,circuitpython_interpreter_required=False,
             hardware_tested=False,files=matches,padding_zero=True,index_bounds_valid=True,
             pcm_samples=80000,pcm_peak=max(abs(x) for x in samples),clipped_samples=0,
             renderer_failure_checks=failure_checks)
(args.output/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('BOOT_SOURCE_PARITY_PASS',json.dumps(receipt,indent=2))
