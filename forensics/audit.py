"""Forensic audit of Kling outputs (detection only; prints no ProduceIDs).

Usage (from the repository root, with Pillow, NumPy and SciPy installed):
    python forensics/audit.py container   # PNG/MP4 structure, colour chunks, encoder fingerprint, SEI
    python forensics/audit.py steg        # bit planes, chi-square LSB test, channel relations, entropy
    python forensics/audit.py dct         # 8x8 block-DCT coefficient bias test on plain images
    python forensics/audit.py wavelet     # Haar subband split-half test on plain images
    python forensics/audit.py robust      # does the shared plain-image signal survive common transforms?
    python forensics/audit.py residual    # flatness, leave-one-out, averaged-residual energy, split-half
    python forensics/audit.py bands       # shared signal by spatial-frequency band (shading, 32 px grid)
    python forensics/audit.py grid        # 32 px grid strength in single images, Kling vs controls
    python forensics/audit.py texture     # fixed pattern in textured regions only, with and without the grid
    python forensics/audit.py samples     # sample-level CSV with hashes (written to git-ignored samples/)

Targeted watermark hunt (forensics/wmhunt.py; also needs opencv-python-headless, PyWavelets,
onnxruntime and invisible-watermark; see docs/watermark-hunt-plan.md):
    python forensics/audit.py controls    # positive controls on synthetic images (run first)
    python forensics/audit.py qim         # key-free QIM lattice scan (DWT-DCT-SVD "blind watermark" family)
    python forensics/audit.py decoders    # RivaGAN / StegaStamp / HiDDeN, fixed-message test vs controls
    python forensics/audit.py video       # VideoSeal, RivaGAN and QIM on video frames
Options for qim, decoders and video: --kling GLOB, --control GLOB (repeatable), --limit N.
These commands print scores and indices only: no file names, IDs or decoded messages.

Sample folders are local only (samples/ is git-ignored):
    samples/kling_*.png, samples/round2/*.png   Kling outputs (normal and plain)
    samples/round3/*.png, samples/round4/*.png  plain IMAGE 3.0 outputs
    samples/control/*                           non-Kling images
"""

import glob
import io
import struct
import sys
import zlib

import numpy as np
from PIL import Image
from scipy.fft import dctn
from scipy.ndimage import gaussian_filter
from scipy.stats import chi2

KLING_NORMAL = sorted(glob.glob("samples/kling_*Text_to_Image*.png")) + [
    f"samples/round2/r2_time_{i}.png" for i in (1, 2, 3)]
PLAIN = (sorted(glob.glob("samples/round4/*.png")) + sorted(glob.glob("samples/round3/*.png"))
         + sorted(glob.glob("samples/round2/r2_plain30_*.png")) + sorted(glob.glob("samples/*Exact_copy_808*.png")))
CONTROL_PNG = sorted(f for f in glob.glob("samples/control/*") if f.lower().endswith(".png"))
CONTROL_ALL = sorted(f for f in glob.glob("samples/control/*") if f.lower().endswith((".png", ".jpg", ".jpeg")))
VIDEOS = sorted(glob.glob("samples/round2/*.mp4"))


# ---------------------------------------------------------------- container
def png_chunks(path):
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks = 8, []
    while pos + 12 <= len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        chunks.append((typ.decode("latin1"), data[pos + 8:pos + 8 + n]))
        pos += 12 + n
        if typ == b"IEND":
            break
    return chunks, len(data) - pos


def png_report(path):
    chunks, trailing = png_chunks(path)
    ihdr = chunks[0][1]
    w, h, depth, ctype, comp, filt, inter = struct.unpack(">IIBBBBB", ihdr)
    idat = b"".join(body for t, body in chunks if t == "IDAT")
    raw = zlib.decompress(idat)
    bpp = {2: 3, 6: 4, 0: 1, 4: 2}[ctype] * depth // 8
    stride = w * bpp + 1
    filters = np.bincount(np.frombuffer(raw, np.uint8)[::stride][:h], minlength=5)
    flevel = idat[1] >> 6
    order = [t for t, _ in chunks if t != "IDAT"]
    n_idat = sum(t == "IDAT" for t, _ in chunks)
    sizes = sorted({len(b) for t, b in chunks if t == "IDAT"})
    return dict(size=(w, h), depth=depth, ctype=ctype, interlace=inter, order=order, n_idat=n_idat,
                idat_sizes=sizes[:3], zlib_level=flevel, filters=filters.tolist(), trailing=trailing)


