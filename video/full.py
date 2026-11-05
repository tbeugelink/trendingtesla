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

SPEED = {"en": "1.17", "nl": "1.17"}
OUTRO_SAY = {"en": "Like and subscribe for more Tesla news and join us on TrendingTesla.com. I'll see you there!",
             "nl": "Like en abonneer voor meer Tesla-nieuws, of ga naar TrendingTesla.com. Ik zie je daar!"}
OUTRO_CARD = {"en": "LIKE & SUBSCRIBE", "nl": "LIKE & ABONNEER"}
OUTRO_SEC = 10.0
GAP = 8  # at least 8 other photos before one comes back
SCENE_MAX, ZOOM_IN = 3.0, 0.07  # the story-Short rhythm: a new shot every 3 s, 2 s crossfades  # calm like the story Shorts: slow steady zoom, a new photo every ~5 s
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


LEAD = 0.25  # key words appear this much before the spoken word
STOP = set("so the a an of to in on for with such and or but its it is was were be been that this these those "
           "would could should did does do had has have get got really still actually".split())


GENERIC = {"tesla", "tesla's", "motors", "company", "musk", "musk's", "elon", "what", "how", "why", "when", "who", "it", "its", "but", "and", "then", "there", "here", "back", "that", "this"}
MONTHS = "january february march april may june july august september october november december".split()


def phrase(ws, k):
    """A clean key word from the spoken words around ws[k]: a number with its unit ("6,831 CELLS"), a year alone,
    a two-word name ("SANTA MONICA"), never joined across punctuation."""
    w = ws[k][0]
    c = re.sub(r"'s$", "", re.sub(r"[^\w$%,.'-]", "", w).strip(".,;'-"))
    nxt = ws[k + 1][0] if k + 1 < len(ws) else ""
    nc = re.sub(r"[^\w$%'-]", "", nxt).strip("-")
    if c.lower() == "model" and re.fullmatch(r"[3SXY]", nc):
        return f"MODEL {nc}"
    ends = w[-1:] in ",.;:!?"
    if re.fullmatch(r"(19|20)\d\d", c):
        return c
    if re.search(r"\d", c) and not ends and nc and nc.lower() not in STOP and not re.search(r"\d", nc):
        return f"{c} {nc}".upper()
    if c.lower() in MONTHS and re.fullmatch(r"(19|20)\d\d", nc):
        return f"{c} {nc}".upper()
    if c[:1].isupper() and not ends and nc[:1].isupper() and nc.lower() not in GENERIC:
        return f"{c} {nc}".upper()
    return c.upper()


def key_phrase(ws, k):
    """A short key phrase (1-4 words, one line) from the spoken words starting near ws[k]: the meaningful words
    up to the end of that clause, small words left out ("ONLY 7% LOTUS PARTS", "STUCK IN SECOND GEAR")."""
    out = []
    j = k
    while j > 0 and strength(ws[j - 1][0], ws[j - 2][0] if j > 1 else "") >= 1 and ws[j - 1][0][-1:] not in ",.;:!?" \
            and k - j < 1:
        j -= 1
    for w, _, _ in ws[j:j + 9]:
        c = re.sub(r"'s$", "", re.sub(r"[^\w$%,.'-]", "", w).strip(".,;'-"))
        if c and (c.lower() not in STOP or (out and c.lower() in ("in", "on", "of", "to", "no", "not", "never"))):
            out.append(c.upper())
        if len(out) >= 4 or w[-1:] in ",.;:!?":
            break
    while out and out[-1].lower() in ("in", "on", "of", "to", "and", "the", "a", "not", "no", "never", "could", "would"):
        out.pop()
    return " ".join(out[:4])


