"""Targeted invisible-watermark tests for Kling outputs (detection only).

Used by forensics/audit.py (commands qim, decoders, video, controls) and by
forensics/test_wmhunt.py. Every detector here has a positive control that runs on
synthetic images made in code, so a negative result on real samples can be trusted
only as far as the matching control passed.

Nothing here removes, forges or alters a watermark in a real file. Watermarks are
embedded only into synthetic images, only with the open libraries themselves
(invisible-watermark, blind-watermark, RivaGAN, VideoSeal, or ONNX models the owner
supplies), and only to prove that a detector works. No command prints a decoded
message from a real file; only scores and bit-agreement statistics are reported.

Dependencies: numpy, opencv-python-headless, PyWavelets, onnxruntime; optional:
invisible-watermark and blind-watermark (positive controls), torch + videoseal.
"""

import importlib.util
import os

import cv2
import numpy as np
import pywt


class Unavailable(Exception):
    """A detector or control cannot run here (missing package or weights)."""


# ---------------------------------------------------------------- synthetic fixtures
def synthetic_image(seed, h=768, w=640):
    """A textured RGB image (1/f colour noise plus fine grain), uint8. Made-up content only."""
    rng = np.random.default_rng(seed)
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.fftfreq(w)[None, :]
    f = np.sqrt(fy ** 2 + fx ** 2); f[0, 0] = 1
    img = np.zeros((h, w, 3))
    for c in range(3):
        x = np.real(np.fft.ifft2((rng.normal(size=(h, w)) + 1j * rng.normal(size=(h, w))) / f ** 1.1))
        img[..., c] = (x - x.mean()) / x.std()
    return np.clip(128 + 40 * img + rng.normal(0, 3, img.shape), 0, 255).astype(np.uint8)


def synthetic_frames(seed, n=24, h=360, w=640):
    """A short synthetic clip: a textured image drifting by one pixel per frame."""
    base = synthetic_image(seed, h + n, w + n)
    return [base[i:i + h, i:i + w].copy() for i in range(n)]


def load_rgb(path):
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGB"))


def jpeg_roundtrip(rgb, quality):
    ok, buf = cv2.imencode(".jpg", rgb[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, quality])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)[..., ::-1]


# ---------------------------------------------------------------- QIM lattice scan
# Classic "blind" watermarks (DWT-DCT-SVD family: invisible-watermark dwtDct/dwtDctSvd,
# guofei9987/blind_watermark and most textbook 盲水印 schemes) move one transform value x
# per block onto a lattice: x = (n + 1/4 + bit/2) * d. Whatever the bits, 2x mod d then
# sits at d/2, so exp(4*pi*i*x/d) points the same way in every block. That needs no key
# and no message. A narrow peak over d (high contrast against nearby d) is the signature;
# smooth or flat content gives broad, low-contrast structure instead.
STEPS = np.exp(np.arange(np.log(2.5), np.log(120), 0.004))
QIM_FLAG_SCORE, QIM_MIN_CONTRAST = 50.0, 8.0
# Values that sit on an integer grid (e.g. chroma upsampled from 4:2:0, so each 2x2 block of
# U or V is equal) light up at steps 2*delta/j. Peaks within 1.2% of these steps are ignored;
# a watermark with exactly one of these steps would be missed.
INTEGER_STEPS = (8 / 3, 4.0, 16 / 3, 8.0, 16.0, 32.0)
_STEP_OK = np.all([np.abs(np.log(STEPS / d)) > 0.012 for d in INTEGER_STEPS], axis=0)


