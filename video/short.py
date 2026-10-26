"""Make a video for an article: landscape 1920x1080 (default) or a vertical Short 1080x1920 (--portrait).

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
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

PORTRAIT = "--portrait" in sys.argv or os.environ.get("VIDEO_FORMAT") == "portrait"
W, H, FPS = (1080, 1920, 30) if PORTRAIT else (1920, 1080, 30)
# layout per format: brand y, label y, caption top y, caption line height, caption size, end screen y, label width
LAY = dict(brand=92, label=1080, cap=1460, capl=96, caps=74, end=760, lw=W - 140) if PORTRAIT else \
      dict(brand=44, label=640, cap=880, capl=78, caps=62, end=400, lw=int(W * 0.55))
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
    # short on photos? add the gallery of the car the article is about (never a new Roadster before its reveal)
    for m in a.get("models", []):
        if len(out) >= 5:
            break
        if m.startswith("roadster") and a.get("date", "") < "2026-10-15":
            continue
        for g in build.MODELS.get(m, {}).get("gallery", []):
            q = build.STATIC / "img/models" / g
            if q.exists() and g not in {o.name for o in out} and len(out) < 6:
                out.append(q)
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
                         "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.15,
                                            "speed": float(os.environ.get("ELEVENLABS_SPEED", "1.08"))}}).encode(),
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


PAL = {  # same colour sets as the site labels: (block bg, block text, big text, big text outline)
    "yr": (RED, "#fff", YEL, RED), "bw": (BLUE, "#fff", "#fff", "#000"), "kw": ("#111", "#fff", "#fff", BLUE),
    "wb": ("#fff", "#111", "#3d7bff", "#fff"), "by": (BLUE, "#fff", YEL, "#111"),
}
SIZES = {"a": [6.6, 10.5], "c": [8, 6.2], "n": [10, 5.8], "r": [7.4, 7.4]}  # % of width, as on the site


def site_palette(slug):
    """Run the site's own photo and palette choice so the video label has the same colours."""
    arts = build.load_articles()
    build.ALL_ARTS[:] = arts
    seen = {}
    for x in sorted(arts, key=build.published):
        build.PHOTO_ORDER[x["slug"]] = seen.get(x["category"], 0)
        seen[x["category"]] = build.PHOTO_ORDER[x["slug"]] + 1
        if x.get("models"):
            gk = "g:" + (build.MODELS[x["models"][0]].get("parent") or x["models"][0])
            build.GALLERY_ORDER[x["slug"]] = seen.get(gk, 0)
            seen[gk] = build.GALLERY_ORDER[x["slug"]] + 1
    build.assign_photos(arts)
    build.assign_palettes(arts)
    return build.PALETTE.get(slug, "yr")


