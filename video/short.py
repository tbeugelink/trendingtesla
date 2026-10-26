"""Make a vertical YouTube Short (1080x1920) for an article.

Usage:  python3 video/short.py <slug> [en|nl] [--voice piper|elevenlabs]

The spoken text is the article's "short" field ({"en": "...", "nl": "..."}): a 45-60 second
script, one sentence per scene. Without it the script is built from the title and description.
Voice: ElevenLabs when ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are set (captions are synced
with the word timestamps ElevenLabs returns), otherwise the result has no audio.
Output: video/out/<slug>-<lang>.mp4 and a matching .txt with the YouTube title, description and tags.
"""
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

W, H, FPS = 1080, 1920, 30
FB = str(ROOT / "video/fonts/Inter-Black.otf")
FX = str(ROOT / "video/fonts/Inter-ExtraBold.otf")
OUT = ROOT / "video/out"
SITE = "trendingtesla.com"
RED, YEL, BLUE = "#d61a1a", "#ffd400", "#1d5cff"


def font(f, s):
    return ImageFont.truetype(f, s)


def load(slug):
    f = next((ROOT / "content/articles").glob(f"*-{slug}.json"))
    return json.loads(f.read_text(encoding="utf-8"))


def photos(a):
    """Article photos in order, falling back to the site's own choice."""
    build.ALL_ARTS[:] = build.load_articles()
    out = []
    for c in build.candidates(a):
        p = build.STATIC / "img" / c.split("/img/", 1)[-1] if c.startswith("/img/") else None
        if p and p.exists() and "/v/" not in c and p not in out:
            out.append(p)
    return out or [build.STATIC / "img/topics/gigafactory.jpg"]


def script(a, lang):
    s = (a.get("short") or {}).get(lang)
    if not s:
        s = a[lang]["title"] + ". " + a[lang]["description"]
    end = {"en": f"More on {SITE}.", "nl": f"Meer op {SITE}."}[lang]
    if SITE not in s:
        s = s.rstrip() + " " + end
    return s


def spoken(text, lang):
    """Make numbers and symbols easier to pronounce."""
    t = text.replace("trendingtesla.com", "Trending Tesla dot com" if lang == "en" else "Trending Tesla punt com")
    t = t.replace("TrendingTesla", "Trending Tesla")
    return t


def tts_elevenlabs(text, out_mp3):
    key, voice = os.environ["ELEVENLABS_API_KEY"], os.environ["ELEVENLABS_VOICE_ID"]
    model = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": model,
                         "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.15}}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    out_mp3.write_bytes(base64.b64decode(d["audio_base64"]))
    al = d.get("normalized_alignment") or d["alignment"]
    return al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def words_timed(chars, starts, ends):
    """Group character timestamps into words with start/end times."""
    words, cur, t0 = [], "", None
    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if cur:
                words.append((cur, t0, e))
            cur, t0 = "", None
            continue
        if t0 is None:
            t0 = s
        cur += c
        last = e
    if cur:
        words.append((cur, t0, last))
    return words


def wrap(d, txt, f, maxw):
    out, cur = [], ""
    for w in txt.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    return out


def block(d, x, y, t, f, bg, fg):
    bb = f.getbbox("H")
    ch = bb[3] - bb[1]
    pad = int(ch * 0.32)
    w = d.textlength(t, font=f)
    d.rectangle([x, y, x + w + 2 * pad, y + ch + 2 * pad], fill=bg)
    d.text((x + pad, y + pad - bb[1]), t, font=f, fill=fg)
    return y + ch + 2 * pad


