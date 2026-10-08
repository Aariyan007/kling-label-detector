import contextlib
import io
import json
import os
import tempfile
import unittest

from kling_label.cli import main
from tests import fakes
from tests.fakes import FAKE_ID, FAKE_USCC_PRODUCER, aigc_json


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(args))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, data):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_text_output_matches_design(self):
        path = self.write("image.png", fakes.kling_png())
        code, out, _ = run(path)
        self.assertEqual(code, 0)
        self.assertEqual(out, (
            f"File:     {path} (PNG, 32x48)\n"
            "Result:   KLING LABEL FOUND (AI-generated)\n"
            'Where:    PNG text chunk "AIGC" (China GB 45438-2025 format)\n'
            "  Label             1  (= AI-generated)\n"
            "  ContentProducer   kling\n"
            f"  ProduceID         {FAKE_ID}\n"
            "    region SGP · system PROD · made on ai_web\n"
            "    made at 2026-01-10 07:01:59 UTC (decoded from ID)\n"
            "  ContentPropagator kling\n"
            "Privacy:  this ID reveals when the image was made.\n"
        ))

    def test_no_label(self):
        path = self.write("plain.png", fakes.png_bytes())
        code, out, _ = run(path)
        self.assertEqual(code, 1)
        self.assertIn("Result:   NO KLING LABEL FOUND. The file may still be AI-made; "
                      "screenshots, re-saves and chat apps remove this label.", out)
        self.assertNotIn("Privacy", out)

    def test_uscc_producer(self):
        path = self.write("a.png", fakes.kling_png(producer=FAKE_USCC_PRODUCER))
        _, out, _ = run(path)
        self.assertIn(f"  ContentProducer   {FAKE_USCC_PRODUCER}\n"
                      "    0011 · USCC 91110108335469089C (check digit valid) · 10100\n", out)

    def test_video_privacy_line_and_extra_fields(self):
        path = self.write("v.mp4", fakes.kling_mp4(propagate_id="SGP_PROD_ai_web_300000009000001",
                                                   reserved1="abc"))
        code, out, _ = run(path)
        self.assertEqual(code, 0)
        self.assertIn("(MP4, 1280x720)", out)
        self.assertIn("  PropagateID       SGP_PROD_ai_web_300000009000001\n", out)
        self.assertIn("  ReservedCode1     abc\n", out)
        self.assertNotIn("ReservedCode2", out)
        self.assertIn("this ID reveals when the video was made.", out)

    def test_other_label_value(self):
        path = self.write("a.png", fakes.kling_png(label="2"))
        _, out, _ = run(path)
        self.assertIn("Result:   KLING LABEL FOUND (Label = 2)", out)
        self.assertIn("  Label             2  (other value; see GB 45438-2025)", out)

    def test_not_kling(self):
        path = self.write("a.png", fakes.kling_png(producer="someone", produce_id="abc"))
        code, out, _ = run(path)
        self.assertEqual(code, 0)
        self.assertIn("Result:   AI LABEL FOUND (GB 45438-2025, producer is not Kling)", out)
        self.assertIn("  ProduceID         abc\n  ContentPropagator", out)

    def test_unreadable_label(self):
        path = self.write("a.png", fakes.png_bytes(before_idat=[fakes.text_chunk("AIGC", "garbage")]))
        code, out, _ = run(path)
        self.assertEqual(code, 0)
        self.assertIn("AIGC LABEL FOUND, BUT ITS CONTENT COULD NOT BE READ", out)
        self.assertIn("  Raw:              garbage", out)

    def test_control_characters_are_escaped(self):
        path = self.write("a.png", fakes.kling_png(producer="evil\x1b[2Jname"))
        _, out, _ = run(path)
        self.assertNotIn("\x1b", out)
        self.assertIn("evil\\x1b[2Jname", out)

    def test_jpeg_note(self):
        path = self.write("a.jpg", fakes.jpeg_bytes())
        code, out, _ = run(path)
        self.assertEqual(code, 1)
        self.assertIn(f"File:     {path} (JPEG)", out)
        self.assertIn("Note:     JPEG files have no full parser yet; only a raw byte scan was done.", out)

    def test_several_files_and_exit_codes(self):
        a = self.write("a.png", fakes.kling_png())
        b = self.write("b.mp4", fakes.kling_mp4())
        c = self.write("c.png", fakes.png_bytes())
        missing = os.path.join(self.tmp.name, "missing.png")
        code, out, _ = run(a, b)
        self.assertEqual(code, 0)
        self.assertEqual(out.count("File:"), 2)
        self.assertIn("was made.\n\nFile:", out)
        self.assertEqual(run(a, c)[0], 1)
        code, out, _ = run(a, c, missing)
        self.assertEqual(code, 2)
        self.assertIn("Result:   ERROR: No such file or directory", out)

    def test_json(self):
        a = self.write("a.png", fakes.kling_png())
        c = self.write("c.png", fakes.png_bytes())
        code, out, _ = run("--json", a, c)
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual([d["result"] for d in data], ["kling_label", "no_label"])
        first = data[0]
        self.assertEqual(first["file"], a)
        self.assertEqual(first["format"], "PNG")
        self.assertEqual(first["found_by"], "png_text_chunk")
        self.assertEqual(first["label"], json.loads(aigc_json()))
        self.assertEqual(first["decoded"]["produce_id"]["created_utc"], "2026-01-10T07:01:59Z")
        self.assertEqual(first["decoded"]["producer"], {"form": "kling"})
        self.assertIsNone(first["error"])

    def test_no_arguments(self):
        code, _, err = run()
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
