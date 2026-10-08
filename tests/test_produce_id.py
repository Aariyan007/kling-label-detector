import unittest

from kling_label.produce_id import decode_produce_id
from tests.fakes import FAKE_ID


class DecodeProduceIdTest(unittest.TestCase):
    def test_made_up_web_id(self):
        d = decode_produce_id(FAKE_ID)
        self.assertEqual(d["region"], "SGP")
        self.assertEqual(d["system"], "PROD")
        self.assertEqual(d["client"], "ai_web")
        self.assertEqual(d["digits"], "300000000123456")
        self.assertEqual(d["extra_digits"], "123456")
        self.assertEqual(d["created_unix"], 1468028519 + 300000000)
        self.assertEqual(d["created_utc"], "2026-01-10T07:01:59Z")

    def test_other_client_name(self):
        d = decode_produce_id("SGP_PROD_ai_app_300000001999000")
        self.assertEqual(d["client"], "ai_app")
        self.assertEqual(d["created_unix"], 1468028519 + 300000001)

    def test_bad_shapes_give_none(self):
        for bad in ["", "kling", "SGP_PROD_ai_web_12345", "SGP_PROD_ai_web_3000000001234567",
                    "sgp_PROD_ai_web_300000000123456", "SGP_PROD__300000000123456",
                    "SGP_PROD_ai_web_30000000012345x", None, 123]:
            with self.subTest(bad=bad):
                self.assertIsNone(decode_produce_id(bad))