def outlined(d, x, y, t, f, fill, stroke):
    d.text((x, y), t, font=f, fill=fill, stroke_width=max(3, f.size // 22), stroke_fill=stroke)
    bb = f.getbbox("H")
    return y + (bb[3] - bb[1]) + int(f.size * 0.3)


def fit(d, t, f, s, maxw):
    while s > 30 and d.textlength(t, font=font(f, s)) > maxw:
        s -= 4
    return font(f, s)


def label(d, a, lang, y):
    lb = a.get("label") or {}
    t = lb.get(lang) or {}
    st = {"k": "a", "y": "a", "tag": "a", "w": "c", "s": "c"}.get(lb.get("style", "a"), lb.get("style", "a"))
    sub, txt, mw = t.get("sub", ""), t.get("text", a[lang]["title"]), W - 140
    if st == "r":
        block(d, 60, y, txt, fit(d, txt, FB, 92, mw - 40), RED, "#fff")
    elif st == "n":
        y = outlined(d, 60, y, txt, fit(d, txt, FB, 190, mw), YEL, "#111")
        block(d, 60, y + 10, sub, fit(d, sub, FB, 64, mw - 40), RED, "#fff")
    elif st == "c":
        y = outlined(d, 60, y, sub, fit(d, sub, FB, 100, mw), YEL, RED)
        block(d, 60, y + 6, txt, fit(d, txt, FB, 76, mw - 40), RED, "#fff")
    else:
        if sub:
            y = block(d, 60, y, sub, fit(d, sub, FB, 68, mw - 40), RED, "#fff") + 14
        outlined(d, 60, y, txt, fit(d, txt, FB, 112, mw), YEL, RED)


def render(a, lang, audio, words, total):
    imgs = photos(a)
    pics = []
    for p in imgs[:6]:
        im = Image.open(p).convert("RGB")
        sc = H * 1.08 / im.height
        pics.append(im.resize((int(im.width * sc), int(H * 1.08)), Image.LANCZOS))
    shade = Image.new("L", (1, H))
    for y in range(H):
        shade.putpixel((0, y), int(185 * max(0, (y - H * 0.5) / (H * 0.5)) ** 1.25 + 120 * max(0, (H * 0.16 - y) / (H * 0.16))))
    shade = shade.resize((W, H))
    black = Image.new("RGB", (W, H))
    fbrand, fcap = font(FX, 50), font(FB, 74)
    # captions: chunks of max ~4 words, timed from the voice
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 4 or w[0].endswith((".", "!", "?", ",")):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    scene_len = max(3.2, total / max(1, len(pics)))
    out = OUT / f"{a['slug']}-{lang}.mp4"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-c:a", "aac", "-b:a", "160k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(total * FPS) + 1
    for fr in range(n):
        t = fr / FPS
        i = min(len(pics) - 1, int(t / scene_len))
        im, p = pics[i], (t - i * scene_len) / scene_len
        x0 = int((im.width - W) * (0.2 + 0.6 * (p if i % 2 == 0 else 1 - p)))
        frame = im.crop((x0, int((im.height - H) / 2), x0 + W, int((im.height - H) / 2) + H))
        z = 1 + 0.035 * p
        cw, chh = int(W / z), int(H / z)
        frame = frame.crop(((W - cw) // 2, (H - chh) // 2, (W - cw) // 2 + cw, (H - chh) // 2 + chh)).resize((W, H))
        if t < 0.25:
            frame = Image.blend(black, frame, t / 0.25)
        frame = Image.composite(black, frame, shade)
        d = ImageDraw.Draw(frame)
        d.text((60, 92), "Trending", font=fbrand, fill="#fff")
        d.text((60 + d.textlength("Trending", font=fbrand), 92), "Tesla", font=fbrand, fill="#e8231c")
        if t < min(scene_len, 4.0):  # opening: the article label, like the thumbnail
            label(d, a, lang, 1080)
        last = t > total - 2.6
        if last:
            fe = font(FB, 104)
            w1, w2 = d.textlength("Trending", font=fe), d.textlength("Tesla", font=fe)
            x = (W - w1 - w2) / 2
            d.text((x, 760), "Trending", font=fe, fill="#fff")
            d.text((x + w1, 760), "Tesla", font=fe, fill="#e8231c")
            fs = font(FX, 58)
            d.text(((W - d.textlength(SITE, font=fs)) / 2, 900), SITE, font=fs, fill=YEL)
        ch = next((c for c in chunks if c[0][1] <= t <= c[-1][2] + 0.25), None)
        if ch and not last:
            txt = " ".join(w[0] for w in ch)
            y = 1460
            for ln in wrap(d, txt, fcap, W - 140):
                w = d.textlength(ln, font=fcap)
                d.text(((W - w) / 2, y), ln, font=fcap, fill="#fff", stroke_width=7, stroke_fill="#000")
                y += 96
        d.rectangle([0, H - 12, int(W * t / total), H], fill="#e8231c")
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    return out


def meta(a, lang, out):
    t = a[lang]
    url = f"https://{SITE}/{'nl/' if lang == 'nl' else ''}{a['slug']}/"
    tags = ["Tesla", "TrendingTesla"] + [build.CATEGORIES[a["category"]][lang]] + \
           [build.MODELS[m]["name"] for m in a.get("models", []) if m in build.MODELS]
    read = {"en": "Read the full article", "nl": "Lees het hele artikel"}[lang]
    note = {"en": "Voice-over generated with AI (ElevenLabs); script written and checked by TrendingTesla.",
            "nl": "Voice-over gemaakt met AI (ElevenLabs); tekst geschreven en gecontroleerd door TrendingTesla."}[lang]
    txt = (f"TITLE:\n{t['title'][:95]} #Shorts\n\nDESCRIPTION:\n{t['description']}\n\n{read}: {url}\n\n{note}\n\n"
           f"TAGS:\n{', '.join(dict.fromkeys(tags))}\n")
    out.with_suffix(".txt").write_text(txt, encoding="utf-8")


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    slug, lang = args[0], (args[1] if len(args) > 1 else "en")
    a = load(slug)
    OUT.mkdir(parents=True, exist_ok=True)
    text = script(a, lang)
    audio = None
    if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
        audio = OUT / f"{slug}-{lang}.mp3"
        chars, s, e = tts_elevenlabs(spoken(text, lang), audio)
        words = words_timed(chars, s, e)
        total = duration(audio) + 0.6
    else:  # silent preview: spread the words over ~2.6 words per second
        ws = text.split()
        words = [(w, i / 2.6, (i + 1) / 2.6) for i, w in enumerate(ws)]
        total = len(ws) / 2.6 + 1
    out = render(a, lang, audio, words, total)
    meta(a, lang, out)
    print(out, f"{total:.1f}s", "audio" if audio else "silent")


if __name__ == "__main__":
    main()
