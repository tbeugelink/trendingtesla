"""Test whether the Gemini API key can use Veo (Google's video model), and make one test clip.

Usage:  python3 tools/veo_test.py list                      -> list the video models this key can use (free)
        python3 tools/veo_test.py clip <image> <out.mp4> [model] [seconds]
                                                            -> animate one photo into a short clip with Veo (billed per second)
        python3 tools/veo_test.py omni <image> <out.mp4> [9:16|16:9]
                                                            -> the same with Gemini Omni Flash, Veo's successor
Nothing on the site changes; the workflow uploads the clip as an artifact to look at.
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_image as G  # noqa: E402  (same auth and API helper)

PROMPT = ("Slow, smooth cinematic camera move: the camera glides forward and slightly around the car while it drives "
          "along the winding road; wheels turn naturally, trees sway gently, warm afternoon light. Keep the car's "
          "design exactly as in the image. No text, no logos, no people's faces, no new objects.")


def video_models():
    names, tok = [], ""
    while True:
        d = G.api("models?pageSize=200" + (f"&pageToken={tok}" if tok else ""))
        names += [(m["name"].split("/", 1)[1], m.get("supportedGenerationMethods", []))
                  for m in d.get("models", []) if "veo" in m["name"].lower() or "omni" in m["name"].lower()]
        tok = d.get("nextPageToken")
        if not tok:
            return names


def clip(image, out, mdl=None, seconds=8):
    if not mdl:
        names = [n for n, _ in video_models()]
        lite = [n for n in names if "lite" in n] or [n for n in names if "fast" in n] or names
        if not lite:
            raise RuntimeError("this key has no Veo model")
        mdl = sorted(lite)[-1]
    data = base64.b64encode(Path(image).read_bytes()).decode()
    body = {"instances": [{"prompt": PROMPT, "image": {"bytesBase64Encoded": data, "mimeType": "image/jpeg"}}],
            "parameters": {"aspectRatio": "16:9", "durationSeconds": int(seconds), "resolution": "720p"}}
    print(f"::notice::Veo model {mdl}, {seconds} s, 720p")
    op = G.api(f"models/{mdl}:predictLongRunning", body)
    t0 = time.time()
    while not op.get("done"):
        if time.time() - t0 > 600:
            raise RuntimeError("Veo did not finish within 10 minutes")
        time.sleep(10)
        op = G.api(op["name"])
    if op.get("error"):
        raise RuntimeError(f"Veo error: {json.dumps(op['error'])[:400]}")
    resp = op.get("response", {})
    samples = (resp.get("generateVideoResponse") or resp).get("generatedSamples") or resp.get("videos") or []
    if not samples:
        raise RuntimeError(f"no video in response: {json.dumps(resp)[:400]}")
    v = samples[0].get("video", samples[0])
    if v.get("bytesBase64Encoded"):
        Path(out).write_bytes(base64.b64decode(v["bytesBase64Encoded"]))
    else:
        h = G.AUTH[0] if G.AUTH else {"x-goog-api-key": G.key()}
        with urllib.request.urlopen(urllib.request.Request(v["uri"], headers=h), timeout=300) as r:
            Path(out).write_bytes(r.read())
    print(f"::notice::clip saved ({Path(out).stat().st_size // 1024} KB) after {time.time() - t0:.0f} s")


def find_video(x):
    """The first {mime_type: video/..., data|uri} item anywhere in the response."""
    if isinstance(x, dict):
        if str(x.get("mime_type") or x.get("mimeType") or "").startswith("video") and (x.get("data") or x.get("uri")):
            return x
        x = list(x.values())
    if isinstance(x, list):
        for y in x:
            v = find_video(y)
            if v:
                return v
    return None


def omni(image, out, aspect="9:16"):
    """Gemini Omni Flash (the successor of Veo in the Gemini API): animate one photo, billed per second of video."""
    data = base64.b64encode(Path(image).read_bytes()).decode()
    body = {"model": "gemini-omni-1.1-flash",
            "input": [{"type": "image", "data": data, "mime_type": "image/jpeg"}, {"type": "text", "text": PROMPT}],
            "response_format": {"type": "video", "aspect_ratio": aspect, "resolution": "720p"}}
    t0 = time.time()
    d = G.api("interactions", body)
    v = find_video(d)
    if not v:
        raise RuntimeError(f"no video in response: {json.dumps(d)[:600]}")
    if v.get("data"):
        Path(out).write_bytes(base64.b64decode(v["data"]))
    else:
        h = G.AUTH[0] if G.AUTH else {"x-goog-api-key": G.key()}
        with urllib.request.urlopen(urllib.request.Request(v["uri"], headers=h), timeout=300) as r:
            Path(out).write_bytes(r.read())
    usage = d.get("usage") or d.get("usage_metadata") or {}
    print(f"::notice::Omni clip saved ({Path(out).stat().st_size // 1024} KB, {aspect}) after {time.time() - t0:.0f} s; usage {json.dumps(usage)[:300]}")


if __name__ == "__main__":
    if sys.argv[1] == "list":
        ms = video_models()
        for n, meth in ms:
            print(f"::notice::{n}: {', '.join(meth)}")
        if not ms:
            print("::warning::this key lists no Veo model")
    elif sys.argv[1] == "omni":
        omni(sys.argv[2], sys.argv[3], *(sys.argv[4:5] or ["9:16"]))
    else:
        clip(sys.argv[2], sys.argv[3], *(sys.argv[4:5] or [None]), *(sys.argv[5:6] or [8]))
