"""Generate a fresh article photo with Nano Banana (Gemini image model), using reference photos for the details.

The article JSON may carry:
  "gen_image": {
    "prompt":   "Scene to create: subject, situation from the story, place, season, time of day, mood",
    "subject":  "What must match the references exactly, e.g. 'the Tesla Semi truck (cab shape, light bar, wheels)'",
    "refs":     [{"src": "models/semi-2.jpg"}, {"src": "https://upload.wikimedia.org/...jpg", "page": "https://commons.wikimedia.org/wiki/File:..."}],
    "describe": "One line for PHOTOS.md: what is visible in the new photo"
  }
refs: photos of the real subject, ours first (paths inside static/img/), then freely licensed ones (Wikimedia
Commons), then press photos. They are only used as a reference for shape and details: the prompt asks for a new
angle, setting and composition, and the result is rejected when it looks too much like any reference (dHash).

Result: static/img/gen/<slug>.jpg, article "image" set to it (and put first in "images"), "gen_image.done" true,
provenance in content/image_sources.json, a line in PHOTOS.md. Without GEMINI_API_KEY or on any error the article
keeps its normal photos (exit code 0, warning printed).

Usage:  python3 tools/gen_image.py <slug> [<slug> ...]
"""
import base64
import glob
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "static" / "img"
API = "https://generativelanguage.googleapis.com/v1beta"
UA = {"User-Agent": "TrendingTesla image bot (https://trendingtesla.com)"}
STYLE = ("Photorealistic editorial news photo, landscape 16:9, natural light, sharp focus, realistic proportions. "
         "Colourful but natural colour grading with yellow, red and blue accents in the scene (sky, surroundings, "
         "clothing, signs), never grey or washed out. Leave calm space in the lower-left third for a text label. ")
RULES = ("Use the reference images ONLY to get the subject's real design right ({subject}): exact shape, "
         "proportions, lights, wheels and details. Create a NEW photo: different camera angle, different place and "
         "background, different composition and lighting than every reference. Do not copy any reference photo. "
         "No text, no captions, no logos or brand marks, no watermarks, no readable licence plates, no recognisable "
         "real people's faces.")
SIMILAR = 10  # dHash distance (of 64 bits) at or below which a result counts as a copy of a reference


def key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        raise RuntimeError("GEMINI_API_KEY missing")
    return k


AUTH = []  # the header style that works for this key (API key or the newer auth key)


def api(path, body=None):
    styles = AUTH or [{"x-goog-api-key": key()}, {"Authorization": f"Bearer {key()}"}]
    err = None
    for h in styles:
        req = urllib.request.Request(f"{API}/{path}", data=json.dumps(body).encode() if body else None,
                                     headers={**h, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                if not AUTH:
                    AUTH.append(h)
                return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:400]
            err = RuntimeError(f"HTTP {e.code}: {msg}")
            err.code = e.code
            if e.code not in (401, 403) or AUTH:
                raise err
    raise err


def model():
    if os.environ.get("GEMINI_IMAGE_MODEL"):
        return os.environ["GEMINI_IMAGE_MODEL"]
    names, tok = [], ""
    while True:
        d = api("models?pageSize=200" + (f"&pageToken={tok}" if tok else ""))
        names += [m["name"].split("/", 1)[1] for m in d.get("models", [])
                  if "image" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])]
        tok = d.get("nextPageToken")
        if not tok:
            break
    if not names:
        raise RuntimeError("no image model available for this key")
    # prefer the newest stable "flash-image" (Nano Banana), then any other image model
    def rank(n):
        return ("flash-image" in n, "preview" not in n and "exp" not in n, n)
    return sorted(names, key=rank)[-1]


def load_ref(src):
    if src.startswith("http"):
        with urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=60) as r:
            data = r.read()
    else:
        data = (IMG / src).read_bytes()
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    im.thumbnail((1024, 1024))
    return im


def dhash(im, n=8):
    g = ImageOps.grayscale(im).resize((n + 1, n), Image.LANCZOS)
    px = list(g.getdata())
    return sum(1 << i for i, (a, b) in enumerate((px[r * (n + 1) + c], px[r * (n + 1) + c + 1])
                                                 for r in range(n) for c in range(n)) if a > b)


