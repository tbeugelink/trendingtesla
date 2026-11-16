"""Real moving footage for Shorts and the weekly long video.

Clips live in video/clips/manifest.json (source, licence, attribution, tags). The bytes are not in git:
they are fetched into video/clips/cache/ the first time a render needs them. Allowed licences are public
domain, CC0 and CC BY only. Nothing is taken from a YouTube channel or a news broadcaster.

A shot uses a clip only when the beat matches a topic, the clip's tags name that subject and none of
the blocked scenes, and (for an unreviewed Pixabay hit) an image model sees the subject in the frames.
Otherwise the still photo is used.
"""
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "clips" / "manifest.json"
REVIEWED = ROOT / "clips" / "pixabay-reviewed.json"
CACHE = ROOT / "clips" / "cache"
ALLOW = {"public-domain", "cc0", "cc-by", "pixabay"}
# Pixabay asks callers to cache API responses for 24 hours.
PIXABAY_TTL = 24 * 60 * 60
_LAST_HTTP = [0.0]
# Tags that mean the clip is not a car, a charger, or a rocket we can use.
PIXABAY_DROP = {"nikola", "plasma", "coil", "lightning", "thunder"}
# Another maker's badge in the tags. "tesla" is allowed. Short tokens are matched whole.
OTHER_BRANDS = {
    "bmw", "audi", "mercedes", "porsche", "toyota", "honda", "ford", "volkswagen", "nissan",
    "hyundai", "kia", "volvo", "rivian", "lucid", "byd", "xpeng", "nio", "polestar", "chevrolet",
    "chevy", "jeep", "subaru", "mazda", "lexus", "ferrari", "lamborghini", "bugatti", "genesis",
    "cadillac", "peugeot", "renault", "skoda", "jaguar", "fiat", "dodge", "chrysler",
}
# Words that appear in almost every sentence and must not pull in a clip.
STOP = {"the", "and", "for", "with", "that", "this", "from", "into", "then", "than", "any", "its",
        "was", "were", "had", "has", "have", "not", "but", "you", "your", "our", "their", "they",
        "one", "two", "only", "own", "out", "off", "over", "after", "before", "about", "more"}


def load():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    clips = []
    for c in data["clips"]:
        lic = c["licence"]
        if lic not in ALLOW:
            raise SystemExit(f"clip {c['id']} has a licence that is not allowed: {lic}")
        blob = c["file_url"]
        if "youtube.com" in blob or "youtu.be" in blob or "youtube.com" in c["page"]:
            raise SystemExit(f"clip {c['id']} points at YouTube")
        clips.append(c)
    return clips


def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOP and len(w) > 2}


def score(clip, text, models):
    """How well a clip fits one beat. 0 means do not use it."""
    words = _words(text)
    if "falcon" in words and "wing" in words:  # a falcon-wing door is not a Falcon 9
        words = words - {"falcon"}
    tags = set()
    for t in clip.get("tags") or []:
        tags.add(t.lower())
        tags.update(t.lower().split("-"))
    hit = tags & words
    clip_models = set(clip.get("models") or [])
    model_hit = bool(clip_models & set(models or []))
    if clip_models and not model_hit and not (hit - {"model", "car", "tesla"}):
        return 0
    if not hit and not model_hit:
        return 0
    base = len(hit) + (3 if model_hit else 0)
    # Government launch footage wins over a stock rocket when both fit the beat.
    if clip.get("licence") != "pixabay" and hit & {"launch", "liftoff", "rocket", "starship", "booster", "falcon", "landing", "reentry"}:
        base += 5
    return base


def pick(clips, text, models, used):
    ranked = sorted(clips, key=lambda c: (-score(c, text, models), used.get(c["id"], 0), c["id"]))
    best = ranked[0] if ranked else None
    if not best or score(best, text, models) <= 0:
        return None
    return best