def mp4_boxes(data, off=0, end=None, depth=0, out=None):
    out = [] if out is None else out
    end = len(data) if end is None else end
    while off + 8 <= end:
        size, typ = struct.unpack(">I4s", data[off:off + 8])
        hdr = 8
        if size == 1:
            size, hdr = struct.unpack(">Q", data[off + 8:off + 16])[0], 16
        elif size == 0:
            size = end - off
        t = typ.decode("latin1")
        out.append((depth, t, off, size, hdr))
        if t in ("moov", "trak", "mdia", "minf", "stbl", "udta", "edts", "dinf"):
            mp4_boxes(data, off + hdr, off + size, depth + 1, out)
        elif t == "meta":
            mp4_boxes(data, off + hdr + 4, off + size, depth + 1, out)
        if size < 8:
            break
        off += size
    return out


def video_sei(path):
    """List H.264 SEI payload types (and user-data UUIDs) in the first video samples."""
    d = open(path, "rb").read()
    boxes = mp4_boxes(d)
    def body(name, start=0):
        for dep, t, off, size, hdr in boxes:
            if t == name and off >= start:
                return off, size, hdr
    stsd = d.find(b"avcC")
    if stsd < 0:
        return {"codec": "not H.264 (avcC missing)"}
    nal_len = (d[stsd + 4 + 4] & 3) + 1
    # sample sizes (stsz) and chunk offsets (stco) of the video track (first trak with vmhd)
    vm = d.find(b"vmhd")
    stsz = d.find(b"stsz", vm); stco = d.find(b"stco", vm)
    count = struct.unpack(">I", d[stsz + 12:stsz + 16])[0]
    sizes = struct.unpack(f">{count}I", d[stsz + 16:stsz + 16 + 4 * count])
    first_off = struct.unpack(">I", d[stco + 12:stco + 16])[0]
    types, uuids, pos = {}, set(), first_off
    for s in sizes[:5]:                      # SEI normally sits in the first access units
        p, end = pos, pos + s
        while p + nal_len <= end:
            n = int.from_bytes(d[p:p + nal_len], "big"); nal = d[p + nal_len:p + nal_len + n]
            if nal and nal[0] & 0x1F == 6:
                i = 1
                while i < len(nal) - 1:
                    pt = 0
                    while nal[i] == 0xFF: pt += 255; i += 1
                    pt += nal[i]; i += 1
                    ps = 0
                    while nal[i] == 0xFF: ps += 255; i += 1
                    ps += nal[i]; i += 1
                    types[pt] = types.get(pt, 0) + 1
                    if pt == 5:
                        uuids.add((nal[i:i + 16].hex(), bytes(nal[i + 16:i + 16 + 60]).decode("latin1", "replace")))
                    i += ps
                    if i < len(nal) and nal[i] == 0x80: break
            p += nal_len + n
        pos = end
    return {"codec": "H.264", "sei_payload_types": types, "user_data_unregistered": sorted(uuids)}


def cmd_container():
    print("== PNG structure (Kling, normal + plain)")
    seen = {}
    for f in KLING_NORMAL + PLAIN[:20]:
        r = png_report(f)
        key = (tuple(r["order"]), r["depth"], r["ctype"], r["interlace"], r["zlib_level"], r["trailing"])
        seen.setdefault(key, []).append((r["size"], r["n_idat"], tuple(r["idat_sizes"]), r["filters"]))
    for key, rows in seen.items():
        order, depth, ctype, inter, lvl, trailing = key
        print(f"  {len(rows)} files: chunks {order} | bit depth {depth} | colour type {ctype} | interlace {inter}"
              f" | zlib level flag {lvl} | bytes after IEND {trailing}")
        print(f"     IDAT chunk count {sorted({r[1] for r in rows})}, IDAT sizes (sample) {rows[0][2]}")
        print(f"     row filter histogram (None,Sub,Up,Avg,Paeth), first file: {rows[0][3]}")
    print("== PNG structure (non-Kling PNG controls)")
    ctrl = {}
    for f in CONTROL_PNG:
        try:
            r = png_report(f)
        except Exception as e:
            continue
        ctrl.setdefault((tuple(r["order"]), r["zlib_level"]), 0)
        ctrl[(tuple(r["order"]), r["zlib_level"])] += 1
    for (order, lvl), n in ctrl.items():
        print(f"  {n} files: chunks {order} | zlib level flag {lvl}")
    print("== MP4 boxes and H.264 SEI")
    for v in VIDEOS:
        d = open(v, "rb").read()
        names = sorted({t for _, t, *_ in mp4_boxes(d)})
        print(f"  {v.split('/')[-1]}: boxes {names}")
        print(f"     {video_sei(v)}")


