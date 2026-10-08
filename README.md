# kling-label-detector

Reverse-engineering the hidden "AI-generated" label that Kling AI puts in its images, and (next) a small detection-only tool that reads it.

Status: **research findings published, tool in design.** The detailed write-up is in [FINDINGS.md](FINDINGS.md).

## Background

Since 1 September 2025, Chinese rules (the *Measures for Labeling AI-Generated Synthetic Content* and the national standard **GB 45438-2025**) require AI services to mark their output twice:

- an **explicit** label people can see (Kling's corner logo), and
- an **implicit** label hidden in the file.

Kling (by Kuaishou) is one of the most used AI image and video generators. This project documents exactly what Kling's implicit label is, where it lives, what it reveals, and what it does not protect against.

## Key findings (October 2026)

1. **The hidden label is plain file metadata.** Every Kling PNG tested since the rules took effect carries a PNG `tEXt` chunk named `AIGC` holding JSON with the GB 45438 fields `Label`, `ContentProducer`, `ProduceID`, `ContentPropagator`, `PropagateID`, `ReservedCode1` and `ReservedCode2`. Videos carry the same JSON in the MP4 `moov/udta/meta` box under the key `AIGC`.
2. **There is no invisible pixel watermark.** A noise-residual (PRNU-style) analysis of 24 images, plus two near-uniform images whose interiors were 100% one value in the red and green channels, found no hidden pixel pattern. A screenshot, re-save or chat-app upload therefore removes the only machine-readable label.
3. **`ProduceID` leaks the creation time to the second.** The numeric part of `ProduceID` is `seconds × 10^6 + 6 more digits`, where the seconds count from 2016-07-09 01:41:59 UTC. Five images generated at measured times all matched within 0.45 s.
4. **The model decides the producer format.** IMAGE 2.1 and VIDEO 3.0 write `ContentProducer: "kling"`. IMAGE 3.0 writes `0011` + an 18-character Chinese Unified Social Credit Code (valid checksum, registered in Haidian District, Beijing) + `10100`. The same account produced both formats.
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
- [ ] `kling-label` command-line tool (reads a file, reports the label and decoded fields)
- [x] Video (MP4) label location
- [ ] Mobile-app samples
