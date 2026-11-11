"""A short moving clip from one of our photos (image-to-video), for the hook of a Short.

make(photo, prompt, out_mp4, resolution="720p", focus=0.5) -> info dict (seconds, tokens, cost_usd) or raises.
CLI: python3 tools/video_clip.py <photo> "<what moves>" <out.mp4> [resolution]

Model: Google's gemini-omni-1.1-flash through the Gemini API (the same GEMINI_API_KEY as the photos; Veo 3.1 was
switched off on that API on 22 Oct 2026). The photo is cropped to 9:16 and sent as the first frame. Billing is per
output token ($17.50 per million; about $0.10 per second at 720p): the real usage from the response is logged in
ops/clips-log.jsonl, and allowed_now() keeps the month under CLIP_MONTH_CAP_USD (default 15, William's budget).
Rules (ops/visual-standard.md): an illustration that moves, never a fake documentary shot of a real event, never
a real person; the subject must stay exactly as in the photo.
"""
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
API = "https://generativelanguage.googleapis.com/v1beta"
MODEL = os.environ.get("CLIP_MODEL", "gemini-omni-1.1-flash")
RATE_OUT = float(os.environ.get("CLIP_USD_PER_M_TOKENS", "17.5"))
MONTH_CAP = float(os.environ.get("CLIP_MONTH_CAP_USD", "15"))
LOG = ROOT / "ops/clips-log.jsonl"
STYLE = ("Use this image as the first frame and keep everything in it exactly as it is: the same vehicle or object, "
         "the same shape, colours, proportions and details; nothing is added or removed. Photorealistic, natural "
         "motion, steady camera. No people appear. No text, captions, logos or watermarks appear. No dialogue, no "
         "voice, no music. Motion: ")


def key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        raise RuntimeError("GEMINI_API_KEY missing")
    return k


def spent_this_month():
    now = datetime.now(timezone.utc).strftime("%Y-%m")
    total = 0.0
    for line in (LOG.read_text().splitlines() if LOG.exists() else []):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("at", "")[:7] == now:
            total += r.get("cost_usd", 0)
    return total


def allowed_now(next_cost=1.1):
    s = spent_this_month()
    return s + next_cost <= MONTH_CAP, s


def first_frame(photo, focus=0.5, height=1280):
    im = Image.open(photo).convert("RGB")
    w, h = im.size
    cw = min(w, round(h * 9 / 16))
    x0 = max(0, min(w - cw, round(focus * w - cw / 2)))
    im = im.crop((x0, 0, x0 + cw, h)).resize((height * 9 // 16, height), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def find_video(node):
    """The video part anywhere in the response: a dict with type 'video' and 'data' (base64) or 'uri'."""
    if isinstance(node, dict):
        if node.get("type") == "video" and (node.get("data") or node.get("uri")):
            return node
        for v in node.values():
            r = find_video(v)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = find_video(v)
            if r:
                return r
    return None


def strip(node):
    """The response without the big base64 fields (for the log and for debugging)."""
    if isinstance(node, dict):
        return {k: (f"<{len(v)} chars>" if isinstance(v, str) and len(v) > 400 else strip(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [strip(v) for v in node]
    return node


def make(photo, prompt, out, resolution="720p", focus=0.5, note=""):
    body = {"model": MODEL,
            "input": [{"type": "image", "data": base64.b64encode(first_frame(photo, focus)).decode(), "mime_type": "image/jpeg"},
                      {"type": "text", "text": STYLE + prompt.strip()}],
            "response_format": {"type": "video", "aspect_ratio": "9:16", "resolution": resolution},
            "generation_config": {"video_config": {"task": "image_to_video"}},
            "store": False, "background": False, "stream": False}
    t0 = time.time()
    req = urllib.request.Request(f"{API}/interactions", data=json.dumps(body).encode(), method="POST",
                                 headers={"x-goog-api-key": key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"clip HTTP {e.code}: {' '.join(e.read().decode(errors='replace').split())[:500]}")
    v = find_video(d)
    if not v:
        raise RuntimeError(f"no video in the response: {json.dumps(strip(d))[:800]}")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if v.get("data"):
        out.write_bytes(base64.b64decode(v["data"]))
    else:
        rq = urllib.request.Request(v["uri"], headers={"x-goog-api-key": key()})
        with urllib.request.urlopen(rq, timeout=300) as r:
            out.write_bytes(r.read())
    usage = d.get("usage") or d.get("usage_metadata") or {}
    tokens = usage.get("total_output_tokens") or usage.get("output_tokens") or usage.get("candidates_token_count") or 0
    info = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "photo": str(photo).replace(str(ROOT) + "/", ""),
            "model": MODEL, "resolution": resolution, "bytes": out.stat().st_size, "output_tokens": tokens,
            "cost_usd": round(tokens * RATE_OUT / 1e6, 4), "seconds_to_make": round(time.time() - t0, 1),
            "usage": usage, "note": note}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info) + "\n")
    info["response"] = strip(d)
    return info


if __name__ == "__main__":
    ok, spent = allowed_now()
    if not ok:
        sys.exit(f"::warning::clip budget reached (${spent:.2f} of ${MONTH_CAP:.0f} this month)")
    info = make(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "720p", note="test")
    print(json.dumps(info, indent=1)[:3000])
