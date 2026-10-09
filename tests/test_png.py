import io
import unittest

from kling_label.png import read_png
from tests import fakes
from tests.fakes import aigc_json


def texts(info):
    return [(t.ctype, t.keyword, t.text) for t in info.texts]


class ReadPngTest(unittest.TestCase):
    def test_size_from_ihdr(self):
        info = read_png(io.BytesIO(fakes.png_bytes(width=24, height=40)))
        self.assertEqual((info.width, info.height), (24, 40))
        self.assertEqual(info.texts, [])
        self.assertEqual(info.warnings, [])

    def test_text_chunk(self):
        info = read_png(io.BytesIO(fakes.kling_png()))
        self.assertEqual(texts(info), [("tEXt", "AIGC", aigc_json())])

    def test_text_chunk_after_image_data(self):
        data = fakes.png_bytes(after_idat=[fakes.text_chunk("AIGC", aigc_json())])
        self.assertEqual(texts(read_png(io.BytesIO(data))), [("tEXt", "AIGC", aigc_json())])

    def test_compressed_text_chunk(self):
        data = fakes.png_bytes(before_idat=[fakes.ztxt_chunk("AIGC", aigc_json())])
        self.assertEqual(texts(read_png(io.BytesIO(data))), [("zTXt", "AIGC", aigc_json())])

    def test_international_text_chunk(self):
        for compressed in (False, True):
            with self.subTest(compressed=compressed):
                data = fakes.png_bytes(before_idat=[fakes.itxt_chunk("AIGC", aigc_json(), compressed)])
                self.assertEqual(texts(read_png(io.BytesIO(data))), [("iTXt", "AIGC", aigc_json())])

    def test_wrong_crc_is_a_warning(self):
        data = fakes.png_bytes(before_idat=[fakes.text_chunk("AIGC", aigc_json(), bad_crc=True)])
        info = read_png(io.BytesIO(data))
        self.assertEqual(texts(info), [("tEXt", "AIGC", aigc_json())])
        self.assertTrue(any("CRC" in w for w in info.warnings))

    def test_cut_off_file_keeps_what_was_read(self):
        data = fakes.png_bytes(before_idat=[fakes.text_chunk("AIGC", aigc_json())])
        cut = data[: data.index(b"IDAT") + 10]
        info = read_png(io.BytesIO(cut))
        self.assertEqual(texts(info), [("tEXt", "AIGC", aigc_json())])
        self.assertTrue(any("ends early" in w for w in info.warnings))

    def test_cut_inside_label_chunk(self):
        data = fakes.kling_png()
        cut = data[: data.index(b"tEXt") + 20]
        info = read_png(io.BytesIO(cut))
        self.assertEqual(info.texts, [])
        self.assertTrue(any("ends early" in w for w in info.warnings))

    def test_broken_compressed_chunk_is_a_warning(self):
        broken = fakes.png_chunk(b"zTXt", b"AIGC\0\0not zlib data")
        info = read_png(io.BytesIO(fakes.png_bytes(before_idat=[broken])))
        self.assertEqual(info.texts, [])
        self.assertTrue(info.warnings)

    def test_not_a_png(self):
        with self.assertRaises(ValueError):
            read_png(io.BytesIO(b"GIF89a" + b"\0" * 20))