def ensure(clip):
    """Download the clip into the cache if it is not there yet. Returns the local path."""
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"{clip['id']}{Path(clip['file']).suffix or '.webm'}"
    if dest.exists() and dest.stat().st_size > 10000:
        return dest
    req = urllib.request.Request(clip["file_url"], headers={"User-Agent": "TrendingTeslaClipBot/1.0 (clips@trendingtesla.com)"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r, dest.open("wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            break
        except urllib.error.HTTPError as e:
            dest.unlink(missing_ok=True)
            if e.code != 429 or attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    if dest.stat().st_size < 10000:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"download of {clip['id']} was empty")
    return dest


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return max(0.1, float(out.stdout.strip() or "0"))


class Reader:
    """One shot of a real clip, cropped to the frame, decoded a frame at a time."""

    def __init__(self, path, w, h, fps, start):
        self.w, self.h = w, h
        self.p = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(path),
             "-vf", f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.last = None

    def next(self):
        raw = self.p.stdout.read(self.w * self.h * 3)
        if len(raw) == self.w * self.h * 3:
            self.last = Image.frombytes("RGB", (self.w, self.h), raw)
        return self.last

    def close(self):
        if self.p.poll() is None:
            self.p.kill()


def reviewed_doc():
    return json.loads(REVIEWED.read_text(encoding="utf-8"))


def topic_for(text, models=None, category=""):
    """The one stock-video topic for this beat, or None. More specific topics are listed first."""
    doc = reviewed_doc()
    blob = f"{text} {' '.join(models or [])} {category}".lower()
    if "falcon" in blob and "wing" in blob:
        blob = blob.replace("falcon", " ")
    models = [str(m) for m in (models or [])]
    for topic in doc["topics"]:
        when = topic.get("when") or {}
        if when.get("not_regex") and re.search(when["not_regex"], blob):
            continue
        hit = False
        if any(m in (when.get("models") or []) for m in models):
            hit = True
        if any(m.startswith(p) for m in models for p in (when.get("models_prefix") or [])):
            hit = True
        if category and category in (when.get("category") or []):
            hit = True
        if when.get("regex") and re.search(when["regex"], blob):
            hit = True
        if hit:
            return topic
    return None


def queries_for(text, models=None, category=""):
    """Curated searches for the beat's topic. Never the bare word tesla."""
    topic = topic_for(text, models, category)
    if not topic:
        return []
    return [q for q in topic["queries"] if q.strip().lower() != "tesla"]


def _tag_words(hit):
    raw = hit.get("tags") if isinstance(hit, dict) else ""
    words = set()
    for part in str(raw or "").lower().replace(",", " ").split():
        words.add(part.strip(".#"))
    return words


def block_words():
    return set(reviewed_doc().get("block") or []) | PIXABAY_DROP


def tags_ok(hit, topic):
    """The tags must name the subject and must not name a blocked scene or another brand."""
    words = _tag_words(hit)
    if not words or words & OTHER_BRANDS or words & block_words():
        return False
    need = set(topic.get("need") or [])
    if not (words & need):
        return False
    people = words & {"people", "person", "man", "woman", "crowd", "portrait"}
    if people and not (words & {"car", "vehicle", "suv", "automobile", "truck", "robot"}):
        return False
    return True


def rejected(hit):
    words = _tag_words(hit)
    if words & PIXABAY_DROP or words & OTHER_BRANDS or words & block_words():
        return True
    return False


def rendition(hit, portrait):
    """Largest 1080p-or-better file. Vertical wins when the Short is vertical."""
    opts = []
    for item in (hit.get("videos") or {}).values():
        if not isinstance(item, dict) or not item.get("url"):
            continue
        w, h = int(item.get("width") or 0), int(item.get("height") or 0)
        if max(w, h) < 1920:  # 1080p or larger (1920 on the long side); 720p is too soft to crop
            continue
        vertical = h > w
        prefer = 1 if portrait == vertical else 0
        opts.append((prefer, -(w * h), item))  # smallest file that is still 1080p
    if not opts:
        return None
    opts.sort(reverse=True)
    return opts[0][2]


def _http_json(url):
    wait = 0.7 - (time.time() - _LAST_HTTP[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": "TrendingTeslaClipBot/1.0 (clips@trendingtesla.com)"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            _LAST_HTTP[0] = time.time()
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _LAST_HTTP[0] = time.time()
        print(f"::warning::Pixabay search failed: HTTP {e.code}")
        return None


def search_pixabay(query, ident=None):
    """Cached for 24 hours, as Pixabay requires. Returns hit dicts, or [] when there is no key."""
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        if not getattr(search_pixabay, "warned", False):
            print("::warning::PIXABAY_API_KEY is not set; stock video search is skipped")
            search_pixabay.warned = True
        return []
    folder = CACHE / "pixabay-search"
    folder.mkdir(parents=True, exist_ok=True)
    label = f"id:{ident}" if ident else query
    dest = folder / (hashlib.sha256(label.encode()).hexdigest()[:20] + ".json")
    if dest.exists() and time.time() - dest.stat().st_mtime < PIXABAY_TTL:
        try:
            return json.loads(dest.read_text(encoding="utf-8")).get("hits") or []
        except (OSError, json.JSONDecodeError):
            pass
    url = "https://pixabay.com/api/videos/?key=" + urllib.parse.quote(key)
    if ident:
        url += "&id=" + urllib.parse.quote(str(ident))
    else:
        url += "&q=" + urllib.parse.quote(query)
    url += "&video_type=film&safesearch=true&per_page=20"
    data = _http_json(url)
    if not data:
        return []
    kept = []
    for hit in data.get("hits") or []:
        if rejected(hit):
            continue
        if not (rendition(hit, True) or rendition(hit, False)):
            continue
        kept.append(hit)
    dest.write_text(json.dumps({"hits": kept}), encoding="utf-8")
    return kept


def hit_to_clip(hit, portrait):
    if rejected(hit):
        return None
    video = rendition(hit, portrait)
    if not video:
        return None
    user = str(hit.get("user") or "Pixabay").strip() or "Pixabay"
    ident = hit.get("id")
    return {
        "id": f"pixabay-{ident}",
        "file": f"pixabay-{ident}.mp4",
        "file_url": video["url"],
        "page": hit.get("pageURL") or f"https://pixabay.com/videos/id-{ident}/",
        "licence": "pixabay",
        "attribution": f"Video: {user} via Pixabay",
        "tags": sorted(_tag_words(hit)),
        "models": [],
    }


PIXABAY_CAP = 4  # distinct stock downloads per video; further shots reuse these
_VISION = {"model": None}
_SEEN_BAD = set()


def sample_frames(path):
    """Two or three JPEG frames spread through the clip."""
    dur = duration(path)
    frames = []
    for frac in (0.2, 0.5, 0.8):
        raw = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-ss", f"{max(0.1, dur * frac):.2f}", "-i", str(path),
             "-frames:v", "1", "-vf", "scale=512:-1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
            capture_output=True).stdout
        if raw:
            frames.append(raw)
    return frames


def vision_ok(path, subject):
    """True only when an image model sees the subject in the frames. No model means reject."""
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        print("::warning::no image model for the footage check; stock clip rejected")
        return False
    frames = sample_frames(path)
    if len(frames) < 2:
        return False
    import sys
    sys.path.insert(0, str(ROOT.parent / "tools"))
    import gen_image as G
    if not _VISION["model"]:
        try:
            names = [m["name"].split("/", 1)[1] for m in G.api("models?pageSize=200").get("models", [])
                     if "generateContent" in m.get("supportedGenerationMethods", []) and "flash" in m["name"]
                     and "image" not in m["name"] and "tts" not in m["name"] and "live" not in m["name"]]
            names = [n for n in names if "lite" not in n] or names
            _VISION["model"] = names[0] if names else None
        except Exception as e:
            print(f"::warning::footage vision model lookup failed: {e}")
            return False
    if not _VISION["model"]:
        return False
    import base64
    parts = [{"text": ("You check stock video for a news channel. The clip may be used only if the frames "
                        f"clearly show this subject: {subject}. Reject scenery, food, offices, animals, wind "
                        "turbines, and any clip where that subject is missing or only a tiny detail. "
                        'Answer only JSON: {"ok": true or false, "why": "a few words"}')}]
    for raw in frames:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(raw).decode()}})
    try:
        d = G.api(f"models/{_VISION['model']}:generateContent",
                  {"contents": [{"role": "user", "parts": parts}],
                   "generationConfig": {"responseMimeType": "application/json", "temperature": 0}})
        txt = d["candidates"][0]["content"]["parts"][0]["text"]
        verdict = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
        ok = bool(verdict.get("ok"))
        if not ok:
            print(f"::notice::stock clip rejected: {verdict.get('why', '')[:120]}")
        return ok
    except Exception as e:
        print(f"::warning::footage vision check failed, clip rejected: {e}")
        return False


