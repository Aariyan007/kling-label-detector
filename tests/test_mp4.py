import io
import unittest

from kling_label.mp4 import read_mp4
from tests import fakes
from tests.fakes import aigc_json


def items(info):
    return {i.key: i.value for i in info.items}


class ReadMp4Test(unittest.TestCase):
    def test_label_and_size(self):
        info = read_mp4(io.BytesIO(fakes.kling_mp4()))
        self.assertEqual(items(info)["AIGC"], aigc_json())
        self.assertEqual(items(info)["encoder"], "Lavf61.7.100")
        self.assertEqual((info.width, info.height), (1280, 720))
        self.assertEqual(info.items[0].path, "moov/udta/meta")
        self.assertEqual(info.warnings, [])

    def test_quicktime_meta_without_version_header(self):
        info = read_mp4(io.BytesIO(fakes.mp4_bytes(quicktime_meta=True)))
        self.assertEqual(items(info)["AIGC"], aigc_json())

    def test_meta_inside_track(self):
        info = read_mp4(io.BytesIO(fakes.mp4_bytes(meta_in_trak=True)))
        self.assertEqual(items(info)["AIGC"], aigc_json())
        self.assertEqual(info.items[0].path, "moov/trak/udta/meta")

    def test_64_bit_box_size(self):
        info = read_mp4(io.BytesIO(fakes.mp4_bytes(large_moov=True)))
        self.assertEqual(items(info)["AIGC"], aigc_json())

    def test_old_video_with_only_encoder(self):
        info = read_mp4(io.BytesIO(fakes.mp4_bytes(items={"encoder": "Lavf58.76.100"})))
        self.assertEqual(items(info), {"encoder": "Lavf58.76.100"})

    def test_no_metadata(self):
        info = read_mp4(io.BytesIO(fakes.mp4_bytes(items={})))
        self.assertEqual(info.items, [])

    def test_cut_off_file(self):
        data = fakes.kling_mp4()
        cut = data[: data.index(b"ilst") + 30]
        info = read_mp4(io.BytesIO(cut))
        self.assertNotIn("AIGC", items(info))
        self.assertTrue(any("ends early" in w for w in info.warnings))

    def test_cut_inside_label_value_is_not_reported(self):
        data = fakes.kling_mp4()
        cut = data[: data.index(b'"ProduceID"')]
        info = read_mp4(io.BytesIO(cut))
        self.assertNotIn("AIGC", items(info))
        self.assertIn("major_brand", items(info))

    def test_broken_box_size(self):
        data = fakes.box(b"ftyp", b"isom\0\0\0\0") + b"\0\0\0\x03moov"
        info = read_mp4(io.BytesIO(data))
        self.assertEqual(info.items, [])
        self.assertTrue(info.warnings)

    def test_size_from_version_1_tkhd(self):
        moov = fakes.box(b"moov", fakes.box(b"trak", fakes.tkhd_box(640, 360, version=1)))
        info = read_mp4(io.BytesIO(fakes.box(b"ftyp", b"isom\0\0\0\0") + moov))
        self.assertEqual((info.width, info.height), (640, 360))
