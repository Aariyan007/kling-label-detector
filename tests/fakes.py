"""Build small fake PNG, MP4 and JPEG files in memory for tests.

Every ID here is made up. No real sample file is ever needed.
"""

import json
import struct
import zlib

FAKE_ID = "SGP_PROD_ai_web_300000000123456"
FAKE_ID_TIME = "2026-01-10 07:01:59 UTC"  # 1468028519 + 300000000
FAKE_USCC = "91110108335469089C"  # public company code seen in IMAGE 3.0 output
FAKE_USCC_PRODUCER = "0011" + FAKE_USCC + "10100"


def aigc_json(
    produce_id=FAKE_ID,
    producer="kling",
    propagator=None,
    propagate_id=None,
    label="1",
    reserved1=None,
    reserved2=None,
):
    """The label JSON, in the same compact form Kling writes."""
    payload = {
        "Label": label,
        "ContentProducer": producer,
        "ProduceID": produce_id,
        "ReservedCode1": reserved1,
        "ContentPropagator": producer if propagator is None else propagator,
        "PropagateID": produce_id if propagate_id is None else propagate_id,
        "ReservedCode2": reserved2,
    }
    return json.dumps(payload, separators=(",", ":"))


# ---------------------------------------------------------------- PNG

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_chunk(ctype, data, bad_crc=False):
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    if bad_crc:
        crc ^= 0xFFFFFFFF
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)


def text_chunk(keyword, text, bad_crc=False):
    return png_chunk(b"tEXt", keyword.encode("latin-1") + b"\0" + text.encode("latin-1"), bad_crc)


def ztxt_chunk(keyword, text):
    return png_chunk(b"zTXt", keyword.encode("latin-1") + b"\0\0" + zlib.compress(text.encode("latin-1")))


def itxt_chunk(keyword, text, compressed=False):
    body = text.encode("utf-8")
    if compressed:
        body = zlib.compress(body)
    data = keyword.encode("latin-1") + b"\0" + bytes([1 if compressed else 0, 0]) + b"\0" + b"\0" + body
    return png_chunk(b"iTXt", data)


def png_bytes(width=32, height=48, before_idat=(), after_idat=()):
    """A real, valid RGB PNG with extra chunks placed before or after IDAT."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = (b"\x00" + b"\x80" * (3 * width)) * height
    out = PNG_SIGNATURE + png_chunk(b"IHDR", ihdr)
    out += b"".join(before_idat)
    out += png_chunk(b"IDAT", zlib.compress(raw))
    out += b"".join(after_idat)
    out += png_chunk(b"IEND", b"")
    return out


def kling_png(**kwargs):
    """A PNG labelled the way Kling labels it today."""
    return png_bytes(before_idat=[text_chunk("AIGC", aigc_json(**kwargs))])


# ---------------------------------------------------------------- XMP

def xmp_packet(label_json, style="attr"):
    """An XMP packet holding the label. The namespace is made up for tests."""
    from xml.sax.saxutils import escape, quoteattr

    if style == "attr":
        field = "<rdf:Description rdf:about='' xmlns:AIGC_NS='http://example.invalid/aigc/' AIGC_NS:AIGC=%s/>" % quoteattr(label_json)
    else:
        field = (
            "<rdf:Description rdf:about='' xmlns:AIGC_NS='http://example.invalid/aigc/'>"
            "<AIGC_NS:AIGC>%s</AIGC_NS:AIGC></rdf:Description>" % escape(label_json)
        )
    return (
        "<?xpacket begin='﻿' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        "<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        + field
        + "</rdf:RDF></x:xmpmeta><?xpacket end='w'?>"
    )


# ---------------------------------------------------------------- MP4

def box(btype, payload, large=False):
    if large:
        return struct.pack(">I", 1) + btype + struct.pack(">Q", 16 + len(payload)) + payload
    return struct.pack(">I", 8 + len(payload)) + btype + payload


def full_box(btype, payload, version=0, flags=0):
    return box(btype, struct.pack(">I", (version << 24) | flags) + payload)


def meta_box(items, quicktime=False):
    """moov/udta/meta with mdta keys + ilst, like FFmpeg writes with -movflags use_metadata_tags."""
    hdlr = full_box(b"hdlr", b"\0\0\0\0" + b"mdta" + b"\0" * 12 + b"\0")
    key_entries = b"".join(box(b"mdta", name.encode("utf-8")) for name in items)
    keys = full_box(b"keys", struct.pack(">I", len(items)) + key_entries)
    ilst_items = b""
    for index, value in enumerate(items.values(), start=1):
        data = box(b"data", struct.pack(">II", 1, 0) + value.encode("utf-8"))
        ilst_items += box(struct.pack(">I", index), data)
    ilst = box(b"ilst", ilst_items)
    inner = hdlr + keys + ilst
    if quicktime:
        return box(b"meta", inner)
    return box(b"meta", b"\0\0\0\0" + inner)


def tkhd_box(width, height, version=0):
    if version == 1:
        head = struct.pack(">QQIIQ", 0, 0, 1, 0, 0)
    else:
        head = struct.pack(">IIIII", 0, 0, 1, 0, 0)
    rest = b"\0" * 8 + struct.pack(">hhhh", 0, 0, 0, 0) + b"\0" * 36
    rest += struct.pack(">II", width << 16, height << 16)
    return full_box(b"tkhd", head + rest, version=version)


def mp4_bytes(
    items=None,
    quicktime_meta=False,
    meta_in_trak=False,
    width=1280,
    height=720,
    large_moov=False,
    brand=b"isom",
    mdat_size=64,
):
    """A small MP4 container. `items` maps mdta key names to string values."""
    if items is None:
        items = {"major_brand": "isom", "AIGC": aigc_json(), "encoder": "Lavf61.7.100"}
    ftyp = box(b"ftyp", brand + struct.pack(">I", 512) + brand + b"iso2mp41")
    mvhd = full_box(b"mvhd", b"\0" * 96)
    meta = meta_box(items, quicktime=quicktime_meta) if items else b""
    trak_children = tkhd_box(width, height)
    if meta_in_trak:
        trak_children += box(b"udta", meta)
    trak = box(b"trak", trak_children)
    moov_children = mvhd + trak
    if not meta_in_trak and meta:
        moov_children += box(b"udta", meta)
    moov = box(b"moov", moov_children, large=large_moov)
    mdat = box(b"mdat", b"\0" * mdat_size)
    return ftyp + moov + mdat


def kling_mp4(**kwargs):
    return mp4_bytes(items={"major_brand": "isom", "minor_version": "512",
                            "compatible_brands": "isomiso2avc1mp41",
                            "AIGC": aigc_json(**kwargs), "encoder": "Lavf61.7.100"})


# ---------------------------------------------------------------- JPEG

def jpeg_segment(marker, payload):
    return b"\xff" + bytes([marker]) + struct.pack(">H", len(payload) + 2) + payload


def jpeg_bytes(comment=None, xmp=None, padding=0):
    """Not a decodable image, but has the right markers for the tool."""
    out = b"\xff\xd8"
    out += jpeg_segment(0xE0, b"JFIF\0\x01\x01\0\0\x01\0\x01\0\0")
    if xmp is not None:
        out += jpeg_segment(0xE1, b"http://ns.adobe.com/xap/1.0/\0" + xmp.encode("utf-8"))
    out += b"\x00" * padding
    if comment is not None:
        out += jpeg_segment(0xFE, comment.encode("utf-8"))
    out += b"\xff\xd9"
    return out
