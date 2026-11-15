"""Real moving footage for Shorts and the weekly long video.

Clips live in video/clips/manifest.json (source, licence, attribution, tags). The bytes are not in git:
they are fetched into video/clips/cache/ the first time a render needs them. Allowed licences are public
domain, CC0 and CC BY only. Nothing is taken from a YouTube channel or a news broadcaster.

A shot uses a clip only when the beat's words overlap the clip's tags (and, when the clip is about one
car, that car is the one the article is about). Otherwise the existing stills and hook clip stay.
"""
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "clips" / "manifest.json"
CACHE = ROOT / "clips" / "cache"
ALLOW = {"public-domain", "cc0", "cc-by"}
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
    return len(hit) + (3 if model_hit else 0)


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


def bind_shots(shots, beats, article, w, h, fps, shot_max=2.0):
    """Attach a real clip to each shot that has a fitting one. Hard-cut length is the shot length, at most shot_max."""
    clips = load()
    models = list(article.get("models") or [])
    used = {}
    readers = []
    real = 0.0
    total = 0.0
    chosen = []
    for sh in shots:
        beat = beats[sh["beat"]] if sh.get("beat") is not None and sh["beat"] < len(beats) else {}
        text = " ".join(str(beat.get(k) or "") for k in ("text", "visual", "overlay"))
        total += sh["dur"]
        clip = pick(clips, text, models, used)
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
                         "page": clip["page"], "licence": clip["licence"]}
        sh["footage_reader"] = Reader(path, w, h, fps, start)
        readers.append(sh["footage_reader"])
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
