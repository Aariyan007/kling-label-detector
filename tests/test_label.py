import json
import unittest

from kling_label.label import classify_payload, looks_like_kling
from tests.fakes import FAKE_USCC_PRODUCER, aigc_json


class LooksLikeKlingTest(unittest.TestCase):
    def test_kling_producer(self):
        self.assertTrue(looks_like_kling(json.loads(aigc_json())))

    def test_uscc_producer(self):
        self.assertTrue(looks_like_kling(json.loads(aigc_json(producer=FAKE_USCC_PRODUCER))))

    def test_kling_shaped_id_only(self):
        self.assertTrue(looks_like_kling(json.loads(aigc_json(producer="someone"))))

    def test_other_service(self):
        payload = json.loads(aigc_json(producer="someone", produce_id="abc-123"))
        self.assertFalse(looks_like_kling(payload))


class ClassifyPayloadTest(unittest.TestCase):
    def test_kling(self):
        kind, payload = classify_payload(aigc_json())
        self.assertEqual(kind, "kling_label")
        self.assertEqual(payload["Label"], "1")

    def test_other(self):
        kind, _ = classify_payload(aigc_json(producer="x", produce_id="y"))
        self.assertEqual(kind, "other_label")

    def test_unreadable(self):
        for text in ["not json", "[1, 2]", "\"just a string\"", ""]:
            with self.subTest(text=text):
                kind, payload = classify_payload(text)
                self.assertEqual(kind, "unreadable_label")
                self.assertIsNone(payload)
