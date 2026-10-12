"""Learn-a-detector test: can a classifier tell Kling images from another generator's
images using only high-frequency pixel residuals? (detection only)

Unlike the fixed-pattern tests, this does not guess the watermark's form — it lets a
model learn any content-independent pixel signature (a keyed/learned watermark, or a
generator fingerprint). The decisive metric is NOT in-sample accuracy (a classifier can
memorise a batch) but generalisation to a **content-different, held-out** set. If it still
flags unseen Kling images, a real Kling pixel signature exists; if it collapses to chance,
the in-sample separability was content, not a watermark.

Features: per-image, high-pass residual (image - Gaussian), patches, log|FFT| of each
patch down-sampled to a scale-normalised spectral vector. RandomForest; image-level score
is the mean patch probability.

Usage:
    python forensics/pixel_classifier.py \
        --kling-train DIR --other-train DIR \
        --kling-test  DIR [--kling-test DIR ...] --other-test DIR \
        [--native]   # native-resolution patches instead of resize-to-512 (keeps a fine mark,
                     #  but lets resolution leak; default resizes for a scale-fair test)

Deps: numpy, pillow, scikit-learn. Prints numbers only; exports nothing.
"""

import os
import glob
import argparse
import collections
import warnings
import numpy as np
from PIL import Image, ImageFilter

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(0)


def imgs(d):
    out = []
    for e in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        out += glob.glob(os.path.join(d, "**", e), recursive=True)
    return sorted(out)


def feats(path, native):
    try:
        im = Image.open(path).convert("L")
    except Exception:
        return []
    if not native:
        w, h = im.size
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((512, 512))
    a = np.asarray(im, np.float32)
    b = np.asarray(im.filter(ImageFilter.GaussianBlur(radius=1.5)), np.float32)
    r = a - b
    H, W = r.shape
    P = 256 if native else 128
    out = []
    if native:
        for _ in range(6):
            if H < P or W < P:
                break
            y = RNG.integers(0, max(1, int(H * 0.80) - P)); x = RNG.integers(0, W - P)
            out.append(_spec(r[y:y + P, x:x + P]))
    else:
        for i in range(3):
            for j in range(3):
                p = r[i * 160:i * 160 + P, j * 160:j * 160 + P]
                if p.shape == (P, P):
                    out.append(_spec(p))
    return out


def _spec(p):
    F = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(p - p.mean()))))
    n = F.shape[0]; k = n // 16
    return F.reshape(16, k, 16, k).mean((1, 3)).ravel()


def collect(paths, label, native, g0=0):
    X, y, g = [], [], []
    for k, p in enumerate(paths):
        for f in feats(p, native):
            X.append(f); y.append(label); g.append(g0 + k)
    return X, y, g


def image_probs(clf, paths, native):
    X, _, g = collect(paths, 1, native)
    if not X:
        return np.array([])
    pr = clf.predict_proba(np.array(X))[:, 1]
    d = collections.defaultdict(list)
    for p_, i in zip(pr, g):
        d[i].append(p_)
    return np.array([np.mean(v) for v in d.values()])


def main():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.metrics import roc_auc_score
    ap = argparse.ArgumentParser()
    ap.add_argument("--kling-train", required=True)
    ap.add_argument("--other-train", required=True)
    ap.add_argument("--kling-test", action="append", default=[])
    ap.add_argument("--other-test", required=True)
    ap.add_argument("--native", action="store_true")
    a = ap.parse_args()

    kt = imgs(a.kling_train); ot = imgs(a.other_train)
    Xk, yk, gk = collect(kt, 1, a.native, 0)
    Xg, yg, gg = collect(ot, 0, a.native, 100000)
    X = np.array(Xk + Xg); y = np.array(yk + yg); grp = np.array(gk + gg)

    # (A) in-sample image-level AUC via group CV (positive control: is there ANY separability?)
    aucs = []
    for tr, te in StratifiedGroupKFold(n_splits=5).split(X, y, grp):
        c = RandomForestClassifier(n_estimators=300, random_state=0, n_jobs=-1).fit(X[tr], y[tr])
        pr = c.predict_proba(X[te])[:, 1]
        d = collections.defaultdict(list); lab = {}
        for p_, i, l in zip(pr, grp[te], y[te]):
            d[i].append(p_); lab[i] = l
        ip = [np.mean(v) for i, v in d.items()]; il = [lab[i] for i in d]
        if len(set(il)) > 1:
            aucs.append(roc_auc_score(il, ip))
    print(f"(A) in-sample 5-fold image-level AUC = {np.mean(aucs):.3f} +/- {np.std(aucs):.3f}  "
          f"(~0.5 = no learnable signal; high = separable in-sample)")

    # (B) held-out, content-different generalisation (the decisive test)
    clf = RandomForestClassifier(n_estimators=400, random_state=0, n_jobs=-1).fit(X, y)
    kprobs = [image_probs(clf, imgs(d), a.native) for d in a.kling_test]
    allk = np.concatenate([p for p in kprobs if len(p)]) if kprobs else np.array([])
    gp = image_probs(clf, imgs(a.other_test), a.native)
    for d, p in zip(a.kling_test, kprobs):
        print(f"    held-out Kling  {os.path.basename(d.rstrip('/')):16s} mean P(Kling)={p.mean():.2f} (N={len(p)})")
    print(f"    held-out other  {os.path.basename(a.other_test.rstrip('/')):16s} mean P(Kling)={gp.mean():.2f} (N={len(gp)})")
    if len(allk) and len(gp):
        yv = np.r_[np.ones(len(allk)), np.zeros(len(gp))]; sv = np.r_[allk, gp]
        print(f"(B) HELD-OUT AUC (content-different Kling vs other) = {roc_auc_score(yv, sv):.3f}")
        print("    reliable generalisation (e.g. >0.9 AND Kling scored as Kling) => a real pixel signature;")
        print("    near 0.5 => in-sample separability was content, not a watermark.")


if __name__ == "__main__":
    main()
