# Dataset manifest (frozen)

This records the sample set the watermark investigation ran on, so results can be
read against a fixed, described corpus. **No sample files, filenames, real `ProduceID`
values, or generation timestamps appear here or anywhere in the repository** (project
rule: samples are local-only and git-ignored). Only counts and categories are given.

Each physical sample is referenced internally by an **anonymous ID** (`S0001`, `S0002`, …)
in the owner's local log; the mapping is not published.

## Local corpus (collected 2026-10-08 to 2026-10-09)

**505 files — 498 images, 7 videos.** By embedded producer:

| Producer tag | Count | Means |
|--------------|------:|-------|
| USCC `0011…335469089C…10100` | 335 | IMAGE 3.0 |
| `kling` | 36 | IMAGE 2.1, or VIDEO 3.0 |
| no `AIGC` label | 134 | non-Kling controls, other-AI, and pre-rules Kling |

By role (top-level sample groups):

| Role | Count | Purpose |
|------|------:|---------|
| round2–round5 (+ `_zip`) | ~390 | Kling IMAGE 3.0 / 2.1 originals, multiple accounts and batches |
| control | 49 | non-Kling PNG/JPEG (screenshots, photos) — negative controls |
| other_ai | 15 | Google Gemini images (a different AI generator) |
| colab_upload | 55 | 512×512 centre crops prepared for the Colab latent-inversion test |
| edit_test | 6 | Kling Inpaint / Expand outputs |
| detector_test (×3) | 16 | files used against Kling's own detector |
| control_video | 2 | non-Kling videos (one stock clip, one other-AI video) |

Resolution (images): the dominant size is **1536×2720** (2K, 9:16); also 2048×2048 (2K 1:1),
768×1360 (1K), 512×512 (crops), and a few others. 2K is exactly 2× the 1K dimensions
(evidence of a 2× upscale; FINDINGS §6).

## Paid-plan set (generated 2026-10-11 to 2026-10-12)

Produced for the decisive experiments (docs/paid-credits-experiment-2026-10-12.md),
stored locally outside the repo:

| Item | Count | Notes |
|------|------:|-------|
| IMAGE 3.0 2K originals | 4 | 2 scenes (spice ×2, rainforest ×2); one scene downloaded **with** and **without** the visible logo |
| VIDEO 3.0 720p original | 1 | freshly generated (rainy-city), distinct scene |
| Reused Kling videos | 2 | steam clip, Omni clip (from the local corpus) |

## Data-hygiene note (found 2026-10-12)

The `round3` and `round4` IMAGE 3.0 groups are **near-duplicate batches** (averaged-residual
correlation r = 0.986), i.e. they largely contain the same generations. This matters: naive
pooling of all samples inflates any "shared pattern" measurement with duplicate content. The
#4/#5 analyses therefore report **cross-batch** results (e.g. round4 vs round5), which are the
content-independent comparisons, and treat within-pool numbers as upper bounds only.

## Discovery vs validation

To avoid tuning a detector to the same data it is evaluated on:
- **Discovery** (building/tuning methods, choosing thresholds): the round2–round4 Kling
  images and the controls.
- **Held-out validation**: the paid-plan 2026-10-12 set and round5 were analysed only
  *after* the metrics and thresholds in [methodology.md](methodology.md) were fixed.

## Negative controls

Three kinds, matched as closely as the pipeline allows:
- **non-Kling photos / screenshots** (`control`) — different capture and compression history;
- **other-AI images** (`other_ai`, Gemini) — AI-generated but not by Kling;
- **synthetic controls generated in code** — used inside every forensic script as the
  positive-control carrier (so a negative on real files is only trusted when the matching
  synthetic positive is detected).

Caveat (from the review): screenshot/photo controls do not share Kling's exact export path.
Where it mattered, Kling-vs-Kling comparisons were used so both sides share the same pipeline.
