"""Make a full-length landscape video of a whole article, read by the ElevenLabs voice.

Usage:  python3 video/full.py <slug> [en|nl]

The script is the article's "video" field: {"en": [block, ...], "nl": [...]}, where a block is
  {"head": "Section title", "img": [...]}            -> title card, the voice reads the head
  {"text": "...", "key": "Keyword", "img": [...]}    -> spoken text with captions; "key" shows a keyword bar
"img" (optional) lists photos (topic file names or "models/x.jpg") that start with that block.
The opening reads the photo label (like the shorts), the end card says "For more information, go to
trendingtesla.com". Output: video/out/<slug>-<lang>-full.mp4 plus a .txt with title, description,
YouTube chapters (one per head) and tags.
"""
import os
import re
import subprocess
import sys
import time
import urllib.error

from PIL import Image, ImageDraw, ImageFilter

sys.argv = [x for x in sys.argv if x != "--portrait"]
import short as S  # noqa: E402  (same folder; landscape layout)
from short import W, H, FPS, font, FB, FX, YEL  # noqa: E402

SPEED = {"en": "1.15", "nl": "1.15"}
OUTRO_SAY = {"en": "Like and subscribe for more Tesla news, or go to TrendingTesla.com. I'll see you there!",
             "nl": "Like en abonneer voor meer Tesla-nieuws, of ga naar TrendingTesla.com. Ik zie je daar!"}
OUTRO_CARD = {"en": "LIKE & SUBSCRIBE", "nl": "LIKE & ABONNEER"}
OUTRO_SEC = 10.0
SCENE_MAX, ZOOM_IN = 6.0, 0.42
NUM = re.compile(r"^([(\"'“]?)(\$?)(\d[\d.,]*\d|\d)(%?)([)\"'”.,:;!?]*)$")


SAY_NL = None


def say_fix(tok, lang):
    """Respell a Dutch word so the English voice pronounces it naturally (video/say_nl.json)."""
    global SAY_NL
    if lang != "nl":
        return tok
    if SAY_NL is None:
        import json
        SAY_NL = json.loads((S.ROOT / "video/say_nl.json").read_text(encoding="utf-8"))
    m = re.match(r"^([(\"'“]*)(.*?)([)\"'”.,:;!?]*)$", tok)
    pre, core, post = m.groups()
    if core in SAY_NL.get("always", {}):
        return pre + SAY_NL["always"][core] + post
    for k, v in SAY_NL.get("always_parts", {}).items():
        core = core.replace(k, v)
    if os.environ.get("RESPELL_NL") != "1":  # the extra respellings made the English voice sound odd; off by default
        return pre + core + post
    if core in SAY_NL["words"]:
        core = SAY_NL["words"][core]
    else:
        new = core
        for k, v in SAY_NL["parts"].items():
            new = new.replace(k, v)
        if new != core:
            core = re.sub(r"\s*-\s*|\s+", " ", new).strip()
    return pre + core + post if core else tok


def say_numbers(text, lang):
    """Write numbers out in words so the voice says them clearly. Returns the spoken text and, per original
    word, how many spoken words it became (so captions can still show the digits)."""
    from num2words import num2words
    out, counts = [], []
    for tok in text.split():
        m = NUM.match(tok)
        if not m:
            ws = say_fix(tok, lang).split()
            out += ws
            counts.append(len(ws))
            continue
        pre, dollar, num, pct, post = m.groups()
        thou, dec = (",", ".") if lang == "en" else (".", ",")
        try:
            if len(num) == 4 and num.isdigit() and 1900 <= int(num) <= 2099:
                words = num2words(int(num), lang=lang, to="year")
            else:
                v = num.replace(thou, "")
                v = float(v.replace(dec, ".")) if dec in v else int(v)
                words = num2words(v, lang=lang)
        except (ValueError, NotImplementedError):
            out.append(tok)
            counts.append(1)
            continue
        if lang == "nl":  # "elfduizend honderd", "vierhonderd zevenenzeventig": easier to say smoothly
            words = re.sub(r"(duizend|honderd)(?=[a-z])", r"\1 ", words)
            words = words.replace("zes", "zès")  # otherwise the voice says "zees"
        if pct:
            words += " percent" if lang == "en" else " procent"
        if dollar:
            words += " dollars" if lang == "en" else " dollar"
        ws = words.replace("-", " ").split() if lang == "en" else words.split()
        ws[0], ws[-1] = pre + ws[0], ws[-1] + post
        out += ws
        counts.append(len(ws))
    return " ".join(out), counts


