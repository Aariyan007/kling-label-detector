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
| **Content-keyed / learned mark** (e.g. Stable-Signature-style) | **not excluded** | needs Kling's private extractor | undetectable without the key/model |
| **Sub-±1-level fixed mark** | **not excluded** | below C's floor | would not survive ordinary resave/compression |

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

- **Ground truth from Kling:** a technical description of the blind-watermark scheme, a
  working verification method, or confirmation of which models/routes carry it. This is the
  real unlock; negative experiments cannot substitute for it.
- **A genuine positive sample** with a documented way to verify it.
- **Untested pipelines:** mobile-app output, edit/expand/upscale, JPEG/MOV exports, the
  mainland `可灵` service — each tested first for metadata preservation, then for a pixel signal.

Until then, the repository states the detector gap as its primary finding and the
watermark result as a bounded negative with explicit limits.
