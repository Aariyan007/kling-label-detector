# Watermark hunt: results on the real samples

Run locally on 2026-10-09 following [watermark-hunt-plan.md](watermark-hunt-plan.md). Numbers and row indices only; no file names, IDs or decoded messages.

## Setup notes

- Installed: opencv-python-headless, PyWavelets, onnxruntime, onnx, invisible-watermark, blind-watermark (Python 3.14).
- **VideoSeal: not run.** `pip install videoseal` failed with a dependency conflict on Python 3.14.
- **StegaStamp, HiDDeN: not run.** No ONNX model files (optional in the plan).

## Step 1: controls

All lines PASS, INFO or SKIPPED; no FAIL. RivaGAN positive control: bit accuracy 0.97, marked agreement 0.95 (T 25.9), clean agreement 0.54 (T 1.4). `forensics.test_wmhunt`: 10/10 tests pass.

## Step 2: QIM lattice scan (images)

| Group | n | Flagged | Score median / max |
|-------|--:|--------:|--------------------|
| Kling normal | 27 | 4 | 0.0 / 126.7 |
| Kling IMAGE 3.0 textured | 40 | 0 | 0.0 / 45.4 |
| Kling plain | 20 | 0 | 0.0 / 0.0 |
| Control PNG | 26 | 17 | 185.5 / 1281.2 |
| Control JPEG | 23 | 21 | 1075.7 / 4026.9 |

The 4 flagged "normal" files are all from one batch of near-flat grey IMAGE 2.1 images, with different steps (20.9 to 25.6) and contrast just above the threshold (8.2 to 10.3). This matches gradient-quantization structure, which also flags many screenshot controls.

**Verdict: ruled out** for this family (plan rule: 0 Kling files flagged in the textured group, which has the most room for a mark).

## Step 3: public neural decoders (images)

| Group | RivaGAN agreement | T |
|-------|------------------:|--:|
| Null (controls half vs half) | 0.56 | 1.1 |
| Kling normal (n=27) | 0.69 | 1.1 |
| Kling IMAGE 3.0 textured (n=40) | 0.71 | 4.8 |

**Verdict: not confirmed.** The plan requires agreement >= 0.8 and T >= 4 in both Kling groups. The modest excess fits decoder bias on visually similar AI images (the textured set came from 10 prompts), not a shared message.

## Step 4: video

- QIM on H.264 frames: 0 flagged in the 2 post-rules Kling videos, the pre-rules Kling video and 2 non-Kling control videos (one stock clip, one AI video from another provider). A weak test for video.
- RivaGAN, post-rules Kling (2 videos) vs controls (2 videos): agreement 0.66, T 7.5. **Not confirmed** (agreement below 0.8; with only 2 videos per group and 32 correlated frames each, T is not reliable). The pre-rules comparison needs at least 2 pre-rules videos and could not run.

## Patent leads (checked by hand)

None of the three leads in the research note belongs to Kuaishou:
- US 12,579,598: Tencent (QIM in the Cb channel of video frames, a family the QIM scan covers).
- US 11,869,112: Huawei (3D-model watermarking).
- CN110322386A: China Mobile (text watermarking).

## Overall

No public method tested here finds a watermark in Kling images or videos. This rules out QIM blind watermarks and the public RivaGAN weights. It does not rule out an in-house keyed or learned watermark; only Kling's own detector (plan step 5) can settle that.