PAUSE = {"title": 0.7, "head_before": 0.8, "head_after": 1.0, "text": 0.3, "outro": 0.6, "outro2": 0.45}


def img_path(name):
    p = S.build.STATIC / "img" / (name if "/" in name else f"topics/{name}")
    return p if p.exists() else None


def head_overlay(a, lang, num, text):
    """Section title card, bottom-left like the photo labels: small block 'PART n' + big yellow head."""
    bg, fg, yc, line = S.PAL.get(S.site_palette(a["slug"]), S.PAL["yr"])
    if bg == YEL:  # yellow block variant: use red for the small block
        bg, fg = S.RED, "#fff"
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(im), ImageDraw.Draw(sh)
    cq = W / 100
    left = 2.6 * cq
    small = {"en": f"PART {num}", "nl": f"DEEL {num}"}[lang]
    f1 = font(FB, int(4.2 * cq))
    big = text.upper()
    s2 = 8.4 * cq
    while font(FB, int(s2)).getlength(big) > 0.86 * W and s2 > 30:
        s2 *= 0.96
    f2 = font(FB, int(s2))
    h2 = 0.864 * s2 + 0.136 * s2
    y2 = H - 2.6 * cq - h2 - 40
    pad = 0.24 * f1.size
    w1 = f1.getlength(small) + 2 * pad
    h1 = f1.size * 1.25
    y1 = y2 - h1 - 0.1 * s2
    ds.rectangle([left, y1 + 0.4 * cq, left + w1, y1 + h1 + 0.4 * cq], fill=(0, 0, 0, 90))
    d.rectangle([left, y1, left + w1, y1 + h1], fill=bg)
    d.text((left + pad, y1 + h1 * 0.5), small, font=f1, fill=fg, anchor="lm")
    ds.text((left, y2 + 0.864 * s2 + 0.5 * cq), big, font=f2, fill=(0, 0, 0, 110), anchor="ls")
    d.text((left, y2 + 0.864 * s2), big, font=f2, fill=yc, anchor="ls", stroke_width=max(2, round(0.2 * cq)), stroke_fill=line)
    sh = sh.filter(ImageFilter.GaussianBlur(cq * 0.6))
    sh.alpha_composite(im)
    return sh


def key_overlay(a, text):
    """Keyword bar above the captions, bottom-left."""
    bg, fg, _, _ = S.PAL.get(S.site_palette(a["slug"]), S.PAL["yr"])
    if bg == YEL:
        bg, fg = S.RED, "#fff"
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(FB, 56)
    pad = 18
    w = f.getlength(text.upper()) + 2 * pad
    x, y = 2.6 * W / 100, H - 330
    d.rectangle([x + 4, y + 6, x + w + 4, y + 82], fill=(0, 0, 0, 90))
    d.rectangle([x, y, x + w, y + 76], fill=bg)
    d.text((x + pad, y + 38), text.upper(), font=f, fill=fg, anchor="lm")
    return im


