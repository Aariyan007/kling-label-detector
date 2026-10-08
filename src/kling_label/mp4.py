"""Read MP4 / MOV metadata boxes without any video library.

An MP4 file is a tree of boxes: 4-byte size, 4-byte type, data. Size 1 means
a 64-bit size follows; size 0 means "to the end of the file". Kling puts its
label in moov/udta/meta, as an "mdta" key named AIGC:

    meta -> hdlr (handler "mdta")
         -> keys (list of key names, numbered from 1)
         -> ilst (one box per key number, each holding a "data" box)

Only small boxes are read into memory; everything else is skipped with seek().
"""

import struct
from dataclasses import dataclass, field

CONTAINERS = {b"moov", b"trak", b"udta"}
MAX_READ = 16 * 1024 * 1024
MAX_DEPTH = 8


@dataclass
class MetaItem:
    key: str
    value: str
    path: str


@dataclass
class Mp4Info:
    width: int | None = None
    height: int | None = None
    items: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def read_mp4(f):
    info = Mp4Info()
    size = f.seek(0, 2)
    _walk(f, 0, size, size, "", info, 0)
    return info


def _boxes(f, start, end, file_size, info):
    """Yield (type, data_start, data_end, complete) for each box between start and end.

    complete is False when the box is cut off by the end of the file.
    """
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        size, btype = struct.unpack(">I4s", f.read(8))
        header = 8
        if size == 1:
            raw = f.read(8)
            if len(raw) < 8:
                info.warnings.append(f"file ends early (cut inside a box header at byte {pos})")
                return
            size = struct.unpack(">Q", raw)[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header:
            info.warnings.append(f"box at byte {pos} has a broken size ({size}); stopped reading")
            return
        box_end = pos + size
        complete = box_end <= file_size
        if box_end > end:
            info.warnings.append(
                f"file ends early ({_name(btype)} box at byte {pos} is cut off)"
                if box_end > file_size else f"{_name(btype)} box at byte {pos} is larger than its parent")
            box_end = end
        yield btype, pos + header, box_end, complete
        pos = box_end
    if 0 < end - pos < 8:
        info.warnings.append(f"file ends early (cut inside a box header at byte {pos})")


def _walk(f, start, end, file_size, path, info, depth):
    if depth > MAX_DEPTH:
        return
    for btype, data_start, data_end, _ in _boxes(f, start, end, file_size, info):
        here = f"{path}/{_name(btype)}" if path else _name(btype)
        if btype in CONTAINERS:
            _walk(f, data_start, data_end, file_size, here, info, depth + 1)
        elif btype == b"meta" and path:
            _read_meta(f, data_start, data_end, file_size, here, info)
        elif btype == b"tkhd" and info.width is None:
            _read_tkhd(_read(f, data_start, data_end), info)


def _read(f, start, end):
    f.seek(start)
    return f.read(min(end - start, MAX_READ))


def _read_tkhd(data, info):
    offset = 88 if data[:1] == b"\x01" else 76
    if len(data) >= offset + 8:
        width, height = struct.unpack(">II", data[offset:offset + 8])
        if width >> 16 and height >> 16:
            info.width, info.height = width >> 16, height >> 16


def _read_meta(f, start, end, file_size, path, info):
    # The ISO form of "meta" has a 4-byte version/flags header; the QuickTime
    # form does not. In the QuickTime form the first child box starts at once.
    peek = _read(f, start, min(end, start + 8))
    if peek[4:8] not in (b"hdlr", b"keys", b"ilst"):
        start += 4
    keys, values = [], {}
    for btype, data_start, data_end, _ in _boxes(f, start, end, file_size, info):
        if btype == b"keys":
            keys = _parse_keys(_read(f, data_start, data_end))
        elif btype == b"ilst":
            values = _parse_ilst(f, data_start, data_end, file_size, info)
    for index, value in sorted(values.items()):
        if 1 <= index <= len(keys):
            info.items.append(MetaItem(keys[index - 1], value, path))


def _parse_keys(data):
    keys = []
    if len(data) < 8:
        return keys
    count = struct.unpack(">I", data[4:8])[0]
    pos = 8
    while len(keys) < count and pos + 8 <= len(data):
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        if size < 8 or pos + size > len(data):
            break
        keys.append(data[pos + 8:pos + size].decode("utf-8", errors="replace"))
        pos += size
    return keys


def _parse_ilst(f, start, end, file_size, info):
    values = {}
    for btype, data_start, data_end, _ in _boxes(f, start, end, file_size, info):
        index = struct.unpack(">I", btype)[0]
        for inner, value_start, value_end, complete in _boxes(f, data_start, data_end, file_size, info):
            # A value cut off by the end of the file is never reported as a label.
            if inner == b"data" and complete and value_end - value_start >= 8:
                raw = _read(f, value_start + 8, value_end)
                values.setdefault(index, raw.decode("utf-8", errors="replace"))
    return values


def _name(btype):
    return btype.decode("latin-1", errors="replace")
