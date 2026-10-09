"""Work out the file type from its first bytes, not from its name."""

QUICKTIME_TOP_BOXES = (b"moov", b"mdat", b"free", b"wide", b"skip")
HEIF_BRANDS = (b"heic", b"heix", b"mif1", b"msf1", b"avif", b"avis")


def sniff(head):
    """Return "PNG", "MP4", "MOV", "HEIF", "JPEG", "WebP", "GIF" or "unknown"."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand == b"qt  ":
            return "MOV"
        if brand in HEIF_BRANDS:
            return "HEIF"
        return "MP4"
    if head[4:8] in QUICKTIME_TOP_BOXES:
        return "MOV"
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WebP"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    return "unknown"
