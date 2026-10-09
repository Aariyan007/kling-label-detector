"""Check one file for the label, following the find order in the spec:
PNG text chunks -> MP4 metadata -> XMP -> raw byte scan."""

import struct
import zlib
from dataclasses import asdict, dataclass, field

from .label import classify_payload, decode_payload
from .mp4 import read_mp4
from .png import read_png
from .scan import find_xmp_aigc, scan_file
from .sniff import sniff

GB = "(China GB 45438-2025 format)"
PNG_WHERE = {
    "tEXt": f'PNG text chunk "AIGC" {GB}',
    "zTXt": f'PNG compressed text chunk (zTXt) "AIGC" {GB}',
    "iTXt": f'PNG international text chunk (iTXt) "AIGC" {GB}',
}
MAX_WARNINGS = 5


@dataclass
class Result:
    file: str
    format: str | None = None
    width: int | None = None
    height: int | None = None
    result: str = "no_label"
    found_by: str | None = None
    where: str | None = None
    label: dict | None = None
    raw: str | None = None
    decoded: dict | None = None
    warnings: list = field(default_factory=list)
    error: str | None = None

    def to_dict(self):
        return asdict(self)


def detect(path):
    result = Result(file=path)
    try:
        with open(path, "rb") as f:
            _detect(f, result)
    except OSError as e:
        result.result, result.error = "error", e.strerror or str(e)
    except (ValueError, struct.error, zlib.error) as e:
        result.result, result.error = "error", f"could not parse file: {e}"
    if len(result.warnings) > MAX_WARNINGS:
        extra = len(result.warnings) - MAX_WARNINGS
        result.warnings = result.warnings[:MAX_WARNINGS] + [f"... and {extra} more warnings"]
    return result


def _detect(f, result):
    head = f.read(16)
    if not head:
        result.result, result.error = "error", "file is empty"
        return
    result.format = sniff(head)
    f.seek(0)

    # Each candidate is (found_by, where, text). Normal places first.
    candidates = []
    if result.format == "PNG":
        info = read_png(f)
        result.width, result.height = info.width, info.height
        result.warnings += info.warnings
        for t in info.texts:
            if t.keyword == "AIGC":
                candidates.append(("png_text_chunk", PNG_WHERE[t.ctype], t.text))
        for t in info.texts:
            if t.keyword == "XML:com.adobe.xmp":
                value = find_xmp_aigc(t.text.encode("utf-8"))
                if value is not None:
                    candidates.append(("xmp", f'XMP metadata field "AIGC" in a PNG iTXt chunk {GB}', value))
    elif result.format in ("MP4", "MOV", "HEIF"):
        info = read_mp4(f)
        result.width, result.height = info.width, info.height
        result.warnings += info.warnings
        kind = "MOV" if result.format == "MOV" else "MP4"
        for item in info.items:
            if item.key == "AIGC":
                candidates.append(("mp4_metadata", f'{kind} metadata key "AIGC" in {item.path} {GB}', item.value))

    if not candidates:
        hit = scan_file(f)
        if hit and hit.kind == "xmp":
            candidates.append(("xmp", f'XMP metadata field "AIGC", found by raw byte scan at offset {hit.offset}', hit.text))
        elif hit:
            candidates.append(("raw_scan", f"raw byte scan at offset {hit.offset} (not a standard place)", hit.text))

    if not candidates:
        return
    distinct = list(dict.fromkeys(text for _, _, text in candidates))
    if len(distinct) > 1:
        result.warnings.append(f"file has {len(distinct)} different AIGC labels; showing the first")
    result.found_by, result.where, text = candidates[0]
    result.result, result.label = classify_payload(text)
    if result.label is None:
        result.raw = text
    else:
        result.decoded = decode_payload(result.label)