def strength(w, prev=""):
    """How strong a spoken word is as a key word: numbers and names first, then long words; stop words 0."""
    c = re.sub(r"[^\w$%]", "", re.sub(r"'s\W*$", "", w))
    if not c or c.lower() in STOP or c.lower() in GENERIC or c.lower() in MONTHS or len(c) < 3 and not c[0].isdigit():
        return 0
    if re.fullmatch(r"\d{1,2}", c):  # a lone small number ("1", "3") says nothing on its own
        return 1
    if c.lower() == "model":
        return 3
    sentence_start = not prev or prev[-1:] in ".!?"
    return 4 if re.search(r"\d", c) else 3 if c[0].isupper() and not sentence_start else 1 + len(c) / 6


def short_head(txt):
    """A chapter question as key words: question word + the last meaningful words, at most 4 ("WHY A LOTUS?")."""
    ws = re.findall(r"[\w$%',.-]+", txt.rstrip("?.!"))
    qw = next((w for w in ws if w.lower() in ("why", "how", "what", "when", "who", "which", "where")), "")
    rest = [w for w in ws if w.lower() not in STOP and w != qw]
    return (" ".join(([qw] if qw else []) + rest[-(3 if qw else 4):]) + ("?" if txt.strip().endswith("?") else "")).upper()


POP_SIZE = 150  # key words: big yellow, centre; each stays until the next one (no empty gaps)


def norm(w):
    return re.sub(r"[^\w$%]", "", w.lower())


FILLER = set("a an the in into if because want so that just".split())  # only small linking words; the sense stays
SUB_SIZE, SUB_Y = 72, 0.855  # like the reference: bold caps, white with black edge, one key word yellow, low centre


def subtitle_pops(words, start, stop):
    """Subtitles of the full script: at most 3 words at a time, small linking words left out, a new group at every
    pause or punctuation; each group shows a fraction before it is spoken and stays until the next one."""
    groups, cur = [], []
    for w, st, en in words:
        if st < start - 0.2:
            continue
        clean = re.sub(r"[^\w$%,.'?!-]", "", w)
        if clean and re.sub(r"[^a-z]", "", clean.lower()) not in FILLER:
            cur.append((clean.strip(",.;:"), st, en))
        if cur and (len(cur) >= 3 or w[-1:] in ",.;:!?"):
            if len(cur) == 3 and w[-1:] not in ",.;:!?" and re.search(r"\d", cur[-1][0]):
                groups.append(cur[:2])  # keep a number with the word after it ("40 TONNE")
                cur = cur[2:]
            else:
                groups.append(cur)
                cur = []
    if cur:
        groups.append(cur)
    calm = []  # a lone word joins the group before it when that has room, so nothing flashes by on its own
    for g in groups:
        if calm and (len(g) == 1 or len(calm[-1]) == 1) and len(calm[-1]) + len(g) <= 3 \
                and g[0][1] - calm[-1][-1][2] < 0.6:
            calm[-1] = calm[-1] + g
        else:
            calm.append(g)
    groups = calm
    out = []
    for k, g in enumerate(groups):
        t0 = max(start, g[0][1] - LEAD)
        t1 = min(groups[k + 1][0][1] - LEAD if k + 1 < len(groups) else g[-1][2] + 0.4, g[-1][2] + 1.2, stop)
        if t1 - t0 > 0.15:
            out.append((t0, t1, subtitle_overlay([x[0] for x in g])))
    return out


def subtitle_overlay(ws):
    """One subtitle line: bold capitals, white with a black edge, the strongest word in yellow, centred low."""
    f = font(FB, SUB_SIZE)
    up = [w.upper() for w in ws]
    hi = max(range(len(up)), key=lambda i: (bool(re.search(r"\d", ws[i])),  # numbers first, then names, then
                                            ws[i][:1].isupper() and i > 0,   # the longest word
                                            len(ws[i])))
    gap = f.getlength(" ")
    total = sum(f.getlength(w) for w in up) + gap * (len(up) - 1)
    while total > W * 0.84 and f.size > 40:
        f = font(FB, f.size - 4)
        gap = f.getlength(" ")
        total = sum(f.getlength(w) for w in up) + gap * (len(up) - 1)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x, y = (W - total) / 2, H * SUB_Y - f.size * 0.6
    for i, w in enumerate(up):
        d.text((x + 3, y + 5), w, font=f, fill=(0, 0, 0, 140))
        d.text((x, y), w, font=f, fill=(255, 221, 0) if i == hi else (255, 255, 255), stroke_width=6,
               stroke_fill=(0, 0, 0))
        x += f.getlength(w) + gap
    return im


