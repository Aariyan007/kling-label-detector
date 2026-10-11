"""Compare Kling 'with watermark' vs 'without watermark' downloads (detection only).

Kling says its images carry an imperceptible watermark plus metadata. Downloading
the SAME generation twice -- once with the visible logo, once with Kling's paid
"without watermark" option -- isolates whatever the finishing step adds, apart from
the image content. This script measures that difference and characterises it.

It answers two questions, with numbers only:
  1. Is there any pixel change outside the visible-logo corner?
  2. If yes, is the change the SAME pattern in every image (a fixed, non-keyed mark)
     or different per image (a content-/key-dependent mark)? -> cross-pair correlation.

DETECTION ONLY. This script never writes image data, never saves the difference
pattern, and never prints raw pixels. It prints summary statistics so a human can
decide whether a watermark is present and what type it is. It is NOT a remover and
does not reconstruct or apply any pattern.

Usage:
    python forensics/wm_pair_compare.py <dir>
Files are paired by stem: foo_with.png <-> foo_without.png (any image extension).

Deps: numpy, pillow.
"""

import os
import sys
import glob
import numpy as np
from PIL import Image

LOGO_FRAC_Y = 0.88   # logo sits in the bottom-right; ignore rows below this fraction
LOGO_FRAC_X = 0.60   # ... and columns right of this fraction


def load_rgb(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def logo_mask(h, w):
    m = np.ones((h, w), bool)
    m[int(h * LOGO_FRAC_Y):, int(w * LOGO_FRAC_X):] = False
    return m


def find_pairs(d):
    pairs = {}
    for p in glob.glob(os.path.join(d, "*")):
        stem, ext = os.path.splitext(os.path.basename(p))
        if ext.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        for tag in ("_with", "_without"):
            if stem.endswith(tag):
                pairs.setdefault(stem[: -len(tag)], {})[tag] = p
    return {k: v for k, v in sorted(pairs.items()) if "_with" in v and "_without" in v}


def describe_pair(key, with_p, without_p):
    a = load_rgb(with_p)      # with logo
    b = load_rgb(without_p)   # without watermark
    if a.shape != b.shape:
        print(f"[{key}] SKIP: sizes differ {a.shape} vs {b.shape} (not the same generation?)")
        return None
    h, w = a.shape[:2]
    m = logo_mask(h, w)
    diff = (a - b)                                  # signed, HxWx3
    adiff = np.abs(diff)
    out = adiff[m]                                  # pixels outside the logo, Nx3
    changed = out.max(-1) > 0
    pct = changed.mean() * 100

    print(f"\n[{key}]  {w}x{h}")
    print(f"  outside logo: pixels that differ {pct:.3f}% | mean |diff| {out.mean():.4f} | max {int(out.max())}")

    if pct < 0.01:
        print("  -> essentially identical outside the logo. Finishing step adds only the visible logo.")
        return None

    # how big are the changes? (small, spread changes ~1-3 levels look like a watermark)
    mags = out.max(-1)[changed]
    for lo, hi in [(1, 1), (2, 2), (3, 3), (4, 8), (9, 255)]:
        share = np.mean((mags >= lo) & (mags <= hi)) * 100
        label = f"{lo}" if lo == hi else f"{lo}-{hi}"
        print(f"     changed pixels at |diff| {label:>5}: {share:5.1f}%")

    # which channel carries it? (a blue-only mark suggests a classic spatial watermark)
    per_ch = adiff[m].mean(0)
    print(f"  mean |diff| per channel  R {per_ch[0]:.4f}  G {per_ch[1]:.4f}  B {per_ch[2]:.4f}")

    # spread vs localised: block map of change density (numbers, not an image)
    gy, gx = 8, 8
    dens = np.zeros((gy, gx))
    ch = (adiff.max(-1) > 0) & m
    for i in range(gy):
        for j in range(gx):
            ys = slice(i * h // gy, (i + 1) * h // gy)
            xs = slice(j * w // gx, (j + 1) * w // gx)
            sub = m[ys, xs]
            dens[i, j] = ch[ys, xs].sum() / max(sub.sum(), 1) * 100
    print(f"  change density over 8x8 blocks: min {dens[dens>0].min() if (dens>0).any() else 0:.1f}% "
          f"median {np.median(dens):.1f}% max {dens.max():.1f}%  (flat = spread everywhere)")

    # frequency signature of the change (broadband vs a few periodic peaks)
    g = diff.astype(np.float32).mean(-1)
    g = g - g.mean()
    F = np.abs(np.fft.fftshift(np.fft.fft2(g)))
    F[F.shape[0] // 2, F.shape[1] // 2] = 0
    peak = F.max()
    med = np.median(F)
    print(f"  FFT of change: peak/median energy ratio {peak / max(med, 1e-6):.1f}  "
          f"({'periodic/structured' if peak / max(med, 1e-6) > 50 else 'broadband/noise-like'})")

    return g  # mean signed change map, kept in memory only for cross-pair correlation


def cross_pair(maps):
    """Correlate the change maps across different images.
    High correlation -> the SAME pattern in every image (fixed, non-keyed mark).
    Near zero       -> a different pattern each time (keyed or content-adaptive)."""
    keys = [k for k, v in maps.items() if v is not None]
    if len(keys) < 2:
        print("\ncross-pair: need >=2 pairs with a change to compare.")
        return
    # resize all to a common small grid so different resolutions can be compared
    import numpy as np
    H = W = 256
    def grid(g):
        gi = Image.fromarray(((g - g.min()) / (np.ptp(g) + 1e-9) * 255).astype(np.uint8))
        gi = gi.resize((W, H), Image.BILINEAR)
        x = np.asarray(gi, dtype=np.float32)
        return (x - x.mean()) / (x.std() + 1e-9)
    G = {k: grid(maps[k]) for k in keys}
    print("\ncross-pair correlation of the change pattern (|r|):")
    rs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            x, y = G[keys[i]].ravel(), G[keys[j]].ravel()
            r = float(np.dot(x, y) / (len(x)))
            rs.append(abs(r))
            print(f"   {keys[i]} vs {keys[j]}: r = {r:+.3f}")
    mean_abs = np.mean(rs)
    print(f"\n   mean |r| = {mean_abs:.3f}")
    if mean_abs > 0.5:
        print("   -> SAME pattern across images: a fixed, non-keyed watermark (or a fixed artifact).")
    elif mean_abs > 0.2:
        print("   -> partly shared: possibly a template modulated by content.")
    else:
        print("   -> different each image: a per-image keyed / content-adaptive mark, or just content.")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    d = sys.argv[1]
    pairs = find_pairs(d)
    if not pairs:
        print(f"No *_with / *_without image pairs found in {d}")
        sys.exit(1)
    print(f"Found {len(pairs)} pair(s). Logo corner ignored: rows below {LOGO_FRAC_Y:.0%}, cols right of {LOGO_FRAC_X:.0%}.")
    maps = {}
    for k, v in pairs.items():
        maps[k] = describe_pair(k, v["_with"], v["_without"])
    cross_pair(maps)
    print("\nReport the numbers only. Do not export or post the difference pattern.")


if __name__ == "__main__":
    main()
