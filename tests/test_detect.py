import os
import tempfile
import unittest

from kling_label.detect import detect
from tests import fakes
from tests.fakes import FAKE_ID, aigc_json


class DetectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, data):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_kling_png(self):
        r = detect(self.write("a.png", fakes.kling_png()))
        self.assertEqual(r.result, "kling_label")
        self.assertEqual(r.format, "PNG")
        self.assertEqual((r.width, r.height), (32, 48))
        self.assertEqual(r.found_by, "png_text_chunk")
        self.assertEqual(r.where, 'PNG text chunk "AIGC" (China GB 45438-2025 format)')
        self.assertEqual(r.label["ProduceID"], FAKE_ID)
        self.assertEqual(r.decoded["produce_id"]["created_utc"], "2026-01-10T07:01:59Z")

    def test_png_without_label(self):
        r = detect(self.write("a.png", fakes.png_bytes()))
        self.assertEqual(r.result, "no_label")
        self.assertIsNone(r.found_by)

    def test_png_xmp(self):
        chunk = fakes.itxt_chunk("XML:com.adobe.xmp", fakes.xmp_packet(aigc_json()))
        r = detect(self.write("a.png", fakes.png_bytes(before_idat=[chunk])))
        self.assertEqual(r.result, "kling_label")
        self.assertEqual(r.found_by, "xmp")

    def test_png_with_damaged_signature_still_found_by_scan(self):
        data = b"\x00" + fakes.kling_png()[1:]
        r = detect(self.write("a.png", data))
        self.assertEqual(r.format, "unknown")
        self.assertEqual(r.result, "kling_label")
        self.assertEqual(r.found_by, "raw_scan")
        self.assertIn("raw byte scan at offset", r.where)

    def test_two_different_labels_warns(self):
        chunks = [fakes.text_chunk("AIGC", aigc_json()),
                  fakes.text_chunk("AIGC", aigc_json(produce_id="SGP_PROD_ai_web_300000005000001"))]
        r = detect(self.write("a.png", fakes.png_bytes(before_idat=chunks)))
        self.assertEqual(r.label["ProduceID"], FAKE_ID)
        self.assertTrue(any("2 different" in w for w in r.warnings))

    def test_unreadable_label(self):
        r = detect(self.write("a.png", fakes.png_bytes(before_idat=[fakes.text_chunk("AIGC", "garbage")])))
        self.assertEqual(r.result, "unreadable_label")
        self.assertEqual(r.raw, "garbage")

    def test_kling_mp4(self):
        r = detect(self.write("v.mp4", fakes.kling_mp4()))
        self.assertEqual(r.result, "kling_label")
        self.assertEqual(r.format, "MP4")
        self.assertEqual((r.width, r.height), (1280, 720))
        self.assertEqual(r.found_by, "mp4_metadata")
        self.assertEqual(r.where, 'MP4 metadata key "AIGC" in moov/udta/meta (China GB 45438-2025 format)')

    def test_mov_brand(self):
        r = detect(self.write("v.mov", fakes.mp4_bytes(brand=b"qt  ")))
        self.assertEqual(r.format, "MOV")
        self.assertEqual(r.result, "kling_label")

    def test_old_mp4_without_label(self):
        r = detect(self.write("v.mp4", fakes.mp4_bytes(items={"encoder": "Lavf58.76.100"})))
        self.assertEqual(r.result, "no_label")

    def test_jpeg_found_by_scan(self):
        r = detect(self.write("a.jpg", fakes.jpeg_bytes(comment=aigc_json())))
        self.assertEqual(r.format, "JPEG")
        self.assertEqual(r.found_by, "raw_scan")
        self.assertEqual(r.result, "kling_label")

    def test_jpeg_xmp(self):
        r = detect(self.write("a.jpg", fakes.jpeg_bytes(xmp=fakes.xmp_packet(aigc_json()))))
        self.assertEqual(r.found_by, "xmp")
        self.assertIn("XMP", r.where)

    def test_other_service_label(self):
        r = detect(self.write("a.png", fakes.png_bytes(before_idat=[
            fakes.text_chunk("AIGC", aigc_json(producer="someone", produce_id="abc"))])))
        self.assertEqual(r.result, "other_label")

    def test_missing_file(self):
        r = detect(os.path.join(self.tmp.name, "nope.png"))
        self.assertEqual(r.result, "error")
        self.assertIn("No such file", r.error)

    def test_directory(self):
        r = detect(self.tmp.name)
        self.assertEqual(r.result, "error")

    def test_empty_file(self):
        r = detect(self.write("e.png", b""))
        self.assertEqual(r.result, "error")
        self.assertEqual(r.error, "file is empty")

    def test_cut_off_png_keeps_label_and_warns(self):
        data = fakes.kling_png()
        r = detect(self.write("a.png", data[: data.index(b"IDAT") + 10]))
        self.assertEqual(r.result, "kling_label")
        self.assertTrue(r.warnings)