def _accept_stock(hit, topic, portrait, used, held, reviewed=False):
    denied = {int(i) for i in (reviewed_doc().get("deny") or [])}
    if int(hit.get("id") or 0) in denied or hit.get("id") in _SEEN_BAD or not tags_ok(hit, topic):
        return None
    clip = hit_to_clip(hit, portrait)
    if not clip or clip["id"] in used:
        return None
    try:
        path = ensure(clip)
    except Exception as e:
        print(f"::warning::real clip {clip['id']} skipped: {e}")
        return None
    if not reviewed and not vision_ok(path, topic["subject"]):
        _SEEN_BAD.add(hit.get("id"))
        path.unlink(missing_ok=True)
        return None
    clip["topic"] = topic["id"]
    held.append(clip)
    return clip


def choose(text, models, category, used, portrait, held=None):
    """Library clip first (NASA and Space Force win on launches). Then a stock clip that shows the subject.
    None means the still photo is used."""
    local = pick(load(), text, models, used)
    if local:
        return local
    topic = topic_for(text, models, category)
    if not topic:
        return None
    held = held if held is not None else []
    stock = [c for c in held if c.get("topic") == topic["id"]]
    if len(stock) >= PIXABAY_CAP:
        return min(stock, key=lambda c: (used.get(c["id"], 0), c["id"]))
    reviewed = {int(i) for i in (topic.get("ids") or [])}
    for ident in reviewed:
        for hit in search_pixabay(f"id:{ident}", ident=ident):
            clip = _accept_stock(hit, topic, portrait, used, held, reviewed=True)
            if clip:
                return clip
    for query in topic["queries"]:
        for hit in search_pixabay(query):
            if int(hit.get("id") or 0) in reviewed:
                continue
            clip = _accept_stock(hit, topic, portrait, used, held, reviewed=False)
            if clip:
                return clip
    if stock:
        return min(stock, key=lambda c: (used.get(c["id"], 0), c["id"]))
    return None


