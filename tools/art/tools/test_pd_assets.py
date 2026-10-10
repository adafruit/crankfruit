"""Self-authored fixtures and hostile-format bounds; no downloaded game assets."""
import hashlib
import json
from pathlib import Path
import random
import struct
import tempfile
import unittest
import zlib

from pd_assets import (AssetError, Image, Limits, PDI, PDT, COMPRESSED, from_rows,
                       decode_pdi, decode_pdt, encode_pdi, encode_pdt,
                       pack_atlas, pack_native_atlas, read_bundle, write_bundle,
                       write_png)


APPLE = ["    #    ", "   #.#   ", " ###.### ", "#########",
         "##.###.##", "#########", " ####### ", "  #####  "]


def raw_cell(cw=1, ch=1, stride=4, left=0, right=0, top=0, bottom=0,
             flags=0, color=b'\x80\0\0\0', alpha=b''):
    return struct.pack('<8H', cw, ch, stride, left, right, top, bottom, flags) + color + alpha


def raw_pdi(cell):
    return PDI + struct.pack('<I', 0) + cell


class Images(unittest.TestCase):
    def test_authored_pdi_roundtrip_all_flags(self):
        for image in (from_rows(APPLE), from_rows(['.##..', '#..##']), from_rows(['   ', '   '])):
            for compressed in (False, True):
                for crop in (False, True):
                    self.assertEqual(decode_pdi(encode_pdi(image, compressed=compressed, crop=crop)), image)

    def test_random_roundtrips(self):
        rand = random.Random(1977)
        for width in (1, 7, 8, 9, 31, 32, 33, 47):
            for height in (1, 2, 7, 16):
                image = from_rows([''.join(rand.choice(' .#') for _ in range(width)) for _ in range(height)])
                for compressed in (False, True):
                    self.assertEqual(decode_pdi(encode_pdi(image, compressed=compressed)), image)

    def test_authored_pdt_roundtrip(self):
        images = (from_rows(APPLE), from_rows(['.#', '#.']), from_rows([' ']))
        for compressed in (False, True):
            table = decode_pdt(encode_pdt(images, compressed=compressed))
            self.assertEqual(table.images, images); self.assertEqual(table.columns, 3)

    def test_matrix_pdt(self):
        images = (from_rows(APPLE),) * 6
        table = decode_pdt(encode_pdt(images, columns=2))
        self.assertEqual(table.columns, 2); self.assertEqual(table.images, images)

    def test_pdt_offsets_handcrafted(self):
        # Independent fixture construction, not our encoder: two one-pixel cells.
        a = raw_cell(color=b'\0\0\0\0'); b = raw_cell(color=b'\x80\0\0\0')
        payload = struct.pack('<HHII', 2, 2, len(a), len(a) + len(b)) + a + b
        table = decode_pdt(PDT + struct.pack('<I', 0) + payload)
        self.assertEqual(table.images, (from_rows(['#']), from_rows(['.'])))

    def test_cropped_alpha_handcrafted(self):
        cell = raw_cell(cw=2, ch=1, left=2, right=1, top=1, bottom=1,
                        flags=1, color=b'\xc0\0\0\0', alpha=b'\x80\0\0\0')
        self.assertEqual(decode_pdi(raw_pdi(cell)), from_rows(['     ', '  .  ', '     ']))

    def test_no_alpha_cropped_margin_matches_reference(self):
        cell = raw_cell(left=1, right=1, top=1, bottom=1, color=b'\0\0\0\0')
        self.assertEqual(decode_pdi(raw_pdi(cell)), from_rows(['...', '.#.', '...']))

    def test_flags_two_and_three_are_alpha(self):
        for flags in (2, 3):
            self.assertEqual(decode_pdi(raw_pdi(raw_cell(flags=flags, alpha=b'\0'*4))), from_rows([' ']))

    def test_padding_is_ignored_on_import_and_zeroed(self):
        image = decode_pdi(raw_pdi(raw_cell(color=b'\xff'*4)))
        self.assertEqual(image.pixels, b'\x80'); self.assertEqual(image.alpha, b'\x80')

    def test_empty_transparent_cell(self):
        cell = raw_cell(cw=0, ch=0, stride=0, right=3, bottom=2, flags=1, color=b'')
        self.assertEqual(decode_pdi(raw_pdi(cell)), from_rows(['   ', '   ']))

    def test_unknown_flags_fail(self):
        for flags in (1, 2, COMPRESSED | 1):
            with self.assertRaises(AssetError): decode_pdi(PDI + struct.pack('<I', flags) + b'\0'*16)
        with self.assertRaises(AssetError): decode_pdi(raw_pdi(raw_cell(flags=4)))

    def test_every_truncation_fails(self):
        for data, decoder in ((encode_pdi(from_rows(APPLE)), decode_pdi),
                              (encode_pdi(from_rows(APPLE), compressed=False), decode_pdi),
                              (encode_pdt([from_rows(APPLE)]*2), decode_pdt),
                              (encode_pdt([from_rows(APPLE)]*2, compressed=False), decode_pdt)):
            for length in range(len(data)):
                with self.assertRaises(AssetError): decoder(data[:length])

    def test_stride_invalid(self):
        for stride in (0, 1, 2, 3, 5):
            with self.assertRaises(AssetError): decode_pdi(raw_pdi(raw_cell(stride=stride)))
        with self.assertRaises(AssetError): decode_pdi(raw_pdi(raw_cell(cw=33, stride=4)))

    def test_dimensions_and_total_budget(self):
        data = raw_pdi(raw_cell(left=2048))
        with self.assertRaises(AssetError): decode_pdi(data)
        with self.assertRaises(AssetError): decode_pdi(encode_pdi(from_rows(APPLE)), Limits(max_pixels=10))
        with self.assertRaises(AssetError): decode_pdt(encode_pdt([from_rows(APPLE)]*2), Limits(max_total_pixels=100))

    def test_decompression_bomb_and_reported_size(self):
        payload = zlib.compress(b'A'*100000)
        for reported in (16, 100001, 16*1024*1024+1):
            with self.assertRaises(AssetError): decode_pdi(PDI+struct.pack('<5I', COMPRESSED, reported, 1, 1, 0)+payload)

    def test_trailing_zlib_and_garbage(self):
        data = encode_pdi(from_rows(APPLE))
        for tail in (b'x', zlib.compress(b'abc')):
            with self.assertRaises(AssetError): decode_pdi(data+tail)
        with self.assertRaises(AssetError): decode_pdi(data[:32]+b'garbage')

    def test_metadata_mismatch(self):
        for encoder, decoder, offset, value in ((encode_pdi, decode_pdi, 20, 1),
                                                (encode_pdi, decode_pdi, 28, 1),
                                                (encode_pdt, decode_pdt, 28, 2)):
            obj = [from_rows(APPLE)] if encoder is encode_pdt else from_rows(APPLE)
            data = bytearray(encoder(obj)); struct.pack_into('<I', data, offset, value)
            with self.assertRaises(AssetError): decoder(bytes(data))

    def test_table_offsets_invalid(self):
        good = encode_pdt([from_rows(APPLE)]*2, compressed=False)
        for first, end in ((0, 0), (0xffffffff, 0xffffffff), (16, 16), (100, 20)):
            data = bytearray(good); struct.pack_into('<2I', data, 20, first, end)
            with self.assertRaises(AssetError): decode_pdt(bytes(data))

    def test_table_count_and_columns_invalid(self):
        for count, columns in ((0, 0), (1025, 1), (1, 0), (1, 2)):
            data = PDT+struct.pack('<I2H', 0, count, columns)
            with self.assertRaises(AssetError): decode_pdt(data)

    def test_cell_trailing_and_truncated_data(self):
        cell = raw_cell()
        for data in (cell+b'\0', cell[:-1], raw_cell(flags=1)):
            with self.assertRaises(AssetError): decode_pdi(raw_pdi(data))

    def test_bad_signature_and_input_budget(self):
        for magic in (b'Playdate BAD', b'x'*12):
            with self.assertRaises(AssetError): decode_pdi(magic+b'\0'*24)
        with self.assertRaises(AssetError): decode_pdi(encode_pdi(from_rows(APPLE)), Limits(max_input=20))

    def test_canonical_image_validation(self):
        for pixels, alpha in ((b'\x81', b'\x80'), (b'\x80', b'\0'), (b'', b'')):
            with self.assertRaises(AssetError): Image(1, 1, pixels, alpha)
        with self.assertRaises(AssetError): from_rows(['.', '..'])
        with self.assertRaises(AssetError): from_rows(['x'])
        with self.assertRaises(AssetError): from_rows([])

    def test_matrix_unequal_sizes_rejected(self):
        a,b=from_rows(['#']),from_rows(['##'])
        with self.assertRaises(AssetError): encode_pdt([a,b],columns=1)
        data=bytearray(encode_pdt([a,b],compressed=False)); struct.pack_into('<H',data,18,1)
        with self.assertRaises(AssetError): decode_pdt(bytes(data))

    def test_spatial_atlas(self):
        images = [from_rows(APPLE), from_rows(['.#', '#.'])]
        atlas, placements = pack_atlas(images, columns=2, padding=2)
        for image, rect in zip(images, placements):
            for y in range(image.height):
                for x in range(image.width):
                    self.assertEqual(image.pixel(x,y),atlas.pixel(rect['x']+x,rect['y']+y))
        self.assertEqual(atlas.pixel(0,0),(0,0))

    def test_native_descriptor_exact_layout(self):
        images=decode_pdt(encode_pdt([from_rows(APPLE),from_rows(['.#','#.'])])).images
        atlas, descriptors=pack_native_atlas(images)
        self.assertEqual(len(descriptors),24)
        for number,image in enumerate(images):
            w,h,p,m=struct.unpack_from('<HHII',descriptors,number*12)
            self.assertEqual((w,h),(image.width,image.height))
            self.assertEqual(atlas[p:p+len(image.pixels)],image.pixels)
            self.assertEqual(atlas[m:m+len(image.mask)],image.mask)

    def test_native_limit_256(self):
        image=from_rows(['.'])
        self.assertEqual(len(pack_native_atlas([image]*256)[1]),3072)
        with self.assertRaises(AssetError): pack_native_atlas([image]*257)

    def test_native_150_glyph_pipeline(self):
        # Parent's intended large atlas scale, through actual encoded PDT.
        sprites=[from_rows([''.join('.' if (x+y+n)%3 else '#' for x in range(7))
                            for y in range(9)]) for n in range(150)]
        images=decode_pdt(encode_pdt(sprites)).images
        self.assertEqual(images,tuple(sprites))
        atlas,descriptors=pack_native_atlas(images)
        self.assertEqual(len(descriptors),1800)
        self.assertEqual(len(atlas),150*9*2)

    def test_native_export_matches_device_limits(self):
        with self.assertRaises(AssetError):
            pack_native_atlas([from_rows(['.'*401])])
        with self.assertRaises(AssetError):
            pack_native_atlas([from_rows(['.']*241)])
        frame=from_rows(['.'*400]*240)
        self.assertEqual(len(pack_native_atlas([frame]*10)[0]),240000)
        with self.assertRaises(AssetError):pack_native_atlas([frame]*11)

    def test_mutated_inputs_fail_cleanly_or_remain_valid(self):
        randomizer=random.Random(88772)
        for decoder,good in ((decode_pdi,encode_pdi(from_rows(APPLE))),
                             (decode_pdt,encode_pdt([from_rows(APPLE)]*2))):
            for _ in range(200):
                data=bytearray(good)
                for _ in range(randomizer.randrange(1,5)):
                    position=randomizer.randrange(len(data))
                    data[position]^=1<<randomizer.randrange(8)
                try:
                    decoder(bytes(data))
                except AssetError:
                    pass

    def test_bundle_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'sprites'
            images=(from_rows(APPLE),from_rows(['.']))
            write_bundle(images,path)
            self.assertEqual(read_bundle(path).images,images)
            with self.assertRaises(FileExistsError): write_bundle(images,path)
            self.assertTrue((path/'frame-0000.png').read_bytes().startswith(b'\x89PNG'))

    def test_bundle_malformed_offsets_hashes_and_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'sprites'; write_bundle([from_rows(APPLE)],path,previews=False)
            good=json.loads((path/'manifest.json').read_text())
            for change in ('offset','hash','count','dimensions'):
                m=json.loads(json.dumps(good))
                if change=='offset': m['frames'][0]['offset']=-1
                elif change=='hash': m['pixels_sha256']='abc'
                elif change=='count': m['frames']=[]
                else: m['frames'][0]['width']=999999999
                (path/'manifest.json').write_text(json.dumps(m))
                with self.assertRaises(AssetError): read_bundle(path)


if __name__=='__main__':
    unittest.main(verbosity=2)