def _blocks(a, b):
    h, w = a.shape[0] // b * b, a.shape[1] // b * b
    return a[:h, :w].reshape(h // b, b, w // b, b).transpose(0, 2, 1, 3).reshape(-1, b, b)


def _dct_matrix(n):
    k = np.arange(n)[:, None]; m = np.arange(n)[None, :]
    c = np.sqrt(2 / n) * np.cos(np.pi * (2 * m + 1) * k / (2 * n)); c[0] /= np.sqrt(2)
    return c


C4, C8 = _dct_matrix(4), _dct_matrix(8)


def qim_features(rgb, levels=(1, 2), max_blocks=12000, seed=0):
    """Per-block values that common blind schemes quantize, for each colour plane and DWT level.

    Two YUV conversions are used because libraries differ: float input (offset 0.5, as in
    blind_watermark) and uint8 input (offset 128, rounded, as in invisible-watermark).
    Level 2 is the DWT of the level-1 LL band, i.e. the image at half size, which matches
    a mark embedded before Kling's 2x upscale. Only textured blocks are kept."""
    bgr = np.ascontiguousarray(rgb[..., ::-1])
    rng = np.random.default_rng(seed)
    planes = {"f32": cv2.cvtColor(bgr.astype(np.float32), cv2.COLOR_BGR2YUV),
              "u8": cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV).astype(np.float32)}
    channels = "Y" if chroma_subsampled(planes["u8"]) else "YUV"
    out = {}
    for var, yuv in planes.items():
        for c, cname in enumerate(channels):
            ll = yuv[..., c]
            for level in range(1, max(levels) + 1):
                ll = pywt.dwt2(ll, "haar")[0]
                if level not in levels:
                    continue
                B = _blocks(ll, 4)
                if len(B) < 256:
                    continue
                flat = B.reshape(len(B), -1)
                keep = np.flatnonzero(flat.std(1) > 1.0)
                if len(keep) < 256:
                    continue
                keep = rng.choice(keep, min(max_blocks, len(keep)), replace=False)
                B, flat = B[keep], flat[keep]
                s = np.linalg.svd(C4 @ B @ C4.T, compute_uv=False)
                idx = np.abs(flat[:, 1:]).argmax(1) + 1
                key = f"L{level}/{var}/{cname}"
                out[key + "/svd0"] = s[:, 0]
                out[key + "/svd1"] = s[:, 1]
                out[key + "/maxabs"] = np.abs(flat[np.arange(len(flat)), idx])
    return out