# ---------------------------------------------------------------- steg
def chi_square_lsb(ch):
    """Westfeld-Pfitzmann chi-square test: high p => pairs of values equalised (typical of LSB embedding)."""
    hist = np.bincount(ch.ravel(), minlength=256).astype(float)
    even, odd = hist[0::2], hist[1::2]
    exp = (even + odd) / 2
    m = exp > 5
    stat = (((even[m] - exp[m]) ** 2) / exp[m]).sum()
    return float(1 - chi2.cdf(stat, m.sum() - 1))


def plane_stats(ch, bit):
    p = (ch >> bit) & 1
    ones = p.mean()
    same = ((p[:, 1:] == p[:, :-1]).mean() + (p[1:] == p[:-1]).mean()) / 2
    return ones, same


def entropy(x):
    h = np.bincount(x.ravel(), minlength=256).astype(float); h = h[h > 0] / h.sum()
    return float(-(h * np.log2(h)).sum())


def cmd_steg():
    groups = {"Kling normal": KLING_NORMAL, "Kling plain": PLAIN[:40], "Control": CONTROL_ALL}
    for name, files in groups.items():
        p_vals, lsb_same, lsb_ones, rg, gb, ent_lsb = [], [], [], [], [], []
        for f in files:
            a = np.asarray(Image.open(f).convert("RGB"))
            for c in range(3):
                ch = a[..., c]
                p_vals.append(chi_square_lsb(ch))
                ones, same = plane_stats(ch, 0)
                lsb_ones.append(ones); lsb_same.append(same)
            r = [x.astype(np.float32) - gaussian_filter(x.astype(np.float32), 1.5) for x in (a[..., 0], a[..., 1], a[..., 2])]
            def corr(x, y):
                x = x - x.mean(); y = y - y.mean(); d = np.sqrt((x * x).sum() * (y * y).sum()); return float((x * y).sum() / d) if d else 0.0
            rg.append(corr(r[0], r[1])); gb.append(corr(r[1], r[2]))
            ent_lsb.append(entropy(((a & 1) * 255).astype(np.uint8)))
        print(f"== {name} ({len(files)} files)")
        print(f"   chi-square LSB p-value: median {np.median(p_vals):.3f}, share > 0.95 (embedding-like): {np.mean(np.array(p_vals) > 0.95):.2f}")
        print(f"   LSB plane: ones {np.median(lsb_ones):.3f}, neighbour agreement {np.median(lsb_same):.3f} (0.5 = random)")
        print(f"   residual channel correlation R-G {np.median(rg):+.3f}, G-B {np.median(gb):+.3f}")
    print("== Bit-plane structure, first Kling normal image (ones share, neighbour agreement) per plane 0..7, G channel")
    a = np.asarray(Image.open(KLING_NORMAL[0]).convert("RGB"))[..., 1]
    print("   " + "  ".join(f"b{b}:{plane_stats(a, b)[0]:.2f}/{plane_stats(a, b)[1]:.2f}" for b in range(8)))