def label_overlay(a, lang):
    """The photo label exactly as the site draws it: bottom-left, 2.6% margin, same type sizes and colours.
    Returns the RGBA overlay and the y of its top edge."""
    lb = a.get("label") or {}
    t = lb.get(lang) or {}
    st = {"k": "a", "y": "a", "tag": "a", "w": "c", "s": "c"}.get(lb.get("style", "a"), lb.get("style", "a"))
    txt, sub = t.get("text") or a[lang]["title"], t.get("sub", "")
    if st == "n":
        lines = [("yo", txt, False), ("bk", sub, False)]
    elif st == "r":
        lines = [("bk", txt, True)]
    else:
        if not sub:
            sub, txt = build.split2(txt)
        lines = [("bk", sub, True), ("yo", txt, True)] if st == "a" else [("yo", sub, True), ("bk", txt, True)]
    lines = [(c, x.upper(), nb) for c, x, nb in lines if x]
    bg, fg, yc, yo_line = PAL["yr"] if st == "r" else PAL.get(site_palette(a["slug"]), PAL["yr"])
    cq = W / 100
    left = 2.6 * cq
    avail = 0.85 * W  # the site leaves room for the reading-time badge on the right
    m = SIZES.get(st, SIZES["a"])

    def parts(x, use_nb, cls):
        """Split a leading number with its unit off, shown bigger (like the site's numbig)."""
        mm = build.NUMRE.match(x) if use_nb else None
        if mm and mm.group(2).strip():
            tok = mm.group(1)
            if sum(ch.isdigit() for ch in tok) >= 2 or re.search(r"[€$%+\-–−]|[A-Z]", tok):
                return [(tok, 1.32 if cls == "yo" else 1.22), (mm.group(2), 1.0)]
        return [(x, 1.0)]

    def width(segs, f, cls):
        w = sum(font(FB, max(8, int(f * k))).getlength(s) for s, k in segs)
        return w + (0.48 * f if cls == "bk" else 0)

    segs = [parts(x, nb, c) for c, x, nb in lines]
    fs = []
    for i, (c, x, nb) in enumerate(lines):
        f = (m[1] if len(lines) == 1 else m[i]) * cq
        for _ in range(3):
            w = width(segs[i], f, c)
            if w > avail:
                f *= avail / w * 0.995
        fs.append(f)
    if len(fs) == 2:
        if st == "a":
            w0, w1 = width(segs[0], fs[0], "bk"), width(segs[1], fs[1], "yo")
            if w1 > w0 * 1.04:
                g = max(fs[1] * w0 / w1, fs[0] * 1.18)
                fs[1] = min(fs[1], g)
            fs[0] = min(fs[0], fs[1] * 0.85)
        if st == "c":
            fs[1] = min(fs[1], fs[0] * 0.9)
        if st == "n":
            fs[1] = min(fs[1], fs[0] * 0.62)
    # line boxes (CSS line-height 1 with Inter: baseline at 0.864em, 0.136em below)
    boxes = []
    for i, (c, x, nb) in enumerate(lines):
        f = fs[i]
        up = max(0.864 * f * k for _, k in segs[i] + [("", 1.0)])
        dn = max(0.136 * f * k for _, k in segs[i] + [("", 1.0)])
        if c == "bk":
            up, dn = up + 0.13 * f, dn + 0.12 * f
        gap = 0.1 * f if i else 0
        boxes.append((gap, up, dn))
    height = sum(g + u + d for g, u, d in boxes)
    y = H - 2.6 * cq - height
    top = y
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(im), ImageDraw.Draw(sh)
    for i, (c, x, nb) in enumerate(lines):
        g, up, dn = boxes[i]
        y += g
        f, base = fs[i], y + up
        if c == "bk":
            w = width(segs[i], f, c)
            ds.rectangle([left, y + 0.4 * cq, left + w, y + up + dn + 0.4 * cq], fill=(0, 0, 0, 90))
            d.rectangle([left, y, left + w, y + up + dn], fill=bg)
            xx = left + 0.24 * f
        else:
            xx = left
        for sgm, k in segs[i]:
            fo = font(FB, max(8, int(f * k)))
            if c == "bk":
                d.text((xx, base), sgm, font=fo, fill=fg, anchor="ls")
            else:
                ds.text((xx, base + 0.5 * cq), sgm, font=fo, fill=(0, 0, 0, 110), anchor="ls")
                d.text((xx, base), sgm, font=fo, fill=yc, anchor="ls", stroke_width=max(2, round(0.2 * cq)), stroke_fill=yo_line)
            xx += fo.getlength(sgm)
        y += up + dn
    sh = sh.filter(ImageFilter.GaussianBlur(cq * 0.6))
    sh.alpha_composite(im)
    return sh, top


