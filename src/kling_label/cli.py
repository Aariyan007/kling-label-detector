"""kling-label: report Kling AI's hidden "AI-generated" label in files.

Detection only: files are opened read-only and never changed.
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from . import __version__
from .detect import detect

HEADLINES = {
    "other_label": "AI LABEL FOUND (GB 45438-2025, producer is not Kling)",
    "unreadable_label": "AIGC LABEL FOUND, BUT ITS CONTENT COULD NOT BE READ",
    "no_label": ("NO KLING LABEL FOUND. The file may still be AI-made; "
                 "screenshots, re-saves and chat apps remove this label."),
}
FOUND = ("kling_label", "other_label", "unreadable_label")
SCAN_ONLY = ("JPEG", "WebP", "GIF", "HEIF", "unknown")
VIDEO = ("MP4", "MOV")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="kling-label",
        description="Report Kling AI's hidden AI-generated label (China GB 45438-2025) in PNG and MP4 files. "
                    "Detection only: files are never changed.",
        epilog="Exit codes: 0 = every file has a label, 1 = a file has no label, 2 = error.",
    )
    parser.add_argument("files", nargs="+", metavar="FILE", help="image or video files to check")
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    results = [detect(path) for path in args.files]
    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
    else:
        print("\n\n".join(format_text(r) for r in results))

    if any(r.result == "error" for r in results):
        return 2
    if any(r.result not in FOUND for r in results):
        return 1
    return 0


def format_text(r):
    kind = f"{r.format}, {r.width}x{r.height}" if r.width else r.format
    lines = [f"File:     {clean(r.file)}" + (f" ({kind})" if kind else "")]
    if r.result == "error":
        lines.append(f"Result:   ERROR: {clean(r.error)}")
        return "\n".join(lines)

    lines.append(f"Result:   {headline(r)}")
    if r.where:
        lines.append(f"Where:    {r.where}")
    if r.result == "unreadable_label":
        lines.append(f"  Raw:              {clean(r.raw[:200])}")
    elif r.label is not None:
        lines += label_lines(r.label, r.decoded)
    if r.result == "no_label" and r.format in SCAN_ONLY:
        lines.append(f"Note:     {r.format} files have no full parser yet; only a raw byte scan was done.")
    if r.decoded and r.decoded["produce_id"]:
        thing = "video" if r.format in VIDEO else "file" if r.format == "unknown" else "image"
        lines.append(f"Privacy:  this ID reveals when the {thing} was made.")
    lines += [f"Warning:  {clean(w)}" for w in r.warnings]
    return "\n".join(lines)


def headline(r):
    if r.result != "kling_label":
        return HEADLINES[r.result]
    value = r.label.get("Label")
    return "KLING LABEL FOUND (AI-generated)" if value == "1" else f"KLING LABEL FOUND (Label = {show(value)})"


def label_lines(label, decoded):
    value = label.get("Label")
    meaning = "(= AI-generated)" if value == "1" else "(other value; see GB 45438-2025)"
    lines = [f"  Label             {show(value)}  {meaning}"]

    producer = label.get("ContentProducer")
    lines.append(f"  ContentProducer   {show(producer)}")
    p = decoded["producer"]
    if p["form"] == "uscc":
        check = "check digit valid" if p["uscc_valid"] else "check digit WRONG"
        parts = [x for x in (p["prefix"], f"USCC {p['uscc']} ({check})", p["suffix"]) if x]
        lines.append("    " + " · ".join(clean(x) for x in parts))

    produce_id = label.get("ProduceID")
    lines.append(f"  ProduceID         {show(produce_id)}")
    d = decoded["produce_id"]
    if d:
        made = datetime.fromtimestamp(d["created_unix"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"    region {d['region']} · system {d['system']} · made on {d['client']}")
        lines.append(f"    made at {made} UTC (decoded from ID)")

    lines.append(f"  ContentPropagator {show(label.get('ContentPropagator'))}")
    if label.get("PropagateID") != produce_id:
        lines.append(f"  PropagateID       {show(label.get('PropagateID'))}")
    for key in ("ReservedCode1", "ReservedCode2"):
        if label.get(key) is not None:
            lines.append(f"  {key:<17} {show(label[key])}")
    return lines


def show(value):
    if value is None:
        return "(none)"
    return clean(value if isinstance(value, str) else json.dumps(value))


def clean(text):
    """Escape control characters so a file cannot send commands to the terminal."""
    return "".join(ch if ch.isprintable() else ascii(ch)[1:-1] for ch in str(text))


if __name__ == "__main__":
    sys.exit(main())
