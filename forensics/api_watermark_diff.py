"""Ground-truth watermark test via Kling's own API (detection only).

Kling's image-generation API documents a `watermark_info` field. With it enabled,
the task returns the normal image *and* a separately-watermarked version
(`watermark_url`). Comparing those two images — the SAME generation, one plain and
one watermarked, both produced by Kling — isolates exactly what Kling's watermark
step adds, with no guessing. This is the clean version of the with/without test.

DETECTION ONLY. This script asks Kling to generate two versions of one image and
then *compares* them with the validated pair tool. It never removes, forges, or
strips a watermark. It prints numbers only (via wm_pair_compare) and keeps the
downloaded originals local (they carry an ID that reveals creation time).

Setup (once you have API access):
  1. Create an app in Kling's API console; get an AccessKey and a SecretKey.
  2. export KLING_ACCESS_KEY=...   export KLING_SECRET_KEY=...
     (API credits are separate from the website plan.)
  3. pip install pyjwt requests pillow numpy   # pyjwt optional; a fallback is built in
  4. python forensics/api_watermark_diff.py "a crowded spice market, highly detailed"

Config constants below (BASE_URL, endpoints, model name, the exact watermark field)
follow Kling's published API. Verify them against the current API docs before a run;
they are isolated at the top so a doc change is a one-line edit.
"""

import os
import sys
import time
import json
import hmac
import base64
import hashlib
import tempfile
import subprocess
import urllib.request

# ----------------------------------------------------------------- config (verify vs docs)
BASE_URL   = os.environ.get("KLING_BASE_URL", "https://api-singapore.klingai.com")
GEN_PATH   = "/v1/images/generations"            # POST to create a task
QUERY_PATH = "/v1/images/generations/{task_id}"  # GET to poll a task
MODEL_NAME = os.environ.get("KLING_MODEL", "kling-v2")   # the IMAGE model that carries the label
# The field that turns on the watermarked second output. Kling's IMAGE 3.0 docs describe
# `watermark_info`; keep it here so it is easy to adjust if the schema differs.
WATERMARK_PAYLOAD = {"watermark_info": {"enabled": True}}


def jwt_token(ak, sk, ttl=1800):
    """HS256 JWT the way Kling's API expects (iss=accesskey). Uses pyjwt if present."""
    now = int(time.time())
    payload = {"iss": ak, "exp": now + ttl, "nbf": now - 5}
    try:
        import jwt  # pyjwt
        return jwt.encode(payload, sk, algorithm="HS256",
                          headers={"alg": "HS256", "typ": "JWT"})
    except Exception:
        def b64(d):
            return base64.urlsafe_b64encode(d).rstrip(b"=")
        head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        body = b64(json.dumps(payload, separators=(",", ":")).encode())
        sig = b64(hmac.new(sk.encode(), head + b"." + body, hashlib.sha256).digest())
        return (head + b"." + body + b"." + sig).decode()


def api(method, path, token, body=None):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def download(url, path):
    with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as f:
        f.write(r.read())


def main():
    ak = os.environ.get("KLING_ACCESS_KEY")
    sk = os.environ.get("KLING_SECRET_KEY")
    if not ak or not sk:
        print("Set KLING_ACCESS_KEY and KLING_SECRET_KEY first (see the header of this file).")
        sys.exit(1)
    prompt = sys.argv[1] if len(sys.argv) > 1 else "a crowded outdoor spice market, highly detailed, photorealistic"

    token = jwt_token(ak, sk)
    body = {"model_name": MODEL_NAME, "prompt": prompt, "n": 1, "aspect_ratio": "9:16"}
    body.update(WATERMARK_PAYLOAD)
    print(f"Submitting generation (model {MODEL_NAME}) with watermark enabled ...")
    res = api("POST", GEN_PATH, token, body)
    task_id = (res.get("data") or {}).get("task_id") or res.get("task_id")
    if not task_id:
        print("No task_id in response:", json.dumps(res)[:500]); sys.exit(1)

    # poll
    for _ in range(60):
        time.sleep(5)
        token = jwt_token(ak, sk)
        q = api("GET", QUERY_PATH.format(task_id=task_id), token)
        data = q.get("data") or q
        status = (data.get("task_status") or data.get("status") or "").lower()
        if status in ("succeed", "success", "completed", "done"):
            imgs = (data.get("task_result") or {}).get("images") or data.get("images") or []
            if not imgs:
                print("Done but no images:", json.dumps(data)[:500]); sys.exit(1)
            img = imgs[0]
            plain_url = img.get("url")
            wm_url = img.get("watermark_url") or img.get("url_watermark")
            if not wm_url:
                print("No separate watermark_url returned — the API did not produce a second "
                      "(watermarked) version for this model/options. Nothing to diff.")
                print("image keys:", list(img.keys())); sys.exit(0)
            outdir = os.path.join(tempfile.gettempdir(), "kling_api_pair")
            os.makedirs(outdir, exist_ok=True)
            download(plain_url, os.path.join(outdir, "img1_without.png"))  # plain = no visible wm
            download(wm_url,    os.path.join(outdir, "img1_with.png"))     # watermarked version
            print(f"Downloaded both versions to {outdir}")
            here = os.path.dirname(os.path.abspath(__file__))
            print("\n--- comparing (detection only, numbers only) ---")
            subprocess.run([sys.executable, os.path.join(here, "wm_pair_compare.py"), outdir])
            print("\nRead the numbers: 0% differ outside the logo => the watermark step adds only "
                  "the visible logo. Small broadband differences everywhere => the isolated "
                  "invisible watermark (report numbers only; do not post the pattern).")
            return
        if status in ("failed", "error"):
            print("Generation failed:", json.dumps(data)[:500]); sys.exit(1)
        print(f"  status={status or '?'} ...")
    print("Timed out waiting for the task.")


if __name__ == "__main__":
    main()
