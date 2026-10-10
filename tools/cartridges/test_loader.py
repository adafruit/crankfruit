"""Portable host tests. All fixtures are local temporary authored source only."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

import cartridge_loader as loader
from cartridge_cli import pack


SOURCE = b'function playdate.update() end\n'


def manifest(**overrides):
    result = dict(kind="lua", profile="crankfruit-lua-v1", title="A New Game",
                  author="Fixture Author", description="Independent authored fixture",
                  controls="B1/B2 move; B3 play", target_fps=30)
    result.update(overrides)
    return result


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # Many macOS temporary-directory ancestors are symlinks. Resolve the
        # trusted test root explicitly; loader must not silently follow them.
        self.root = Path(self.temp.name).resolve()
        self.games = self.root / "games"
        self.games.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def game(self, name="sample", metadata=None, source=SOURCE):
        folder = self.games / name
        folder.mkdir()
        (folder / "manifest.json").write_text(json.dumps(manifest() if metadata is None else metadata))
        (folder / "main.lua").write_bytes(source)
        return folder

    def discover(self):
        return loader.discover(str(self.games))

    def test_valid_defaults_and_load(self):
        self.game()
        item, = self.discover()
        self.assertTrue(item["enabled"])
        self.assertEqual(item["compatibility"], "source candidate")
        self.assertEqual(item["heap_cap"], 65536)
        self.assertEqual(loader.load(item), SOURCE)

    def test_independent_game_insertion_not_hardcoded(self):
        self.game("almost-tennis", manifest(title="Almost Tennis"))
        self.assertEqual([i["slug"] for i in self.discover()], ["almost-tennis"])
        self.game("third-party-fresh", manifest(title="Fresh Independent Game"), b'-- unrelated source\n'+SOURCE)
        items = self.discover()
        self.assertEqual([i["slug"] for i in items], ["almost-tennis", "third-party-fresh"])
        self.assertTrue(all(i["enabled"] for i in items))
        self.assertIn(b'unrelated', loader.load(items[1]))

    def test_unknown_game_api_is_not_certified_or_executed(self):
        self.game(source=b'playdate.a_missing_feature()\n')
        item, = self.discover()
        self.assertTrue(item["enabled"])
        self.assertEqual(item["compatibility"], "source candidate")

    def test_python_in_folder_is_not_executed(self):
        folder = self.game()
        (folder / 'evil.py').write_text('raise RuntimeError("must not execute")')
        self.assertEqual(loader.load(self.discover()[0]), SOURCE)

    def test_bad_folder_does_not_break_library(self):
        self.game('good')
        self.game('bad', manifest(profile='unsupported'))
        items = self.discover()
        self.assertEqual(len(items), 2)
        self.assertFalse(items[0]['enabled']); self.assertTrue(items[1]['enabled'])
        self.assertIn('profile', items[0]['reason'])

    def test_display_fields_ascii_and_lengths(self):
        for key,value in (('title',''),('title','  '),('title','x'*49),('author',''),
                          ('author','x'*65),('description','x'*161),('controls','x'*161),
                          ('title','café'),('controls','line\nbreak'),('description',{}),
                          ('author',None),('title','\x7f')):
            folder=self.game('case'+str(len(list(self.games.iterdir()))),manifest(**{key:value}))
            self.assertFalse(loader.inspect_folder(str(folder))['enabled'])

    def test_required_fields(self):
        for key in ('kind','profile','title','author','description','controls','target_fps'):
            m=manifest();del m[key]
            folder=self.game('missing-'+key.replace('_','-'),m)
            self.assertFalse(loader.inspect_folder(str(folder))['enabled'])

    def test_heap_and_fps_bounds(self):
        cases=[({'heap_cap':32768},True),({'heap_cap':262144},True),
               ({'heap_cap':32767},False),({'heap_cap':262145},False),
               ({'heap_cap':65536.0},False),({'heap_cap':True},False),
               ({'target_fps':30.0},False),({'target_fps':False},False),({'target_fps':60},False)]
        for index,(values,expected) in enumerate(cases):
            folder=self.game('heap%d'%index,manifest(**values))
            self.assertEqual(loader.inspect_folder(str(folder))['enabled'],expected)

    def test_unknown_fields_rejected(self):
        self.game(metadata=manifest(id='not-in-schema'))
        self.assertIn('unknown manifest field',self.discover()[0]['reason'])

    def test_duplicate_keys_even_escaped_rejected(self):
        folder=self.game()
        base=json.dumps(manifest())[:-1]
        for duplicate in ('"title":"Second"','"\\u0074itle":"Second"'):
            (folder/'manifest.json').write_text(base+','+duplicate+'}')
            self.assertIn('duplicate',self.discover()[0]['reason'])

    def test_manifest_quotes_and_colons_in_values(self):
        self.game(metadata=manifest(description='say "title": safely; key text is a value'))
        self.assertTrue(self.discover()[0]['enabled'])

    def test_manifest_size_and_invalid_json(self):
        folder=self.game()
        for raw in (b'',b'{',b'[]',b'null',b'"string"',b'\xff',b' '*4097,b'{"x":'*700):
            (folder/'manifest.json').write_bytes(raw)
            self.assertFalse(self.discover()[0]['enabled'])

    def test_exact_manifest_limit(self):
        folder=self.game()
        raw=(folder/'manifest.json').read_bytes()
        (folder/'manifest.json').write_bytes(raw+b' '*(4096-len(raw)))
        self.assertTrue(self.discover()[0]['enabled'])

    def test_source_size_boundaries(self):
        folder=self.game()
        for size,expected in ((0,False),(1,True),(131072,True),(131073,False)):
            (folder/'main.lua').write_bytes(b' '*size)
            self.assertEqual(self.discover()[0]['enabled'],expected)

    def test_binary_source_rejected(self):
        folder=self.game()
        for source in (b'\x1bLua',b'\x7fELF',b'\xff\xff',b'a\0b',b'hello\x03',b'x\x7f'):
            (folder/'main.lua').write_bytes(source)
            self.assertFalse(self.discover()[0]['enabled'])

    def test_unicode_source_comment_allowed(self):
        self.game(source='-- café\nfunction playdate.update() end'.encode())
        self.assertTrue(self.discover()[0]['enabled'])

    def test_unsupported_files_and_directories_visible(self):
        for suffix in ('.pdx','.pdz','.luac','.elf','.bin','.uf2','.zip'):
            (self.games/('example'+suffix)).write_bytes(b'junk')
        (self.games/'directory.pdx').mkdir()
        (self.games/'README.md').write_text('ordinary docs ignored')
        items=self.discover()
        self.assertEqual(len(items),8)
        self.assertTrue(all(not i['enabled'] and 'unsupported' in i['reason'] for i in items))

    def test_missing_manifest_and_entry(self):
        a=self.game('a');(a/'manifest.json').unlink()
        b=self.game('b');(b/'main.lua').unlink()
        self.assertEqual([i['reason'] for i in self.discover()],['missing manifest.json','missing main.lua'])

    def test_paths_confined(self):
        for index,entry in enumerate(('../outside.lua','/absolute.lua','sub/main.lua','other.lua','main.lua/..')):
            folder=self.game('entry%d'%index,manifest(entry=entry))
            self.assertFalse(loader.inspect_folder(str(folder))['enabled'])
        for name in ('UPPER','bad.name','has space'):
            self.game(name)
        self.assertTrue(all(not i['enabled'] for i in self.discover()))
        self.assertFalse(loader.discover(str(self.games)+'/../games')[0]['enabled'])

    @unittest.skipUnless(hasattr(os,'symlink') and hasattr(os,'lstat'),'host lacks symlinks')
    def test_symlinks_rejected_everywhere(self):
        folder=self.game()
        target=self.root/'outside.lua';target.write_bytes(SOURCE)
        (folder/'main.lua').unlink();os.symlink(target,folder/'main.lua')
        self.assertIn('symlink',self.discover()[0]['reason'])
        (folder/'main.lua').unlink();(folder/'main.lua').write_bytes(SOURCE)
        os.symlink(folder,self.games/'linked')
        self.assertTrue(any('symlink' in i['reason'] for i in self.discover()))
        alias=self.root/'alias';os.symlink(self.games,alias)
        self.assertIn('symlink',loader.discover(str(alias))[0]['reason'])

    def test_extra_real_subfolder_ignored_not_executed(self):
        folder=self.game();(folder/'assets').mkdir()
        (folder/'assets'/'evil.py').write_text('raise RuntimeError("never execute")')
        self.assertTrue(self.discover()[0]['enabled'])

    def test_directory_entry_limits(self):
        folder=self.game()
        for i in range(31):(folder/('extra%d'%i)).write_text('')
        self.assertIn('32',self.discover()[0]['reason'])
        for i in range(32):(self.games/('extra%d'%i)).write_text('')
        items=self.discover();self.assertEqual(len(items),1);self.assertIn('32',items[0]['reason'])

    def test_empty_and_missing_root(self):
        self.assertEqual(self.discover(),[])
        self.assertFalse(loader.discover(str(self.root/'absent'))[0]['enabled'])
        for value in ('',None,7):self.assertFalse(loader.discover(value)[0]['enabled'])

    def test_changed_source_and_metadata_require_refresh(self):
        folder=self.game();item=self.discover()[0]
        (folder/'main.lua').write_bytes(b'-- changed\n'+SOURCE)
        with self.assertRaises(loader.CartridgeError):loader.load(item)
        item=self.discover()[0]
        (folder/'manifest.json').write_text(json.dumps(manifest(title='Changed')))
        with self.assertRaises(loader.CartridgeError):loader.load(item)
        self.assertIn(b'changed',loader.load(self.discover()[0]))

    def test_invalidated_and_forged_items(self):
        folder=self.game();item=self.discover()[0]
        forged=dict(item);forged['folder']='/outside'
        with self.assertRaises(loader.CartridgeError):loader.load(forged)
        (folder/'main.lua').unlink()
        with self.assertRaises(loader.CartridgeError):loader.load(item)
        for value in ({},None,{'enabled':False}):
            with self.assertRaises(loader.CartridgeError):loader.load(value)

    def test_pack_allowlist_no_python_private_paths_or_overwrite(self):
        folder=self.game();(folder/'LICENSE').write_text('fixture license')
        (folder/'README.md').write_text('fixture readme')
        (folder/'secret.py').write_text('must not be copied or executed')
        destination=self.root/'game.zip'
        result=pack(str(folder),destination)
        self.assertFalse(result['execution_performed'])
        with zipfile.ZipFile(destination) as archive:
            self.assertEqual(set(archive.namelist()),{'sample/main.lua','sample/manifest.json','sample/LICENSE','sample/README.md'})
            self.assertEqual(archive.read('sample/main.lua'),SOURCE)
        with self.assertRaises(FileExistsError):pack(str(folder),destination)

    def test_pack_bad_candidate_creates_nothing(self):
        folder=self.game(metadata=manifest(profile='bad'))
        destination=self.root/'game.zip'
        with self.assertRaises(loader.CartridgeError):pack(str(folder),destination)
        self.assertFalse(destination.exists())


if __name__=='__main__':unittest.main(verbosity=2)
