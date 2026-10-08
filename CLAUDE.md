# Project guide for Claude

## Goal

This is a portfolio project for a **reverse-engineering job**. It reverse-engineers Kling AI's hidden "AI-generated" label (China GB 45438-2025) and will ship a small **detection-only** command-line tool, `kling-label`. A clear write-up matters more than feature count. The owner prefers very simple English.

## Hard rules

1. **Detection only.** Never write code, docs or steps that remove, forge, strip or bypass labels or watermarks.
2. **No private data in git.** Never commit sample images, personal photos, real `ProduceID` values, generation timestamps or capture logs. Tests must build their own synthetic fixtures in code with made-up IDs such as `SGP_PROD_ai_web_300000000123456`. Before every commit, scan the staged diff for real IDs (15-digit numbers starting `3234`) and image files.
3. Samples live only on the owner's laptop (`samples/`, ignored by git). A cloud session has **no sample files**, so work from FINDINGS.md and synthetic fixtures.

## What is known (details in FINDINGS.md)

- **PNG:** a `tEXt` chunk with keyword `AIGC`, holding JSON: `Label`, `ContentProducer`, `ProduceID`, `ReservedCode1`, `ContentPropagator`, `PropagateID`, `ReservedCode2`.
- **MP4:** the same JSON under the `mdta` key `AIGC` in `moov/udta/meta` (`keys` + `ilst` boxes).
- **`ProduceID`:** `SGP_PROD_ai_web_` + 15 digits. Creation time in UTC = `1468028519 + digits // 1_000_000` (Unix seconds, confirmed to ±0.5 s). The remaining 6 digits are probably a server number (3 digits) and a sequence counter (3 digits); unconfirmed.
- **`ContentProducer`:** `kling` (IMAGE 2.1, VIDEO 3.0), or `0011` + an 18-character USCC (valid GB 32100 checksum) + `10100` (IMAGE 3.0).
- **No pixel watermark.** SynthID, TrustMark, Watermark Anything, `invisible-watermark` and a PRNU-style test all found nothing.
- Videos made before 2025-09-01 have no label.

## Status

- Research: done and published.
- Brainstorming: approach A was approved (a write-up plus a small CLI). Design part 1 (CLI behavior, below) is **waiting for the owner's approval**. Still to come: part 2 (code layout), part 3 (tests and README), then a spec in `docs/superpowers/specs/`, then a plan, then TDD implementation.
- Still to test: a mobile-app sample (does the client field say `ai_app`?).

## Design part 1 (proposed, not yet approved)

```
$ kling-label image.png
File:     image.png (PNG, 1536x2720)
Result:   KLING LABEL FOUND (AI-generated)
Where:    PNG text chunk "AIGC" (China GB 45438-2025 format)
  Label             1  (= AI-generated)
  ContentProducer   kling
  ProduceID         SGP_PROD_ai_web_300000000123456
    region SGP · system PROD · made on ai_web
    made at 2025-11-xx xx:xx:xx UTC (decoded from ID)
  ContentPropagator kling
Privacy:  this ID reveals when the image was made.
```

- No label: "NO KLING LABEL FOUND. The file may still be AI-made; screenshots, re-saves and chat apps remove this label."
- Several files: `kling-label a.png b.mp4` reports one result per file.
- `--json` prints the same result as data.
- Formats: PNG and MP4. Decode the USCC producer form as well.
- Python, standard library only for parsing (no Pillow needed to read chunks or boxes).
