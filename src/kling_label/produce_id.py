"""Split a Kling ProduceID and decode the creation time hidden in it.

Shape: <REGION>_<SYSTEM>_<client>_<15 digits>, e.g. SGP_PROD_ai_web_300000000123456.
The 15 digits are seconds (9) + worker (3) + milliseconds (3), see FINDINGS.md.
Seconds count from about 2016-07-09 01:41:59 UTC, so decoded times are good to about 1 s.
The millisecond field is strongly supported; the worker meaning is a hypothesis.
"""

import re
from datetime import datetime, timezone

EPOCH = 1468028519  # 2016-07-09 01:41:59 UTC

_ID_RE = re.compile(r"([A-Z0-9]+)_([A-Z0-9]+)_([A-Za-z0-9]+(?:_[A-Za-z0-9]+)*)_(\d{15})")


def decode_produce_id(value):
    """Return a dict with the parts and creation time, or None if the shape is not Kling's."""
    if not isinstance(value, str):
        return None
    match = _ID_RE.fullmatch(value)
    if not match:
        return None
    region, system, client, digits = match.groups()
    created = EPOCH + int(digits) // 1_000_000
    millis = int(digits[-3:])
    return {
        "region": region,
        "system": system,
        "client": client,
        "digits": digits,
        "extra_digits": digits[-6:],
        "created_unix": created,
        "created_utc": datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "worker": digits[9:12],
        "milliseconds": millis,
        "created_utc_ms": datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        + f".{millis:03d}Z",
    }