def too_similar(im, refs):
    h = dhash(im)
    hm = dhash(ImageOps.mirror(im))
    return min(min(bin(h ^ dhash(r)).count("1"), bin(hm ^ dhash(r)).count("1")) for r in refs) <= SIMILAR


def generate(mdl, prompt, refs):
    parts = [{"text": prompt}]
    for r in refs:
        buf = io.BytesIO()
        r.save(buf, "JPEG", quality=90)
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}}
    try:
        d = api(f"models/{mdl}:generateContent", body)
    except RuntimeError as e:
        if getattr(e, "code", 0) == 400:  # older models without imageConfig
            body["generationConfig"] = {"responseModalities": ["TEXT", "IMAGE"]}
            d = api(f"models/{mdl}:generateContent", body)
        else:
            raise
    for c in d.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            blob = p.get("inline_data") or p.get("inlineData")
            if blob and blob.get("data"):
                return Image.open(io.BytesIO(base64.b64decode(blob["data"]))).convert("RGB")
    raise RuntimeError(f"no image in response: {json.dumps(d)[:300]}")


def fit_16x9(im, w=1920):
    h = w * 9 // 16
    return ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(0.5, 0.5))


def run(slug):
    files = [f for f in glob.glob(str(ROOT / "content/articles" / f"*{slug}.json"))
             if json.load(open(f, encoding="utf-8")).get("slug") == slug]
    if not files:
        raise RuntimeError(f"article {slug} not found")
    f = Path(files[0])
    a = json.loads(f.read_text(encoding="utf-8"))
    g = a.get("gen_image") or {}
    if not g.get("prompt") or g.get("done"):
        print(f"{slug}: nothing to generate")
        return
    refs, used = [], []
    for r in g.get("refs", [])[:4]:
        try:
            refs.append(load_ref(r["src"]))
            used.append(r)
        except Exception as e:  # a dead link must not stop the rest
            print(f"::warning::{slug}: reference {r.get('src')} skipped: {e}")
    if not refs:
        raise RuntimeError("no usable reference photo")
    mdl = model()
    prompt = STYLE + g["prompt"].strip() + "\n\n" + RULES.format(subject=g.get("subject") or "the main subject")
    out = None
    for attempt in range(3):
        im = fit_16x9(generate(mdl, prompt, refs))
        if not too_similar(im, refs):
            out = im
            break
        print(f"::warning::{slug}: result {attempt + 1} too close to a reference, trying again")
        prompt += "\nThe previous attempt looked too much like a reference photo: change the camera angle and the whole setting completely."
    if out is None:
        raise RuntimeError("every result was too close to a reference photo")
    rel = f"gen/{slug}.jpg"
    (IMG / "gen").mkdir(parents=True, exist_ok=True)
    out.save(IMG / rel, "JPEG", quality=88, optimize=True, progressive=True)
    a["image"] = rel
    a["images"] = [rel] + [x for x in a.get("images", []) if x != rel]
    g["done"] = True
    g["model"] = mdl
    a["gen_image"] = g
    f.write_text(json.dumps(a, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    src_file = ROOT / "content" / "image_sources.json"
    src = json.loads(src_file.read_text(encoding="utf-8")) if src_file.exists() else {}
    src[rel] = {"article": slug, "model": mdl, "made": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "references": [{"src": r["src"], **({"page": r["page"]} if r.get("page") else {})} for r in used]}
    src_file.write_text(json.dumps(src, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    cat = ROOT / "PHOTOS.md"
    line = f"- {rel} — {g.get('describe') or g['prompt'][:140]}"
    text = cat.read_text(encoding="utf-8")
    if "## Generated photos" not in text:
        text = text.rstrip() + ("\n\n## Generated photos (made per article with Nano Banana; reusable, give as "
                                "\"gen/<file>.jpg\" in \"images\" or as a reference)\n")
    cat.write_text(text.rstrip() + "\n" + line + "\n", encoding="utf-8")
    print(f"::notice::{slug}: new photo {rel} ({mdl}, {len(used)} reference(s))")


if __name__ == "__main__":
    for s in sys.argv[1:]:
        try:
            run(s)
        except Exception as e:  # never block publishing: the article keeps its normal photos
            print(f"::warning::{s}: no generated photo ({e})")