# ---------------------------------------------------------------- dct
def cmd_dct():
    """For each 8x8 DCT position, test whether its mean across all blocks of all plain images is non-zero.
    An additive block-DCT watermark aligned to the 8x8 grid would produce strong, consistent biases."""
    sums = np.zeros((8, 8)); sq = np.zeros((8, 8)); n = 0
    pos_frac = np.zeros((8, 8))
    for f in PLAIN:
        y = np.asarray(Image.open(f).convert("L"), dtype=np.float32)[96:2384, 96:1440]
        y = y[: y.shape[0] // 8 * 8, : y.shape[1] // 8 * 8] - y.mean()
        B = y.reshape(y.shape[0] // 8, 8, y.shape[1] // 8, 8).transpose(0, 2, 1, 3)
        D = dctn(B, axes=(2, 3), norm="ortho").reshape(-1, 8, 8)
        sums += D.sum(0); sq += (D ** 2).sum(0); n += D.shape[0]
        pos_frac += (D > 0).mean(0)
    mean = sums / n; std = np.sqrt(sq / n - mean ** 2)
    z = mean / (std / np.sqrt(n) + 1e-12)
    z[0, 0] = 0
    print(f"== Block-DCT bias test on {len(PLAIN)} plain images ({n} blocks)")
    print(f"   largest |z| among 63 AC positions: {np.abs(z).max():.1f} at {np.unravel_index(np.abs(z).argmax(), z.shape)}")
    print(f"   positions with |z| > 5: {int((np.abs(z) > 5).sum())}")
    print(f"   mean |coefficient| by position (x1000):")
    print("   " + np.array2string(np.round(np.abs(mean) * 1000, 2), max_line_width=200).replace("\n", "\n   "))


# ---------------------------------------------------------------- wavelet
def haar(a):
    a = a[: a.shape[0] // 2 * 2, : a.shape[1] // 2 * 2]
    p, q, r, s = a[0::2, 0::2], a[0::2, 1::2], a[1::2, 0::2], a[1::2, 1::2]
    return (p + q + r + s) / 4, (p - q + r - s) / 4, (p + q - r - s) / 4, (p - q - r + s) / 4


def cmd_wavelet():
    """Split-half correlation of each Haar subband: a shared embedded pattern shows up as a positive
    correlation between the mean subband of odd-indexed and even-indexed plain images."""
    acc = {}
    for i, f in enumerate(PLAIN):
        a = np.asarray(Image.open(f).convert("L"), dtype=np.float32)[96:2144, 96:1376]
        a = (a - a.mean()) / (a.std() + 1e-6)
        for lvl in range(1, 6):
            a, lh, hl, hh = haar(a)
            for name, band in (("LH", lh), ("HL", hl), ("HH", hh)):
                k = (lvl, name); acc.setdefault(k, [np.zeros_like(band), np.zeros_like(band)])
                acc[k][i % 2] += band
    print(f"== Haar wavelet split-half correlation, {len(PLAIN)} plain images")
    for (lvl, name), (A, B) in sorted(acc.items()):
        A = A - A.mean(); B = B - B.mean()
        c = float((A * B).sum() / np.sqrt((A * A).sum() * (B * B).sum()))
        print(f"   level {lvl} {name}: {c:+.3f}")


# ---------------------------------------------------------------- robustness
def transforms():
    def jpeg(q):
        def t(im):
            b = io.BytesIO(); im.save(b, "JPEG", quality=q); return Image.open(io.BytesIO(b.getvalue())).convert("RGB")
        return t
    def resize(f):
        return lambda im: im.resize((int(im.width * f), int(im.height * f)), Image.Resampling.BICUBIC).resize(im.size, Image.Resampling.BICUBIC)
    def arr(fn):
        return lambda im: Image.fromarray(np.clip(fn(np.asarray(im, np.float32)), 0, 255).astype(np.uint8))
    rng = np.random.default_rng(0)
    return {
        "none (PNG round trip)": lambda im: im,
        "JPEG q95": jpeg(95), "JPEG q75": jpeg(75), "JPEG q50": jpeg(50),
        "resize 0.5x and back": resize(0.5), "resize 1.5x and back": resize(1.5),
        "crop 7 px (shift)": lambda im: im.crop((7, 7, im.width, im.height)),
        "RGB->YCbCr->RGB": lambda im: im.convert("YCbCr").convert("RGB"),
        "brightness +10%": arr(lambda a: a * 1.1), "contrast 1.2": arr(lambda a: (a - 128) * 1.2 + 128),
        "Gaussian noise sd 2": arr(lambda a: a + rng.normal(0, 2, a.shape)),
        "blur sigma 1": arr(lambda a: gaussian_filter(a, (1, 1, 0))),
        "sharpen": arr(lambda a: a + 1.0 * (a - gaussian_filter(a, (1, 1, 0)))),
    }


def shared_signal(images):
    """Return (split-half corr in 0.02-0.05 cyc/px band, 32 px peak share of that band) for a list of images."""
    H, W = 2048, 1280
    SA = np.zeros((H, W // 2 + 1), complex); SB = np.zeros_like(SA)
    for i, im in enumerate(images):
        a = np.asarray(im.convert("L"), dtype=np.float32)[200:200 + H, 128:128 + W]
        a = a - a.mean(); s = a.std(); a = a / s if s > 0 else a
        X = np.fft.rfft2(a)
        if i % 2: SB += X
        else: SA += X
    fy = np.fft.fftfreq(H)[:, None]; fx = np.fft.rfftfreq(W)[None, :]; fr = np.sqrt(fy ** 2 + fx ** 2)
    m = (fr >= 0.02) & (fr < 0.05)
    num = np.real(SA * np.conj(SB))
    corr = num[m].sum() / np.sqrt((np.abs(SA[m]) ** 2).sum() * (np.abs(SB[m]) ** 2).sum())
    grid = num[0, W // 32] + num[H // 32, 0] + num[-H // 32, 0]
    return float(corr), float(grid / num[m].sum())


def cmd_robust():
    files = PLAIN[:60]
    base = [Image.open(f).convert("RGB") for f in files]
    print(f"== Shared plain-image signal under transforms ({len(files)} images)")
    print("   transform                  split-half corr (20-50 px band)   32 px grid share")
    for name, t in transforms().items():
        c, g = shared_signal([t(im) for im in base])
        print(f"   {name:26s} {c:+.3f}                            {g * 100:5.1f}%")
    print("== AIGC metadata after a plain re-save with Pillow (no pnginfo passed)")
    im = Image.open(KLING_NORMAL[-1]); b = io.BytesIO(); im.save(b, "PNG")
    print("   label present after re-save:", "AIGC" in Image.open(io.BytesIO(b.getvalue())).info)


# ---------------------------------------------------------------- residual / bands / grid
def cmd_residual():
    """Flatness, leave-one-out correlation, averaged-residual energy and split-half test on plain images."""
    R, distinct, flat = [], [], 0
    for f in PLAIN:
        a = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)[96:2384, 96:-96]
        d = [len(np.unique(a[..., c])) for c in range(3)]
        distinct.append(max(d)); flat += any(x == 1 for x in d)
        y = a.mean(-1); r = y - gaussian_filter(y, 2); s = r.std()
        R.append((r / s if s > 0 else r).astype(np.float32))
    R = np.stack(R); N = len(R); S = R.sum(0)
    def corr(x, y):
        x = x - x.mean(); y = y - y.mean(); d = np.sqrt((x * x).sum() * (y * y).sum()); return float((x * y).sum() / d) if d else 0.0
    loo = [corr(R[i], (S - R[i]) / (N - 1)) for i in range(N)]
    print(f"== {N} plain images: distinct values/channel median {int(np.median(distinct))}, max {max(distinct)}; "
          f"channel 100% one value in {flat}/{N}")
    print(f"   leave-one-out corr mean {np.mean(loo):+.4f}, max {np.max(loo):+.4f}")
    print(f"   averaged residual energy {float(((S / N) ** 2).mean()):.4f} vs pure-noise 1/N = {1 / N:.4f}")
    print(f"   split-half corr (odd vs even mean residual) {corr(R[0::2].mean(0), R[1::2].mean(0)):+.4f}")


def cmd_bands():
    """Split the shared plain-image signal by spatial-frequency band and list the strongest components."""
    H, W = 2048, 1280
    SA = np.zeros((H, W // 2 + 1), complex); SB = np.zeros_like(SA)
    for i, f in enumerate(PLAIN):
        a = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)[200:200 + H, 128:128 + W].mean(-1)
        a = a - a.mean(); s = a.std(); a = a / s if s > 0 else a
        X = np.fft.rfft2(a)
        if i % 2: SB += X
        else: SA += X
    fy = np.fft.fftfreq(H)[:, None]; fx = np.fft.rfftfreq(W)[None, :]; fr = np.sqrt(fy ** 2 + fx ** 2)
    num = np.real(SA * np.conj(SB)); tot = num[fr > 0].sum()
    print("== band (cycles/px)  split-half corr  share of shared energy")
    for lo, hi in [(0, .005), (.005, .02), (.02, .05), (.05, .1), (.1, .2), (.2, .35), (.35, .71)]:
        m = (fr >= lo) & (fr < hi) & (fr > 0)
        c = num[m].sum() / np.sqrt((np.abs(SA[m]) ** 2).sum() * (np.abs(SB[m]) ** 2).sum())
        print(f"   {lo:.3f}-{hi:.3f}        {c:+.4f}         {num[m].sum() / tot * 100:5.1f}%")
    m = (fr >= .02) & (fr < .05)
    for k in np.argsort(np.where(m, num, -np.inf).ravel())[::-1][:4]:
        yy, xx = divmod(int(k), W // 2 + 1)
        print(f"   component fy={fy[yy, 0]:+.4f} fx={fx[0, xx]:.4f}: {num[yy, xx] / num[m].sum() * 100:.1f}% of 0.02-0.05 band")


def grid_score(f, P=32):
    a = np.asarray(Image.open(f).convert("L"), dtype=np.float32)
    h = (min(a.shape[0], 2048) // 64) * 64; w = (min(a.shape[1], 1280) // 64) * 64
    if h < 256 or w < 256:
        return None
    y0 = (a.shape[0] - h) // 2; x0 = (a.shape[1] - w) // 2
    a = a[y0:y0 + h, x0:x0 + w]; a = a - a.mean()
    S = np.abs(np.fft.rfft2(a)) ** 2
    def ratio(y, x):
        nb = [S[(y + dy) % h, x + dx] for dy in range(-3, 4) for dx in range(-3, 4) if (dy or dx) and 0 <= x + dx < S.shape[1]]
        return S[y, x] / (np.median(nb) + 1e-9)
    return max(ratio(h // P, 0), ratio(0, w // P))


def cmd_grid():
    """Is the 32 px grid strong enough in single images to tell Kling from non-Kling? (it is not)"""
    for name, files in {"Kling plain": PLAIN, "Kling normal": KLING_NORMAL, "Control": CONTROL_ALL}.items():
        s = [x for x in (grid_score(f) for f in files) if x is not None]
        print(f"   {name:13s} 32 px peak ratio median {np.median(s):6.1f} (n={len(s)})")


def cmd_texture():
    """Fixed-pattern test restricted to textured, unclipped pixels of normal IMAGE 2.1 images,
    before and after removing the periodic (period <= 32 px) pipeline grid."""
    from scipy.ndimage import uniform_filter
    H, W, P = 2464, 1536, 32
    def notch(x):
        X = np.fft.fft2(x); X[np.ix_(np.arange(H) % (H // P) == 0, np.arange(W) % (W // P) == 0)] = 0
        return np.real(np.fft.ifft2(X)).astype(np.float32)
    R, M = [], []
    for f in sorted(glob.glob("samples/kling_*Text_to_Image*.png")):
        y = np.asarray(Image.open(f).convert("L"), dtype=np.float32)[:H]
        loc = np.sqrt(np.maximum(uniform_filter(y * y, 9) - uniform_filter(y, 9) ** 2, 0))
        m = (loc > 2.0) & (y > 8) & (y < 247)
        if m.mean() < 0.15:
            continue
        r = y - gaussian_filter(y, 1.5)
        R.append(np.where(m, r / (r[m].std() + 1e-6), 0).astype(np.float32)); M.append(m)
    R = np.stack(R); M = np.stack(M); N = len(R)
    def loo(Rs):
        S = Rs.sum(0); C = M.sum(0).astype(np.float32); out = []
        for i in range(N):
            v = M[i] & (C - M[i] >= 3); fbar = (S - Rs[i]) / np.maximum(C - M[i], 1)
            x = Rs[i][v] - Rs[i][v].mean(); y = fbar[v] - fbar[v].mean()
            out.append(float((x * y).sum() / np.sqrt((x * x).sum() * (y * y).sum())))
        return np.array(out)
    a = loo(R); b = loo(np.stack([notch(r) * m for r, m in zip(R, M)]))
    print(f"== {N} textured IMAGE 2.1 images: LOO corr raw {a.mean():+.4f} (all > 0: {bool((a > 0).all())}); "
          f"grid removed {b.mean():+.4f} (all > 0: {bool((b > 0).all())})")


def cmd_samples():
    """Write a sample-level CSV (sha256, group, size, label present, chunk list, flatness) to samples/ (git-ignored)."""
    import csv, hashlib, json
    rows = []
    for group, files in {"kling_normal": KLING_NORMAL, "kling_plain": PLAIN, "control": CONTROL_ALL}.items():
        for f in files:
            raw = open(f, "rb").read(); im = Image.open(f)
            lab = im.info.get("AIGC")
            prod = json.loads(lab)["ContentProducer"] if lab else ""
            a = np.asarray(im.convert("RGB"), dtype=np.float32)
            rows.append({"file": f.split("/")[-1], "group": group, "sha256": hashlib.sha256(raw).hexdigest(),
                         "format": im.format, "width": im.width, "height": im.height, "aigc_label": bool(lab),
                         "producer_form": "uscc" if prod.startswith("0011") else (prod or "-"),
                         "interior_std": round(float(a[96:-96, 96:-96].std()), 3)})
    with open("samples/forensic_samples.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"wrote samples/forensic_samples.csv ({len(rows)} rows)")


def cmd_payload():
    """Second-order test for a per-image (payload-modulated) mark on textured IMAGE 3.0 images.

    If every image adds sum_k b_ik * P_k with fixed secret patterns P_k and per-image bits b_ik, averaging cancels it,
    but pairwise residual correlations get a larger spread than chance. Compare the mean squared cross-batch
    correlation of aligned residuals with the same statistic after random circular shifts, which break any
    position-locked structure. The periodic pipeline grid is removed first, and same-batch pairs are excluded so
    shared prompts cannot create correlation."""
    import re
    from scipy.ndimage import uniform_filter
    files = sorted(glob.glob("samples/round5/*.png"))
    S, P = 1024, 32
    def notch(x):
        X = np.fft.fft2(x); X[np.ix_(np.arange(S) % (S // P) == 0, np.arange(S) % (S // P) == 0)] = 0
        return np.real(np.fft.ifft2(X)).astype(np.float32)
    R, B = [], []
    for f in files:
        y = np.asarray(Image.open(f).convert("L"), dtype=np.float32)
        y0 = (y.shape[0] - S) // 2; x0 = (y.shape[1] - S) // 2; y = y[y0:y0 + S, x0:x0 + S]
        loc = np.sqrt(np.maximum(uniform_filter(y * y, 9) - uniform_filter(y, 9) ** 2, 0))
        m = (loc > 2.0) & (y > 8) & (y < 247)
        r = notch(y - gaussian_filter(y, 1.5)) * m
        s = r[m].std() if m.any() else 1.0
        R.append((r / s).astype(np.float32)); B.append(re.findall(r"_(\d+)_\d+\.png$", f)[0])
    R = np.stack(R); N = len(R)
    def msq(Rs):
        flat = Rs.reshape(N, -1); flat = flat - flat.mean(1, keepdims=True)
        flat = flat / (np.linalg.norm(flat, axis=1, keepdims=True) + 1e-9)
        C = flat @ flat.T
        vals = [C[i, j] ** 2 for i in range(N) for j in range(i + 1, N) if B[i] != B[j]]
        return float(np.mean(vals)), len(vals)
    aligned, npairs = msq(R)
    rng = np.random.default_rng(0)
    null = [msq(np.stack([np.roll(r, (int(rng.integers(64, S - 64)), int(rng.integers(64, S - 64))), (0, 1)) for r in R]))[0]
            for _ in range(8)]
    z = (aligned - np.mean(null)) / (np.std(null) + 1e-12)
    print(f"== {N} textured IMAGE 3.0 images, {npairs} cross-batch pairs, grid removed")
    print(f"   mean squared pairwise correlation: aligned {aligned:.3e} vs shifted null {np.mean(null):.3e} "
          f"(sd {np.std(null):.1e}); z = {z:+.1f}")


# ---------------------------------------------------------------- targeted watermark hunt
KLING_TEXTURED = sorted(glob.glob("samples/round5/*.png"))
CONTROL_JPEG = sorted(f for f in CONTROL_ALL if f.lower().endswith((".jpg", ".jpeg")))
KLING_VIDEOS = VIDEOS + sorted(glob.glob("samples/**/*.mov", recursive=True))
CONTROL_VIDEOS = sorted(glob.glob("samples/control_video/*"))


def hunt_options(argv):
    """--kling GLOB / --control GLOB (repeatable) replace the default groups; --limit N caps each group."""
    opts = {"kling": [], "control": [], "limit": 40}
    i = 0
    while i < len(argv):
        if argv[i] in ("--kling", "--control"):
            opts[argv[i][2:]] += sorted(glob.glob(argv[i + 1], recursive=True)); i += 2
        elif argv[i] == "--limit":
            opts["limit"] = int(argv[i + 1]); i += 2
        else:
            raise SystemExit(f"unknown option {argv[i]}")
    return opts


def hunt_groups(opts, kling_default, control_default):
    import os
    kling = {"Kling (--kling)": opts["kling"]} if opts["kling"] else kling_default
    control = {"Control (--control)": opts["control"]} if opts["control"] else control_default
    def cut(groups):
        groups = {k: [f for f in v if os.path.isfile(f)][: opts["limit"]] for k, v in groups.items()}
        return {k: v for k, v in groups.items() if v}
    kling, control = cut(kling), cut(control)
    if not kling:
        raise SystemExit("no Kling sample files found (samples/ is local only; or pass --kling GLOB)")
    return kling, control


def wmhunt_module():
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import wmhunt
    return wmhunt


def cmd_controls():
    """Positive and negative controls for every hunt detector, on synthetic images only."""
    import tempfile
    wm = wmhunt_module()
    with tempfile.TemporaryDirectory() as tmp:
        for r in wm.run_all_controls(tmp):
            print(f"   {r['status']:8s} {r['control']:44s} {r.get('flagged', ''):4s} {r['detail']}")


def cmd_qim(argv):
    """Key-free scan for quantization-index-modulation lattices (the DWT-DCT-SVD blind-watermark family)."""
    wm = wmhunt_module()
    kling, control = hunt_groups(hunt_options(argv), {
        "Kling normal": KLING_NORMAL, "Kling IMAGE 3.0 textured": KLING_TEXTURED, "Kling plain": PLAIN[:20]},
        {"Control PNG": CONTROL_PNG, "Control JPEG": CONTROL_JPEG})
    print(f"== QIM lattice scan (flag: score >= {wm.QIM_FLAG_SCORE:.0f} with contrast >= {wm.QIM_MIN_CONTRAST:.0f}, "
          "no JPEG history). Run 'controls' first.")
    for name, files in {**kling, **control}.items():
        reps = [wm.qim_report(wm.load_rgb(f)) for f in files]
        flagged = [r for r in reps if r["flag"]]
        scores = [r["score"] for r in reps]
        print(f"   {name:26s} n={len(reps):3d}  flagged {len(flagged):3d}  JPEG history {sum(r['jpeg_history'] for r in reps):3d}  "
              f"score median {np.median(scores):7.1f} max {max(scores):8.1f}")
        for i, r in enumerate(reps):
            if r["score"] > 0:
                print(f"      #{i:<3d} score {r['score']:8.1f}  step {r['step']:6.2f}  contrast {r['contrast']:6.1f}  {r['feature']}"
                      f"{'  (JPEG history)' if r['jpeg_history'] else ''}")


def cmd_decoders(argv):
    """Do Kling images share one message under a public neural watermark decoder? Compared with PNG controls."""
    wm = wmhunt_module()
    kling, control = hunt_groups(hunt_options(argv), {
        "Kling normal": KLING_NORMAL, "Kling IMAGE 3.0 textured": KLING_TEXTURED},
        {"Control PNG": CONTROL_PNG})
    ref_files = [f for files in control.values() for f in files]
    for make in (wm.RivaGan, wm.stegastamp, wm.hidden):
        try:
            model = make()
        except wm.Unavailable as e:
            print(f"== {getattr(make, 'name', make.__name__)}: SKIPPED ({e})"); continue
        ctl = wm.control_decoder(model)
        print(f"== {model.name} ({model.nbits} bits). Positive control: {ctl['status']} - {ctl['detail']}")
        ref = [model.decode(wm.load_rgb(f)) for f in ref_files]
        null = wm.null_split(ref)
        print(f"   null (control half vs half)  agreement {null['agreement']:.2f}  T {null['T']:5.1f}  (n={len(ref)})")
        for name, files in kling.items():
            st = wm.decoder_stats([model.decode(wm.load_rgb(f)) for f in files], ref)
            print(f"   {name:28s} agreement {st['agreement']:.2f}  T {st['T']:5.1f}  (n={st['n']})")


def cmd_video(argv):
    """VideoSeal detection bit, RivaGAN fixed-message test and QIM scan on frames of Kling and control videos."""
    wm = wmhunt_module()
    opts = hunt_options(argv)
    kling, control = hunt_groups(opts, {"Kling video": KLING_VIDEOS}, {"Control video": CONTROL_VIDEOS})
    try:
        vs = wm.VideoSeal()
        print(f"== VideoSeal positive control: {wm.control_videoseal()['detail']}")
    except wm.Unavailable as e:
        vs = None
        print(f"== VideoSeal: SKIPPED ({e})")
    riva = wm.RivaGan()
    scores = {}
    for name, files in {**kling, **control}.items():
        print(f"== {name} ({len(files)} files)")
        scores[name] = []
        for i, f in enumerate(files):
            frames = wm.read_frames(f, 32)
            if not frames:
                print(f"   #{i:<3d} no frames could be read"); continue
            q = [wm.qim_report(fr) for fr in frames[:: max(1, len(frames) // 3)][:3]]
            r = np.mean([riva.decode(fr) for fr in frames[::4]], 0)
            scores[name].append(r)
            line = (f"   #{i:<3d} frames {len(frames):3d} {frames[0].shape[1]}x{frames[0].shape[0]}  "
                    f"QIM flagged {sum(x['flag'] for x in q)}/{len(q)} (max score {max(x['score'] for x in q):7.1f}"
                    f"{', luma only' if q[0]['chroma_subsampled'] else ''})")
            if vs is not None:
                _, det = vs.decode_frames(frames)
                line += f"  VideoSeal detection logit {det:+.2f}"
            print(line)
    ref = [s for name in control for s in scores.get(name, [])]
    for name in kling:
        st = wm.decoder_stats(scores.get(name, []), ref)
        print(f"   RivaGAN fixed-message test, {name} vs control videos: agreement {st['agreement']:.2f}  T {st['T']:.1f}"
              + ("" if len(ref) >= 2 else "  (needs >= 2 control videos)"))


if __name__ == "__main__":
    if sys.argv[1] in ("qim", "decoders", "video"):
        {"qim": cmd_qim, "decoders": cmd_decoders, "video": cmd_video}[sys.argv[1]](sys.argv[2:]); sys.exit()
    if sys.argv[1] in ("texture", "samples", "payload", "controls"):
        {"texture": cmd_texture, "samples": cmd_samples, "payload": cmd_payload, "controls": cmd_controls}[sys.argv[1]](); sys.exit()
    {"container": cmd_container, "steg": cmd_steg, "dct": cmd_dct, "wavelet": cmd_wavelet,
     "robust": cmd_robust, "residual": cmd_residual, "bands": cmd_bands, "grid": cmd_grid}[sys.argv[1]]()
