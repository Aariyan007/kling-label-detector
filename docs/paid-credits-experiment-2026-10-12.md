# Paid-plan experiment: with/without watermark, live detector, and baked-in test (2026-10-12)

This closes the project's last open question (GitHub issue #10): **does a Kling image carry an invisible pixel watermark, separate from the visible logo and the text metadata?**

It was run on a paid Standard plan (IMAGE 3.0, 2K HD) using a small number of credits, driving the real web app. It is **detection only**: no watermark or label was removed, forged, or altered by us. The "without watermark" files were produced by Kling's own download option. Only numbers are reported; no difference pattern, ID, or image is included. The real `ProduceID` is redacted.

## What was generated

- 3 scenes, IMAGE 3.0, 2K HD (1760 x 2336): one spice market (eye-level), two rainforest canopies (different compositions).
- Each generation of 2 images cost 2 credits.
- Every file carried the `AIGC` metadata in the IMAGE 3.0 producer form (`0011` + USCC `91110108335469089C` + `10100`), which our `kling-label` tool reads correctly.
- New detail: the `ProduceID` is **per generation batch** — both images from one 2-image request share the same `ProduceID` and the same decoded timestamp (`SGP_PROD_ai_web_3237…`, redacted). So the ID identifies the request, not the individual image.

## Test A — same image, with vs without the visible logo

The default download carries a visible "KlingAI 3.0" logo in the bottom-right corner. Kling's "Without Watermark" download option removes it. We obtained **both versions of the same generated image** and compared them pixel for pixel (`forensics/wm_pair_compare.py`, validated beforehand with a planted-watermark positive control and a null pair).

| Region | Result |
|--------|--------|
| Centre 1024 x 1024 crop | **byte-identical** (0 pixels differ) |
| Whole image | **99.8% of pixels identical**; the only differences are inside the logo corner (rows 95–98%, cols 79–97%) |
| Outside the logo corner (tool mask: rows < 88% or cols < 60%) | **0.000% of pixels differ, mean \|diff\| 0.0000, max 0** |

**Conclusion:** the watermarking/finishing step changes **only the ~8,000 pixels of the visible logo** and leaves every other pixel untouched. No invisible pixel watermark is added alongside the visible one. The API hypothesis — that an imperceptible mark is added in the same finishing step that adds the logo (`watermark_info` → `watermark_url`) — is **disproved** for these images. The `AIGC` metadata is present in **both** versions (it is a legal requirement; the "Without Watermark" option does not touch it).

## Test B — Kling's own detector on a pristine, logo-free original

We uploaded the untouched, full-resolution **without-logo** PNG to Kling's own detector (kling.ai/detection) and read the two checks it reports.

| Check | Kling's detector | Our `kling-label` on the same file |
|-------|------------------|------------------------------------|
| AIGC metadata | **Not detected** | **Found** — `Label 1`, producer USCC `91110108335469089C`, valid `ProduceID` |
| Invisible watermark (`BLIND_WATERMARK`) | **Failed** | — |
| Overall conclusion | **"No supported signal was detected."** | KLING LABEL FOUND |

**Conclusion:** two findings at once, on a single pristine file, side by side.
1. **Kling's own detector cannot read its own IMAGE 3.0 metadata** (the USCC producer form). Our tool reads it; theirs returns "not detected". This reproduces the IMAGE 3.0 detector gap live.
2. **No invisible watermark in a clean original.** Kling's own `BLIND_WATERMARK` check returned `Failed` on a perfect, unmodified file — not a screenshot, not a re-save. If a working invisible watermark existed, Kling's own detector is where it would show.

## Test C — baked-in fixed-pattern test across different scenes

A watermark added at generation time (not the finishing step) could sit identically in every image. If it is a **fixed** additive pattern, different-scene images would share it, so their high-pass residuals would correlate. We measured pairwise residual correlation across the 3 scenes (full frame minus the logo corner, ~3.9M pixels), and calibrated sensitivity by planting the same synthetic pattern into these exact Kling images at several strengths.

| Case | mean \|r\| | z vs null | Verdict |
|------|-----------:|----------:|---------|
| Null (shuffled residual) | 0.00038 | 0 | baseline |
| **Kling real images (cross-scene)** | **0.00040** | **+0.1** | **no shared pattern** |
| Positive control: ± 2 levels planted | 0.01749 | +58.4 | DETECTED |
| Positive control: ± 1 level planted | 0.00440 | +13.7 | DETECTED |
| Positive control: ± 0.5 level planted | 0.00110 | +2.5 | below detection |

**Conclusion:** the positive controls prove the test would catch a fixed baked-in additive watermark of **± 1 level or stronger** (z = 13.7 and 58.4). The real Kling images sit **exactly at the null (z = +0.1)**. So there is no fixed baked-in watermark down to about ± 1 level (≈ 0.4% of full scale); anything weaker would be too fragile to survive a resave and useless as a robust mark. (This test targets a *fixed* pattern; *keyed* per-image marks were addressed by the earlier neural-decoder and latent-inversion tests, also negative with positive controls.)

## Test D — video: is there a watermark spread over the frames?

A video watermark could live in the frames rather than the bitstream (the known `kling-ai` H.264 SEI marker is bitstream, not decoded pixels). We tested for a pattern that repeats across frames and is **shared between different Kling videos**: extract ~40 frames per video, take the per-frame high-pass residual, average over frames (moving content cancels, a persistent pattern survives), then correlate those temporal-average residuals across videos.

Videos: 3 different Kling videos (a steam clip, an Omni clip, and one freshly generated rainy-city clip, VIDEO 3.0 720p), 1 pre-rules Kling video, 2 non-Kling controls. A note on method: two of our sample files turned out to be the same video (identical MD5) — caught because their correlation was exactly +1.000 — so one fresh video was generated to keep three genuinely different Kling clips.

| Comparison | mean \|r\| |
|------------|-----------:|
| **Kling vs Kling** (3 different clips, 3 pairs) | **0.005** |
| Kling vs control | 0.004 |
| control vs control | 0.004 |
| Kling vs pre-rules | 0.008 |
| **Positive control** (same ±2 pattern planted in two clips) | **0.045** |

**Conclusion:** different Kling videos share **no more hidden signal than unrelated videos do** (0.005 ≈ 0.004). The planted positive control sits ~10× higher (0.045), so a shared fixed frame watermark would have been obvious. No invisible watermark is detectable in the decoded video frames. (Same honest limit as the images: a keyed per-video mark, or a time-varying mark, is not fully excluded by a fixed-pattern test.)

## Overall

Across every method available to an outside researcher **and** Kling's own detector, there is **no detectable invisible watermark** on Kling IMAGE 3.0 images (or its videos):

- the "without watermark" step removes only the visible corner logo (Test A);
- Kling's own invisible-watermark check fails on a pristine original (Test B);
- no fixed baked-in pattern exists down to ± 1 level, with a validated positive control (Test C);
- no shared frame watermark across different videos, with a validated positive control (Test D);
- earlier tests ruled out common schemes, QIM, public neural decoders, and Tree-Ring-style latent marks (FINDINGS §5, §8).

The only AI markings on these images are the **visible corner logo** (easily removed) and the **`AIGC` text metadata** — and that metadata is in a form **Kling's own detector cannot read**. In practice, a Kling IMAGE 3.0 image passes Kling's own checker as "no signal".

**Caveat (honest limits):** this does not prove a mathematical impossibility. A mark readable only with Kling's private model/key, or a fixed mark weaker than ± 1 level, cannot be excluded — but such a mark would not survive ordinary compression and so could not serve the traceability Kling's documentation claims.
