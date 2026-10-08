# Spec: `kling-label` command-line tool

Date: 2026-10-08. Status: approved (parts 1, 2 and 3).

## 1. Goal

A small, **detection-only** tool that reads a file and says whether it carries
Kling AI's hidden "AI-generated" label (China GB 45438-2025), and explains what
the label contains. It never changes files.

Background and evidence: [FINDINGS.md](../../../FINDINGS.md).

## 2. Behavior (part 1)

```
$ kling-label image.png
File:     image.png (PNG, 1536x2720)
Result:   KLING LABEL FOUND (AI-generated)
Where:    PNG text chunk "AIGC" (China GB 45438-2025 format)
  Label             1  (= AI-generated)
  ContentProducer   kling
  ProduceID         SGP_PROD_ai_web_300000000123456
    region SGP · system PROD · made on ai_web
    made at 2026-01-10 07:01:59 UTC (decoded from ID)
  ContentPropagator kling
Privacy:  this ID reveals when the image was made.
```

- No label: `Result:   NO KLING LABEL FOUND. The file may still be AI-made;
  screenshots, re-saves and chat apps remove this label.`
- Several files: `kling-label a.png b.mp4` prints one block per file, with a
  blank line between blocks.
- `--json` prints a JSON array with one object per file (fields in section 5).
- `PropagateID` is printed only when it differs from `ProduceID`.
  `ReservedCode1` and `ReservedCode2` are printed only when they are not null.
- USCC producer form: the producer line is split into its parts and the check
  digit result is shown.

### Result kinds

| Kind | Headline | When |
|------|----------|------|
| `kling_label` | `KLING LABEL FOUND (AI-generated)` | Label JSON found and it looks like Kling (see below). If `Label` is not `"1"`, the headline shows `(Label = X)` instead. |
| `other_label` | `AI LABEL FOUND (GB 45438-2025, producer is not Kling)` | Label JSON found, but nothing in it points to Kling. |
| `unreadable_label` | `AIGC LABEL FOUND, BUT ITS CONTENT COULD NOT BE READ` | An `AIGC` entry exists, but it is not a JSON object. |
| `no_label` | `NO KLING LABEL FOUND. ...` | Nothing found. |
| `error` | `ERROR: <reason>` | File missing, unreadable, or broken in a way that stops parsing. |

"Looks like Kling" means any of: `ContentProducer` or `ContentPropagator` is
`kling`; the producer contains the USCC seen in Kling IMAGE 3.0 output
(`91110108335469089C`); or `ProduceID` has the Kling shape
`<REGION>_<SYSTEM>_<client>_<15 digits>`.

### Exit codes

- `0`: every file has a label (any of the three "found" kinds).
- `1`: at least one file has no label (and none had an error).
- `2`: at least one file had an error, or the arguments were wrong.

## 3. Where the tool looks (the "find" order)

For each file, the tool first works out the type from the first bytes (not
the file name):

| Type | How it is recognised | Full parser |
|------|----------------------|-------------|
| PNG | 8-byte PNG signature | yes |
| MP4 / MOV | box type `ftyp` (or `moov`, `mdat`, `free`, `wide`) at byte 4 | yes (same box format) |
| HEIF / AVIF | `ftyp` with brand `heic`, `mif1`, `avif`, ... | MP4 walker, then raw scan |
| JPEG, WebP, GIF, unknown | other magic bytes | no, raw scan only |

Then, in order, it stops at the first place that has a label:

1. **PNG text chunks:** `tEXt`, `zTXt` (zlib-compressed) and `iTXt`
   (possibly compressed) with keyword `AIGC`. This is where Kling puts it
   today. The other two types are checked in case this changes.
2. **MP4 metadata:** every `meta` box under `moov` (including inside `udta`
   and `trak`) that has `keys` + `ilst`; the value of the `mdta` key `AIGC`.
   Both the ISO form of `meta` (with a 4-byte version/flags header) and the
   QuickTime form (without it) are handled.
3. **XMP:** GB 45438-2025 also allows the label inside XMP. In any XMP packet
   (PNG `iTXt` keyword `XML:com.adobe.xmp`, or found by the raw scan) the tool
   looks for an `AIGC` attribute or element in any namespace and reads its
   JSON value.
4. **Raw byte scan (fallback):** if steps 1–3 found nothing, the whole file is
   read in blocks and searched for a JSON object that contains
   `"ProduceID"`, or for an XMP `AIGC` field. A hit is reported as
   `raw byte scan at offset N (not a standard place)`. This also covers
   formats nobody has tested yet (JPEG, WebP, MOV variants).

Not done: reading pixels. The research found no pixel watermark, so the ID
cannot be read from pixels.

## 4. Decoding

### `ProduceID`

Pattern: `<REGION>_<SYSTEM>_<client>_<15 digits>`, for example
`SGP_PROD_ai_web_300000000123456`.

