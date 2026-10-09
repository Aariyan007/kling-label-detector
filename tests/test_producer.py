import unittest

from kling_label.producer import decode_producer, uscc_is_valid
from tests.fakes import FAKE_USCC, FAKE_USCC_PRODUCER


class UsccTest(unittest.TestCase):
    def test_known_code_is_valid(self):
        self.assertTrue(uscc_is_valid(FAKE_USCC))

    def test_wrong_check_digit(self):
        self.assertFalse(uscc_is_valid(FAKE_USCC[:-1] + "D"))

    def test_bad_characters_and_length(self):
        self.assertFalse(uscc_is_valid("91110108335469089"))
        self.assertFalse(uscc_is_valid("9111010833546908IC"))  # I is not used in USCC
        self.assertFalse(uscc_is_valid("91110108335469089c"))


class DecodeProducerTest(unittest.TestCase):
    def test_kling(self):
        self.assertEqual(decode_producer("kling"), {"form": "kling"})

    def test_uscc_form(self):
        d = decode_producer(FAKE_USCC_PRODUCER)
        self.assertEqual(d["form"], "uscc")
        self.assertEqual(d["prefix"], "0011")
        self.assertEqual(d["uscc"], FAKE_USCC)
        self.assertEqual(d["suffix"], "10100")
        self.assertTrue(d["uscc_valid"])

    def test_uscc_shape_with_wrong_check_digit(self):
        d = decode_producer("0011" + FAKE_USCC[:-1] + "D" + "10100")
        self.assertEqual(d["form"], "uscc")
        self.assertEqual(d["uscc"], FAKE_USCC[:-1] + "D")
        self.assertFalse(d["uscc_valid"])

    def test_valid_uscc_found_anywhere(self):
        d = decode_producer("XY" + FAKE_USCC)
        self.assertEqual(d["form"], "uscc")
        self.assertEqual(d["prefix"], "XY")
        self.assertEqual(d["suffix"], "")
        self.assertTrue(d["uscc_valid"])

    def test_other(self):
        self.assertEqual(decode_producer("somebody"), {"form": "other"})
        self.assertEqual(decode_producer(None), {"form": "missing"})
        self.assertEqual(decode_producer(42), {"form": "other"})
