# Methodology and pre-registration: the invisible-watermark question

This document states, up front, *what* each experiment tests, *how* success/failure is
decided, and *what it can and cannot exclude*. It is written so the conclusion can be
judged against fixed criteria rather than after-the-fact interpretation.

## The three possibilities (framing)

For a Kling image that carries ordinary `AIGC` metadata, an invisible pixel watermark
could be:

1. **present but unrecognised** — a real mark our detectors are not matched to;
2. **conditional** — present only for certain models, routes, or processing paths;
3. **absent** — Kling embeds the metadata but no working pixel watermark in these samples.

No single negative test separates these. The strategy is to exclude concrete *classes*
of watermark one at a time, each with a positive control, and to state the residual
possibilities honestly.

## Pre-registered metrics and thresholds

Decided **before** evaluating the held-out set (dataset.md):

| Test | Metric | Detect threshold (decided in advance) | Positive control |
|------|--------|---------------------------------------|------------------|
| With/without logo (A) | % pixels differing outside the logo mask | > 0.05% ⇒ "something added outside the logo" | planted ±2 pattern + null pair |
| Baked-in fixed pattern, images (C) | cross-scene residual correlation, z vs shuffled null | z > 5 ⇒ shared pattern present | ±0.25…±2 patterns planted into the real images |
| Video frame watermark (D) | cross-video temporal-average residual \|r\|, vs control-control | Kling-Kling ≫ control-control ⇒ shared mark | ±2 pattern planted into two clips |
| Neural decoders (earlier) | bit-agreement / marked-vs-clean separation T | agreement ≥ 0.8 **and** T ≥ 4 in both Kling groups | RivaGAN-marked synthetic images |
| QIM lattice (earlier) | # Kling files flagged in the textured group | any flagged ⇒ not excluded | QIM-marked synthetic images |
| Latent inversion / Tree-Ring (earlier) | ring-score p vs clean, one-sided | p < 0.01 ⇒ latent ring present | self-made Tree-Ring key, same model |
| Large-scale averaging (#4) | cross-**batch** correlation of per-batch average residuals | consistent r > 0.3 across *different-content* batches | planted ±0.3 fixed pattern |
| Blind-watermark decode (#5) | cross-**batch** bit-agreement, default password | > 0.55 across *different-content* batches | library embed→extract round-trip |
| Learn-a-detector (#2) | **held-out** AUC, Kling vs other-AI, pixels only | AUC > 0.9 *and* held-out Kling scored as Kling | in-sample 5-fold AUC (separability exists) |

A test's negative result is reported **only if its positive control passed** under the
same settings.

## Results against those thresholds

All Kling results fell on the "not detected" side of every pre-set threshold, while every
positive control crossed it. Key numbers:

- **A:** 0.000% differ outside the logo (threshold 0.05%); control pair flagged correctly.
- **C:** Kling z = +0.1 (threshold 5); controls z = +13.7 (±1) and +58.4 (±2).
- **D:** Kling-Kling \|r\| = 0.005 ≈ control-control 0.004; planted control = 0.045.
- Neural decoders: Kling agreement 0.69–0.71 (threshold 0.80); control 0.95–0.97.
- QIM: 0 Kling textured files flagged; controls heavily flagged.
- Latent inversion: Kling p = 0.57 (threshold 0.01); control p = 0.0011.
- **#4 averaging (331 images):** within-pool split-half r = 0.41 and an averaged residual 2.6–4.4× the noise floor *looked positive* — but the content control killed it: cross-batch correlation between different-content batches was round4×round5 = **−0.001** (and round3×round4 = +0.986, i.e. those two batches are near-duplicates). The apparent signal was duplicate/similar content, not a watermark.
- **#5 blind-watermark decode:** Kling images agreed 0.64 vs 0.50 for non-Kling (Gemini, photos) *looked positive* — but cross-batch bit-agreement was round4×round5 = **0.49** and round4×fresh-session = **0.50**. The 0.64 was within-batch content similarity, not a shared message.
- **#2 learn-a-detector (RandomForest on residual spectra, Kling vs Gemini):** in-sample 5-fold AUC = **1.000** (perfectly separable in-sample) — but on content-different held-out data (round5 + the fresh paid images) AUC = **0.59** (scale-normalised) / **0.72** (native resolution), and *every* held-out Kling image scored as non-Kling. The 1.000 was content/batch overfitting; there is no reliable content-independent pixel signature. The faint native-resolution tendency is consistent with Kling's known 2× upscale fingerprint (§5), not a deliberate watermark, and is not a usable detector. Script: [`forensics/pixel_classifier.py`](../forensics/pixel_classifier.py).

### Content control: how two false positives were caught

Both #4 and #5 first produced Kling-specific-looking signals. Both were artifacts of the
sample containing **repeated prompts and near-duplicate batches**. The decisive control in
each case was the same: **compare Kling images that share no content** (different prompt
batches, and a fresh independent session). A real Kling-wide watermark must survive that;
both signals dropped to the random baseline, so neither is a watermark. This is why the
exclusion table below reports these as negatives, and why content-matched controls — not
just "Kling vs non-Kling" — are required.

## What this excludes — and what it does not

| Watermark class | Status | Basis | Detection floor / limit |
|-----------------|--------|-------|-------------------------|
| Added in the download/finishing step | **excluded** | A: identical outside logo | any change > 0 would show |
| Fixed additive pixel pattern (images) | **excluded ≥ ±1 level** | C, with controls | a ±0.5-level or weaker fixed mark is below the floor |
| Shared/fixed frame pattern (video) | **excluded** | D, with controls | keyed-per-video or time-varying marks not covered |
| DWT-DCT mid-frequency (invisible-watermark family) | **excluded** | 0/14, control decoded | tied to that library's scheme/keys |
| Public RivaGAN neural mark | **excluded** | below agreement threshold | only the public weights |
| QIM lattice mark | **excluded** | 0 flagged, control flagged | — |
| Tree-Ring latent mark, via a public model | **excluded** | p = 0.57 vs control 0.0011 | inversion used public SD 1.5, not Kling's model |
| Weak **fixed** additive pattern (content-independent) | **excluded to ≈ ±0.24 levels** | #4 averaging 331 images, cross-batch control | only *fixed* marks; content-keyed not covered |
| Message via `blind_watermark` (DWT-DCT-SVD, default password) | **excluded** | #5, cross-batch control (0.49) vs control round-trip | non-default password / variant scheme not covered |
| Learnable content-independent pixel signature (keyed watermark or strong fingerprint) | **not clearly present** | #2: in-sample AUC 1.0 but held-out 0.59–0.72, no Kling calls | a weak native-res tendency (≈ known upscale fingerprint) remains; resolution-linked, not usable |
| **Content-keyed / learned mark** (e.g. Stable-Signature-style) | **not excluded** | needs Kling's private extractor | undetectable without the key/model |
| **Sub-±0.24-level fixed mark** | **not excluded** | below #4's floor | would not survive ordinary resave/compression |

**Honest conclusion.** No **independently detectable** invisible watermark was found in the
tested IMAGE 3.0 samples (or video frames). This narrows possibility (1)/(3) strongly for the
classes above, but does not reach possibility (2) for pipelines we could not test (mobile app,
mainland service) nor exclude a content-keyed/private-model mark. "No watermark that any method
available to us can detect" is the defensible statement; "no watermark" is not.

## On Kling's own detector (why it can't settle it)

Kling's `BLIND_WATERMARK` check returns `Failed` on **every** file, including a VIDEO 3.0
original it positively identifies as Kling (metadata `Detected`). `Failed` therefore means
the check does not run to a result — it is **not** `NOT_DETECTED` and carries no information
about watermark presence. The *metadata* check does work and exposes the real, reproducible
finding: it reads producer `kling` but not the IMAGE 3.0 USCC form. See
docs/paid-credits-experiment-2026-10-12.md for the matrix.

## What would actually resolve possibility (1) and (2)

- **The API differential (ready to run).** Kling's image API documents `watermark_info`;
  with it enabled the task returns the plain image *and* a `watermark_url` (a watermarked
  copy of the same generation). [`forensics/api_watermark_diff.py`](../forensics/api_watermark_diff.py)
  generates one image, downloads both versions, and diffs them with the validated pair tool —
  a clean with/without comparison from Kling itself, no guessing. It needs a Kling API key
  (`KLING_ACCESS_KEY` / `KLING_SECRET_KEY`; API credits are separate from the website plan).
- **Ground truth from Kling:** a technical description of the blind-watermark scheme, a
  working verification method, or confirmation of which models/routes carry it. This is the
  real unlock; negative experiments cannot substitute for it.
  *Update 2026-10-16:* Kling support wrote that the invisible image watermark is "temporarily
  unsupported". That is a second-hand answer, not a technical description (FINDINGS.md §5).
- **A genuine positive sample** with a documented way to verify it.
- **Untested pipelines:** mobile-app output, upscale and multi-reference, JPEG exports, the
  mainland `可灵` service — each tested first for metadata preservation, then for a pixel signal.
  (Inpaint/Expand and a MOV download were tested; see FINDINGS.md §8 and §9.)

Until then, the repository states the detector gap as its primary finding and the
watermark result as a bounded negative with explicit limits.