def chroma_subsampled(yuv_u8):
    """True when U or V repeats each value over 2x2 blocks, as in frames decoded from 4:2:0 video.
    Such planes sit on a scaled integer grid that mimics a lattice, so only Y is scanned."""
    h, w = yuv_u8.shape[0] // 2 * 2, yuv_u8.shape[1] // 2 * 2
    b = yuv_u8[:h, :w, 1:].reshape(h // 2, 2, w // 2, 2, 2)
    return bool((np.mean(b.max((1, 3)) - b.min((1, 3)) <= 1, axis=(0, 1)) >= 0.8).any())


def jpeg_feature(rgb, max_blocks=12000, seed=0):
    """8x8 pixel-block DCT coefficient (0,1) of luma. JPEG quantizes it on a lattice, so a
    peak here means the file was JPEG-compressed at some point, not that it is watermarked."""
    y = cv2.cvtColor(np.ascontiguousarray(rgb[..., ::-1]), cv2.COLOR_BGR2YUV)[..., 0].astype(np.float32)
    B = _blocks(y, 8)
    coef = (C8 @ B @ C8.T)[:, 0, 1]
    coef = coef[np.abs(coef) > 1.0]
    rng = np.random.default_rng(seed)
    return np.abs(rng.choice(coef, min(max_blocks, len(coef)), replace=False)) if len(coef) else coef


def lattice_scan(x):
    """Return (Z, contrast) over STEPS. Z = N*R^2 is the Rayleigh statistic of the doubled
    lattice phase (about 1 for random values); contrast compares Z with nearby steps."""
    if len(x) < 64:
        return np.zeros(len(STEPS)), np.zeros(len(STEPS))
    Z = np.empty(len(STEPS))
    for i in range(0, len(STEPS), 64):
        Z[i:i + 64] = np.abs(np.exp(4j * np.pi * x[None, :] / STEPS[i:i + 64, None]).mean(1)) ** 2 * len(x)
    logd = np.log(STEPS)
    contrast = np.empty(len(STEPS))
    for i in range(len(STEPS)):
        dist = np.abs(logd - logd[i])
        contrast[i] = Z[i] / (np.median(Z[(dist < 0.03) & (dist > 0.006)]) + 1.0)
    return Z, contrast


def _peak(x):
    Z, con = lattice_scan(x)
    interior = (STEPS > STEPS[0] * 1.03) & (STEPS < STEPS[-1] / 1.03)  # contrast needs neighbours on both sides
    # a QIM mark spreads values over many lattice cells; with only a few cells, a handful of
    # distinct values (flat colour planes) can line up by chance
    spread = np.subtract(*np.percentile(x, [95, 5])) if len(x) else 0.0
    ok = (con >= QIM_MIN_CONTRAST) & interior & _STEP_OK & (STEPS <= spread / 6)
    if not ok.any():
        return 0.0, None, 0.0
    i = np.flatnonzero(ok)[Z[ok].argmax()]
    # report the largest strong step: lattices also light up at d/2, d/3, ...
    strong = np.flatnonzero(ok & (Z >= 0.5 * Z[i]))
    j = strong.max()
    return float(Z[i]), float(STEPS[j]), float(con[i])


def qim_report(rgb, levels=(1, 2)):
    """Strongest narrow lattice peak over all features.

    flag is True when score >= QIM_FLAG_SCORE and the file shows no JPEG history. A JPEG
    (quality about 90 or lower) puts its own lattice on the same block values, so for such
    files the scan cannot tell a watermark from compression and jpeg_history is set instead."""
    best = {"score": 0.0, "feature": None, "step": None, "contrast": 0.0}
    for name, x in qim_features(rgb, levels).items():
        score, step, con = _peak(x)
        if score > best["score"]:
            best = {"score": score, "feature": name, "step": step, "contrast": con}
    best["jpeg_history_score"] = _peak(jpeg_feature(rgb))[0]
    best["chroma_subsampled"] = chroma_subsampled(cv2.cvtColor(np.ascontiguousarray(rgb[..., ::-1]), cv2.COLOR_BGR2YUV))
    best["jpeg_history"] = best["jpeg_history_score"] >= QIM_FLAG_SCORE
    best["flag"] = best["score"] >= QIM_FLAG_SCORE and not best["jpeg_history"]
    return best


# ---------------------------------------------------------------- open-library embedders (positive controls only)
def _imwatermark_dir():
    spec = importlib.util.find_spec("imwatermark")  # finds the package without importing it (it imports torch)
    if spec is None or not spec.submodule_search_locations:
        raise Unavailable("pip install invisible-watermark")
    return list(spec.submodule_search_locations)[0]


def _load_file_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def embed_imwatermark(rgb, bits, method="dwtDctSvd", scale=36):
    """invisible-watermark's key-free DWT-DCT (dwtDct) or DWT-DCT-SVD (dwtDctSvd) scheme, U channel."""
    d = _imwatermark_dir()
    if method == "dwtDct":
        cls = _load_file_module("_imwm_maxdct", os.path.join(d, "maxDct.py")).EmbedMaxDct
    else:
        cls = _load_file_module("_imwm_dwtdctsvd", os.path.join(d, "dwtDctSvd.py")).EmbedDwtDctSvd
    bgr = cls(list(bits), wmLen=len(bits), scales=[0, scale, 0]).encode(np.ascontiguousarray(rgb[..., ::-1]))
    return bgr[..., ::-1]


def embed_blind_watermark(rgb, bits, password_img=1):
    """guofei9987/blind_watermark in its default (keyed, shuffled) mode."""
    try:
        from blind_watermark.bwm_core import WaterMarkCore
    except ImportError as e:
        raise Unavailable("pip install blind-watermark") from e
    core = WaterMarkCore(password_img=password_img, mode="common")
    core.read_img_arr(np.ascontiguousarray(rgb[..., ::-1]).astype(np.float32))
    core.read_wm(np.asarray(bits))
    return np.clip(np.round(core.embed()), 0, 255).astype(np.uint8)[..., ::-1]


# ---------------------------------------------------------------- neural decoders
class BitModel:
    """Common interface: decode(rgb) -> raw per-bit scores (logits, probabilities or any
    monotonic score); embed(rgb, bits) -> rgb. Scores are only compared after centering on a
    reference set, because decoders have strong per-bit biases on unmarked images."""
    name, nbits = "?", 0

    def decode(self, rgb):
        raise NotImplementedError

    def embed(self, rgb, bits):
        raise NotImplementedError


class RivaGan(BitModel):
    """RivaGAN (32 bits), using the ONNX models shipped inside the invisible-watermark package.
    Runs with onnxruntime and numpy only (no torch)."""
    name, nbits = "RivaGAN", 32

    def __init__(self):
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise Unavailable("pip install onnxruntime") from e
        d = _imwatermark_dir()
        self.enc = ort.InferenceSession(os.path.join(d, "rivagan_encoder.onnx"))
        self.dec = ort.InferenceSession(os.path.join(d, "rivagan_decoder.onnx"))

    @staticmethod
    def _frame(rgb):  # invisible-watermark feeds BGR frames scaled to [-1, 1], shape 1x3x1xHxW
        return (rgb[..., ::-1].astype(np.float32) / 127.5 - 1.0).transpose(2, 0, 1)[None, :, None]

    def decode(self, rgb):
        return self.dec.run(None, {"frame": self._frame(rgb)})[0][0]

    def embed(self, rgb, bits):
        out = self.enc.run(None, {"frame": self._frame(rgb), "data": np.asarray([bits], np.float32)})[0]
        bgr = (np.clip(out[0, :, 0].transpose(1, 2, 0), -1, 1) + 1.0) * 127.5
        return bgr.astype(np.uint8)[..., ::-1]


class OnnxBitModel(BitModel):
    """Generic encoder/decoder pair exported to ONNX, e.g. StegaStamp (100 bits, 400x400,
    pixels in [0,1]) or HiDDeN (30 bits, 128x128, pixels in [-1,1]).

    Inputs and outputs are matched by shape: the image input is the 4-D one (NCHW or NHWC),
    the message is the 2-D one. Images are resized to the model's fixed size if it has one.
    The decoder output may be probabilities or logits; both work after centering."""

    def __init__(self, name, encoder_path, decoder_path, pixel_range=(0.0, 1.0)):
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise Unavailable("pip install onnxruntime") from e
        for p in (encoder_path, decoder_path):
            if not p or not os.path.isfile(p):
                raise Unavailable(f"{name}: ONNX file not found ({p or 'path not set'})")
        self.name, self.lo, self.hi = name, pixel_range[0], pixel_range[1]
        self.enc = ort.InferenceSession(encoder_path)
        self.dec = ort.InferenceSession(decoder_path)
        ins = self.enc.get_inputs()
        self.enc_img = next(i for i in ins if len(i.shape) == 4)
        self.enc_msg = next(i for i in ins if len(i.shape) == 2)
        self.dec_img = next(i for i in self.dec.get_inputs() if len(i.shape) == 4)
        self.nbits = int(self.enc_msg.shape[1])

    @staticmethod
    def _layout(shape):
        nchw = shape[1] == 3
        hw = shape[2:4] if nchw else shape[1:3]
        size = tuple(int(v) for v in hw) if all(isinstance(v, int) for v in hw) else None
        return nchw, size

    def _to_input(self, rgb, spec):
        nchw, size = self._layout(spec.shape)
        x = rgb if size is None else cv2.resize(rgb, (size[1], size[0]), interpolation=cv2.INTER_AREA)
        x = x.astype(np.float32) / 255.0 * (self.hi - self.lo) + self.lo
        return (x.transpose(2, 0, 1) if nchw else x)[None]

    def decode(self, rgb):
        outs = self.dec.run(None, {self.dec_img.name: self._to_input(rgb, self.dec_img)})
        return next(o for o in outs if o.ndim == 2 and o.shape[1] == self.nbits)[0].astype(np.float64)

    def embed(self, rgb, bits):
        feed = {self.enc_img.name: self._to_input(rgb, self.enc_img),
                self.enc_msg.name: np.asarray([bits], np.float32)}
        out = next(o for o in self.enc.run(None, feed) if o.ndim == 4)[0]
        nchw, size = self._layout(self.enc_img.shape)
        out = out.transpose(1, 2, 0) if nchw else out
        out = np.clip((out - self.lo) / (self.hi - self.lo) * 255.0, 0, 255).astype(np.uint8)
        return out if size is None else cv2.resize(out, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_CUBIC)


def stegastamp():
    return OnnxBitModel("StegaStamp", os.environ.get("STEGASTAMP_ENCODER"), os.environ.get("STEGASTAMP_DECODER"), (0.0, 1.0))


def hidden():
    return OnnxBitModel("HiDDeN", os.environ.get("HIDDEN_ENCODER"), os.environ.get("HIDDEN_DECODER"), (-1.0, 1.0))


class VideoSeal:
    """Meta VideoSeal 1.0 (256 bits) through the videoseal package. Needs torch and downloads its
    weights on first use, so it does not run in a sandbox without network access."""
    name = "VideoSeal"

    def __init__(self):
        try:
            import torch
            import videoseal
        except ImportError as e:
            raise Unavailable("pip install torch videoseal") from e
        from pathlib import Path
        card = Path(videoseal.__file__).parent / "cards" / "videoseal_1.0.yaml"
        try:
            self.model = videoseal.load(card).eval()
        except Exception as e:  # usually the weight download
            raise Unavailable(f"VideoSeal weights could not be loaded: {e}") from e
        self.torch = torch
        self.nbits = int(self.model.get_random_msg().shape[-1])

    def _tensor(self, frames):
        return self.torch.from_numpy(np.stack(frames)).permute(0, 3, 1, 2).float() / 255.0

    def decode_frames(self, frames):
        """Per-bit logits for a clip (average over frames) and the mean detection-bit logit."""
        preds = self.model.detect(self._tensor(frames), is_video=True)["preds"]
        preds = preds.reshape(preds.shape[0], preds.shape[1], -1).mean(-1)
        return preds[:, 1:].mean(0).numpy().astype(np.float64), float(preds[:, 0].mean())

    def embed_frames(self, frames, bits):
        msg = self.torch.tensor([bits], dtype=self.torch.float32)
        out = self.model.embed(self._tensor(frames), msgs=msg, is_video=True)["imgs_w"]
        return [(f.permute(1, 2, 0).numpy() * 255).round().clip(0, 255).astype(np.uint8) for f in out]


def decoder_stats(scores, ref_scores):
    """Key-agnostic test for "one fixed message in every file" against a reference set.

    Bits are read as score > reference mean (this removes the decoder's own per-bit bias).
    agreement: mean pairwise share of equal bits (0.5 = unrelated, near 1 = same message).
    T: mean over bits of the squared two-sample t statistic (about 1 when the group and the
    reference come from the same distribution; large when the group shares a message)."""
    S, R = np.asarray(scores, np.float64), np.asarray(ref_scores, np.float64)
    if len(S) < 2 or len(R) < 2:
        return {"n": len(S), "agreement": float("nan"), "T": float("nan")}
    B = S - R.mean(0) > 0
    agree = [np.mean(B[i] == B[j]) for i in range(len(B)) for j in range(i + 1, len(B))]
    t = (S.mean(0) - R.mean(0)) / np.sqrt(S.var(0, ddof=1) / len(S) + R.var(0, ddof=1) / len(R) + 1e-12)
    return {"n": len(S), "agreement": float(np.mean(agree)), "T": float(np.mean(t ** 2))}


def null_split(ref_scores, seed=0):
    """decoder_stats on a random half of the reference against the other half: the null value."""
    R = np.asarray(ref_scores, np.float64)
    idx = np.random.default_rng(seed).permutation(len(R))
    return decoder_stats(R[idx[: len(R) // 2]], R[idx[len(R) // 2:]])


def bit_accuracy(scores, bits, ref_scores):
    """Share of bits read correctly, after centering on the reference mean."""
    return float(np.mean((np.asarray(scores) - np.mean(ref_scores, 0) > 0) == (np.asarray(bits) > 0.5)))


# ---------------------------------------------------------------- video
def read_frames(path, max_frames=32):
    """Up to max_frames RGB frames spread evenly over the clip."""
    cap = cv2.VideoCapture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not 0 < n < 10 ** 7:  # unknown or nonsense count (e.g. a still image): take the first frames
        n = max_frames
    want = set(np.linspace(0, n - 1, min(n, max_frames)).astype(int).tolist())
    frames, i = [], 0
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        if i in want:
            frames.append(bgr[..., ::-1].copy())
        i += 1
    cap.release()
    return frames


def write_video(path, frames, fourcc, fps=24):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*fourcc), fps, (w, h))
    if not vw.isOpened():
        raise Unavailable(f"OpenCV cannot write {fourcc} video here")
    for f in frames:
        vw.write(np.ascontiguousarray(f[..., ::-1]))
    vw.release()


# ---------------------------------------------------------------- positive controls
def control_qim(n=2, size=(512, 512)):
    """The QIM scan must stay quiet on clean synthetic images and flag every open blind scheme,
    including one embedded at half size and then upscaled 2x (Kling's 2K pipeline)."""
    rows, rng = [], np.random.default_rng(7)
    h, w = size
    cases = [("clean", lambda im: im, False)]
    for method, scale in (("dwtDct", 36), ("dwtDctSvd", 36), ("dwtDctSvd", 12)):
        cases.append((f"invisible-watermark {method} scale {scale}",
                      lambda im, m=method, s=scale: embed_imwatermark(im, rng.integers(0, 2, 32), m, s), True))
    cases.append(("blind_watermark default (keyed)", lambda im: embed_blind_watermark(im, rng.integers(0, 2, 64)), True))
    cases.append(("dwtDctSvd at half size, then 2x upscale",
                  lambda im: cv2.resize(embed_imwatermark(cv2.resize(im, (w // 2, h // 2), interpolation=cv2.INTER_AREA),
                                                          rng.integers(0, 2, 32), "dwtDctSvd", 36),
                                        (w, h), interpolation=cv2.INTER_CUBIC), None))
    cases.append(("dwtDctSvd scale 36, then JPEG q90", lambda im: jpeg_roundtrip(
        embed_imwatermark(im, rng.integers(0, 2, 32), "dwtDctSvd", 36), 90), None))
    cases.append(("clean, JPEG q75 (lattice blamed on JPEG)", lambda im: jpeg_roundtrip(im, 75), False))
    for label, fn, expect in cases:
        try:
            reps = [qim_report(fn(synthetic_image(1000 + i, h, w))) for i in range(n)]
        except Unavailable as e:
            rows.append({"control": label, "status": "SKIPPED", "detail": str(e)}); continue
        flags = [r["flag"] for r in reps]
        if expect is None:
            status = "INFO"
        else:
            status = "PASS" if all(f == expect for f in flags) else "FAIL"
        top = max(reps, key=lambda r: r["score"])
        rows.append({"control": label, "status": status, "flagged": f"{sum(flags)}/{n}",
                     "detail": (f"score {top['score']:.0f}, step {top['step'] or 0:.1f}, {top['feature']}, "
                                f"JPEG-history score {top['jpeg_history_score']:.0f}")})
    return rows


def control_decoder(model, n=6, size=(512, 512)):
    """Embed one fixed random message into n synthetic images. Read against a separate clean
    reference set, the decoder must recover the message (mean bit accuracy >= 0.9) and the
    group test must fire (T >= 4), while n other clean images must not (T < 4)."""
    rng = np.random.default_rng(11)
    msg = rng.integers(0, 2, model.nbits)
    ref = [model.decode(synthetic_image(3000 + i, *size)) for i in range(n)]
    clean = [synthetic_image(2000 + i, *size) for i in range(n)]
    marked = [model.embed(im, msg) for im in clean]
    s_marked = [model.decode(im) for im in marked]
    s_clean = [model.decode(im) for im in clean]
    s_jpeg = [model.decode(jpeg_roundtrip(im, 90)) for im in marked]
    acc = np.mean([bit_accuracy(s, msg, ref) for s in s_marked])
    acc_jpeg = np.mean([bit_accuracy(s, msg, ref) for s in s_jpeg])
    sm, sc = decoder_stats(s_marked, ref), decoder_stats(s_clean, ref)
    psnr = np.mean([10 * np.log10(255 ** 2 / max(np.mean((a.astype(float) - b) ** 2), 1e-9)) for a, b in zip(marked, clean)])
    ok = acc >= 0.9 and sm["T"] >= 4 and sc["T"] < 4
    return {"control": f"{model.name} embed/decode", "status": "PASS" if ok else "FAIL",
            "detail": (f"bit accuracy {acc:.2f} (after JPEG q90 {acc_jpeg:.2f}); "
                       f"marked: agreement {sm['agreement']:.2f}, T {sm['T']:.1f}; "
                       f"clean: agreement {sc['agreement']:.2f}, T {sc['T']:.1f}; PSNR {psnr:.1f} dB")}


def control_video_pipeline(tmpdir, n_frames=24):
    """Synthetic clip -> RivaGAN on every frame -> lossless (FFV1) and lossy (mp4v) files ->
    read back -> decode. Proves the frame reader and per-frame decoding work on video files."""
    model = RivaGan()
    rng = np.random.default_rng(13)
    msg = rng.integers(0, 2, model.nbits)
    clean = synthetic_frames(21, n_frames)
    frames = [model.embed(f, msg) for f in clean]
    ref = [model.decode(f) for f in clean[::3]]  # unmarked frames play the role of control videos
    out = []
    for label, name, fourcc in (("lossless FFV1", "ctl.avi", "FFV1"), ("lossy mp4v", "ctl.mp4", "mp4v")):
        path = os.path.join(tmpdir, name)
        try:
            write_video(path, frames, fourcc)
        except Unavailable as e:
            out.append({"control": f"video RivaGAN {label}", "status": "SKIPPED", "detail": str(e)}); continue
        back = read_frames(path, 8)
        acc = bit_accuracy(np.mean([model.decode(f) for f in back], 0), msg, ref) if back else 0.0
        status = ("PASS" if acc >= 0.9 else "FAIL") if fourcc == "FFV1" else "INFO"
        out.append({"control": f"video RivaGAN {label}", "status": status,
                    "detail": f"{len(back)} frames read, bit accuracy {acc:.2f}"})
    return out


def control_video_qim_h264(tmpdir, n_frames=12):
    """Clean and blind_watermark-marked synthetic frames through H.264 (needs the ffmpeg binary).
    A clip counts as flagged when any of 3 scanned frames is: the clean clip must not be, the
    marked clip at crf 18 must be; crf 28 (typical streaming quality) is reported only."""
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        raise Unavailable("ffmpeg binary not found")
    from PIL import Image
    bits = np.random.default_rng(19).integers(0, 2, 64)
    clean = synthetic_frames(41, n_frames, 720, 1280)
    rows = []
    for label, frames, crf, expect in (("clean", clean, 18, False),
                                       ("blind_watermark", [embed_blind_watermark(f, bits) for f in clean], 18, True),
                                       ("blind_watermark", None, 28, None)):
        frames = frames if frames is not None else [embed_blind_watermark(f, bits) for f in clean]
        src = os.path.join(tmpdir, f"h264_{label}_{crf}")
        os.makedirs(src, exist_ok=True)
        for i, f in enumerate(frames):
            Image.fromarray(f).save(os.path.join(src, f"{i:03d}.png"))
        out = src + ".mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "24", "-i", os.path.join(src, "%03d.png"),
                        "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p", out], check=True)
        reps = [qim_report(f) for f in read_frames(out, 3)]
        flagged = sum(r["flag"] for r in reps)  # a clip counts as flagged when any scanned frame is
        status = "INFO" if expect is None else ("PASS" if (flagged > 0) == expect else "FAIL")
        rows.append({"control": f"QIM on H.264 frames, {label}, crf {crf}", "status": status,
                     "flagged": f"{flagged}/{len(reps)}", "detail": f"max score {max(r['score'] for r in reps):.0f}"})
    return rows


def control_videoseal(n_frames=16):
    model = VideoSeal()
    rng = np.random.default_rng(17)
    msg = rng.integers(0, 2, model.nbits)
    clean = synthetic_frames(31, n_frames, 256, 256)
    marked = model.embed_frames(clean, msg)
    p_m, det_m = model.decode_frames(marked)
    p_c, det_c = model.decode_frames(clean)
    acc = bit_accuracy(p_m, msg, np.zeros((1, model.nbits)))  # VideoSeal logits are centred at 0 by design
    return {"control": "VideoSeal embed/decode", "status": "PASS" if acc >= 0.9 else "FAIL",
            "detail": f"bit accuracy {acc:.2f}; detection logit marked {det_m:+.2f} vs clean {det_c:+.2f}"}


def run_all_controls(tmpdir, quick=False):
    n = 1 if quick else 2
    rows = control_qim(n=n)
    for make in (RivaGan, stegastamp, hidden):
        try:
            rows.append(control_decoder(make(), n=4 if quick else 6))
        except Unavailable as e:
            rows.append({"control": f"{getattr(make, 'name', make.__name__)} embed/decode", "status": "SKIPPED", "detail": str(e)})
    try:
        rows += control_video_pipeline(tmpdir)
    except Unavailable as e:
        rows.append({"control": "video pipeline", "status": "SKIPPED", "detail": str(e)})
    try:
        rows += control_video_qim_h264(tmpdir)
    except Unavailable as e:
        rows.append({"control": "QIM on H.264 frames", "status": "SKIPPED", "detail": str(e)})
    try:
        rows.append(control_videoseal())
    except Unavailable as e:
        rows.append({"control": "VideoSeal embed/decode", "status": "SKIPPED", "detail": str(e)})
    return rows
