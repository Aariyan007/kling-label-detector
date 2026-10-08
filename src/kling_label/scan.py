"""Fallback search: look for the label anywhere in the raw bytes of a file.

Used when the normal parsers find nothing, or when the file type has no
parser (JPEG, WebP, unknown). It finds:
  - a JSON object that contains "ProduceID" (the GB 45438-2025 label), and
  - an XMP field named AIGC (attribute or element, any namespace prefix).
The file is read in blocks, so large videos are never loaded at once.
"""

import html
import re
from dataclasses import dataclass

MAX_FIELD = 4096
OVERLAP = 3 * MAX_FIELD

_JSON_RE = re.compile(rb'\{[^{}]{0,%d}"ProduceID"[^{}]{0,%d}\}' % (MAX_FIELD, MAX_FIELD))
_XMP_ATTR_RE = re.compile(rb'(?<![\w.-])(?:[A-Za-z_][\w.-]*:)?AIGC\s*=\s*(?:"([^"]{1,%d})"|\'([^\']{1,%d})\')'
                          % (MAX_FIELD, MAX_FIELD))
_XMP_ELEM_RE = re.compile(rb'<((?:[A-Za-z_][\w.-]*:)?AIGC)>([^<]{1,%d})</\1>' % MAX_FIELD)


@dataclass
class Hit:
    kind: str  # "json" or "xmp"
    offset: int
    text: str


def find_xmp_aigc(data):
    """Return the AIGC value from XMP bytes, or None."""
    hit = _first_xmp(data)
    return hit[1] if hit else None


def _first_xmp(data):
    best = None
    for regex in (_XMP_ATTR_RE, _XMP_ELEM_RE):
        m = regex.search(data)
        if m and (best is None or m.start() < best.start()):
            best = m
    if best is None:
        return None
    raw = best.group(2) if best.re is _XMP_ELEM_RE else (best.group(1) or best.group(2))
    return best.start(), html.unescape(raw.decode("utf-8", errors="replace"))


def scan_file(f, block_size=1024 * 1024):
    """Return the first Hit in the file, or None."""
    f.seek(0)
    base = 0
    buf = b""
    while True:
        block = f.read(block_size)
        buf += block
        hit = _scan_buffer(buf, base)
        if hit:
            return hit
        if not block:
            return None
        # Keep a tail so a label split across two blocks is still found. Every
        # pattern ends with a closing character, so a match is never half-read,
        # and the tail is longer than the longest possible match.
        keep = min(len(buf), OVERLAP)
        base += len(buf) - keep
        buf = buf[-keep:] if keep else b""


def _scan_buffer(buf, base):
    hits = []
    m = _JSON_RE.search(buf)
    if m:
        hits.append(Hit("json", base + m.start(), m.group().decode("utf-8", errors="replace")))
    xmp = _first_xmp(buf)
    if xmp:
        hits.append(Hit("xmp", base + xmp[0], xmp[1]))
    return min(hits, key=lambda h: h.offset, default=None)
