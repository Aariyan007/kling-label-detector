"""Tests for forensics/wmhunt.py on synthetic images only (no samples needed).

Run from the repository root:  python -m unittest forensics.test_wmhunt -v
Needs numpy, opencv-python-headless, PyWavelets, onnxruntime; tests that need
invisible-watermark, blind-watermark or onnx are skipped when those are missing.
"""

import importlib.util
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wmhunt  # noqa: E402

HAVE = {m: importlib.util.find_spec(m) is not None for m in ("imwatermark", "blind_watermark", "onnx", "onnxruntime")}


class QimScanTest(unittest.TestCase):
    def test_clean_images_are_not_flagged(self):
        for seed in (1, 2):
            self.assertFalse(wmhunt.qim_report(wmhunt.synthetic_image(seed, 384, 384))["flag"])

    @unittest.skipUnless(HAVE["imwatermark"], "invisible-watermark not installed")
    def test_flags_dwtdctsvd_and_finds_its_step(self):
        bits = np.random.default_rng(0).integers(0, 2, 32)
        r = wmhunt.qim_report(wmhunt.embed_imwatermark(wmhunt.synthetic_image(3, 384, 384), bits, "dwtDctSvd", 36))
        self.assertTrue(r["flag"])
        self.assertIn("/U/svd0", r["feature"])
        self.assertAlmostEqual(36 / r["step"], round(36 / r["step"]), delta=0.05)  # 36 or a subharmonic

    @unittest.skipUnless(HAVE["blind_watermark"], "blind-watermark not installed")
    def test_flags_keyed_blind_watermark_without_the_key(self):
        bits = np.random.default_rng(0).integers(0, 2, 64)
        r = wmhunt.qim_report(wmhunt.embed_blind_watermark(wmhunt.synthetic_image(4, 384, 384), bits, password_img=12345))
        self.assertTrue(r["flag"])

    def test_jpeg_lattice_is_not_reported_as_a_watermark(self):
        r = wmhunt.qim_report(wmhunt.jpeg_roundtrip(wmhunt.synthetic_image(5, 384, 384), 75))
        self.assertTrue(r["jpeg_history"])
        self.assertFalse(r["flag"])

    def test_chroma_subsampling_guard(self):
        yuv = np.random.default_rng(0).integers(0, 256, (64, 64, 3)).astype(np.uint8)
        self.assertFalse(wmhunt.chroma_subsampled(yuv))
        yuv[..., 1:] = np.repeat(np.repeat(yuv[::2, ::2, 1:], 2, 0), 2, 1)
        self.assertTrue(wmhunt.chroma_subsampled(yuv))


class DecoderStatsTest(unittest.TestCase):
    def test_null_and_fixed_message(self):
        rng = np.random.default_rng(0)
        ref = rng.normal(size=(20, 32))
        null = wmhunt.decoder_stats(rng.normal(size=(20, 32)), ref)
        self.assertLess(null["T"], 2.5)
        self.assertAlmostEqual(null["agreement"], 0.5, delta=0.1)
        shift = np.where(rng.integers(0, 2, 32) > 0, 1.5, -1.5)
        marked = wmhunt.decoder_stats(rng.normal(size=(20, 32)) + shift, ref)
        self.assertGreater(marked["T"], 10)
        self.assertGreater(marked["agreement"], 0.8)

    @unittest.skipUnless(HAVE["imwatermark"] and HAVE["onnxruntime"], "invisible-watermark/onnxruntime missing")
    def test_rivagan_positive_control(self):
        r = wmhunt.control_decoder(wmhunt.RivaGan())  # same settings as "audit.py controls"
        self.assertEqual(r["status"], "PASS", r["detail"])


def _toy_onnx_pair(tmp, nbits=8, size=32):
    """A linear encoder/decoder in ONNX, only to test the generic adapter (not a real detector)."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper
    P = np.random.default_rng(1).choice([-1.0, 1.0], (nbits, 3 * size * size)).astype(np.float32)
    shape = numpy_helper.from_array(np.array([1, 3, size, size], np.int64), "shape")
    flat = numpy_helper.from_array(np.array([1, 3 * size * size], np.int64), "flat")
    enc = helper.make_graph(
        [helper.make_node("Mul", ["msg", "two"], ["m2"]), helper.make_node("Sub", ["m2", "one"], ["pm"]),
         helper.make_node("MatMul", ["pm", "P"], ["pat"]), helper.make_node("Reshape", ["pat", "shape"], ["pat4"]),
         helper.make_node("Mul", ["pat4", "amp"], ["d"]), helper.make_node("Add", ["image", "d"], ["encoded"])],
        "enc", [helper.make_tensor_value_info("image", TensorProto.FLOAT, [1, 3, size, size]),
                helper.make_tensor_value_info("msg", TensorProto.FLOAT, [1, nbits])],
        [helper.make_tensor_value_info("encoded", TensorProto.FLOAT, [1, 3, size, size])],
        [numpy_helper.from_array(P, "P"), shape, numpy_helper.from_array(np.float32(2), "two"),
         numpy_helper.from_array(np.float32(1), "one"), numpy_helper.from_array(np.float32(0.08), "amp")])
    dec = helper.make_graph(
        [helper.make_node("Reshape", ["image", "flat"], ["x"]), helper.make_node("Sub", ["x", "half"], ["xc"]),
         helper.make_node("MatMul", ["xc", "PT"], ["bits"])],
        "dec", [helper.make_tensor_value_info("image", TensorProto.FLOAT, [1, 3, size, size])],
        [helper.make_tensor_value_info("bits", TensorProto.FLOAT, [1, nbits])],
        [numpy_helper.from_array(P.T.copy(), "PT"), flat, numpy_helper.from_array(np.float32(0.5), "half")])
    paths = []
    for name, g in (("enc.onnx", enc), ("dec.onnx", dec)):
        m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)]); m.ir_version = 8
        onnx.save(m, os.path.join(tmp, name)); paths.append(os.path.join(tmp, name))
    return paths


class OnnxAdapterTest(unittest.TestCase):
    @unittest.skipUnless(HAVE["onnx"] and HAVE["onnxruntime"], "onnx/onnxruntime missing")
    def test_generic_adapter_with_toy_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            enc, dec = _toy_onnx_pair(tmp)
            model = wmhunt.OnnxBitModel("toy", enc, dec, (0.0, 1.0))
            self.assertEqual(model.nbits, 8)
            r = wmhunt.control_decoder(model, n=4, size=(64, 64))
            self.assertEqual(r["status"], "PASS", r["detail"])

    def test_missing_weights_are_reported_not_faked(self):
        with self.assertRaises(wmhunt.Unavailable):
            wmhunt.OnnxBitModel("StegaStamp", "/nonexistent/enc.onnx", "/nonexistent/dec.onnx")


class VideoTest(unittest.TestCase):
    def test_lossless_roundtrip_and_still_image_input(self):
        frames = wmhunt.synthetic_frames(3, 6, 64, 96)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "clip.avi")
            try:
                wmhunt.write_video(path, frames, "FFV1")
            except wmhunt.Unavailable as e:
                self.skipTest(str(e))
            back = wmhunt.read_frames(path, 32)
            self.assertEqual(len(back), 6)
            self.assertTrue(np.array_equal(back[0], frames[0]))
            png = os.path.join(tmp, "still.png")
            import cv2
            cv2.imwrite(png, frames[0][..., ::-1])
            self.assertLessEqual(len(wmhunt.read_frames(png, 4)), 4)  # must not crash on a still image


if __name__ == "__main__":
    unittest.main()
