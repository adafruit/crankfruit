#!/usr/bin/env python3
"""Explicit-target application installer. Never flashes firmware or deletes files.

Requires Python 3.9+ and pyserial==3.5 for device installation. --validate-only
uses only the standard library. Backups and receipts stay on the host.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import tempfile
import time

ROOT=Path(__file__).resolve().parent
BOARD='adafruit_fruit_jam'
MAX_FILE=8*1024*1024
MAX_TOTAL=14*1024*1024

def digest(data):return hashlib.sha256(data).hexdigest()

def relative_name(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('invalid manifest path')
    path=PurePosixPath(name)
    if path.is_absolute() or any(x in ('','.','..') for x in name.split('/')):
        raise ValueError('manifest path must be a normalized relative path')
    if any(part.startswith('.') for part in path.parts):raise ValueError('hidden application path rejected')
    return path

def safe_target(root,name):
    path=root
    for part in relative_name(name).parts:
        path=path/part
        if path.is_symlink():raise ValueError('symlink in application path')
    if not path.resolve().is_relative_to(root.resolve()):raise ValueError('application path escapes root')
    return path

def preflight(root):
    manifest=root/'app-manifest.json';app=root/'app'
    if manifest.is_symlink() or app.is_symlink():raise ValueError('package paths must not be symlinks')
    entries=json.loads(manifest.read_text())
    if not isinstance(entries,list) or not 1<=len(entries)<=1024:raise ValueError('invalid manifest list')
    files=[];seen=set();total=0
    for item in entries:
        if not isinstance(item,dict) or not {'path','bytes','sha256'}<=item.keys():raise ValueError('invalid manifest record')
        name=item['path'];relative_name(name)
        if name in seen:raise ValueError('duplicate manifest path')
        seen.add(name)
        if type(item['bytes']) is not int or not 0<=item['bytes']<=MAX_FILE:raise ValueError('invalid file length')
        if not isinstance(item['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',item['sha256']):raise ValueError('invalid hash')
        source=safe_target(app,name)
        if not source.is_file() or source.stat().st_size!=item['bytes']:raise ValueError('missing/size-mismatched app file: '+name)
        data=source.read_bytes()
        if digest(data)!=item['sha256']:raise ValueError('app hash mismatch: '+name)
        if source.suffix=='.py':compile(data,name,'exec')
        total+=len(data)
        if total>MAX_TOTAL:raise ValueError('application exceeds bounded total size')
        files.append((name,data))
    actual=set()
    for path in app.rglob('*'):
        if path.is_symlink():raise ValueError('symlink in app inventory')
        if path.is_file():actual.add(path.relative_to(app).as_posix())
    if actual!=seen:raise ValueError('app directory inventory differs from manifest')
    if 'code.py' not in seen:raise ValueError('application needs code.py')
    files.sort(key=lambda item:(item[0]=='code.py',item[0]))
    return files,digest(manifest.read_bytes())

def boot_identity(mount,uid):
    path=mount/'boot_out.txt'
    if path.is_symlink():raise ValueError('boot identity must not be a symlink')
    if path.stat().st_size>16384:raise ValueError('invalid boot identity size')
    text=path.read_text(errors='replace')
    if not re.search(r'(?m)^UID:\s*'+re.escape(uid)+r'\s*$',text,re.I):raise ValueError('mounted volume UID mismatch')
    if not re.search(r'(?m)^Board ID:\s*'+BOARD+r'\s*$',text):raise ValueError('mounted volume is not Fruit Jam')
    if not re.search(r'CircuitPython \d+\.\d+',text):raise ValueError('mounted volume does not identify CircuitPython')
    return text

def select_target(port,mount,uid):
    from serial.tools import list_ports
    ports=[p for p in list_ports.comports() if p.device==port]
    if len(ports)!=1:raise ValueError('explicit serial port is not uniquely enumerated')
    selected=ports[0]
    if (selected.serial_number or '').upper()!=uid:raise ValueError('serial descriptor UID mismatch')
    if (selected.vid,selected.pid)!=(0x239a,0x816c):raise ValueError('serial descriptor is not Fruit Jam')
    if mount.is_symlink() or not mount.is_dir() or not os.path.ismount(mount):raise ValueError('--mount must be an actual mounted volume')
    boot_identity(mount,uid)

def send(console,data):
    if console.write(data)!=len(data):raise RuntimeError('incomplete serial write')

def pause(console,seconds=8):
    console.reset_input_buffer()
    deadline=time.monotonic()+seconds;next_interrupt=0;buffer=b''
    while time.monotonic()<deadline:
        now=time.monotonic()
        if now>=next_interrupt:
            send(console,b'\x03');next_interrupt=now+.25
        buffer=(buffer+console.read(4096))[-8192:]
        if buffer.rstrip().endswith(b'>>>'):return
        time.sleep(.01)
    raise RuntimeError('could not regain verified REPL; no device files changed')

def command(console,source,seconds=5):
    marker='IP_ACK_'+secrets.token_hex(12)
    line=source+'; print('+repr(marker)+')\r\n'
    send(console,line.encode('ascii'))
    deadline=time.monotonic()+seconds;buffer=b''
    while time.monotonic()<deadline:
        buffer+=console.read(4096)
        if len(buffer)>65536:raise RuntimeError('unexpected REPL output size')
        text=buffer.decode('utf-8','replace')
        lines=[s.strip() for s in text.splitlines()]
        if 'Traceback (most recent call last):' in text:raise RuntimeError('device command raised an exception')
        # Exact complete output line, not an echoed command string.
        if marker in lines and buffer.rstrip().endswith(b'>>>'):return text
        time.sleep(.01)
    raise RuntimeError('device command not acknowledged at REPL')

def verify_identity(console,uid):
    command(console,"import board,microcontroller,sys; assert board.board_id == "+repr(BOARD)+
            "; assert microcontroller.cpu.uid.hex().upper() == "+repr(uid)+
            "; assert sys.implementation._mpy == 0x1f06; import crankjam,picodvi; "
            "assert hasattr(picodvi.Framebuffer,'audio_write') and hasattr(picodvi.Framebuffer,'audio_pending') and hasattr(picodvi.Framebuffer,'audio_stop')")

def disable_autoreload(console):
    command(console,"import supervisor; supervisor.disable_autoreload() if hasattr(supervisor,'disable_autoreload') else setattr(supervisor.runtime,'autoreload',False); assert not supervisor.runtime.autoreload")

def write_bytes(path,data):
    flags=os.O_WRONLY|os.O_CREAT|os.O_TRUNC|getattr(os,'O_NOFOLLOW',0)
    with os.fdopen(os.open(path,flags,0o600),'wb') as handle:
        handle.write(data);handle.flush();os.fsync(handle.fileno())

def install(console,root,mount,uid,backup_root,files,manifest_hash,start=False):
    pause(console);verify_identity(console,uid);disable_autoreload(console)
    boot_identity(mount,uid)
    backup_root.mkdir(parents=True,exist_ok=True)
    backup=Path(tempfile.mkdtemp(prefix='impossible-playdate-',dir=backup_root))
    receipt=dict(uid=uid,port=console.port,manifest_sha256=manifest_hash,firmware_flashed=False,
                 files=[],state='stopped at REPL; autoreload disabled',status='preparing backups')
    def save():write_bytes(backup/'install.json',(json.dumps(receipt,indent=2)+'\n').encode())
    save()
    try:
        # Back up every replaced file before changing any board file.
        for name,data in files:
            dest=safe_target(mount,name)
            if dest.exists() and not dest.is_file():raise ValueError('destination is not a file: '+name)
            previous=dest.read_bytes() if dest.exists() else None
            changed=previous!=data
            record=dict(path=name,existed=previous is not None,changed=changed,bytes=len(data),sha256=digest(data))
            if previous is not None and changed:
                saved=backup/'files'/name;saved.parent.mkdir(parents=True,exist_ok=True)
                write_bytes(saved,previous)
                if saved.read_bytes()!=previous:raise RuntimeError('backup readback mismatch')
                record['before_sha256']=digest(previous)
            receipt['files'].append(record)
        receipt['status']='backups verified; installing';save()
        for (name,data),record in zip(files,receipt['files']):
            boot_identity(mount,uid)
            dest=safe_target(mount,name)
            if record['changed']:
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest=safe_target(mount,name)
                write_bytes(dest,data)
            if dest.read_bytes()!=data:raise RuntimeError('device readback mismatch: '+name)
            record['readback_verified']=True
            save()
        # Confirm control survived the write sequence before optional execution.
        command(console,'pass')
        receipt['status']='all application files verified'
        if start:
            send(console,b'\x04')
            receipt['state']='normal startup requested; execution not certified by installer'
        save()
        print('INSTALL_READBACK_PASS',len(files),'files; backup:',backup)
        print(receipt['state'])
        return backup
    except Exception:
        receipt['status']='incomplete installation; see per-file readback state; backups preserved'
        receipt['state']='startup not requested; verify REPL before any recovery writes'
        save()
        print('INSTALL_FAILED: no deletes or automatic rollback; backup:',backup)
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit',type=Path,default=ROOT)
    p.add_argument('--port');p.add_argument('--mount',type=Path);p.add_argument('--uid')
    p.add_argument('--backup-dir',type=Path)
    p.add_argument('--start',action='store_true')
    p.add_argument('--validate-only',action='store_true')
    a=p.parse_args();root=a.kit.resolve();files,manifest_hash=preflight(root)
    if a.validate_only:
        print('APP_MANIFEST_PASS',len(files),'files',manifest_hash);return
    if not a.port or a.mount is None or not a.uid:p.error('--port, --mount and --uid are all required for installation')
    uid=a.uid.upper()
    if not re.fullmatch('[0-9A-F]{16,64}',uid):p.error('--uid must be the explicitly selected hexadecimal board UID')
    mount=a.mount.absolute();backup=(a.backup_dir or root/'install-backups').resolve()
    if backup.is_relative_to(mount.resolve()):p.error('backups must be outside the board volume')
    select_target(a.port,mount,uid)
    import serial
    options=dict(baudrate=115200,timeout=0,write_timeout=5)
    if os.name=='posix':options['exclusive']=True
    with serial.Serial(a.port,**options) as console:
        install(console,root,mount,uid,backup,files,manifest_hash,a.start)
if __name__=='__main__':main()