def overlay(draw_fn):
    """Pre-render an RGBA overlay once; pasting it per frame is far cheaper than drawing text."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im))
    return im


ZOOM, TR, SCENE = 1.35, 1.0, 5.0  # image headroom for zoom/pan, crossfade length, seconds per photo


def ease(x):
    return x * x * (3 - 2 * x)


def render(a, lang, audio, words, total):
    imgs = photos(a)
    shade = Image.new("L", (1, H))
    for y in range(H):
        shade.putpixel((0, y), int(185 * max(0, (y - H * 0.5) / (H * 0.5)) ** 1.25 + 120 * max(0, (H * 0.16 - y) / (H * 0.16))))
    shade = shade.resize((W, H))
    pics = []
    for p in imgs[:8]:  # scaled to cover the frame with room to zoom and pan
        im = Image.open(p).convert("RGB")
        sc = max(H * ZOOM / im.height, W * ZOOM / im.width)
        pics.append(im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS))
    fbrand, fcap = font(FX, 50), font(FB, LAY["caps"])

    def brand(d):
        d.text((60, LAY["brand"]), "Trending", font=fbrand, fill="#fff")
        d.text((60 + d.textlength("Trending", font=fbrand), LAY["brand"]), "Tesla", font=fbrand, fill="#e8231c")

    def ending(d):
        fe = font(FB, 104)
        w1, w2 = d.textlength("Trending", font=fe), d.textlength("Tesla", font=fe)
        x = (W - w1 - w2) / 2
        d.text((x, LAY["end"]), "Trending", font=fe, fill="#fff")
        d.text((x + w1, LAY["end"]), "Tesla", font=fe, fill="#e8231c")
        fs = font(FX, 58)
        d.text(((W - d.textlength(SITE, font=fs)) / 2, LAY["end"] + 140), SITE, font=fs, fill=YEL)

    o_brand, o_end = overlay(brand), overlay(ending)
    o_label, label_top = label_overlay(a, lang)
    # captions: chunks of max ~4 words, timed from the voice
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 4 or w[0].endswith((".", "!", "?", ",")):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    caps = {}

    def cap(txt, above=None):
        """Caption overlay; while the label shows, captions sit just above it."""
        key = (txt, above)
        if key not in caps:
            def dr(d):
                lines = wrap(d, txt, fcap, W - 140 if PORTRAIT else W - 360)
                bottom = above if above is not None else (LAY["cap"] + len(lines) * LAY["capl"] if PORTRAIT else H - 70)
                y = bottom - len(lines) * LAY["capl"]
                for ln in lines:
                    w = d.textlength(ln, font=fcap)
                    d.text(((W - w) / 2, y), ln, font=fcap, fill="#fff", stroke_width=7, stroke_fill="#000")
                    y += LAY["capl"]
            caps[key] = overlay(dr)
        return caps[key]

    # one photo per ~5 s, each with a calm but clear move, 1 s crossfade into the next
    nsc = max(1, round(total / SCENE))
    first = total / nsc
    starts = [k * first for k in range(nsc)]
    out = OUT / f"{a['slug']}-{lang}{'-short' if PORTRAIT else ''}.mp4"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:  # pad the voice with silence so it never ends before the picture
        cmd += ["-i", str(audio), "-af", "apad", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-t", f"{total:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "21",
            "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    black, white = Image.new("RGB", (W, H)), Image.new("RGB", (W, H), "#fff")
    nsc = len(starts)

    def shot(k, t):
        """Scene k at time t: alternately a slow deep zoom-in and a camera move from left to right."""
        im = pics[k % len(pics)]
        rnd = k // len(pics)  # repeat round: frame another part of the photo
        span = (starts[k + 1] if k + 1 < nsc else total) - starts[k] + TR  # keeps moving through the fade
        p = ease(max(0.0, min(1.0, (t - starts[k]) / span)))
        if (k + rnd) % 2 == 0:
            z, cx, cy = 1.0 + 0.32 * p, [0.5, 0.35, 0.65][rnd % 3], 0.45   # zoom in
        else:
            z, cx, cy = 1.3, p, 0.5                                          # pan left -> right
        cw, chh = min(W * ZOOM / z, im.width), min(H * ZOOM / z, im.height)  # z=ZOOM: native pixels
        x0, y0 = (im.width - cw) * cx, (im.height - chh) * cy
        return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + chh))

    def picture(t):
        k = max(i for i, s0 in enumerate(starts) if s0 <= t)
        fr = shot(k, t)
        if k > 0 and t - starts[k] < TR:  # crossfade from the previous photo
            fr = Image.blend(shot(k - 1, t), fr, ease((t - starts[k]) / TR))
        return Image.composite(black, fr, shade)

    n = int(total * FPS) + 1
    for fr in range(n):
        t = fr / FPS
        frame = picture(t)
        frame.paste(o_brand, (0, 0), o_brand)
        last = t > total - 2.6
        if t < first:  # opening: the article label, like the thumbnail
            frame.paste(o_label, (0, 0), o_label)
        if last:
            frame.paste(o_end, (0, 0), o_end)
        ch = next((c for c in chunks if c[0][1] <= t <= c[-1][2] + 0.25), None)
        if ch and not last:
            o = cap(" ".join(w[0] for w in ch), int(label_top - 0.02 * W) if t < first else None)
            frame.paste(o, (0, 0), o)
        ImageDraw.Draw(frame).rectangle([0, H - 12, int(W * t / total), H], fill="#e8231c")
        try:
            proc.stdin.write(frame.tobytes())
        except BrokenPipeError:
            break
    try:
        proc.stdin.close()
    except BrokenPipeError:
        pass
    if proc.wait() != 0:
        raise SystemExit(f"ffmpeg failed with code {proc.returncode}")
    return out


def meta(a, lang, out):
    t = a[lang]
    url = f"https://{SITE}/{'nl/' if lang == 'nl' else ''}{a['slug']}/"
    tags = ["Tesla", "TrendingTesla"] + [build.CATEGORIES[a["category"]][lang]] + \
           [build.MODELS[m]["name"] for m in a.get("models", []) if m in build.MODELS]
    read = {"en": "Read the full article", "nl": "Lees het hele artikel"}[lang]
    note = {"en": "Voice-over generated with AI (ElevenLabs); script written and checked by TrendingTesla.",
            "nl": "Voice-over gemaakt met AI (ElevenLabs); tekst geschreven en gecontroleerd door TrendingTesla."}[lang]
    txt = (f"TITLE:\n{t['title'][:95]}{' #Shorts' if PORTRAIT else ''}\n\nDESCRIPTION:\n{t['description']}\n\n{read}: {url}\n\n{note}\n\n"
           f"TAGS:\n{', '.join(dict.fromkeys(tags))}\n")
    out.with_suffix(".txt").write_text(txt, encoding="utf-8")


def main():
    import time
    T0 = time.time()
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    slug, lang = args[0], (args[1] if len(args) > 1 else "en")
    a = load(slug)
    OUT.mkdir(parents=True, exist_ok=True)
    text = script(a, lang)
    audio = None
    if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
        audio = OUT / f"{slug}-{lang}.mp3"
        try:
            chars, s, e = tts_elevenlabs(spoken(text, lang), audio)
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", "replace")[:300]
            print(f"::error::ElevenLabs HTTP {err.code}: {body}")
            raise SystemExit(1)
        print(f"::notice::ElevenLabs ok for {slug}-{lang} after {time.time() - T0:.0f}s")
        words = words_timed(chars, s, e)
        total = duration(audio) + 0.6
    else:  # silent preview: spread the words over ~2.6 words per second
        ws = text.split()
        words = [(w, i / 2.6, (i + 1) / 2.6) for i, w in enumerate(ws)]
        total = len(ws) / 2.6 + 1
    out = render(a, lang, audio, words, total)
    print(f"::notice::Video {out.name} ready after {time.time() - T0:.0f}s ({total:.0f}s long)")
    meta(a, lang, out)
    print(out, f"{total:.1f}s", "audio" if audio else "silent")


if __name__ == "__main__":
    main()