def pop_overlay(txt):
    """A key word or short phrase, big and yellow in the centre (like the story Shorts), always on one line."""
    f = font(FB, POP_SIZE)
    txt = " ".join(txt.split()[:4])  # never more than 4 words, one line
    lines = [txt]  # landscape: always one line, there is room enough
    while f.getlength(txt) > W * 0.78 and f.size > 60:  # safe area: phones crop the edges
        f = font(FB, f.size - 6)
    lh = int(f.size * 1.04)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = H * 0.5 - f.size * 0.62  # centred horizontally and vertically
    for ln in lines:
        x = (W - f.getlength(ln)) / 2
        d.text((x + 6, y + 8), ln, font=f, fill=(0, 0, 0, 150))
        d.text((x, y), ln, font=f, fill=(255, 214, 0), stroke_width=9, stroke_fill=(0, 0, 0))
        y += lh
    return im


def find_pops(b, ws):
    """Key words of one text block: its "pop" list [{"say": spoken words, "show": text on screen}] or, without one,
    numbers and words in capitals. ws = [(word, start, end)] of that block. Returns [(start, text)]."""
    wanted = b.get("pop")
    if wanted is None:
        if b.get("key"):
            return []
        wanted = [w for w, _, _ in ws if (w.strip(".,!?;:").isupper() and len(re.sub(r"\W", "", w)) > 1)
                  or re.match(r"^\$?\d[\d,.]*%?$", w.strip(".,!?;:"))]
    out, k0 = [], 0
    for p in wanted:
        show, say = (p.get("show"), p.get("say")) if isinstance(p, dict) else (p, p)
        toks = [norm(x) for x in str(say).split()]
        for k in range(k0, len(ws) - len(toks) + 1):
            if [norm(w) for w, _, _ in ws[k:k + len(toks)]] == toks:
                out.append((ws[k][1], str(show).upper().strip(".,;: ")))
                k0 = k + len(toks)
                break
    return out


def srt(chunks, path):
    """YouTube closed captions (CC): same word timing as the voice."""
    def ts(t):
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    rows = []
    for i, c in enumerate(chunks):
        end = c[-1][2] + 0.2 if i + 1 == len(chunks) else min(c[-1][2] + 0.2, chunks[i + 1][0][1] - 0.01)
        rows.append(f"{i + 1}\n{ts(c[0][1])} --> {ts(end)}\n{' '.join(w[0] for w in c)}\n")
    path.write_text("\n".join(rows), encoding="utf-8")


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
    os.environ.setdefault("ELEVENLABS_STABILITY", "0.2")  # same lively delivery as the story Shorts
    os.environ.setdefault("ELEVENLABS_STYLE", "0.8")
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
        if kind not in ("text", "head"):
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
            fl.append(f"[0]atrim={a0:.3f}:{a1:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={max(0, a1 - a0 - 0.04):.3f}:d=0.04,"
                      f"adelay={ms}|{ms}[a{i}]")
            ins.append(f"[a{i}]")
        fl.append("".join(ins) + f"amix=inputs={len(ins)}:normalize=0:duration=longest[out]")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp3), "-filter_complex", ";".join(fl), "-map", "[out]",
                        "-c:a", "aac", "-b:a", "192k", str(audio)], check=True)
    else:
        audio = None
    credits = add_real_photos(a, pieces) if os.environ.get("GEMINI_API_KEY") else {}
    out = render(a, lang, pieces, segs, place, words, total, end_start, audio)
    print(f"::notice::Video {out.name} ready after {time.time() - T0:.0f}s ({total / 60:.1f} min)")
    meta(a, lang, pieces, place, out)
    if credits:  # credit the real photos in the YouTube description
        txt = out.with_suffix(".txt")
        if txt.exists():
            txt.write_text(txt.read_text(encoding="utf-8").rstrip() + "\n\nPhotos: " + "; ".join(dict.fromkeys(credits.values())) + "\n",
                           encoding="utf-8")
    print(out, f"{total:.1f}s", "audio" if audio else "silent")