def build_timeline(a, lang):
    """Pieces in spoken order: (kind, text, block) with kind title/head/text/outro."""
    blocks = (a.get("video") or {}).get(lang)
    for i, b in enumerate(blocks or []):  # the head is the question: drop a duplicate question before it
        if "head" in b and i > 0 and "text" in blocks[i - 1]:
            blocks[i - 1]["text"] = S.build.strip_q(blocks[i - 1]["text"])
    if not blocks:
        raise SystemExit(f"article has no video script for {lang}")
    pieces = [("title", S.title_say(a, lang), {"img": (a.get("images") or [])[:1]})] if S.SPOKEN_TITLE else []
    for b in blocks:
        if b.get("head"):
            h = b["head"].strip()
            pieces.append(("head", h if h.endswith(("?", "!", ".")) else h + ".", b))  # keep "?" so the voice rises
        if b.get("text"):
            pieces.append(("text", b["text"], b if not b.get("head") else {k: v for k, v in b.items() if k != "img"}))
    if not S.SPOKEN_TITLE and pieces and not pieces[0][2].get("img"):  # opening photo = the article's first photo
        pieces[0] = (pieces[0][0], pieces[0][1], {**pieces[0][2], "img": (a.get("images") or [])[:1]})
    # the last sentence gets its own short pause, so "I'll see you there!" is not swallowed after ".com"
    o1, _, o2 = OUTRO_SAY[lang].rpartition(". ")
    pieces.append(("outro", o1 + ".", {}))
    pieces.append(("outro2", o2, {}))
    return pieces


def main():
    T0 = time.time()
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    slug, lang = args[0], (args[1] if len(args) > 1 else "en")
    a = S.load(slug)
    S.OUT.mkdir(parents=True, exist_ok=True)
    pieces = build_timeline(a, lang)
    os.environ["ELEVENLABS_SPEED"] = SPEED.get(lang, "1.1")
    S.LANG[0] = lang
    base = [S.spoken(t, lang) for _, t, _ in pieces]
    conv = [say_numbers(t, lang) for t in base]
    spoken = [c[0] for c in conv]
    joined = " ".join(spoken)
    have_voice = os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID")
    if have_voice:
        mp3 = S.OUT / f"{slug}-{lang}-full-all.mp3"
        try:
            chars, cs, ce = S.tts_elevenlabs(joined, mp3)
        except urllib.error.HTTPError as err:
            print(f"::error::ElevenLabs HTTP {err.code}: {err.read().decode('utf-8', 'replace')[:300]}")
            raise SystemExit(1)
        print(f"::notice::ElevenLabs ok for {slug}-{lang} (full, {len(joined)} chars) after {time.time() - T0:.0f}s")
        full = S.duration(mp3)
        if len(chars) != len(joined):
            print(f"::warning::alignment has {len(chars)} chars, text {len(joined)}")
            r = len(chars) / len(joined)
            cs = [cs[min(len(cs) - 1, int(i * r))] for i in range(len(joined))]
            ce = [ce[min(len(ce) - 1, int(i * r))] for i in range(len(joined))]
            chars = list(joined)
    else:  # silent preview: ~2.6 words per second
        chars, cs, ce, t, full = list(joined), [], [], 0.0, 0.0
        for ch in joined:
            cs.append(t)
            t += 1 / 15.5
            ce.append(t)
        full = t
    # where each piece sits in the voice track
    segs, spans, pos = [], [], 0
    for i, pc in enumerate(spoken):
        i0, i1 = pos, pos + len(pc) - 1
        spans.append((i0, i1))
        a0 = max(0.0, cs[i0] - 0.05)
        a1 = min(full, ce[i1] + 0.12) if i < len(spoken) - 1 else full
        segs.append((a0, a1))
        pos += len(pc) + 1
    # place pieces on the video timeline with pauses
    t, place = (0.3 if S.SPOKEN_TITLE else 0.1), []
    for i, ((kind, _, _), (a0, a1)) in enumerate(zip(pieces, segs)):
        if i:
            prev = pieces[i - 1][0]
            gap = PAUSE["title"] if prev == "title" else PAUSE["head_after"] if prev == "head" else \
                PAUSE["head_before"] if kind == "head" else PAUSE.get(kind, PAUSE["text"])
            t += gap
        place.append(t)
        t += a1 - a0
    oi = next(i for i, p in enumerate(pieces) if p[0] == "outro")
    end_start = place[oi] - 0.3
    total = place[oi] + max(OUTRO_SEC, place[-1] - place[oi] + segs[-1][1] - segs[-1][0] + 1.5)
    # words of text pieces on the video timeline (captions)
    words = []
    for (kind, _, _), (a0, a1), t0, (i0, i1), orig, (_, counts) in zip(pieces, segs, place, spans, base, conv):
        if kind != "text":
            continue
        # words by character position, so a head never leaks into the captions
        sw = [(w, s0 - a0 + t0, e0 - a0 + t0) for w, s0, e0 in S.words_timed(chars[i0:i1 + 1], cs[i0:i1 + 1], ce[i0:i1 + 1])]
        ow = orig.split()
        if len(sw) == sum(counts) and len(ow) == len(counts):  # show the digits again in the captions
            j = 0
            for w, n in zip(ow, counts):
                words.append((w, sw[j][1], sw[j + n - 1][2]))
                j += n
        else:
            words += sw
    if have_voice:
        audio = S.OUT / f"{slug}-{lang}-full.m4a"
        fl, ins = [], []
        for i, ((a0, a1), t0) in enumerate(zip(segs, place)):
            ms = int(t0 * 1000)
            fl.append(f"[0]atrim={a0:.3f}:{a1:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={max(0, a1 - a0 - 0.04):.3f}:d=0.04,"
                      f"adelay={ms}|{ms}[a{i}]")
            ins.append(f"[a{i}]")
        fl.append("".join(ins) + f"amix=inputs={len(ins)}:normalize=0:duration=longest[out]")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp3), "-filter_complex", ";".join(fl), "-map", "[out]",
                        "-c:a", "aac", "-b:a", "192k", str(audio)], check=True)
    else:
        audio = None
    out = render(a, lang, pieces, segs, place, words, total, end_start, audio)
    print(f"::notice::Video {out.name} ready after {time.time() - T0:.0f}s ({total / 60:.1f} min)")
    meta(a, lang, pieces, place, out)
    print(out, f"{total:.1f}s", "audio" if audio else "silent")


