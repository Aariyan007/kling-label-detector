import io
import unittest

from kling_label.scan import find_xmp_aigc, scan_file
from tests import fakes
from tests.fakes import aigc_json


class XmpTest(unittest.TestCase):
    def test_attribute_form(self):
        self.assertEqual(find_xmp_aigc(fakes.xmp_packet(aigc_json(), "attr").encode()), aigc_json())

    def test_element_form(self):
        self.assertEqual(find_xmp_aigc(fakes.xmp_packet(aigc_json(), "element").encode()), aigc_json())

    def test_no_field(self):
        self.assertIsNone(find_xmp_aigc(fakes.xmp_packet("x").replace("AIGC", "Other").encode()))


class ScanFileTest(unittest.TestCase):
    def test_json_in_jpeg_comment(self):
        data = fakes.jpeg_bytes(comment=aigc_json())
        hit = scan_file(io.BytesIO(data))
        self.assertEqual(hit.kind, "json")
        self.assertEqual(hit.text, aigc_json())
        self.assertEqual(hit.offset, data.index(b"{"))

    def test_xmp_in_jpeg(self):
        hit = scan_file(io.BytesIO(fakes.jpeg_bytes(xmp=fakes.xmp_packet(aigc_json()))))
        self.assertEqual(hit.kind, "xmp")
        self.assertEqual(hit.text, aigc_json())

    def test_label_split_across_blocks(self):
        for padding in range(0, 300, 7):
            with self.subTest(padding=padding):
                data = fakes.jpeg_bytes(comment=aigc_json(), padding=padding)
                hit = scan_file(io.BytesIO(data), block_size=128)
                self.assertIsNotNone(hit)
                self.assertEqual(hit.text, aigc_json())

    def test_nothing_found(self):
        self.assertIsNone(scan_file(io.BytesIO(fakes.jpeg_bytes(comment="hello {} world"))))
        self.assertIsNone(scan_file(io.BytesIO(b"")))