def bind_shots(shots, beats, article, w, h, fps, shot_max=2.0):
    """Attach a real clip to each shot that has a fitting one. Hard-cut length is the shot length, at most shot_max."""
    models = list(article.get("models") or [])
    category = article.get("category") or ""
    portrait = h > w
    used = {}
    readers = []
    held = []
    real = 0.0
    total = 0.0
    chosen = []
    for sh in shots:
        beat = beats[sh["beat"]] if sh.get("beat") is not None and sh["beat"] < len(beats) else {}
        text = " ".join(str(beat.get(k) or "") for k in ("text", "visual", "overlay"))
        total += sh["dur"]
        clip = choose(text, models, category, used, portrait, held)
        sh["footage"] = None
        if not clip:
            continue
        try:
            path = ensure(clip)
            dur = duration(path)
        except Exception as e:
            print(f"::warning::real clip {clip['id']} skipped: {e}")
            continue
        n = used.get(clip["id"], 0)
        used[clip["id"]] = n + 1
        span = min(sh["dur"], shot_max, max(0.4, dur - 0.2))
        start = (n * span) % max(0.1, dur - span)
        sh["footage"] = {"id": clip["id"], "path": str(path), "start": start, "credit": clip["attribution"],
                         "page": clip["page"], "licence": clip["licence"], "w": w, "h": h, "fps": fps}
        # The decoder starts when that shot is on screen, so one ffmpeg runs at a time.
        real += span
        chosen.append(sh["footage"])
    share = real / total if total else 0.0
    return {"share": share, "real": real, "total": total, "clips": chosen, "readers": readers}


def close_readers(readers):
    for r in readers or []:
        r.close()


def credit_lines(chosen):
    """Unique attribution lines, in first-used order."""
    out, seen = [], set()
    for c in chosen:
        key = c["page"]
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def record(slug, info, root):
    """Remember which real clips an article used, so the page can print the credit."""
    path = Path(root) / "content" / "footage-used.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data[slug] = {"share": round(info["share"], 4),
                  "credits": [{"credit": c["credit"], "page": c["page"]} for c in credit_lines(info["clips"])]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def describe(info):
    pct = info["share"] * 100
    n = len({c["id"] for c in info["clips"]})
    return (f"real footage {pct:.0f}% of screen time ({info['real']:.1f}s of {info['total']:.1f}s, {n} clips). "
            f"Target is 70%. Stills fill the rest.")