def render(a, lang, pieces, segs, place, words, total, end_start, audio):
    # scenes: a block's photos start with that block (just before it, so the fade is done when it begins)
    scenes = []
    for i, (kind, _, b) in enumerate(pieces):
        imgs = [p for p in (img_path(x) for x in (b.get("img") or [])) if p]
        if not imgs:
            continue
        t0 = max(0.0, place[i] - 0.6) if i else 0.0
        nxt = next((place[j] for j in range(i + 1, len(pieces)) if pieces[j][2].get("img")), total)
        span = nxt - t0
        for k, p in enumerate(imgs):
            if scenes and scenes[-1][1] == p:
                continue
            scenes.append((t0 + span * k / len(imgs), p))
    if not scenes:
        scenes = [(0.0, S.photos(a)[0])]
    # very long scenes: show another photo of the same section (or of the article) so nothing stays longer than ~6 s
    sec_of, sec_imgs, sec = [], {}, 0
    for i, (kind, _, b) in enumerate(pieces):
        if kind == "head":
            sec += 1
        sec_of.append(sec)
        for x in b.get("img") or []:
            q = img_path(x)
            if q and q not in sec_imgs.setdefault(sec, []):
                sec_imgs[sec].append(q)
    pool = S.photos(a)
    fixed = []
    for k, (st, p) in enumerate(scenes):
        end = scenes[k + 1][0] if k + 1 < len(scenes) else total
        i = max([j for j in range(len(pieces)) if place[j] - 0.7 <= st] or [0])
        cand = [x for x in sec_imgs.get(sec_of[i], []) + pool if x != p]
        n = max(1, round((end - st) / SCENE_MAX))
        for j in range(n):
            q = p if j == 0 else next((x for x in cand if x not in [f[1] for f in fixed[-2:]]), p)
            fixed.append((st + (end - st) * j / n, q))
    scenes = fixed
    starts = [s for s, _ in scenes]
    nsc = len(scenes)

    shade = Image.new("L", (1, H))
    for y in range(H):
        shade.putpixel((0, y), int(185 * max(0, (y - H * 0.5) / (H * 0.5)) ** 1.25 + 120 * max(0, (H * 0.16 - y) / (H * 0.16))))
    shade = shade.resize((W, H))
    fbrand, fcap = font(FX, 50), font(FB, S.LAY["caps"])

    def brand(d):
        # 1px dark edge + slightly lighter red: stays sharp after video compression (red loses detail first)
        d.text((60, S.LAY["brand"]), "Trending", font=fbrand, fill="#fff", stroke_width=1, stroke_fill=(55, 55, 60))
        d.text((60 + d.textlength("Trending", font=fbrand), S.LAY["brand"]), "Tesla", font=fbrand, fill="#ff2d24",
               stroke_width=1, stroke_fill=(55, 55, 60))

    def ending(d):
        """Closing card: LIKE & SUBSCRIBE above TrendingTesla.com (white / red / white)."""
        f1, f2 = font(FB, 60), font(FB, 132)
        l1 = OUTRO_CARD[lang]
        parts = [("Trending", "#fff"), ("Tesla", "#e8231c"), (".com", "#fff")]
        w2 = sum(d.textlength(x, font=f2) for x, _ in parts)
        w = max(d.textlength(l1, font=f1) + 60, w2) + 140
        h = 360
        x0, y0 = (W - w) / 2, (H - h) / 2
        d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=36, fill=(0, 0, 0, 175))
        bw = d.textlength(l1, font=f1) + 60
        bx = (W - bw) / 2
        d.rounded_rectangle([bx, y0 + 44, bx + bw, y0 + 44 + 92], radius=14, fill="#e8231c")
        d.text((W / 2, y0 + 44 + 46), l1, font=f1, fill="#fff", anchor="mm")
        x = (W - w2) / 2
        for txt, col in parts:
            d.text((x, y0 + 172), txt, font=f2, fill=col)
            x += d.textlength(txt, font=f2)

    o_brand, o_end = S.overlay(brand), S.overlay(ending)
    o_label, _ = S.label_overlay(a, lang)
    # overlays with their time windows
    label_end = place[0] + (segs[0][1] - segs[0][0]) + 0.25 if S.SPOKEN_TITLE else S.LABEL_SEC
    wins = [(0.0, label_end, o_label)]
    num = 0
    for i, (kind, txt, b) in enumerate(pieces):
        if kind == "head":
            num += 1
            wins.append((place[i] - 0.1, place[i] + (segs[i][1] - segs[i][0]) + PAUSE["head_after"] - 0.05, head_overlay(a, lang, num, txt.rstrip("."))))
        if kind == "text" and b.get("key"):
            wins.append((place[i], place[i] + (segs[i][1] - segs[i][0]) + 0.2, key_overlay(a, b["key"])))
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 5 or w[0].endswith((".", "!", "?", ",", ":")):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    caps = {}

    def cap(txt):
        if txt not in caps:
            def dr(d):
                lines = S.wrap(d, txt, fcap, W - 360)
                y = H - 70 - len(lines) * S.LAY["capl"]
                for ln in lines:
                    d.text(((W - d.textlength(ln, font=fcap)) / 2, y), ln, font=fcap, fill="#fff", stroke_width=7, stroke_fill="#000")
                    y += S.LAY["capl"]
            caps[txt] = S.overlay(dr)
            if len(caps) > 40:
                caps.pop(next(iter(caps)))
        return caps[txt]

    cache = {}

    def pic(path):
        if path not in cache:
            im = Image.open(path).convert("RGB")
            sc = max(H * S.ZOOM / im.height, W * S.ZOOM / im.width)
            cache[path] = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
            if len(cache) > 4:
                cache.pop(next(iter(cache)))
        return cache[path]

    FOCUS = [(0.5, 0.45), (0.42, 0.5), (0.58, 0.5), (0.5, 0.55)]

    def shot(k, t):
        im = pic(scenes[k][1])
        span = (starts[k + 1] if k + 1 < nsc else total) - starts[k] + S.TR
        p = S.ease(max(0.0, min(1.0, (t - starts[k]) / span)))
        cx, cy = FOCUS[k % len(FOCUS)]
        z = 1.0 + ZOOM_IN * p
        if k == 0 and t < S.PUNCH_SEC:  # quick punch-in on the opening photo
            z *= 1.0 + S.PUNCH * (1 - S.ease(t / S.PUNCH_SEC))
        cw, chh = min(W * S.ZOOM / z, im.width), min(H * S.ZOOM / z, im.height)
        x0, y0 = (im.width - cw) * cx, (im.height - chh) * cy
        return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + chh))

    black = Image.new("RGB", (W, H))

    def picture(t):
        k = max(i for i, s0 in enumerate(starts) if s0 <= t)
        fr = shot(k, t)
        if k > 0 and t - starts[k] < S.TR:
            fr = Image.blend(shot(k - 1, t), fr, S.ease((t - starts[k]) / S.TR))
        return Image.composite(black, fr, shade)

    out = S.OUT / f"{a['slug']}-{lang}-full.mp4"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-af", "apad", "-c:a", "aac", "-b:a", "192k"]
    # delivered at 1440p: YouTube then streams it with a much higher bitrate, so text stays sharp
    cmd += ["-vf", "scale=2560:1440:flags=lanczos"]
    cmd += ["-t", f"{total:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "18",
            "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ci = 0
    rng = range(int(total * FPS) + 1)
    if os.environ.get("FULL_PREVIEW"):  # quick check: only the given seconds, e.g. "20-30,255-270"
        rng = [f for part in os.environ["FULL_PREVIEW"].split(",") for f in
               range(int(float(part.split("-")[0]) * FPS), int(float(part.split("-")[1]) * FPS))]
    for fr in rng:
        t = fr / FPS
        frame = picture(t)
        frame.paste(o_brand, (0, 0), o_brand)
        last = t >= end_start
        for w0, w1, o in wins:
            if w0 <= t < w1 and not last:
                frame.paste(o, (0, 0), o)
        if last:
            frame.paste(o_end, (0, 0), o_end)
        while ci < len(chunks) and chunks[ci][-1][2] + 0.25 < t:
            ci += 1
        if ci < len(chunks) and chunks[ci][0][1] <= t and not last and t >= label_end:
            o = cap(" ".join(w[0] for w in chunks[ci]))
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


def meta(a, lang, pieces, place, out):
    t = a[lang]
    url = f"https://{S.SITE}/{'nl/' if lang == 'nl' else ''}{a['slug']}/"
    tags = ["Tesla", "TrendingTesla", S.build.CATEGORIES[a["category"]][lang]] + \
        [S.build.MODELS[m]["name"] for m in a.get("models", []) if m in S.build.MODELS]

    def ts(s):
        s = int(s)
        return f"{s // 60}:{s % 60:02d}"
    chap = [f"0:00 {S.title_say(a, lang).rstrip('.')}"]
    def clean(h):  # chapter titles without the spoken "So, ..." lead-in
        h = re.sub(r"^(So,? |Dus,? )", "", h.rstrip("."))
        return h[:1].upper() + h[1:]
    chap += [f"{ts(max(0, place[i] - 0.6))} {clean(txt)}" for i, (k, txt, _) in enumerate(pieces) if k == "head"]
    read = {"en": "Read the full article", "nl": "Lees het hele artikel"}[lang]
    chl = {"en": "Chapters", "nl": "Hoofdstukken"}[lang]
    note = {"en": "Voice-over generated with AI (ElevenLabs); script written and checked by TrendingTesla.",
            "nl": "Voice-over gemaakt met AI (ElevenLabs); tekst geschreven en gecontroleerd door TrendingTesla."}[lang]
    txt = (f"TITLE:\n{t['title'][:100]}\n\nDESCRIPTION:\n{t['description']}\n\n{chl}:\n" + "\n".join(chap) +
           f"\n\n{read}: {url}\n\n{S.photo_credits(a, lang)}{note}\n\nTAGS:\n{', '.join(dict.fromkeys(tags))}\n")
    out.with_suffix(".txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
