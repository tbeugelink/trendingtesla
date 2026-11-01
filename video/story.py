"""Story-style vertical Short: hook -> tension -> payoff, every shot moving, sound effects under the voice.

Usage:  python3 video/story.py <slug> [en|nl]        -> video/out/<slug>-<lang>-short.mp4 (+ .txt for upload.py)

The script comes from the article's "short":
- "story" (optional, best): a list of beats {"text": "...", "part": "hook|tension|payoff", "img": "file or gen/...",
  "move": "punch|push|pan|rise|zoom", "sfx": "sound-effect prompt", "speed": 0.95}. One beat = one shot.
- otherwise the plain "en"/"nl" script is split into beats automatically (first = hook, last two = payoff).
Rules of the first story Shorts (Falcon 1, Cybercab): no still image anywhere, subjects kept horizontally centred,
a hard opening (punch-in + shake + impact), launches move top-to-bottom so the rocket seems to rise ("rise"),
closing shots zoom in with a light tremble, emphasis via capitals and commas, no artificial cartoon effects.
Needs ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID (ELEVENLABS_VOICE_ID_3 is used when set: the story voice).
"""
import base64
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

os.environ["VIDEO_FORMAT"] = "portrait"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import short as S  # noqa: E402  (fonts, photos, label, metadata, spoken text)
from PIL import Image, ImageDraw  # noqa: E402

W, H, FPS = 1080, 1920, 30
OUT = S.OUT
KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE = (os.environ.get(f"ELEVENLABS_VOICE_ID_{os.environ.get('STORY_VOICE', '1')}") or
         os.environ.get("ELEVENLABS_VOICE_ID", ""))  # STORY_VOICE=1 (default) uses ELEVENLABS_VOICE_ID
