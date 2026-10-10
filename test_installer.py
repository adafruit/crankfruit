"""Host-only manifest, REPL acknowledgment and installation-policy checks."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
import install as installer

class FakeSerial:
    port='HOST_TEST_NO_DEVICE'
    def __init__(self,echo_only=False):self.pending=b'';self.writes=[];self.echo_only=echo_only
    def reset_input_buffer(self):self.pending=b''
    def write(self,data):
        self.writes.append(data)
        if data==b'\x03':self.pending+=b'\r\n>>> '
        elif b'IP_ACK_' in data:
            self.pending+=data
            if not self.echo_only:
                marker=re.search(rb'IP_ACK_[0-9a-f]+',data).group()
                self.pending+=marker+b'\r\n>>> '
            else:self.pending+=b'>>> '
        return len(data)
    def read(self,n):result=self.pending[:n];self.pending=self.pending[n:];return result

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='installer-test-',dir=Path(__file__).resolve().parent)
        self.root=Path(self.temp.name);self.kit=self.root/'kit';self.mount=self.root/'volume'
        (self.kit/'app').mkdir(parents=True);self.mount.mkdir()
        (self.mount/'boot_out.txt').write_text('Adafruit CircuitPython 10.3.0\nBoard ID:adafruit_fruit_jam\nUID:0000000000000000\n')
        self.make_manifest({'code.py':b'print("sample")\n','assets/pixel.bin':b'\x00\xff'})
    def tearDown(self):self.temp.cleanup()
    def make_manifest(self,files):
        records=[]
        for name,data in files.items():
            p=self.kit/'app'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            records.append(dict(path=name,bytes=len(data),sha256=installer.digest(data)))
        (self.kit/'app-manifest.json').write_text(json.dumps(records))
    def test_manifest_sorted_and_exact(self):
        files,digest=installer.preflight(self.kit)
        self.assertEqual(files[-1][0],'code.py');self.assertEqual(len(digest),64)
        (self.kit/'app'/'extra').write_bytes(b'x')
        with self.assertRaises(ValueError):installer.preflight(self.kit)
    def test_hash_failure(self):
        (self.kit/'app'/'code.py').write_bytes(b'print("changed")\n')
        with self.assertRaises(ValueError):installer.preflight(self.kit)
    def test_path_validation(self):
        for name in ('../x','/x','a/../b','a//b','./x','a/./b','.hidden','a\\b','x:y','x\x00y'):
            with self.assertRaises(ValueError):installer.relative_name(name)
    def test_duplicate_rejected(self):
        p=self.kit/'app-manifest.json';records=json.loads(p.read_text());records+=records[:1];p.write_text(json.dumps(records))
        with self.assertRaises(ValueError):installer.preflight(self.kit)
    def test_symlink_rejected(self):
        (self.kit/'app'/'link').symlink_to(self.kit/'app'/'code.py')
        with self.assertRaises(ValueError):installer.preflight(self.kit)
    def test_wrong_mount_uid(self):
        with self.assertRaises(ValueError):installer.boot_identity(self.mount,'FFFFFFFFFFFFFFFF')
    def test_repl_ack_not_echo(self):
        with self.assertRaises(RuntimeError):installer.command(FakeSerial(True),'pass',seconds=.025)
        installer.command(FakeSerial(),'pass',seconds=.1)
    def test_installer_backups_readback_no_delete_no_start(self):
        (self.mount/'code.py').write_bytes(b'print("original")\n')
        (self.mount/'unrelated.txt').write_bytes(b'preserve')
        files,digest=installer.preflight(self.kit);serial=FakeSerial()
        with contextlib.redirect_stdout(io.StringIO()):
            backup=installer.install(serial,self.kit,self.mount,'0000000000000000',self.root/'backups',files,digest)
        self.assertEqual((backup/'files'/'code.py').read_bytes(),b'print("original")\n')
        self.assertEqual((self.mount/'unrelated.txt').read_bytes(),b'preserve')
        self.assertEqual((self.mount/'code.py').read_bytes(),files[-1][1])
        receipt=json.loads((backup/'install.json').read_text())
        self.assertTrue(all(r['readback_verified'] for r in receipt['files']))
        self.assertNotIn(b'\x04',serial.writes)
    def test_installer_optional_start(self):
        files,digest=installer.preflight(self.kit);serial=FakeSerial()
        with contextlib.redirect_stdout(io.StringIO()):
            installer.install(serial,self.kit,self.mount,'0000000000000000',self.root/'backups',files,digest,True)
        self.assertEqual(serial.writes[-1],b'\x04')
if __name__=='__main__':unittest.main()
