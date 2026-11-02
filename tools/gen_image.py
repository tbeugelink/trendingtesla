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
sys.path.insert(0, str(ROOT / "tools"))  # image_openai, image_check
sys.path.insert(0, str(ROOT / "video"))
IMG = ROOT / "static" / "img"
API = "https://generativelanguage.googleapis.com/v1beta"
UA = {"User-Agent": "TrendingTesla image bot (https://trendingtesla.com)"}
STYLE = ("Photorealistic editorial news photo, landscape 16:9, natural light, sharp focus, realistic proportions. "
         "Colourful but natural colour grading with yellow, red and blue accents in the scene (sky, surroundings, "
         "clothing, signs), never grey or washed out. Leave calm space in the lower-left third for a text label. ")
RULES = ("Use the reference images ONLY to get the subject's real design right ({subject}): exact shape, "
         "proportions, lights, wheels and details; reproduce how the objects are really built and do not invent extra "
         "parts (no extra poles, cables, screens, doors or wheels). Create a NEW photo: different camera angle, different place and "
         "background, different composition and lighting than every reference. Do not copy any reference photo. "
         "No text, no captions, no logos or brand marks, no watermarks, no readable licence plates, no recognisable "
         "real people's faces.")
HERO = ("This is the thumbnail and the first frame of the video, so it must grab attention at phone size within a "
        "second: one clear subject, big in the frame (filling roughly half of it), sharp and close, seen from a dynamic, "
        "low or three-quarter angle, with strong light and contrast against a clean background; no wide empty landscape "
        "with a small subject, no clutter. Keep the subject in the horizontal centre of the frame: the vertical "
        "Short shows only the middle third of this photo. ")
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
            msg = " ".join(e.read().decode(errors="replace").split())[:400]
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


FREE = ("cc0", "cc by", "cc-by", "public domain", "pd")