MODEL_RE = [("cybertruck", r"cybertruck"), ("cybercab", r"cybercab"), ("semi", r"\bsemi\b"),
            ("model-s", r"model s\b"), ("model-3", r"model 3\b"), ("model-y", r"model y\b"), ("model-x", r"model x\b"),
            ("roadster-new", r"(new|next.generation|second.generation|2020|2026) roadster"),
            ("roadster-1", r"(first.generation|original|2008|first) (tesla )?roadster|roadster \(2008")]


def models_in(text):
    t = (text or "").lower()
    out = {k for k, rx in MODEL_RE if re.search(rx, t)}
    if "roadster" in t and not out & {"roadster-new", "roadster-1"}:
        out.add("roadster-1" if "roadster-new" not in out else "roadster-new")
    return out


DESC = {}
SCENE_WORDS = ["space", "rocket", "launch", "falcon", "starship", "orbit", "booster", "earth", "moon", "mars",
               "factory", "office", "cheque", "chart", "phone", "robot", "optimus", "battery", "motor", "megapack",
               "solar", "powerwall", "supercharger", "charging", "screen", "interior"]


def photo_anchor(p, ws, tags):
    """When does the voice name what photo p shows? The first spoken word (of ws) that matches its car model or a
    meaningful word of its description; None when nothing matches (then it may show any time in its block)."""
    d = set(re.findall(r"[a-z0-9]{4,}", DESC.get(p, "").lower())) - STOP - {"tesla", "photo", "white", "black",
                                                                              "with", "from", "night", "behind"}
    for k, (w, st, _) in enumerate(ws):
        two = " ".join(x[0] for x in ws[k:k + 2])
        if tags.get(p) and models_in(two) & tags[p]:
            return st
        if re.sub(r"[^a-z0-9]", "", w.lower()) in d:
            return st
    return None


def photo_tags(a):
    """Which car model each photo shows: model galleries, library descriptions, real photo and gen descriptions."""
    import json as J
    tags = {}
    DESC.clear()
    prefix = {}
    for key, m in S.build.MODELS.items():
        fam = "roadster-new" if key.startswith("roadster") else (m.get("parent") or key)
        fam = re.sub(r"-(classic|juniper|highland|standard|plaid|performance|20\d\d.*)$", "", fam)
        for g in (m.get("gallery") or []) + [m.get("photo") or ""]:
            if g:
                tags.setdefault(S.build.STATIC / "img/models" / g, set()).add(fam)
                prefix[re.sub(r"-?\d+\.jpg$", "", g)] = fam
    for p in (S.build.STATIC / "img/models").glob("*.jpg"):  # photos not in a gallery: by their file prefix
        fam = prefix.get(re.sub(r"-?\d+$", "", p.stem))
        if fam and p not in tags:
            tags[p] = {fam}
    lib = S.ROOT / "ops/library.json"
    for f, d in (J.loads(lib.read_text()) if lib.exists() else {}).items():
        DESC[S.build.STATIC / "img/lib" / f] = d
        if models_in(d):
            tags[S.build.STATIC / "img/lib" / f] = models_in(d)
    cr = S.build.STATIC / "img/real/story/credits.json"
    for f, d in (J.loads(cr.read_text()) if cr.exists() else {}).items():
        DESC[S.build.STATIC / "img/real/story" / f] = d.get("want", "")
        if models_in(d.get("want", "")):
            tags[S.build.STATIC / "img/real/story" / f] = models_in(d.get("want", ""))
    gi = a.get("gen_image") or {}
    if models_in(gi.get("subject", "") + " " + gi.get("describe", "")):
        for p in (S.build.STATIC / "img/gen").glob(a["slug"] + "*.jpg"):
            tags[p] = models_in(gi.get("subject", "") + " " + gi.get("describe", ""))
    return tags


