"""Decode the ContentProducer field.

Kling writes either "kling" or, for IMAGE 3.0, "0011" + an 18-character
Chinese Unified Social Credit Code (USCC, GB 32100-2015) + "10100".
"""

USCC_CHARS = "0123456789ABCDEFGHJKLMNPQRTUWXY"
USCC_WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)


def uscc_is_valid(code):
    """Check the GB 32100-2015 check digit (the 18th character)."""
    if len(code) != 18 or any(ch not in USCC_CHARS for ch in code):
        return False
    total = sum(USCC_CHARS.index(ch) * w for ch, w in zip(code, USCC_WEIGHTS))
    return USCC_CHARS[(31 - total % 31) % 31] == code[17]


def decode_producer(value):
    if value is None:
        return {"form": "missing"}
    if not isinstance(value, str):
        return {"form": "other"}
    if value == "kling":
        return {"form": "kling"}
    for start in range(len(value) - 17):
        window = value[start:start + 18]
        if uscc_is_valid(window):
            return _uscc(value, start, True)
    if len(value) == 27 and value.startswith("0011") and value.endswith("10100"):
        return _uscc(value, 4, False)
    return {"form": "other"}


def _uscc(value, start, valid):
    return {
        "form": "uscc",
        "prefix": value[:start],
        "uscc": value[start:start + 18],
        "suffix": value[start + 18:],
        "uscc_valid": valid,
    }