- `created_unix = 1468028519 + digits // 1_000_000`, printed as UTC.
- The last 6 digits are kept in JSON as `extra_digits`; their meaning is
  unconfirmed, so the text output does not explain them.
- An ID with another shape is printed as it is, with no decoding.

### `ContentProducer`

- `kling`: printed as it is.
- USCC form: the tool looks for an 18-character window that passes the
  GB 32100-2015 check digit. If found, it prints
  `prefix · USCC · suffix` and `(check digit valid)`. If the string has the
  `0011` + 18 + `10100` shape but the check digit is wrong, it says so.

USCC check digit: characters `0123456789ABCDEFGHJKLMNPQRTUWXY` (values 0–30),
weights `1 3 9 27 19 26 16 17 20 29 25 13 8 24 10 30 28`;
`check = (31 - sum % 31) % 31`.

## 5. JSON output

```json
[
  {
    "file": "image.png",
    "format": "PNG",
    "width": 1536,
    "height": 2720,
    "result": "kling_label",
    "found_by": "png_text_chunk",
    "where": "PNG text chunk \"AIGC\" (China GB 45438-2025 format)",
    "label": {"Label": "1", "ContentProducer": "kling", "...": "..."},
    "decoded": {
      "produce_id": {"region": "SGP", "system": "PROD", "client": "ai_web",
                     "digits": "300000000123456", "extra_digits": "123456",
                     "created_unix": 1768028519,
                     "created_utc": "2026-01-10T07:01:59Z"},
      "producer": {"form": "kling"}
    },
    "warnings": [],
    "error": null
  }
]
```

`found_by` is one of `png_text_chunk`, `mp4_metadata`, `xmp`, `raw_scan`, or
null.

## 6. Code layout (part 2)

```
pyproject.toml            no runtime dependencies; installs `kling-label`
src/kling_label/
  __main__.py             python -m kling_label
  cli.py                  arguments, loop over files, text / JSON, exit code
  detect.py               the find order in section 3; builds the result
  sniff.py                file type from magic bytes
  png.py                  PNG chunk walker (IHDR size, text chunks)
  mp4.py                  MP4 box walker (meta/keys/ilst, tkhd size)
  scan.py                 raw byte scan and XMP field reader
  label.py                result object, JSON payload checks, "is Kling?"
  produce_id.py           ProduceID split and time decode
  producer.py             ContentProducer forms and USCC check digit
tests/
  fakes.py                builds fake PNG / MP4 / JPEG bytes in memory
  test_*.py               one file per module
scripts/check_staged.sh   blocks commits with images or real-looking IDs
```

Rules for the parsers:

- Standard library only (`struct`, `zlib`, `json`, `re`, `datetime`, `html`).
- Never load a whole video: jump from header to header with `seek`; read only
  small boxes and text chunks into memory (limit 16 MiB each).
- Check every length. A file that ends early gives a warning, and whatever
  was found before the cut is still reported (but never a half-read value).
  A file whose first bytes match no known type is treated as `unknown` and
  gets the raw scan. Only a missing, unreadable or empty file gives an
  `error` result. No input may crash the tool.
- A wrong PNG CRC on a text chunk gives a warning; the chunk is still read.
- Read-only: files are opened with `"rb"` only.
- Text from a file is printed with control characters escaped, so a file
  cannot send commands to the terminal.
- The raw scan only runs its regexes on blocks that contain `"ProduceID"`
  or `AIGC`, so a large video without a label is checked quickly.

## 7. Tests (part 3)

Written first (TDD) with `unittest`; all test files are built in memory by
`tests/fakes.py` with made-up IDs such as `SGP_PROD_ai_web_300000000123456`.
No image or video files are stored in git.

- PNG: label in `tEXt`; in `zTXt`; in `iTXt` (plain and compressed); in XMP;
  after `IDAT`; no label; damaged signature (still found by raw scan); file
  cut in the middle of a chunk; wrong CRC; size from IHDR.
- MP4: label present (ISO and QuickTime `meta`); only an `encoder` key; meta
  inside `trak`; 64-bit box size; cut-off box; size from `tkhd`.
- Raw scan: JPEG with the JSON in a comment segment; JPEG with XMP; label
  split across a block boundary; nothing found.
- ProduceID: decode of the made-up ID gives `2026-01-10 07:01:59 UTC`; other
  client (`ai_app`); bad shapes give no time.
- Producer: `kling`; USCC form valid; USCC form with wrong check digit.
- CLI: text output matches section 2; `--json` is valid and complete;
  several files; missing file; exit codes 0 / 1 / 2.

## 8. README (part 3)

Install (`pipx install git+https://github.com/Aariyan007/kling-label-detector`
or `pip install .`), usage with made-up output, `--json` example, exit codes,
what "no label" means, limits, ethics. The research summary stays.

## 9. Out of scope

- Anything that removes, forges, strips or edits labels (hard rule).
- Pixel-based detection and visible-logo detection.
- Decoding the Kling download URL (possible later as `--url`).