def add_real_photos(a, pieces):
    """Blocks with "photo": [{"q": [search words], "want": "what it must show"}] get a real, freely licensed photo
    from Wikimedia Commons (picked and checked by Gemini, as in the story Shorts); its credit goes in the description."""
    import story as ST
    for n, (kind, txt, b) in enumerate(pieces):
        found = []
        for spec in b.get("photo") or []:
            try:
                f, _ = ST.real_photo(a, {"text": txt}, spec)
                found.append(str(f.relative_to(S.build.STATIC / "img")))
            except Exception as e:
                print(f"::warning::no real photo for '{(spec.get('want') or txt)[:50]}': {str(e)[:120]}")
        if found:  # the specific real photos lead the block (the opening keeps its own first photo)
            own = b.get("img") or []
            b["img"] = (own[:1] + found + own[1:]) if n == 0 else (found + own)
    return ST.CREDITS


def render(a, lang, pieces, segs, place, words, total, end_start, audio):
    # scenes: a block's photos start with that block (just before it, so the fade is done when it begins)
    # shots: a new shot every ~3 s. Each block first shows its own photos; around them come photos of nearby
    # blocks (same section first). A photo never comes back until at least GAP other photos were shown, and a
    # photo of a different car model than the block talks about is never used as a fill-in.
    tags = photo_tags(a)
    main = models_in(a[lang]["title"] + " " + a[lang].get("description", "")) | {
        ("roadster-new" if m.startswith("roadster") else m) for m in a.get("models") or []}
    sec_of, sec = [], 0
    for kind, _, b in pieces:
        sec += kind == "head"
        sec_of.append(sec)
    own = [list(dict.fromkeys(p for p in (img_path(x) for x in (b.get("img") or [])) if p and p.name not in S.BLOCKED))
           for _, _, b in pieces]
    pool = [p for p in S.photos(a) if p.name not in S.BLOCKED]
    scenes, uses = [], {}
    bounds = [max(0.0, place[i] - 0.6) if i else 0.0 for i in range(len(pieces))] + [total]
    for i, (kind, txt, b) in enumerate(pieces):
        want = models_in(txt)
        near = sorted(range(len(pieces)), key=lambda j: (sec_of[j] != sec_of[i], abs(j - i)))
        same = {p for j in range(len(pieces)) if sec_of[j] == sec_of[i] for p in own[j]}
        allp = list(dict.fromkeys([p for j in near for p in own[j]] + pool))
        # fill-ins: first photos of the car this block (or, if it names none, the article) is about, then the rest
        topic = want or main
        cand = list(dict.fromkeys(own[i] + [p for p in allp if tags.get(p, set()) & topic] + allp))

        words_i = txt.lower()

        def fits(p, i=i, want=want, same=same, words_i=words_i):
            if p in own[i]:
                return not (want and tags.get(p) and not tags[p] & want)  # never another model than the words
            d = DESC.get(p, "").lower()  # a rocket, a factory, a chart... only where the words are about that
            if any(w in d and w not in words_i for w in SCENE_WORDS):
                return False
            if tags.get(p):  # a car photo: only when the words (or the article) are about that very model
                return bool(tags[p] & (want or main))
            return p in same  # a generic photo only within its own section
        # sync: a photo of something the voice names (a rocket, the Model S, a battery) starts when that word is
        # spoken, never before; the other shots fill the time around it
        t0b, t1b = bounds[i], bounds[i + 1]
        ws = [w for w in words if t0b <= w[1] < t1b]
        anchor = {p: photo_anchor(p, ws, tags) for p in own[i]}
        fixed = sorted((max(t0b, anchor[p] - 0.2), p) for p in own[i] if anchor[p] is not None)
        slots, t = [], t0b
        for at, p in fixed + [(t1b, None)]:
            n = max(0, round((at - t) / SCENE_MAX)) if at - t > 1.2 else 0
            slots += [(t + (at - t) * j / n, None) for j in range(n)]
            if p is not None:
                slots.append((at, p))
                t = at
        if not slots:
            slots = [(t0b, None)]
        for st, q in slots:
            if q is None:
                for gap in range(GAP, -1, -1):  # relax the gap only when there are not enough photos at all
                    recent = [x[1] for x in scenes[-gap:]] if gap else []
                    early = {p for p in own[i] if anchor[p] is not None and anchor[p] - 0.2 > st + 0.5}
                    ok = [p for p in cand if p not in recent and p not in early and fits(p)]
                    if ok:
                        mine = [p for p in ok if p in own[i]]
                        q = min(mine, key=lambda p: uses.get(p, 0)) if mine else ok[0]
                        break
                q = q or (own[i] or pool or [S.photos(a)[0]])[0]
            uses[q] = uses.get(q, 0) + 1
            scenes.append((st, q, uses[q] - 1))
    scenes.sort(key=lambda x: x[0])
    if scenes and scenes[0][0] > 0:  # the first picture always starts at 0
        scenes[0] = (0.0,) + tuple(scenes[0][1:])
    nsc = len(scenes)
    starts = [x[0] for x in scenes]

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
            pass  # no chapter card: the question is spoken in the flow and shown as a key word
        if kind == "text" and b.get("key"):
            pass  # list keywords are shown as key words
    # key words per text block (instead of captions in the picture; the captions go to YouTube as CC)
    pops = []
    for i, (kind, txt, b) in enumerate(pieces):
        if kind == "head":
            hp = b.get("pop")
            show = (hp[0]["show"] if isinstance(hp, list) and hp and isinstance(hp[0], dict) else hp) if hp else short_head(txt)
            pops.append((max(place[i] - LEAD, label_end), None, pop_overlay(show)))
            continue
        if kind != "text":
            continue
        t1 = place[i] + (segs[i][1] - segs[i][0])
        if b.get("key"):  # list item: its keyword first, then key phrases for the rest of what is said
            pops.append((max(place[i] - LEAD, label_end), None, pop_overlay(b["key"].upper())))
        ws = [w for w in words if place[i] - 0.05 <= w[1] < t1 + 0.05]
        found = find_pops(b, ws)
        for k, (st, show) in enumerate(found):
            pops.append((max(st - LEAD, label_end), None, pop_overlay(show)))  # a fraction before the voice
    pops.sort(key=lambda x: x[0])
    extra = []
    for i, (kind, txt, b) in enumerate(pieces):  # fill every gap longer than 2.2 s with the strongest spoken words
        if kind != "text":
            continue
        t1 = place[i] + (segs[i][1] - segs[i][0])
        ws = [w for w in words if place[i] - 0.05 <= w[1] < t1 + 0.05]
        times = sorted([p[0] for p in pops if place[i] - 0.5 <= p[0] <= t1] + [t1])
        last = place[i] - LEAD
        for nxt in times:
            while nxt - last > 2.4:  # never more than ~2.4 s without a new key phrase
                cand = [k for k, w in enumerate(ws) if last + 1.0 <= w[1] - LEAD <= nxt - 0.8]
                if not cand:
                    break
                sc = lambda k: strength(ws[k][0], ws[k - 1][0] if k else "")
                near = [k for k in cand if ws[k][1] - LEAD <= last + 2.2] or cand[:1]
                k = max(near, key=sc)  # the strongest word close to where the gap starts
                show = key_phrase(ws, k)
                if not show:
                    last = ws[k][1] - LEAD
                    continue
                extra.append((max(ws[k][1] - LEAD, label_end), None, pop_overlay(show)))
                last = ws[k][1] - LEAD
            last = max(last, nxt)
    pops = sorted(pops + extra, key=lambda x: x[0])
    pops = [(p0, min(pops[k + 1][0] if k + 1 < len(pops) else end_start, p0 + 2.8), o) for k, (p0, _, o) in enumerate(pops)]
    if os.environ.get("FULL_KEYPHRASES") != "1":  # default: subtitles of the whole script (William, 5 Nov 2026)
        pops = subtitle_pops(words, label_end, end_start)
    print(f"{len(pops)} subtitles")
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 5 or w[0].endswith((".", "!", "?", ",", ":")):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    srt(chunks, S.OUT / f"{a['slug']}-{lang}-full.srt")
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

    # framings for repeated photos: whole photo, then closer left / right / centre, so a second look is a new shot
    FRAMES = [(1.0, 0.5, 0.45), (1.3, 0.25, 0.45), (1.3, 0.75, 0.45), (1.45, 0.5, 0.35), (1.2, 0.35, 0.6), (1.2, 0.65, 0.6)]

    def shot(k, t):
        im = pic(scenes[k][1])
        fz, fcx, fcy = FRAMES[scenes[k][2] % len(FRAMES)]
        span = (starts[k + 1] if k + 1 < nsc else total) - starts[k] + S.TR
        p = max(0.0, min(1.0, (t - starts[k]) / span))  # linear: no stop-start stutter
        cx, cy = fcx, fcy
        z = fz * (1.0 + ZOOM_IN * p)
        cw, chh = min(W * S.ZOOM / z, im.width), min(H * S.ZOOM / z, im.height)
        x0, y0 = (im.width - cw) * cx, (im.height - chh) * cy
        return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + chh))

    black = Image.new("RGB", (W, H))

    def picture(t):
        k = max((i for i, s0 in enumerate(starts) if s0 <= t), default=0)
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
        if not last:
            for p0, p1, o in pops:
                if p0 <= t < p1:
                    frame.paste(o, (0, 0), o)
                    break
        if os.environ.get("FULL_CAPTIONS") == "1":  # old style: captions burned into the picture
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
    check_brand(out, o_brand)
    return out