def commons(query):
    """First freely licensed photo on Wikimedia Commons for `query` -> {"src", "page", "license"}."""
    import urllib.parse
    pages = []
    words = query.split()
    for qq in dict.fromkeys([query, " ".join(words[:-1]), " ".join(words[:2])]):  # fall back to shorter queries
        if not qq:
            continue
        q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                                    "gsrsearch": qq, "gsrlimit": 15, "prop": "imageinfo",
                                    "iiprop": "url|extmetadata|mime", "iiurlwidth": 1280})
        with urllib.request.urlopen(urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{q}", headers=UA),
                                    timeout=60) as r:
            pages = sorted(json.load(r).get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        if any((p.get("imageinfo") or [{}])[0].get("mime") == "image/jpeg" for p in pages):
            break
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
        if ii.get("mime") == "image/jpeg" and lic.lower().startswith(FREE):
            return {"src": ii.get("thumburl") or ii["url"], "page": ii.get("descriptionurl"), "license": lic}
    seen = [(p.get("title"), (p.get("imageinfo") or [{}])[0].get("mime"),
             (p.get("imageinfo") or [{}])[0].get("extmetadata", {}).get("LicenseShortName", {}).get("value")) for p in pages[:4]]
    raise RuntimeError(f"no freely licensed Commons photo for '{query}' ({len(pages)} results: {seen})")


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


def make(g, label="photo", hero=False):
    """Generate one image for spec g -> (image, references used, model)."""
    refs, used = [], []
    for r in g.get("refs", [])[:4]:
        try:
            if r.get("commons") and not r.get("src"):
                r = {**commons(r["commons"]), **r}
            refs.append(load_ref(r["src"]))
            used.append(r)
        except Exception as e:  # a dead link must not stop the rest
            print(f"::warning::{label}: reference {r.get('src') or r.get('commons')} skipped: {e}")
    if not refs:
        raise RuntimeError("no usable reference photo")
    if os.environ.get("IMAGE_PROVIDER", "gemini") == "openai" and os.environ.get("OPENAI_API_KEY"):
        try:
            res = make_openai(g, refs, used, label, hero)
            if res:
                return res
        except Exception as e:  # never lose the photo: fall back to Nano Banana
            print(f"::warning::{label}: OpenAI failed, using Nano Banana: {str(e)[:200]}")
    mdl = model()
    prompt = STYLE + (HERO if hero else "") + g["prompt"].strip() + "\n\n" + RULES.format(subject=g.get("subject") or "the main subject")
    for attempt in range(3):
        im = fit_16x9(generate(mdl, prompt, refs))
        if not too_similar(im, refs):
            return im, used, mdl
        print(f"::warning::{label}: result {attempt + 1} too close to a reference, trying again")
        prompt += "\nThe previous attempt looked too much like a reference photo: change the camera angle and the whole setting completely."
    raise RuntimeError("every result was too close to a reference photo")


def mark_log(rel, mdl):
    """Put the saved file name on the last approved OpenAI log line (so every image can be traced)."""
    lf = ROOT / "ops/images-log.jsonl"
    if "gpt-image" not in str(mdl) or not lf.exists():
        return
    lines = lf.read_text(encoding="utf-8").splitlines()
    for i in range(len(lines) - 1, -1, -1):
        r = json.loads(lines[i])
        if r.get("file") == "pending" and r.get("approved_auto"):
            r["file"] = rel
            lines[i] = json.dumps(r, ensure_ascii=False)
            break
    lf.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ref_allowed(r):
    """Only references whose rights allow derivative work: William's library and CC0 / public-domain photos."""
    src = str(r.get("src", ""))
    if src.startswith("lib/"):
        return True
    lic = str(r.get("license", "")).lower()
    return any(x in lic for x in ("cc0", "public domain", "pdm", "cc-zero"))


def make_openai(g, refs, used, label, hero):
    """GPT Image 2.5 Flare (high) with the allowed references, judged by Gemini (visual, technical, journalistic
    separately); at most 2 more tries (the last with Sunburst). Returns (image, refs used, model) or None."""
    import image_openai as O
    import image_check as C
    ok_refs = [(im, r) for im, r in zip(refs, used) if ref_allowed(r)][:2]
    if not ok_refs:
        print(f"::notice::{label}: no reference with derivative rights; using Nano Banana")
        return None
    subject = g.get("subject") or "the main subject"
    prompt = g["prompt"].strip() + f"\nIt must show exactly: {subject}."
    profile = g.get("profile") or ("technical" if g.get("technical") else "editorial")
    for attempt in range(3):
        go, month, n_day = O.allowed_now()
        if not go:
            print(f"::warning::{label}: OpenAI budget or daily limit reached (${month:.2f} this month, {n_day} today)")
            return None
        mdl = O.os.environ.get("SUNBURST_MODEL", "gpt-image-2.5-sunburst") if attempt == 2 else \
            O.os.environ.get("FLARE_MODEL", "gpt-image-2.5-flare")
        im, info = O.generate(prompt, [x[0] for x in ok_refs], mdl, "high", "1536x1024", profile)
        chk = C.check(im, subject, [x[0] for x in ok_refs], g.get("category", "A"))
        O.log({"at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "label": label, "file": "pending",
               **info, "refs": [x[1].get("src") for x in ok_refs], "try": attempt, "check": chk,
               "approved_auto": chk["ok"], "approved_william": None, "category": g.get("category", "A")})
        print(f"{label}: {mdl} try {attempt}: visual {chk['visual']} tech {chk.get('technical_pass')} "
              f"journ {chk.get('journalistic_pass')} ${info['cost_usd']} {chk.get('technical_errors')}")
        if chk["ok"]:
            return fit_16x9(im), [x[1] for x in ok_refs], mdl
        prompt += "\nAvoid these errors of the previous attempt: " + "; ".join(
            chk.get("technical_errors", []) + chk.get("journalistic_issues", []))
    print(f"::warning::{label}: 3 OpenAI attempts rejected; using Nano Banana")
    return None


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
    out, used, mdl = make(g, hero=True)
    old = a.get("image") if str(a.get("image", "")).startswith(f"gen/{slug}") else None
    rel = f"gen/{slug}.jpg"
    if old or (IMG / rel).exists():  # a redo gets a fresh file name, so no browser or CDN shows the old photo
        rel = f"gen/{slug}-{datetime.now(timezone.utc).strftime('%m%d%H%M')}.jpg"
    if old:  # replacing a wrong photo: drop it everywhere
        (IMG / old).unlink(missing_ok=True)
        a["images"] = [x for x in a.get("images", []) if x != old]
        for bl in (a.get("video") or {}).values():
            for b in bl:
                im = b.get("img")
                if im == old:
                    b["img"] = rel
                elif isinstance(im, list) and old in im:
                    b["img"] = [rel if x == old else x for x in im]
    (IMG / "gen").mkdir(parents=True, exist_ok=True)
    out.save(IMG / rel, "JPEG", quality=88, optimize=True, progressive=True)
    mark_log(rel, mdl)
    a["image"] = rel
    a["images"] = [rel] + [x for x in a.get("images", []) if x != rel]
    g["done"] = True
    g["model"] = mdl
    a["gen_image"] = g
    f.write_text(json.dumps(a, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    src_file = ROOT / "content" / "image_sources.json"
    src = json.loads(src_file.read_text(encoding="utf-8")) if src_file.exists() else {}
    if old:
        src.pop(old, None)
    src[rel] = {"article": slug, "model": mdl, "made": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "references": [{k: r[k] for k in ("src", "page", "license", "commons") if r.get(k)} for r in used]}
    src_file.write_text(json.dumps(src, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    cat = ROOT / "PHOTOS.md"
    line = f"- {rel} — {g.get('describe') or g['prompt'][:140]}"
    text = cat.read_text(encoding="utf-8")
    if old:
        text = "".join(x for x in text.splitlines(True) if not x.startswith(f"- {old} "))
    if "## Generated photos" not in text:
        text = text.rstrip() + ("\n\n## Generated photos (made per article with Nano Banana; reusable, give as "
                                "\"gen/<file>.jpg\" in \"images\" or as a reference)\n")
    cat.write_text(text.rstrip() + "\n" + line + "\n", encoding="utf-8")
    print(f"::notice::{slug}: new photo {rel} ({mdl}, {len(used)} reference(s))")
    extras(slug, f, src_file, cat)


def extras(slug, f, src_file, cat):
    """"gen_image.extra": up to 2 more scenes of the same subject (same refs), so videos have more variety."""
    a = json.loads(f.read_text(encoding="utf-8"))
    g = a.get("gen_image") or {}
    todo = [x for x in (g.get("extra") or [])[:2] if x.get("prompt") and not x.get("file")]
    for i, x in enumerate(todo, 2):
        try:
            out, used, mdl = make({**g, "prompt": x["prompt"]}, label=f"extra {i}")
        except Exception as e:
            print(f"::warning::{slug}: extra photo skipped: {e}")
            continue
        rel = f"gen/{slug}-x{i}-{datetime.now(timezone.utc).strftime('%m%d%H%M')}.jpg"
        out.save(IMG / rel, "JPEG", quality=88, optimize=True, progressive=True)
        mark_log(rel, mdl)
        x["file"] = rel
        a["images"] = a.get("images", [])[:1] + [rel] + a.get("images", [])[1:]
        src = json.loads(src_file.read_text(encoding="utf-8"))
        src[rel] = {"article": slug, "model": mdl, "made": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "references": [{k: r[k] for k in ("src", "page", "license", "commons") if r.get(k)} for r in used]}
        src_file.write_text(json.dumps(src, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        cat.write_text(cat.read_text(encoding="utf-8").rstrip() + f"\n- {rel} — {x.get('describe') or x['prompt'][:140]}\n",
                       encoding="utf-8")
        print(f"::notice::{slug}: extra photo {rel}")
    a["gen_image"] = g
    f.write_text(json.dumps(a, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test(spec_file, out_dir):
    """Test specs (no article changes): {"name": spec, ...} -> <out_dir>/<name>.jpg"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, g in json.loads(Path(spec_file).read_text(encoding="utf-8")).items():
        if os.environ.get("REFS_ONLY"):  # only fetch and save the reference photos (free, for checking them)
            for i, r in enumerate(g.get("refs", []), 1):
                try:
                    r = {**commons(r["commons"]), **r} if r.get("commons") and not r.get("src") else r
                    load_ref(r["src"]).save(out / f"{name}-ref{i}.jpg", "JPEG", quality=88)
                    print(f"::notice::{name}-ref{i}: {r.get('page') or r['src']} ({r.get('license', 'own')})")
                except Exception as e:
                    print(f"::warning::{name}-ref{i}: {e}")
            continue
        try:
            im, used, mdl = make(g, name)
            im.save(out / f"{name}.jpg", "JPEG", quality=88)
            print(f"::notice::test {name}: ok ({mdl}; refs: {', '.join(r.get('page') or r['src'] for r in used)})")
        except Exception as e:
            print(f"::warning::test {name}: {e}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--test"]:
        test(sys.argv[2], sys.argv[3])
        sys.exit(0)
    for s in sys.argv[1:]:
        try:
            run(s)
        except Exception as e:  # never block publishing: the article keeps its normal photos
            print(f"::warning::{s}: no generated photo ({e})")
