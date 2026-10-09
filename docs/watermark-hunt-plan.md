# Watermark hunt: what to run on your laptop

2026-10-09. Detection only. Goal: find out whether Kling images (and videos) carry an invisible pixel watermark, using the new tests in `forensics/wmhunt.py`. Background and sources: [watermark-research-2026-10-09.md](watermark-research-2026-10-09.md).

The cloud session has no samples, so every test was checked only on synthetic images. Your job is to run the same tests on the real files in `samples/` and report the summary lines.

## 0. Rules for this hunt

- Run everything on the **untouched downloads**. Do not re-save or convert them first.
- The new commands print **numbers and row indices only**: no file names, no `ProduceID`, no decoded message. Paste only those lines into notes or a PR.
- If a test does flag Kling files, **do not publish** the step size, feature, decoded bits or any pattern. Report only "flagged / not flagged" and the scores. Never publish what *removes* a mark.
- Nothing goes into git from `samples/`. Run `scripts/check_staged.sh` before any commit.

## 1. Setup (once)

```bash
python -m venv .venv
.venv/bin/pip install pillow numpy scipy opencv-python-headless PyWavelets onnxruntime onnx
.venv/bin/pip install --no-deps invisible-watermark blind-watermark   # --no-deps: avoids pulling in torch and a second OpenCV
# optional, for VideoSeal (downloads its weights from Meta on first use):
.venv/bin/pip install torch videoseal
```

Optional StegaStamp and HiDDeN: these have no pip package. Only do this if you want them; the chance that Kling uses these exact public weights is low.

- StegaStamp: the official TensorFlow model from `github.com/tancik/StegaStamp`, converted with `tf2onnx` into an encoder and a decoder `.onnx` file. Then `export STEGASTAMP_ENCODER=/path/enc.onnx STEGASTAMP_DECODER=/path/dec.onnx`.
- HiDDeN: a checkpoint from `github.com/ando-khachatryan/HiDDeN` (or one you train), exported with `torch.onnx.export` as encoder (image + 30-bit message) and decoder. Then `export HIDDEN_ENCODER=... HIDDEN_DECODER=...`.

The adapter works out the image and message inputs from the ONNX shapes. If the files are missing, the tests say SKIPPED; they never fake a result.

## 2. The tests, in order

Run all commands from the repository root. Times are rough, for a laptop CPU.

### Step 1: controls (about 4 minutes)

```bash
.venv/bin/python forensics/audit.py controls
```

Every line must say PASS, INFO or SKIPPED. **If any line says FAIL, stop**: the matching detector is broken on your machine, and its results below mean nothing. VideoSeal should say PASS if you installed it.

Also run the unit tests once: `.venv/bin/python -m unittest forensics.test_wmhunt`.

### Step 2: QIM lattice scan on images (about 20 s per 2K image)

This is the main new test. It looks for the "blind watermark" family (DWT-DCT-SVD quantization) without needing a key.

```bash
.venv/bin/python forensics/audit.py qim --limit 40
```

Default groups:

| Group | Files |
|---|---|
| Kling normal | `samples/kling_*Text_to_Image*.png` (IMAGE 2.1) + `samples/round2/r2_time_{1,2,3}.png` (IMAGE 3.0, timed) |
| Kling IMAGE 3.0 textured | `samples/round5/*.png` (the 54 textured images) |
| Kling plain | first 20 of the plain IMAGE 3.0 images (round 2, 3, 4) |
| Control PNG | PNG files in `samples/control/` |
| Control JPEG | JPEG files in `samples/control/` (expect "JPEG history"; these are not a fair control for this test) |

Also run it on your **lossless no-label copy** of A2 (same pixels as the original, metadata chunk left out):

```bash
.venv/bin/python forensics/audit.py qim --kling 'samples/<A2 original>.png' --kling 'samples/<A2 no-label>.png' --control 'samples/control/*.png'
```

### Step 3: public neural decoders on images (about 20 s per 2K image per model)

```bash
.venv/bin/python forensics/audit.py decoders --limit 40
```

This decodes every image with RivaGAN (and StegaStamp/HiDDeN if set up) and asks: do Kling images share **one message**, compared with the PNG controls? It prints a null line (controls split in half) to show what "no difference" looks like.

### Step 4: video

Put at least **3 non-AI videos** in `samples/control_video/` (for example short phone clips, H.264 MP4, ideally 720p). Then run the post-rules Kling videos and, separately, the 2025 pre-rules Kling video:

```bash
# post-rules Kling videos (VIDEO 3.0 MP4 and the Omni MOV)
.venv/bin/python forensics/audit.py video --kling 'samples/round2/<VIDEO 3.0>.mp4' --kling 'samples/<Omni>.mov' --control 'samples/control_video/*'
# the VIDEO 1.5 file from July 2025, made before the labeling rules
.venv/bin/python forensics/audit.py video --kling 'samples/round2/<VIDEO 1.5>.mp4' --control 'samples/control_video/*'
```

The pre-rules video is a useful control: it comes from the same company and pipeline, but from before Kling had any reason to add a mark.

### Step 5: the decisive experiment (Kling's own detector)

When your account has detection quota again, run the 4-file batch from the audit (section G): A2 original, A2 lossless no-label copy, a never-generated image of similar content, and the no-label copy after JPEG q85. Only Kling's detector can confirm an in-house learned or in-generation mark.

## 3. How to read the results

A detector result counts only if that detector's control passed in Step 1.

| Test | Confirms a watermark (needs all) | Rules it out | Inconclusive |
|---|---|---|---|
| `qim` | Kling textured groups flagged in **at least 80%** of files; **0** PNG controls flagged; the flagged files share the **same feature and step** (or simple multiples); the lossless no-label copy is flagged too | **0** Kling files flagged in the normal and textured groups, with controls clean | Some files flagged with different features/steps; or controls also flagged (then it is pipeline structure, not a mark) |
| `decoders` (each model) | In **both** Kling groups: agreement **>= 0.8** and **T >= 4 and >= 3x the null T** | T within the range of the null (about 1-3) in both Kling groups | High T in only one group, or a high null T (controls too varied: add more PNG controls) |
| `video` VideoSeal | Detection logit on post-rules Kling videos close to the positive-control **marked** value; control videos and the pre-rules video close to the **clean** value | Post-rules Kling videos look like the controls | Mixed |
| `video` RivaGAN | Agreement >= 0.8 and T >= 4 for post-rules Kling vs control videos, and not for the pre-rules video | T about 1-3 | Fewer than 2 videos per group: not enough data |
| `video` QIM | Post-rules frames flagged, controls and pre-rules video not | No frames flagged (note: strong H.264 compression erases this family anyway, so a video negative is weak) | - |

What a full negative means: Kling does **not** use (a) a fixed-step QIM mark on DWT-DCT / DWT-DCT-SVD blocks at full or half resolution, or (b) the public RivaGAN, StegaStamp, HiDDeN or VideoSeal weights. It does **not** rule out an in-house learned watermark, a keyed-dither QIM, or an in-generation (latent-noise) watermark. For those, only Step 5 can decide.

What a positive means: write down only the group, the share of flagged files and the scores. Then check that the signal is absent from the PNG controls and from the pre-rules video, and present in the lossless no-label copy (so it does not depend on metadata).

## 4. What to send back

For each command: the `PASS/FAIL/SKIPPED` lines of `controls`, and the group summary lines (`n=`, `flagged`, `score median/max`, `agreement`, `T`, `VideoSeal detection logit`). The per-file rows (`#0`, `#1`, ...) are fine to share too; they contain no names or IDs.
