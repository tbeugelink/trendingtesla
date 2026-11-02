"""Independent Gemini check of a new image: three separate judgements (Visual Standard v1.0, "Quality control").

check(im, subject, refs, category) -> dict
  visual: 0-10, technical_pass + technical_errors, journalistic_pass + journalistic_issues, notes, ok.
  ok = visual >= 7 AND technical_pass AND journalistic_pass. A high score never makes up for a critical error.
"""
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "video"))
import gen_image as G  # noqa: E402

CHECKER = []


def init():
    if CHECKER:
        return
    import story as ST
    ST.init_checker(G)
    CHECKER.extend(ST.CHECKER)


def _part(im, side=1024):
    im = im.copy()
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=85)
    return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}


Q = """You are the strict photo editor of TrendingTesla, a Tesla technology publication whose readers know every
detail of the cars. Judge the FIRST image (new, AI-made). The other images are verified reference photos of the
same product: the new image must match them in every technical detail.

What the new image must show: {subject}
Journalistic category: {category} (A = general illustration; B = new technology or prototype, only confirmed
features; C = incident or specific event, must not look like an authentic photo of that event).

Judge three things SEPARATELY:
1. visual: 0-10 for photorealism, sharpness, composition, colour and light (7 = good enough to publish).
2. technical: separate CRITICAL errors from MINOR ones.
   CRITICAL (a Tesla owner would immediately call it wrong): wrong model, generation or variant; mixed
   generations; a charging port, door, door hinge, wheel or screen in the wrong place or of the wrong type;
   a missing steering wheel where there must be one (or one where there must be none); clearly wrong
   proportions; readable or garbled text, invented logos or emblems, licence plates, watermarks; obvious AI
   artefacts (melted parts, extra limbs, impossible geometry).
   MINOR (only an expert with the reference side by side would notice): small differences in pin layout, light
   guide pattern, trim, panel gaps, a missing small logo, slightly different screen size.
   technical_pass = false only when there is at least one CRITICAL error.
3. journalistic_pass: false if it could be mistaken for documentary evidence of a real event, shows a real
   recognisable person, or shows unconfirmed prototype features as fact. List the issues.
Answer only JSON: {{"visual": n, "technical_pass": true/false, "technical_errors": [critical only],
"minor_issues": [...],
"journalistic_pass": true/false, "journalistic_issues": [...], "notes": "one short line"}}"""


def check(im, subject, refs=(), category="A"):
    init()
    parts = [{"text": Q.format(subject=subject, category=category)}, _part(im)]
    parts += [_part(Image.open(r).convert("RGB"), 768) for r in list(refs)[:3]]
    last = None
    for mdl in CHECKER:
        try:
            d = G.api(f"models/{mdl}:generateContent", {"contents": [{"role": "user", "parts": parts}],
                                                       "generationConfig": {"responseMimeType": "application/json",
                                                                            "temperature": 0}})
            t = d["candidates"][0]["content"]["parts"][0]["text"]
            r = json.loads(t[t.find("{"):t.rfind("}") + 1])
            r["visual"] = float(r.get("visual", 0))
            r["ok"] = r["visual"] >= 7 and bool(r.get("technical_pass")) and bool(r.get("journalistic_pass"))
            r["checker"] = mdl
            return r
        except Exception as e:  # try the next checker model
            last = e
    return {"visual": 0, "technical_pass": False, "technical_errors": [f"check failed: {last}"],
            "journalistic_pass": False, "journalistic_issues": [], "ok": False, "checker": None}
