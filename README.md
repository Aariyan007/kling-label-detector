# kling-label-detector

Reverse-engineering the hidden "AI-generated" label that Kling AI puts in its images and videos, plus `kling-label`, a small detection-only tool that reads it.

Status: **research findings published, `kling-label` v0.1 ready.** The detailed write-up is in [FINDINGS.md](FINDINGS.md).

## Install

Needs Python 3.10 or newer. No other packages.

```
pipx install git+https://github.com/Aariyan007/kling-label-detector
```

or, from a copy of this repository:

```
pip install .
```

## Usage

```
$ kling-label image.png
File:     image.png (PNG, 1536x2720)
Result:   KLING LABEL FOUND (AI-generated)
Where:    PNG text chunk "AIGC" (China GB 45438-2025 format)
  Label             1  (= AI-generated)
  ContentProducer   kling
  ProduceID         SGP_PROD_ai_web_300000000123456
    region SGP · system PROD · made on ai_web · worker 123
    made at 2026-01-10 07:01:59.456 UTC (decoded from ID, ±1 s)
  ContentPropagator kling
Privacy:  this ID reveals when the image was made.
```

(The ID above is made up.)

- **Several files:** `kling-label a.png b.mp4 c.jpg` prints one block per file.
- **JSON:** `kling-label --json a.png` prints a list with one object per file: `result`, `format`, `width`, `height`, `found_by`, `where`, the raw `label`, the `decoded` ID and producer, and any `warnings`.
- **Exit code:** `0` every file has a label, `1` at least one file has none, `2` a file could not be read.

What the result lines mean:

| Result | Meaning |
|--------|---------|
| `KLING LABEL FOUND` | The file has the GB 45438-2025 label and it comes from Kling. |
| `AI LABEL FOUND (... producer is not Kling)` | The file has the same kind of label, but from another service. |
| `AIGC LABEL FOUND, BUT ITS CONTENT COULD NOT BE READ` | An `AIGC` entry exists but is not valid label JSON. |
| `NO KLING LABEL FOUND` | No label. **This does not mean the file is human-made.** Screenshots, re-saves and chat apps remove the label, and there is no pixel watermark to fall back on. |

### Where the tool looks

1. PNG text chunks named `AIGC` (`tEXt`, where Kling puts it today, and also `zTXt` and `iTXt`).
2. MP4 / MOV metadata: the `mdta` key `AIGC` in any `meta` box under `moov`.
3. XMP metadata: an `AIGC` field, which GB 45438-2025 also allows.
4. Fallback for every file type (JPEG, WebP, unknown): a raw byte scan for the label JSON.

The tool only reads files. It never changes them.

### Run the tests

```
python -m unittest
```

The tests build their own fake PNG, MP4 and JPEG files in memory with made-up IDs. No sample files are needed.

## Background

Since 1 September 2025, Chinese rules (the *Measures for Labeling AI-Generated Synthetic Content* and the national standard **GB 45438-2025**) require AI services to mark their output twice:

- an **explicit** label people can see (Kling's corner logo), and
- an **implicit** label hidden in the file.

Kling (by Kuaishou) is one of the most used AI image and video generators. This project documents exactly what Kling's implicit label is, where it lives, what it reveals, and what it does not protect against.

## Key findings (October 2026)

1. **The hidden label is plain file metadata.** Every Kling PNG tested since the rules took effect carries a PNG `tEXt` chunk named `AIGC` holding JSON with the GB 45438 fields `Label`, `ContentProducer`, `ProduceID`, `ContentPropagator`, `PropagateID`, `ReservedCode1` and `ReservedCode2`. Videos carry the same JSON in the MP4 `moov/udta/meta` box under the key `AIGC`.
2. **There is no invisible pixel watermark.** A noise-residual (PRNU-style) analysis of 24 images, plus two near-uniform images whose interiors were 100% one value in the red and green channels, found no hidden pixel pattern, and Google SynthID Detector, Adobe TrustMark, Meta Watermark Anything and Stable Diffusion's `invisible-watermark` all found nothing. A screenshot, re-save or chat-app upload therefore removes the only machine-readable label.
3. **`ProduceID` leaks the creation time to the second.** The numeric part of `ProduceID` is `seconds × 10^6 + 6 more digits`, where the seconds count from 2016-07-09 01:41:59 UTC. Five images generated at measured times all matched within 0.45 s.
4. **The model decides the producer format.** IMAGE 2.1 and VIDEO 3.0 write `ContentProducer: "kling"`. IMAGE 3.0 writes `0011` + `91110108335469089C` + `10100`, where the middle part is the Chinese Unified Social Credit Code of Beijing Kuaishou Technology Co., Ltd., Kling's developer. The same account produced both formats.
5. **2K images appear to be 2x-upscaled 1K images.** 1K output is 768x1360 and 2K output is exactly 1536x2720. A period-2 pixel grid found in the noise analysis matches this.

See [FINDINGS.md](FINDINGS.md) for method, evidence and limits.

## Ethics and scope

- **Detection only.** This project reads and explains labels. It does not remove, forge or bypass them, and it publishes no removal method.
- **No personal data.** No sample images, real IDs or capture logs are in this repository. Examples use made-up IDs.
- Findings come from images the author generated on their own accounts through the normal Kling website.

## Roadmap

- [x] Locate and decode the implicit label
- [x] Test for a pixel watermark
- [x] Decode the `ProduceID` time field
- [x] `kling-label` command-line tool (reads a file, reports the label and decoded fields)
- [x] Video (MP4) label location
- [ ] Mobile-app samples
