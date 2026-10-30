"""Add real, freely usable photos of the news to an article (before the videos are made).

The article JSON may carry (the writing task fills it in after checking each photo page itself):
  "real_photos": [
    {"page": "https://commons.wikimedia.org/wiki/File:Tesla_Semi_....jpg", "describe": "what is visible"},
    {"page": "https://www.ntsb.gov/...", "src": "https://www.ntsb.gov/....jpg", "credit": "NTSB",
     "describe": "what is visible"}
  ]
Allowed, because they may be used in articles, videos and thumbnails:
- Wikimedia Commons files with public domain, CC0 or CC BY (any version). NOT CC BY-SA (our label on a
  thumbnail would have to carry the same licence), NOT NC or ND.
- Photos by US federal agencies (public domain): ntsb.gov, nhtsa.gov, nasa.gov, faa.gov, energy.gov,
  dot.gov, fhwa.dot.gov, defense.gov, army.mil, af.mil, navy.mil, usgs.gov, noaa.gov.
Anything else is skipped with a warning. Each photo gets a credit ("Photo: <author>, CC BY 4.0, Wikimedia
Commons") that the site shows under the article and the videos put in their YouTube description.

Result per photo: static/img/news/<slug>-<n>.jpg (16:9, 1920 px), put in front of "images" (real photos
first), entry "file" + "credit" filled in, "credits" list on the article, provenance in
content/image_sources.json, a line in PHOTOS.md. Already processed entries (with "file") are left alone.

Usage:  python3 tools/real_photos.py <slug> [<slug> ...]   (never fails the workflow: problems are warnings)
"""
import glob
import html
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "static" / "img"
UA = {"User-Agent": "TrendingTesla photo bot (https://trendingtesla.com)"}
FED = ("ntsb.gov", "nhtsa.gov", "nasa.gov", "faa.gov", "energy.gov", "dot.gov", "defense.gov", "army.mil",
       "af.mil", "navy.mil", "usgs.gov", "noaa.gov")


def free_licence(lic):
    s = lic.lower().replace("-", " ")
    if " sa" in s or "nc" in s.split() or " nd" in s or "sharealike" in s:
        return False
    return s.startswith(("cc0", "cc by", "public domain", "pd")) or s in ("no restrictions",)


def commons_info(page):
    title = urllib.parse.unquote(page.rsplit("/wiki/", 1)[-1]).replace("_", " ")
    if not title.lower().startswith("file:"):
        raise ValueError("not a Commons File: page")
    q = urllib.parse.urlencode({"action": "query", "format": "json", "titles": title, "prop": "imageinfo",
                                "iiprop": "url|extmetadata|mime", "iiurlwidth": 2400})
    with urllib.request.urlopen(urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{q}", headers=UA),
                                timeout=60) as r:
        p = next(iter(json.load(r)["query"]["pages"].values()))
    ii = (p.get("imageinfo") or [{}])[0]
    meta = ii.get("extmetadata", {})
    lic = meta.get("LicenseShortName", {}).get("value", "")
    if ii.get("mime") not in ("image/jpeg", "image/png"):
        raise ValueError(f"not a photo ({ii.get('mime')})")
    if not free_licence(lic):
        raise ValueError(f"licence not allowed: {lic or 'unknown'}")
    artist = re.sub(r"<[^>]+>", "", html.unescape(meta.get("Artist", {}).get("value", ""))).strip() or "unknown author"
    artist = re.sub(r"\s+", " ", artist)[:80]
    return ii.get("thumburl") or ii["url"], f"{artist}, {lic}, Wikimedia Commons", lic


def federal(entry):
    host = urllib.parse.urlparse(entry.get("src", "")).hostname or ""
    if not entry.get("src") or not any(host == d or host.endswith("." + d) for d in FED):
        raise ValueError(f"not a US federal photo: {host or 'no src'}")
    agency = entry.get("credit") or host.split(".")[-2].upper()
    return entry["src"], f"{agency}, public domain", "public domain (US federal)"


def run(slug):
    files = [f for f in glob.glob(str(ROOT / "content/articles" / f"*{slug}.json"))
             if json.load(open(f, encoding="utf-8")).get("slug") == slug]
    if not files:
        print(f"::warning::real photos: article {slug} not found")
        return
    f = Path(files[0])
    a = json.loads(f.read_text(encoding="utf-8"))
    todo = [e for e in a.get("real_photos", []) if not e.get("file")]
    if not todo:
        return
    src_file = ROOT / "content" / "image_sources.json"
    sources = json.loads(src_file.read_text(encoding="utf-8")) if src_file.exists() else {}
    cat = ROOT / "PHOTOS.md"
    text = cat.read_text(encoding="utf-8")
    if "## News photos" not in text:
        text = text.rstrip() + ("\n\n## News photos (real, freely licensed; credit required, the build shows it: "
                                "only use for the same subject)\n")
    (IMG / "news").mkdir(parents=True, exist_ok=True)
    added = []
    n = len([e for e in a.get("real_photos", []) if e.get("file")])
    for e in todo:
        try:
            page = e.get("page", "")
            url, credit, lic = commons_info(page) if "commons.wikimedia.org" in page else federal(e)
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                im = ImageOps.exif_transpose(Image.open(io.BytesIO(r.read()))).convert("RGB")
            if im.width < 800:
                raise ValueError(f"too small ({im.width} px wide)")
            n += 1
            rel = f"news/{slug}-{n}.jpg"
            ImageOps.fit(im, (1920, 1080), Image.LANCZOS, centering=(0.5, 0.45)).save(
                IMG / rel, "JPEG", quality=88, optimize=True, progressive=True)
            e.update({"file": rel, "credit": credit})
            sources[rel] = {"article": slug, "real": True, "page": page or url, "src": url, "license": lic,
                            "credit": credit, "added": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
            text = text.rstrip() + f"\n- {rel} — {e.get('describe', 'news photo')} (Photo: {credit})\n"
            added.append(rel)
            print(f"::notice::{slug}: real photo {rel} ({credit})")
        except Exception as ex:  # a missing photo must never stop the videos
            print(f"::warning::{slug}: real photo {e.get('page') or e.get('src')} skipped: {ex}")
    if added:
        a["images"] = added + [x for x in a.get("images", []) if x not in added]
        a["credits"] = [{"file": e["file"], "credit": e["credit"], "page": e.get("page") or e.get("src")}
                        for e in a["real_photos"] if e.get("file")]
        if a.get("image", "").startswith("gen/"):  # a real photo of the news beats an illustration as cover
            a["image"] = added[0]
        f.write_text(json.dumps(a, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        src_file.write_text(json.dumps(sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        cat.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    for s in sys.argv[1:]:
        try:
            run(s)
        except Exception as ex:
            print(f"::warning::real photos for {s} failed: {ex}")