CAPTIONS = os.environ.get("STORY_CAPTIONS", "0") == "1"  # running subtitles off: only key words pop in
SPEED = {"hook": 1.0, "tension": 1.1, "payoff": 1.0}
GAP = {"hook": 0.35, "tension": 0.12, "payoff": 0.3}
SFX_VOL, BED_VOL = 0.45, 0.14
DEFAULT_SFX = {  # natural cinematic sounds only (no whistles, coins, spins)
    "hook": "Deep cinematic impact hit with a low boom and short rumble tail",
    "payoff": "Deep cinematic bass drop with a soft sub boom, then silence",
    "bed": "Low tense cinematic ambient drone, dark and subtle, slowly building, no melody",
}
END_SEC = 2.2
END_HOLD = 2.0  # the closing key word (the core message) stays 2 s longer after the voice ends


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def tts(text, speed, out):
    d = json.loads(post(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_192",
                        {"text": text, "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
                         "voice_settings": {"stability": float(os.environ.get("STORY_STABILITY", "0.2")), "similarity_boost": 0.8,
                                            "style": float(os.environ.get("STORY_STYLE", "0.8")),
                                            "use_speaker_boost": True, "speed": speed}}))
    out.write_bytes(base64.b64decode(d["audio_base64"]))
    al = d.get("alignment") or d["normalized_alignment"]
    return S.words_timed(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"])


def sfx(prompt, dur, tmp):
    f = tmp / f"sfx-{hashlib.md5(f'{prompt}|{dur}'.encode()).hexdigest()[:10]}.mp3"
    if not f.exists():
        f.write_bytes(post("https://api.elevenlabs.io/v1/sound-generation",
                           {"text": prompt, "duration_seconds": max(0.5, min(22.0, dur)), "prompt_influence": 0.5}))
    return f


def beats_from(a, lang):
    sh = a.get("short") or {}
    if sh.get("story"):
        bs = [dict(b) for b in sh["story"] if (b.get(lang) or b.get("text"))]
        for b in bs:
            b["text"] = b.get(lang) or b["text"]
        return bs
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", sh.get(lang, "").strip()) if s.strip()]
    beats, cur = [], ""
    for s in sents:  # one shot per sentence, very short sentences join the next (a shot needs ~2 s or more)
        cur = f"{cur} {s}".strip()
        if len(cur.split()) >= 6:
            beats.append(cur)
            cur = ""
    if cur:
        beats[-1:] = [f"{beats[-1]} {cur}"] if beats else [cur]
    n = len(beats)
    return [{"text": t, "part": "hook" if i == 0 else "payoff" if i >= n - 2 and n > 3 else "tension"}
            for i, t in enumerate(beats)]


ROCKET = re.compile(r"\b(launch|lift[s]? off|liftoff|rocket|starship|falcon|booster|ignition)\b", re.I)


def plan_moves(beats):
    alt = ["push", "pan", "push", "pan"]
    k = 0
    for i, b in enumerate(beats):
        if b.get("move"):
            continue
        if i == 0:
            b["move"] = "punch"
        elif b["part"] == "payoff" and i == len(beats) - 1:
            b["move"] = "zoom"
        elif ROCKET.search(b["text"]):
            b["move"] = "rise"
        else:
            b["move"] = alt[k % len(alt)]
            k += 1


def resolve(x):
    q = S.build.STATIC / "img" / (x if "/" in x else f"topics/{x}")
    return q if q.exists() else None


TESLA_FACTS = (
    "Facts Tesla owners know (must be right): Model 3 and Model Y have the charge port behind a small flap in the "
    "LEFT (driver's side) REAR tail light, nowhere else, and only one port; at a Supercharger cars usually back in, "
    "so the post stands behind the car's left rear corner and its single cable goes into that left rear tail light. "
    "Superchargers (V3/V4) are slim white posts with a red accent, one thick black cable each, a small Tesla logo. "
    "Model 3/Y inside: one large landscape touchscreen in the middle of the dashboard, NO screen behind the steering "
    "wheel, a round two-spoke steering wheel, a clean flat dashboard with a wood or fabric strip. Screens never show "
    "invented readable text: messages are short and blurred or simply a red warning box with an icon. ")
VERT = ("Photorealistic editorial photo, VERTICAL 9:16 portrait format, natural light, sharp focus, realistic "
        "proportions, colourful but natural colours (never grey). The main subject large and sharp in the middle of the "
        "frame (the centre third), clean background, no readable text, no logos other than on the real product, "
        "no licence plates, no recognisable real person. It must show exactly this moment of the story: ")


REFS = {}


def gen_scene(a, b, scene):
    """A new vertical photo for one moment of the story (Nano Banana), cached in static/img/gen/story/."""
    sys.path.insert(0, str(S.ROOT / "tools"))
    import gen_image as G
    g = a.get("gen_image") or {}
    subject = b.get("subject") or g.get("subject") or "the Tesla product in the story"
    h = hashlib.md5(f"{scene}|{subject}".encode()).hexdigest()[:10]
    f = S.build.STATIC / "img/gen/story" / f"{a['slug'][:70]}-{h}.jpg"
    qa_f = f.parent / "qa.json"
    qa = json.loads(qa_f.read_text()) if qa_f.exists() else {}
    if f.exists():
        if f.name in qa:
            return f
        ok, why = check_scene(G, Image.open(f), scene, subject, b)
        if ok:
            qa[f.name] = "ok"
            qa_f.write_text(json.dumps(qa, indent=1))
            return f
        print(f"::warning::kept photo rejected ({why[:160]}), making a new one")
    refs = []
    for r in (b.get("refs") or g.get("refs") or [])[:3]:
        k = json.dumps(r, sort_keys=True)
        if k not in REFS:  # fetch each reference once per video (Wikimedia limits repeated requests)
            try:
                rr = {**G.commons(r["commons"]), **r} if r.get("commons") and not r.get("src") else r
                REFS[k] = G.load_ref(rr["src"])
            except Exception as e:
                print(f"::warning::scene reference skipped: {e}")
                REFS[k] = None
        if REFS[k] is not None:
            refs.append(REFS[k])
    base = VERT + scene.strip() + "\n\n" + TESLA_FACTS + (b.get("facts") or a.get("facts") or "") + "\n" + \
        G.RULES.format(subject=subject)
    for attempt in range(3):
        im = scene_image(G, base, refs)
        ok, why = check_scene(G, im, scene, subject, b)
        if ok:
            break
        print(f"::warning::scene photo rejected ({why[:160]}), trying again")
        base += f"\nA previous attempt was wrong: {why}. Fix exactly that."
    else:
        raise RuntimeError(f"no correct photo for: {scene[:60]}")
    f.parent.mkdir(parents=True, exist_ok=True)
    im.save(f, "JPEG", quality=92)
    qa[f.name] = "ok"
    qa_f.write_text(json.dumps(qa, indent=1))
    return f


def scene_image(G, prompt, refs):
    parts = [{"text": prompt}]
    for r in refs:
        import io
        buf = io.BytesIO()
        r.save(buf, "JPEG", quality=90)
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}})
    d = G.api(f"models/{G.model()}:generateContent",
              {"contents": [{"role": "user", "parts": parts}],
               "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}})
    for c in d.get("candidates", []):
        for pt in c.get("content", {}).get("parts", []):
            blob = pt.get("inline_data") or pt.get("inlineData")
            if blob and blob.get("data"):
                import io
                return Image.open(io.BytesIO(base64.b64decode(blob["data"]))).convert("RGB")
    raise RuntimeError("no image in the response")


CHECKER = []


def init_checker(G):
    if CHECKER:
        return
    names = [m["name"].split("/", 1)[1] for m in G.api("models?pageSize=200").get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", []) and "flash" in m["name"]
             and "image" not in m["name"] and "tts" not in m["name"] and "live" not in m["name"]]
    def ver(n):  # newest version first: gemini-3.8-flash before gemini-2.5-flash
        m = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        return float(m.group(1)) if m else 0.0
    good = [n for n in names if "lite" not in n and "preview" not in n and "exp" not in n] or names
    good.sort(key=lambda n: (ver(n), -len(n)), reverse=True)
    CHECKER.extend(good[:3] or [None])
    print(f"photo check model: {CHECKER[0]}")


def check_scene(G, im, scene, subject, b):
    """Ask a Gemini vision model whether the photo gets the real details right. Returns (ok, problems)."""
    import io
    init_checker(G)
    if not CHECKER[0]:
        return True, ""
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=85)
    q = ("You check AI-made photos for a Tesla news channel whose viewers are Tesla owners who notice every wrong "
         f"detail. Subject: {subject}. The photo must show: {scene}\n{TESLA_FACTS}{b.get('facts') or ''}\n"
         "Check strictly: wrong product design or version, charge port in the wrong place or more than one port, "
         "a cable going to the wrong side of the car, invented readable text on screens or signs, extra or missing "
         "parts, physically impossible things, and whether it really shows the requested moment. "
         'Answer only JSON: {"ok": true or false, "problems": "short list, empty when ok"}')
    for mdl in CHECKER:
      try:
        d = G.api(f"models/{mdl}:generateContent",
                  {"contents": [{"role": "user", "parts": [{"text": q}, {"inline_data": {
                      "mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}]}],
                   "generationConfig": {"responseMimeType": "application/json", "temperature": 0}})
        txt = d["candidates"][0]["content"]["parts"][0]["text"]
        r = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
        return bool(r.get("ok")), str(r.get("problems") or "")
      except Exception as e:  # try the next model; the check is a safety net and never blocks the video
        print(f"::warning::photo check with {mdl} failed: {str(e)[:150]}")
    return True, ""


CREDITS = {}  # photo file -> credit line for the description
USED = set()  # Commons pages already used in this video
FOCUS = {}  # photo file -> horizontal position of its subject (0..1), for the vertical crop


def real_photo(a, b, spec):
    """A real, freely licensed photo from Wikimedia Commons for one moment: several searches, Gemini picks the
    photo that best shows what is said (and where its subject is, for the vertical crop). Cached with its credit."""
    import html
    import io
    import urllib.parse
    sys.path.insert(0, str(S.ROOT / "tools"))
    import gen_image as G
    import real_photos as R
    want = spec.get("want") or b["text"]
    qs = spec["q"] if isinstance(spec.get("q"), list) else [spec.get("q") or want]
    h = hashlib.md5((json.dumps(spec, sort_keys=True) + b["text"]).encode()).hexdigest()[:10]
    d = S.build.STATIC / "img/real/story"
    f = d / f"{a['slug'][:70]}-{h}.jpg"
    meta_f = d / "credits.json"
    meta = json.loads(meta_f.read_text()) if meta_f.exists() else {}
    if f.exists() and f.name in meta:
        CREDITS[f] = meta[f.name]["credit"]
        USED.add(meta[f.name]["page"])
        return f, meta[f.name].get("focus", 0.5)
    cands, seen = [], set()
    for q in qs:
        qq = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                                     "gsrsearch": q, "gsrlimit": 12, "prop": "imageinfo",
                                     "iiprop": "url|extmetadata|mime|size", "iiurlwidth": 1600})
        try:
            with urllib.request.urlopen(urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{qq}",
                                                               headers=G.UA), timeout=60) as r:
                pages = sorted(json.load(r).get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        except Exception as e:
            print(f"::warning::Commons search '{q}' failed: {e}")
            continue
        for p in pages:
            ii = (p.get("imageinfo") or [{}])[0]
            m = ii.get("extmetadata", {})
            lic = m.get("LicenseShortName", {}).get("value", "")
            if ii.get("mime") != "image/jpeg" or not R.free_licence(lic) or p.get("title") in seen:
                continue
            if min(ii.get("width", 0), ii.get("height", 0)) < 900:
                continue
            seen.add(p.get("title"))
            artist = re.sub(r"<[^>]+>", "", html.unescape(m.get("Artist", {}).get("value", ""))).strip() or "unknown"
            artist = re.sub(r"\s+", " ", artist)[:60]
            cands.append({"src": ii.get("thumburl") or ii["url"], "page": ii.get("descriptionurl"),
                          "credit": f"{artist}, {lic}, Wikimedia Commons"})
    best = None
    for c in [c for c in cands if c["page"] not in USED][:8]:  # a different real photo for every moment
        try:
            with urllib.request.urlopen(urllib.request.Request(c["src"], headers=G.UA), timeout=60) as r:
                im = Image.open(io.BytesIO(r.read())).convert("RGB")
        except Exception:
            continue
        sc, fx = rate_photo(G, im, want, b)
        print(f"real photo {sc}/10 for '{want[:50]}': {c['page']}")
        if sc >= 7 and (not best or sc > best[0]):
            best = (sc, fx, im, c)
            if sc >= 9:
                break
    if not best:
        raise RuntimeError(f"no fitting real photo for: {want[:60]}")
    d.mkdir(parents=True, exist_ok=True)
    best[2].save(f, "JPEG", quality=92)
    meta[f.name] = {"credit": best[3]["credit"], "page": best[3]["page"], "focus": best[1], "want": want}
    meta_f.write_text(json.dumps(meta, indent=1))
    CREDITS[f] = best[3]["credit"]
    USED.add(best[3]["page"])
    return f, best[1]


def rate_photo(G, im, want, b):
    """Gemini: how well does this real photo show `want` (0-10), and where is its subject (0 = left, 1 = right)?"""
    import io
    init_checker(G)
    buf = io.BytesIO()
    small = im.copy()
    small.thumbnail((1024, 1024))
    small.save(buf, "JPEG", quality=85)
    q = (f"Rate this photo for a Tesla news Short. It must clearly show: {want}. Score 0-10: 10 = shows exactly "
         "that, sharp and attractive; 5 = related but not that moment or detail; 0 = something else, a wrong car or "
         "product, a diagram, a screenshot or a poor photo. Also give focus_x: the horizontal position (0-1) of the "
         'main subject. Answer only JSON: {"score": n, "focus_x": x}')
    for mdl in CHECKER:
        try:
            d = G.api(f"models/{mdl}:generateContent",
                      {"contents": [{"role": "user", "parts": [{"text": q}, {"inline_data": {
                          "mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}]}],
                       "generationConfig": {"responseMimeType": "application/json", "temperature": 0}})
            txt = d["candidates"][0]["content"]["parts"][0]["text"]
            r = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
            return float(r.get("score", 0)), min(1.0, max(0.0, float(r.get("focus_x", 0.5))))
        except Exception as e:
            print(f"::warning::photo rating with {mdl} failed: {str(e)[:120]}")
    return 0.0, 0.5


def assign_images(a, beats):
    # only photos chosen for this article (its new gen/ photos first, then its own images and car galleries):
    # better to repeat a fitting photo than to show an unrelated topic photo
    own = [q for q in (resolve(x) for x in a.get("images") or []) if q]
    for m in a.get("models", []):
        own += [q for q in (S.build.STATIC / "img/models" / g for g in S.build.MODELS.get(m, {}).get("gallery", [])) if q.exists()]
    own = [q for q in dict.fromkeys(own) if q.name not in S.BLOCKED]
    if len(own) < 3:
        own += [q for q in S.photos(a) if q not in own][:3 - len(own)]
    gen = [p for p in own if "/gen/" in str(p)]
    order = gen + [p for p in own if p not in gen]
    a["_pool"] = order
    j, used = 0, {}
    for i, b in enumerate(beats):
        p = resolve(b["img"]) if b.get("img") else None
        if not p:
            p = order[j % len(order)]
            if i and p == beats[i - 1]["_img"] and len(order) > 1:
                j += 1
                p = order[j % len(order)]
            j += 1
        b["_img"] = p
        b["_imgs"] = []
        for lb in ([b["lib"]] if isinstance(b.get("lib"), str) else b.get("lib") or []):
            q = S.build.STATIC / "img/lib" / lb  # William's own checked detail photos come first
            if q.exists():
                b["_imgs"].append(q)
            else:
                print(f"::warning::library photo {lb} not found")
        for ph in ([b["photo"]] if isinstance(b.get("photo"), dict) else b.get("photo") or []):
            try:  # a real photo first where details matter (charge port, plug, screen, a real place)
                rf, fx = real_photo(a, b, ph)
                FOCUS[rf] = fx
                b["_imgs"].append(rf)
            except Exception as e:
                print(f"::warning::real photo failed: {e}")
        for sc in ([b["scene"]] if isinstance(b.get("scene"), str) else b.get("scene") or []):
            try:  # one generated photo per moment of the story: what is said is what you see
                b["_imgs"].append(gen_scene(a, b, sc))
            except Exception as e:
                print(f"::warning::scene photo failed, using an article photo: {e}")
        if b["_imgs"]:
            b["_img"] = b["_imgs"][0]
        b["_use"] = used.get(p, 0)  # 0 = whole photo; 1, 2, ... = a different close-up detail of it
        used[p] = b["_use"] + 1


XFADE = 2.0  # seconds of crossfade between shots (at most 60% of the shorter of the two shots)
SHOT_MAX = 3.0  # seconds: longer sentences are cut into several shots
FRAMINGS = [(1.0, 0.0, 0.0), (1.45, -0.28, -0.05), (1.45, 0.28, -0.05), (1.6, 0.0, -0.12), (1.35, -0.15, 0.05),
            (1.35, 0.15, 0.05)]  # (zoom, x, y offset as share of the free room): whole photo, then close-ups that
#                                  stay near the middle height, where the subject is (not the sky or the ground)
MOVES = ["in", "panL", "out", "panR", "tilt", "in"]


def load_src(p):
    from PIL import ImageEnhance
    im = Image.open(p).convert("RGB")
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.2)).enhance(1.08)  # less flat, more colour
    room = 1.12 if im.height > im.width else 1.30  # generated vertical photos are smaller: less spare room
    s = max(H * room / im.height, W * 1.12 / im.width)  # room to move in every direction
    return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)


def ease(x):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, x)))


def make_shots(beats, pool, rnd):
    """Cut every beat into shots of at most SHOT_MAX s; each shot gets its own photo or framing and its own move."""
    rot = [(im, f) for f in range(len(FRAMINGS)) for im in pool]  # every photo whole first, then close-ups
    k, shots, last = 0, [], None
    for bi, b in enumerate(beats):
        own = b.get("_imgs") or []
        n = max(len(own), 1, math.ceil(b["_dur"] / SHOT_MAX - 0.15))
        for j in range(n):
            if own:  # this beat's own scene photos; extra shots are close-ups of them (still on topic)
                q = j * len(own) // n
                img = own[q]
                fi = 0 if j == q * n // len(own) else 1 + (j % (len(FRAMINGS) - 1))
            elif j == 0 and b.get("img"):
                img, fi = b["_img"], 0
            else:
                for _ in range(len(rot)):
                    img, fi = rot[k % len(rot)]
                    k += 1
                    if img != last or len(pool) == 1:
                        break
            last = img
            if bi == 0 and j == 0:
                mv = "punch"
            elif b.get("move") == "rise":
                mv = "rise"
            elif bi == len(beats) - 1 and j == n - 1:
                mv = "zoom"
            else:
                mv = MOVES[(len(shots) + rnd.randrange(2)) % len(MOVES)]
            shots.append({"img": img, "f": fi, "move": mv, "shake": bool(b.get("shake")), "fx": FOCUS.get(img, 0.5), "t0": b["_t0"] + j * b["_dur"] / n, "dur": b["_dur"] / n,
                          "beat": bi})
    return shots


def frame(src, sh_, t, pop_t):
    """Crop box (source pixels) at t seconds into the shot; pop_t = seconds since a key word popped (or None)."""
    sw, shh = src.size
    u = t / sh_["dur"]
    z0, fx, fy = FRAMINGS[sh_["f"]]
    mv = sh_["move"]
    z, ox, oy = z0, fx, fy
    u = t / (sh_["dur"] + XFADE)  # even, steady motion that keeps going through the crossfade (no stop-start)
    if mv in ("in", "punch", "zoom"):
        z = z0 * (1.0 + 0.07 * u)
    elif mv == "out":
        z = z0 * (1.07 - 0.07 * u)
    elif mv in ("panL", "panR"):
        z = z0 * 1.05
        ox = fx + (0.10 if mv == "panR" else -0.10) * (u - 0.5)
    elif mv == "tilt":
        z = z0 * 1.05
        oy = fy + 0.12 * (u - 0.5)
    fh = min(H / z, shh)
    fw = min(fh * W / H, sw)
    cx = sw * sh_.get("fx", 0.5) + ox * (sw - fw) / 2
    cy = shh / 2 + oy * (shh - fh) / 2
    if mv == "rise":  # camera moves top-to-bottom: the subject seems to rise
        cy = fh / 2 + (shh - fh) * min(1.0, u)
    shake = 3.0 if mv == "rise" or sh_.get("shake") else 0.0  # shaking only fits rockets and launches
    if shake:
        cx += shake * (math.sin(t * 47.0) + 0.5 * math.sin(t * 83.0 + 1.3))
        cy += shake * (math.cos(t * 41.0) + 0.5 * math.sin(t * 71.0 + 0.7))
    cx = min(max(cx, fw / 2), sw - fw / 2)
    cy = min(max(cy, fh / 2), shh - fh / 2)
    return (cx - fw / 2, cy - fh / 2, cx + fw / 2, cy + fh / 2)


FCAP = S.font(S.FB, 92)
FPOP = S.font(S.FB, 230)
NUM = re.compile(r"^[$€£]?\d[\d.,]*[%kKmM]?$")


def norm(w):
    return re.sub(r"[^\w$€£%'-]", "", w).lower()


POP_H = 640


def pop_img(txt):
    """A key word or number, huge and yellow, on its own; two or more words are stacked (one per line)."""
    words = txt.split()
    lines = [txt] if len(words) == 1 else [" ".join(words[:len(words) // 2 + len(words) % 2]), " ".join(words[len(words) // 2 + len(words) % 2:])] \
        if len(words) > 3 else words
    f = FPOP
    while max(f.getlength(ln) for ln in lines) > W - 110 and f.size > 90:
        f = S.font(S.FB, f.size - 8)
    lh = int(f.size * 1.02)
    im = Image.new("RGBA", (W, POP_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = (POP_H - lh * len(lines)) / 2 - f.size * 0.12
    for ln in lines:
        x = (W - f.getlength(ln)) / 2
        d.text((x + 8, y + 10), ln, font=f, fill=(0, 0, 0, 150))
        d.text((x, y), ln, font=f, fill=(255, 214, 0), stroke_width=12, stroke_fill=(0, 0, 0))
        y += lh
    return im


def find_pops(b, words, t0):
    """Pop words of a beat: its "pop" list (words or phrases as spoken, shown as written in "pop") or, without
    one, words in capitals and numbers. Returns (start, end, text) on the video timeline."""
    wanted = b.get("pop")
    if wanted is None:
        wanted = [w for w, _, _ in words if (w.strip(".,!?;:").isupper() and len(re.sub(r"\W", "", w)) > 1)
                  or NUM.match(w.strip(".,!?;:"))]
    out = []
    for p in wanted if isinstance(wanted, list) else [wanted]:
        shown, say = (p.get("show"), p.get("say")) if isinstance(p, dict) else (p, p)
        toks = [norm(x) for x in str(say).split()]
        for k in range(len(words) - len(toks) + 1):
            if [norm(w) for w, _, _ in words[k:k + len(toks)]] == toks:
                st, en = words[k][1], words[k + len(toks) - 1][2]
                out.append((t0 + st - 0.15, t0 + max(en, st + 0.9), str(shown).strip(".,;: ").upper()))
                break
    return out


def caption_img(words):
    txt = " ".join(words)
    im = Image.new("RGBA", (W, 330), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    sp = FCAP.getlength(" ") + 18  # the thick outline eats into normal word spacing
    lines = S.wrap(d, txt, FCAP, W - 160)
    y = 165 - len(lines) * 55
    for ln in lines:
        ws = ln.split(" ")
        x = (W - sum(FCAP.getlength(w) for w in ws) - sp * (len(ws) - 1)) / 2
        for wd in ws:
            hot = wd.isupper() and len(re.sub(r"\W", "", wd)) > 1  # capitals = spoken emphasis -> yellow
            d.text((x, y), wd, font=FCAP, fill=(255, 214, 0) if hot else (255, 255, 255),
                   stroke_width=8, stroke_fill=(0, 0, 0))
            x += FCAP.getlength(wd) + sp
        y += 110
    return im


def groups(words, t0):
    """Caption groups of up to 3 words: (start, end, words) on the video timeline."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) == 3 or re.search(r"[.,!?;:]$", w[0]):
            out.append((t0 + cur[0][1], t0 + cur[-1][2], [x[0] for x in cur]))
            cur = []
    if cur:
        out.append((t0 + cur[0][1], t0 + cur[-1][2], [x[0] for x in cur]))
    for i in range(len(out) - 1):  # keep each group up until the next one starts (no flicker)
        out[i] = (out[i][0], max(out[i][1], out[i + 1][0]), out[i][2])
    return out


def title_card(a, lang):
    """The opening title, big and centred: yellow words plus a red block (story Shorts always use red)."""
    lb = a.get("label") or {}
    t = lb.get(lang) or {}
    st = {"k": "a", "y": "a", "tag": "a", "w": "c", "s": "c"}.get(lb.get("style", "a"), lb.get("style", "a"))
    txt, sub = (t.get("text") or a[lang]["title"]).strip(), t.get("sub", "").strip()
    if st == "r":
        rows = [("block", txt)]
    elif st == "a":
        rows = [("block", sub), ("big", txt)] if sub else [("big", txt)]
    else:  # "c" and "n": the big yellow words on top, the red block below
        rows = [("big", sub or txt), ("block", txt if sub else "")]
    rows = [r for r in rows if r[1]]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fonts = []
    for kind, x in rows:
        f = S.font(S.FB, 150 if kind == "big" else 165)  # the red block (often the number) at least as big
        while f.getlength(x) > W - (120 if kind == "big" else 190) and f.size > 60:
            f = S.font(S.FB, f.size - 6)
        fonts.append(f)
    gap = 30
    heights = [f.size * (1.05 if k == "big" else 1.35) for (k, _), f in zip(rows, fonts)]
    y = H * 0.50 - (sum(heights) + gap * (len(rows) - 1)) / 2  # in the exact centre of the frame
    for (kind, x), f, h in zip(rows, fonts, heights):
        w = f.getlength(x)
        if kind == "big":
            d.text(((W - w) / 2 + 8, y + 10), x, font=f, fill=(0, 0, 0, 150))
            d.text(((W - w) / 2, y), x, font=f, fill=(255, 214, 0), stroke_width=12, stroke_fill=(0, 0, 0))
        else:
            pad = f.size * 0.32
            d.rectangle([(W - w) / 2 - pad + 8, y + 10, (W + w) / 2 + pad + 8, y + h + 10], fill=(0, 0, 0, 110))
            d.rectangle([(W - w) / 2 - pad, y, (W + w) / 2 + pad, y + h], fill=(214, 24, 30))
            d.text(((W - w) / 2, y + (h - f.size) / 2 - f.size * 0.08), x, font=f, fill=(255, 255, 255))
        y += h + gap
    return im


SLOGAN = {"en": "Like and subscribe, and go to Trending Tesla dot com for more Tesla news!",
          "nl": "Like en abonneer, en ga naar Trending Tesla punt com voor meer Tesla-nieuws!"}
RED = (214, 24, 30)


def end_card(lang, bg=None):
    """The closing card: blurred last photo, a dark band, red LIKE & SUBSCRIBE pill, TrendingTesla.com."""
    from PIL import ImageFilter, ImageOps
    if bg is not None:
        im = ImageOps.fit(bg, (W, H)).filter(ImageFilter.GaussianBlur(18))
        im = Image.blend(im, Image.new("RGB", (W, H), (0, 0, 0)), 0.45)
    else:
        im = Image.new("RGB", (W, H), (12, 12, 14))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cy = H * 0.50
    d.rectangle((0, cy - 190, W, cy + 170), fill=(0, 0, 0, 150))
    fp = S.font(S.FB, 64)
    t1 = {"en": "LIKE & SUBSCRIBE", "nl": "LIKE & ABONNEER"}[lang]
    pw, ph = fp.getlength(t1) + 80, 104
    d.rounded_rectangle(((W - pw) / 2, cy - 150, (W + pw) / 2, cy - 150 + ph), radius=22, fill=RED + (255,))
    bb = fp.getbbox(t1)
    d.text(((W - fp.getlength(t1)) / 2, cy - 150 + (ph - (bb[3] + bb[1])) / 2), t1, font=fp, fill="white")
    fs = 136
    parts = [("Trending", (255, 255, 255)), ("Tesla", RED), (".com", (255, 255, 255))]
    while True:
        f = S.font(S.FB, fs)
        tw = sum(f.getlength(t) for t, _ in parts)
        if tw < W * 0.92 or fs < 60:
            break
        fs -= 4
    x, y = (W - tw) / 2, cy - 10
    for t, c in parts:
        d.text((x, y), t, font=f, fill=c, stroke_width=3, stroke_fill=(0, 0, 0))
        x += f.getlength(t)
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def main():
    slug = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] in ("en", "nl") else "en"
    S.LANG[0] = lang
    a = S.load(slug)
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f"story-{slug}"
    tmp.mkdir(exist_ok=True)
    beats = beats_from(a, lang)
    plan_moves(beats)
    assign_images(a, beats)

    # 1. voice per beat, timeline
    t, caps, pops = 0.25, [], []
    for i, b in enumerate(beats):
        f = tmp / f"v{i:02d}.mp3"
        words = tts(S.spoken(b["text"], lang), float(b.get("speed") or SPEED[b["part"]]), f)
        dur = S.duration(f)
        b["_voice"], b["_t0"] = f, t
        if CAPTIONS:
            caps += groups(words, t)
        pops += [(p0, p1, txt, i) for p0, p1, txt in find_pops(b, words, t + (0.25 if i == 0 else 0))]
        nxt = beats[i + 1]["part"] if i + 1 < len(beats) else None
        gap = GAP["payoff"] if nxt == "payoff" and b["part"] != "payoff" else GAP[b["part"]]
        b["_dur"] = dur + gap + (0.25 if i == 0 else 0) + (END_HOLD if i == len(beats) - 1 else 0)
        t += b["_dur"]
        print(f"beat {i} {b['part']:7s} {b['move']:5s} {dur:5.2f}s {b['_img'].name}: {b['text'][:60]}")
    body_end = t
    slog = tmp / "slogan.mp3"
    tts(SLOGAN[lang], 1.05, slog)
    end_sec = max(END_SEC, S.duration(slog) + 0.8)
    total = body_end + end_sec
    if total > 60:
        print(f"::warning::story Short is {total:.1f}s (over 60 s): shorten the script")

    # 2. sound: voice on the timeline, impact at the hook, a low bed under the tension, a drop at the payoff
    pay = next((b["_t0"] for b in beats if b["part"] == "payoff"), None)
    layers = [(b["_voice"], b["_t0"] + (0.25 if i == 0 else 0), 1.0) for i, b in enumerate(beats)]
    layers.append((slog, body_end + 0.2, 1.0))
    try:
        layers.append((sfx(beats[0].get("sfx") or DEFAULT_SFX["hook"], 2.5, tmp), 0.0, SFX_VOL))
        bed_len = (pay or body_end) - beats[0]["_dur"]
        if bed_len > 3:
            layers.append((sfx(DEFAULT_SFX["bed"], min(22.0, bed_len), tmp), beats[0]["_dur"], BED_VOL))
        if pay:
            layers.append((sfx(DEFAULT_SFX["payoff"], 2.5, tmp), pay, SFX_VOL * 0.8))
        for b in beats[1:]:
            if b.get("sfx"):
                layers.append((sfx(b["sfx"], min(6.0, b["_dur"]), tmp), b["_t0"], SFX_VOL))
    except Exception as e:  # sound effects are a bonus: never fail the video on them
        print(f"::warning::sound effects skipped: {e}")
    audio = tmp / "mix.m4a"
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f, _, _ in layers:
        cmd += ["-i", str(f)]
    fl = [f"[{k}:a]adelay={int(st * 1000)}|{int(st * 1000)},volume={v}[a{k}]" for k, (_, st, v) in enumerate(layers)]
    fl.append("".join(f"[a{k}]" for k in range(len(layers))) +
              f"amix=inputs={len(layers)}:normalize=0,alimiter=limit=0.95,apad,atrim=0:{total:.2f}[out]")
    subprocess.run(cmd + ["-filter_complex", ";".join(fl), "-map", "[out]", "-c:a", "aac", "-b:a", "192k",
                          "-ar", "44100", str(audio)], check=True)

    # 3. picture: every frame moves; label on the opening shot; captions; end card
    label, ltop = title_card(a, lang), H * 0.60
    capimgs = {}
    out = OUT / f"{slug}-{lang}-short.mp4"
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                            "-c:a", "copy", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    rnd = random.Random(slug)
    shots = make_shots(beats, a["_pool"], rnd)
    print(f"{len(shots)} shots, {len(set(x['img'] for x in shots))} photos")
    try:
        endimg = end_card(lang, load_src(shots[-1]["img"]))
    except Exception as e:
        print(f"::warning::end card background skipped: {e}")
        endimg = end_card(lang)
    srcs = {}
    n = int(round(total * FPS))
    si = 0
    hook_end = beats[1]["_t0"] if len(beats) > 1 else body_end
    label_end = min([p[0] for p in pops] + [2.2])
    # key words fill each sentence: the first one shows from the start of its sentence (after the label), each one
    # stays until the next one, and never runs into the next sentence (that is another subject)
    pops.sort()
    held = []
    for k, (p0, p1, txt, bi) in enumerate(pops):
        bstart = max(beats[bi]["_t0"] + 0.1, label_end) if bi else p0
        bend = beats[bi]["_t0"] + beats[bi]["_dur"]
        first = k == 0 or pops[k - 1][3] != bi
        nxt = pops[k + 1][0] if k + 1 < len(pops) and pops[k + 1][3] == bi else bend
        held.append((min(p0, bstart) if first else p0, max(p1, nxt), txt))
    pops = held
    for k in range(n):
        tt = k / FPS
        if tt >= body_end:
            fr = endimg.copy()
            zz = 1 + 0.03 * (tt - body_end) / end_sec
            if zz > 1:
                cw, ch = W / zz, H / zz
                fr = fr.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
            enc.stdin.write(fr.tobytes())
            continue
        while si + 1 < len(shots) and tt >= shots[si + 1]["t0"]:
            si += 1
        shot = shots[si]
        if shot["img"] not in srcs:
            srcs[shot["img"]] = load_src(shot["img"])
        src = srcs[shot["img"]]
        st = tt - shot["t0"]
        pg = next((p for p in pops if p[0] <= tt < p[1]), None)
        box = frame(src, shot, st, (tt - pg[0]) if pg else None)
        fr = src.resize((W, H), Image.BILINEAR, box=box)
        xf = min(XFADE, 0.6 * shot["dur"], 0.6 * shots[si - 1]["dur"]) if si > 0 else 0
        if xf > 0.01 and st < xf:  # smooth crossfade from the previous shot, which keeps moving meanwhile
            pv = shots[si - 1]
            if pv["img"] not in srcs:
                srcs[pv["img"]] = load_src(pv["img"])
            pbox = frame(srcs[pv["img"]], {**pv, "dur": pv["dur"] + XFADE}, tt - pv["t0"], None)
            prev = srcs[pv["img"]].resize((W, H), Image.BILINEAR, box=pbox)
            fr = Image.blend(prev, fr, ease(st / xf))
        fr = fr.convert("RGBA")
        bi = 0 if tt < hook_end else 1
        if tt < label_end:  # the label alone for a moment: what the story is about
            fr.alpha_composite(label)
        cg = None if pg else next((c for c in caps if c[0] <= tt < c[1] + 0.15), None)
        if pg:  # a key word pops in big (scale 1.35 -> 1 in 0.15 s) and replaces the caption while it is spoken
            key = "POP " + pg[2]
            if key not in capimgs:
                capimgs[key] = pop_img(pg[2])
            pi = capimgs[key]
            sc = 1 + 0.35 * max(0.0, 1 - (tt - pg[0]) / 0.15)
            if sc > 1.001:
                pi = pi.resize((int(W * sc), int(POP_H * sc)), Image.BILINEAR)
                ox, oy = (pi.width - W) // 2, (pi.height - POP_H) // 2
                pi = pi.crop((ox, oy, ox + W, oy + POP_H))
            fr.alpha_composite(pi, (0, int(H * 0.36)))
        if cg:
            key = " ".join(cg[2])
            if key not in capimgs:
                capimgs[key] = caption_img(cg[2])
            # opening shot: captions above the label; afterwards in the usual place
            fr.alpha_composite(capimgs[key], (0, int(ltop - 300) if bi == 0 else int(H * 0.60)))
        enc.stdin.write(fr.convert("RGB").tobytes())
    enc.stdin.close()
    if enc.wait():
        sys.exit("ffmpeg failed")
    S.PORTRAIT = True
    S.meta(a, lang, out)
    used = [CREDITS[x] for x in dict.fromkeys(sh["img"] for sh in shots) if x in CREDITS]
    if used:
        t = out.with_suffix(".txt")
        lab = {"en": "Photos", "nl": "Foto's"}[lang]
        t.write_text(t.read_text(encoding="utf-8").replace("\n\nTAGS:", f"\n\n{lab}: " + "; ".join(dict.fromkeys(used)) + "\n\nTAGS:", 1),
                     encoding="utf-8")
    print(f"::notice::Story Short {out.name} ready ({total:.1f}s, {len(beats)} shots)")


if __name__ == "__main__":
    main()
