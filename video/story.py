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
VOICE = os.environ.get("ELEVENLABS_VOICE_ID_3") or os.environ.get("ELEVENLABS_VOICE_ID", "")
SPEED = {"hook": 0.95, "tension": 1.0, "payoff": 0.95}
GAP = {"hook": 0.45, "tension": 0.22, "payoff": 0.35}
SFX_VOL, BED_VOL = 0.45, 0.14
DEFAULT_SFX = {  # natural cinematic sounds only (no whistles, coins, spins)
    "hook": "Deep cinematic impact hit with a low boom and short rumble tail",
    "payoff": "Deep cinematic bass drop with a soft sub boom, then silence",
    "bed": "Low tense cinematic ambient drone, dark and subtle, slowly building, no melody",
}
END_SEC = 2.2


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def tts(text, speed, out):
    d = json.loads(post(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_192",
                        {"text": text, "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
                         "voice_settings": {"stability": 0.28, "similarity_boost": 0.8, "style": 0.5, "speed": speed}}))
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
    j = 0
    for i, b in enumerate(beats):
        p = resolve(b["img"]) if b.get("img") else None
        if not p:
            p = order[j % len(order)]
            if i and p == beats[i - 1]["_img"] and len(order) > 1:
                j += 1
                p = order[j % len(order)]
            j += 1
        b["_img"] = p


def load_src(p, move):
    im = Image.open(p).convert("RGB")
    # cover the portrait frame with room to move: "rise" needs extra height, the rest a little zoom margin
    need_h = H * (1.30 if move == "rise" else 1.12)
    s = max(need_h / im.height, W * 1.12 / im.width)
    return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)


def ease(x):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, x)))


def frame(src, move, u, t, d, rnd):
    """Crop box (in source pixels) for progress u (0..1) of a shot; t = seconds into the shot."""
    sw, sh = src.size
    if move == "punch":
        z = 1.18 - 0.18 * ease(t / 0.45) + 0.04 * u
    elif move == "zoom":
        z = 1.0 + 0.12 * ease(u)
    elif move == "push":
        z = 1.0 + 0.07 * u
    else:
        z = 1.02
    fh = min(H / z, sh)  # the source is scaled so 1 source pixel = 1 video pixel at zoom 1
    fw = fh * W / H
    cx, cy = sw / 2, sh / 2
    if move == "pan":  # small, so the subject stays near the centre (the Short shows only the middle of the photo)
        dirn = 1 if rnd < 0.5 else -1
        cx += dirn * (ease(u) - 0.5) * min(0.10 * sw, (sw - fw) / 2)
    if move == "rise":  # camera moves top-to-bottom: the subject seems to rise
        top, bot = fh / 2, sh - fh / 2
        cy = top + (bot - top) * ease(u)
    shake = 0.0
    if move == "punch":
        shake = 18 * max(0.0, 1 - t / 1.3)
    elif move == "zoom":
        shake = 2.5
    elif move == "rise":
        shake = 4.0
    if shake:
        cx += shake * (math.sin(t * 47.0) + 0.5 * math.sin(t * 83.0 + 1.3))
        cy += shake * (math.cos(t * 41.0) + 0.5 * math.sin(t * 71.0 + 0.7))
    cx = min(max(cx, fw / 2), sw - fw / 2)
    cy = min(max(cy, fh / 2), sh - fh / 2)
    return (cx - fw / 2, cy - fh / 2, cx + fw / 2, cy + fh / 2)


FCAP = S.font(S.FB, 92)


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


def end_card(lang):
    im = Image.new("RGB", (W, H), (12, 12, 14))
    d = ImageDraw.Draw(im)
    f1, f2 = S.font(S.FB, 86), S.font(S.FX, 52)
    t1 = "trendingtesla.com"
    t2 = {"en": "More Tesla stories", "nl": "Meer Tesla-verhalen"}[lang]
    d.text(((W - f2.getlength(t2)) / 2, H * 0.42), t2, font=f2, fill=(255, 214, 0))
    d.text(((W - f1.getlength(t1)) / 2, H * 0.47), t1, font=f1, fill=(255, 255, 255))
    return im


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
    t, caps = 0.25, []
    for i, b in enumerate(beats):
        f = tmp / f"v{i:02d}.mp3"
        words = tts(S.spoken(b["text"], lang), float(b.get("speed") or SPEED[b["part"]]), f)
        dur = S.duration(f)
        b["_voice"], b["_t0"] = f, t
        caps += groups(words, t)
        nxt = beats[i + 1]["part"] if i + 1 < len(beats) else None
        gap = GAP["payoff"] if nxt == "payoff" and b["part"] != "payoff" else GAP[b["part"]]
        b["_dur"] = dur + gap + (0.25 if i == 0 else 0)
        t += b["_dur"]
        print(f"beat {i} {b['part']:7s} {b['move']:5s} {dur:5.2f}s {b['_img'].name}: {b['text'][:60]}")
    body_end = t
    total = body_end + END_SEC
    if total > 60:
        print(f"::warning::story Short is {total:.1f}s (over 60 s): shorten the script")

    # 2. sound: voice on the timeline, impact at the hook, a low bed under the tension, a drop at the payoff
    pay = next((b["_t0"] for b in beats if b["part"] == "payoff"), None)
    layers = [(b["_voice"], b["_t0"] + (0.25 if i == 0 else 0), 1.0) for i, b in enumerate(beats)]
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
    label, ltop = S.label_overlay(a, lang)
    capimgs = {}
    endimg = end_card(lang)
    out = OUT / f"{slug}-{lang}-short.mp4"
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio), "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                            "-c:a", "copy", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    rnd = random.Random(slug)
    srcs = {}
    n = int(round(total * FPS))
    bi = 0
    for k in range(n):
        tt = k / FPS
        if tt >= body_end:
            fr = endimg.copy()
            zz = 1 + 0.03 * (tt - body_end) / END_SEC
            if zz > 1:
                cw, ch = W / zz, H / zz
                fr = fr.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
            enc.stdin.write(fr.tobytes())
            continue
        while bi + 1 < len(beats) and tt >= beats[bi + 1]["_t0"]:
            bi += 1
        b = beats[bi]
        if bi not in srcs:
            srcs = {bi: (load_src(b["_img"], b["move"]), rnd.random())}
        src, r = srcs[bi]
        st = tt - b["_t0"]
        box = frame(src, b["move"], st / b["_dur"], st, b["_dur"], r)
        fr = src.resize((W, H), Image.BILINEAR, box=box).convert("RGBA")
        if bi == 0:  # the label tells what the story is about while the hook is spoken
            fr.alpha_composite(label)
        cg = next((c for c in caps if c[0] <= tt < c[1] + 0.15), None)
        if cg:
            key = " ".join(cg[2])
            if key not in capimgs:
                capimgs[key] = caption_img(cg[2])
            # opening shot: captions above the label; afterwards in the usual place
            fr.alpha_composite(capimgs[key], (0, int(ltop - 300) if bi == 0 else int(H * 0.60)))
        if st < 0.12 and bi > 0:  # quick flash-cut between shots instead of a still crossfade
            fr = Image.blend(fr.convert("RGB"), Image.new("RGB", (W, H), (255, 255, 255)), 0.18 * (1 - st / 0.12)).convert("RGBA")
        enc.stdin.write(fr.convert("RGB").tobytes())
    enc.stdin.close()
    if enc.wait():
        sys.exit("ffmpeg failed")
    S.PORTRAIT = True
    S.meta(a, lang, out)
    print(f"::notice::Story Short {out.name} ready ({total:.1f}s, {len(beats)} shots)")


if __name__ == "__main__":
    main()
