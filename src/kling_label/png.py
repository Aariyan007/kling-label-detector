"""Read PNG chunks without any image library.

A PNG is an 8-byte signature followed by chunks:
    4-byte length, 4-byte type, data, 4-byte CRC.
We read IHDR (image size) and the three text chunk types. All other chunks,
including the large IDAT image data, are skipped with seek().
"""

import struct
import zlib
from dataclasses import dataclass, field

SIGNATURE = b"\x89PNG\r\n\x1a\n"
TEXT_TYPES = (b"tEXt", b"zTXt", b"iTXt")
MAX_TEXT = 16 * 1024 * 1024


@dataclass
class TextChunk:
    ctype: str
    keyword: str
    text: str
    offset: int


@dataclass
class PngInfo:
    width: int | None = None
    height: int | None = None
    texts: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def read_png(f):
    if f.read(8) != SIGNATURE:
        raise ValueError("not a PNG file (wrong signature)")
    size = f.seek(0, 2)
    f.seek(8)
    info = PngInfo()
    while True:
        offset = f.tell()
        header = f.read(8)
        if not header:
            info.warnings.append("PNG ends early (no IEND chunk)")
            break
        if len(header) < 8:
            info.warnings.append(f"PNG ends early (cut inside a chunk header at byte {offset})")
            break
        length, ctype = struct.unpack(">I4s", header)
        if ctype == b"IEND":
            break
        if ctype == b"IHDR" or (ctype in TEXT_TYPES and length <= MAX_TEXT):
            data = f.read(length)
            crc = f.read(4)
            if len(data) < length or len(crc) < 4:
                info.warnings.append(f"PNG ends early (cut inside a {_name(ctype)} chunk at byte {offset})")
                break
            if struct.unpack(">I", crc)[0] != zlib.crc32(ctype + data) & 0xFFFFFFFF:
                info.warnings.append(f"{_name(ctype)} chunk at byte {offset} has a wrong CRC (read anyway)")
            if ctype == b"IHDR" and length >= 8:
                info.width, info.height = struct.unpack(">II", data[:8])
            elif ctype in TEXT_TYPES:
                try:
                    keyword, text = _decode_text(ctype, data)
                except (ValueError, zlib.error) as e:
                    info.warnings.append(f"{_name(ctype)} chunk at byte {offset} could not be read: {e}")
                else:
                    info.texts.append(TextChunk(_name(ctype), keyword, text, offset))
        else:
            if ctype in TEXT_TYPES:
                info.warnings.append(f"{_name(ctype)} chunk at byte {offset} is too large; skipped")
            end = offset + 12 + length
            if end > size:
                info.warnings.append(f"PNG ends early (cut inside a {_name(ctype)} chunk at byte {offset})")
                break
            f.seek(end)
    return info


def _decode_text(ctype, data):
    keyword, sep, rest = data.partition(b"\0")
    if not sep:
        raise ValueError("no keyword separator")
    keyword = keyword.decode("latin-1")
    if ctype == b"tEXt":
        return keyword, rest.decode("latin-1")
    if ctype == b"zTXt":
        return keyword, zlib.decompress(rest[1:]).decode("latin-1")
    # iTXt: compression flag, compression method, language\0, translated keyword\0, text
    if len(rest) < 2:
        raise ValueError("iTXt header too short")
    compressed = rest[0]
    language, _, rest = rest[2:].partition(b"\0")
    translated, _, body = rest.partition(b"\0")
    if compressed:
        body = zlib.decompress(body)
    return keyword, body.decode("utf-8", errors="replace")


def _name(ctype):
    return ctype.decode("latin-1", errors="replace")
