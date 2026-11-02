"""OpenAI image generation for TrendingTesla (pilot; not used by production yet).

generate(prompt, refs, model, quality, size) -> (PIL image, info)
  - refs: 1-3 local reference images (only files whose rights allow derivative use, see allowed_ref()).
  - Uses POST /v1/images/edits (multipart, image[] per reference). Without refs: /v1/images/generations.
  - The TrendingTesla Visual Standard (ops/visual-standard.md) and the chosen profile go before every prompt.
  - info has the real token usage from the API response and the cost in USD from RATES.

Needs the secret OPENAI_API_KEY. Costs are logged by the caller (tools/image_pilot.py) in ops/images-log.jsonl.
"""
import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.openai.com/v1"
PROMPT_VERSION = "vs1.0-p1"
# USD per 1M tokens (GPT Image 2.5 Flare and Sunburst share these rates; check platform.openai.com/pricing)
RATES = {"text_in": 5.0, "image_in": 8.0, "out": 30.0}
PROFILES = {"editorial": "Profile A — Editorial", "cinematic": "Profile B — Cinematic", "technical": "Profile C — Technical"}


def standard(profile):
    """The general part of the Visual Standard plus the one profile that applies (kept short for the prompt)."""
    txt = (ROOT / "ops/visual-standard.md").read_text(encoding="utf-8")
    head = txt.split("## Profile A")[0]
    name = PROFILES[profile]
    part = txt.split(f"## {name}")[1].split("\n## ")[0] if f"## {name}" in txt else ""
    return f"{head.strip()}\n\n{name}{part.rstrip()}"


def key():
    k = os.environ.get("OPENAI_API_KEY", "").strip()
    if not k:
        raise RuntimeError("OPENAI_API_KEY missing")
    return k


def models():
    """Image model ids this key can use (to verify the real names before generating)."""
    req = urllib.request.Request(f"{API}/models", headers={"Authorization": f"Bearer {key()}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return sorted(m["id"] for m in json.load(r)["data"] if "image" in m["id"])


def _multipart(fields, files):
    b = uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (name, data) in files:
        out.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                  f"Content-Type: image/png\r\n\r\n".encode() + data + b"\r\n")
    out.write(f"--{b}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={b}"


def _png(path, maxside=1536):
    im = path.convert("RGB") if isinstance(path, Image.Image) else Image.open(path).convert("RGB")
    im.thumbnail((maxside, maxside))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def cost(usage):
    d = usage.get("input_tokens_details") or {}
    img_in = d.get("image_tokens", 0)
    txt_in = d.get("text_tokens", max(0, usage.get("input_tokens", 0) - img_in))
    out = usage.get("output_tokens", 0)
    return round((txt_in * RATES["text_in"] + img_in * RATES["image_in"] + out * RATES["out"]) / 1e6, 5)


def generate(prompt, refs, model="gpt-image-2.5-flare", quality="high", size="1536x1024", profile="editorial"):
    full = f"{standard(profile)}\n\n---\nIMAGE TO CREATE:\n{prompt}"
    t0 = time.time()
    if refs:
        body, ctype = _multipart({"model": model, "prompt": full, "size": size, "quality": quality, "n": "1"},
                                 [("image[]", (f"ref{i}.png", _png(r))) for i, r in enumerate(refs)])
        req = urllib.request.Request(f"{API}/images/edits", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {key()}", "Content-Type": ctype})
    else:
        req = urllib.request.Request(f"{API}/images/generations", method="POST",
                                     data=json.dumps({"model": model, "prompt": full, "size": size,
                                                      "quality": quality, "n": 1}).encode(),
                                     headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI HTTP {e.code}: {' '.join(e.read().decode(errors='replace').split())[:400]}")
    im = Image.open(io.BytesIO(base64.b64decode(d["data"][0]["b64_json"]))).convert("RGB")
    usage = d.get("usage") or {}
    return im, {"model": model, "quality": quality, "size": size, "profile": profile, "prompt_version": PROMPT_VERSION,
                "refs": [("pil" if isinstance(r, Image.Image) else str(r).replace(str(ROOT) + "/", "")) for r in refs],
                "usage": usage, "cost_usd": cost(usage), "seconds": round(time.time() - t0, 1)}


# references: only images we may use for derivative work
def allowed_ref(path):
    """True for William's own library images (made by him with ChatGPT) and CC0 / public-domain real photos.
    CC BY / BY-SA, press images and anything ND or NC are not used as AI references (see the implementation plan)."""
    p = Path(path)
    if "img/lib/" in str(p):
        return True
    if "img/real/" in str(p):
        cr = json.loads((p.parent / "credits.json").read_text()) if (p.parent / "credits.json").exists() else {}
        lic = (cr.get(p.name) or {}).get("credit", "")
        return any(x in lic for x in ("CC0", "Public domain", "PD"))
    return False


# ---- production guard: budget and daily limit (ops/images-log.jsonl) ----
LOG = ROOT / "ops/images-log.jsonl"
MONTH_CAP = float(os.environ.get("OPENAI_MONTH_CAP_USD", "11"))  # ~EUR 10, William's budget
DAY_CAP = int(os.environ.get("OPENAI_DAY_CAP", "25"))


def usage_now():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    month = day = 0.0
    n_day = 0
    for line in (LOG.read_text().splitlines() if LOG.exists() else []):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        at = r.get("at", "")
        if at[:7] == now.strftime("%Y-%m"):
            month += r.get("cost_usd", 0)
        if at[:10] == now.strftime("%Y-%m-%d") and r.get("file") is not None:
            n_day += 1
    return month, n_day


def allowed_now(next_cost=0.12):
    month, n_day = usage_now()
    return month + next_cost <= MONTH_CAP and n_day < DAY_CAP, month, n_day


def log(row):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