def check_brand(out, logo):
    """Stop when the TrendingTesla logo is missing in the finished video (it must never silently disappear)."""
    fr = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "5", "-i", str(out), "-frames:v", "1", "-vf", f"scale={W}:{H}",
                         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    if len(fr) < W * H * 3:  # short preview: nothing to check at 5 s
        return
    img = Image.frombytes("RGB", (W, H), fr[:W * H * 3])
    pts = [(x, y) for x in range(0, W // 2, 2) for y in range(0, 220, 2)
           if (p := logo.getpixel((x, y)))[3] > 200 and p[0] > 240 and p[1] > 240]
    if not pts or sum(sum(img.getpixel(q)) / 3 for q in pts) / len(pts) < 190:
        raise SystemExit("::error::the TrendingTesla logo is missing in the long video")


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
    # a punchy YouTube title for the long video when the article gives one; the search-friendly title stays on the site
    ttl = (a.get("video") or {}).get(f"yt_title_{lang}") or t["title"]
    txt = (f"TITLE:\n{ttl[:100]}\n\nDESCRIPTION:\n{t['description']}\n\n{chl}:\n" + "\n".join(chap) +
           f"\n\n{read}: {url}\n\n{S.photo_credits(a, lang)}{note}\n\nTAGS:\n{', '.join(dict.fromkeys(tags))}\n")
    out.with_suffix(".txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
