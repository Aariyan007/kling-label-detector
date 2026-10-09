"""Check a label payload and decide what kind of result it is."""

import json

from .produce_id import decode_produce_id
from .producer import decode_producer

# The USCC seen in ContentProducer of Kling IMAGE 3.0 output (FINDINGS.md section 4).
KLING_USCC = "91110108335469089C"


def looks_like_kling(payload):
    for field in ("ContentProducer", "ContentPropagator"):
        value = payload.get(field)
        if value == "kling":
            return True
        if decode_producer(value).get("uscc") == KLING_USCC:
            return True
    return any(decode_produce_id(payload.get(f)) for f in ("ProduceID", "PropagateID"))


def classify_payload(text):
    """Return (kind, payload). kind is kling_label, other_label or unreadable_label."""
    try:
        payload = json.loads(text)
    except ValueError:
        return "unreadable_label", None
    if not isinstance(payload, dict):
        return "unreadable_label", None
    return ("kling_label" if looks_like_kling(payload) else "other_label"), payload


def decode_payload(payload):
    return {
        "produce_id": decode_produce_id(payload.get("ProduceID")),
        "producer": decode_producer(payload.get("ContentProducer")),
    }
