"""Cut the LINK pivotal-trial preview Short. Nothing is uploaded or published.

Picture is Neuralink's own 25 Nov 2026 announcement montage: the N1 implant
and participants using computers, a cursor task, and a handheld game.
The @cb_doge clip is not used. It is a host at a table cut with satellites.

No shot is longer than 3 seconds. The soundtrack is Noah's narration only:
no music bed, no whistle, no chirp, no sound effects. The thumbnail is frame 0.
"""
import json
import math
import re
import struct
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
CLIPS = Path("/tmp/neuralink")
OUT = HERE / "render-out"
W, H, FPS = 1080, 1920, 30
FONT = str(HERE.parent / "fonts" / "Inter-Black.otf")
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)
DIM = (210, 206, 230)
NAVY = (28, 18, 48)

LINES = ("s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9")

# crop is x, y, w, h on the 1920x1080 montage. w/h is 9:16.
# avail is the clean source window. stretch is how far that window may be slowed.
SHOTS = [
    {"id": "open", "line": "s1", "kind": "video", "file": "announce.mp4", "ss": 1.08, "avail": 0.60,
     "stretch": 3.8, "hook": True, "fx": "hold", "zoom": (1.02, 1.12), "crop": (656, 0, 608, 1080),
     "shows": "N1 implant, Neuralink announcement montage, turning on a clean field. Hook."},
    {"id": "person", "line": "s1", "kind": "video", "file": "announce.mp4", "ss": 2.20, "avail": 1.60,
     "stretch": 1.35, "fx": "hold", "zoom": (1.00, 1.06), "crop": (1100, 0, 608, 1080),
     "shows": "A trial participant in a chair, from the same montage, as the trial is named."},
    {"id": "date", "line": "s2", "kind": "graphic", "graphic": "date",
     "shows": "November 25, the day Neuralink announced the FDA approval."},
    {"id": "screen", "line": "s3", "kind": "video", "file": "announce.mp4", "ss": 5.28, "avail": 1.55,
     "stretch": 1.45, "fx": "hold", "zoom": (1.02, 1.08), "crop": (700, 0, 608, 1080),
     "shows": "Laptop from the montage, a map on screen. Neuralink's investigational-device line sits at the bottom."},
    {"id": "chess", "line": "s3", "kind": "video", "file": "announce.mp4", "ss": 27.85, "avail": 1.45,
     "stretch": 1.60, "fx": "hold", "zoom": (1.00, 1.05), "crop": (40, 0, 608, 1080),
     "shows": "Chess on a laptop in the montage. The board is the picture, not the camera rig beside it."},
    {"id": "wheel", "line": "s4", "kind": "video", "file": "announce.mp4", "ss": 19.90, "avail": 1.35,
     "stretch": 1.50, "fx": "hold", "zoom": (1.00, 1.05), "crop": (340, 0, 608, 1080),
     "shows": "A participant in a powered wheelchair, at home, from the montage."},
    {"id": "home", "line": "s4", "kind": "video", "file": "announce.mp4", "ss": 33.20, "avail": 1.30,
     "stretch": 1.50, "fx": "hold", "zoom": (1.00, 1.05), "crop": (280, 0, 608, 1080),
     "shows": "A participant at home with a handheld, from the same montage."},
    {"id": "cursor", "line": "s5", "kind": "video", "file": "announce.mp4", "ss": 21.55, "avail": 2.10,
     "stretch": 1.30, "fx": "hold", "zoom": (1.00, 1.06), "crop": (500, 0, 608, 1080),
     "shows": "Cursor task on a laptop: target blocks and a moving dot."},
    {"id": "apps", "line": "s5", "kind": "video", "file": "announce.mp4", "ss": 35.60, "avail": 2.20,
     "stretch": 1.30, "fx": "hold", "zoom": (1.00, 1.06), "crop": (640, 0, 608, 1080),
     "shows": "A handheld game in the montage, with the on-screen cursor arrow."},
    {"id": "thirty", "line": "s6", "kind": "graphic", "graphic": "thirty",
     "shows": "More than 30 people already implanted."},
    {"id": "cost", "line": "s7", "kind": "graphic", "graphic": "cost",
     "shows": "Enrollment is open. Taking part costs nothing."},
    {"id": "travel", "line": "s8", "kind": "graphic", "graphic": "travel",
     "shows": "Travel and lodging for study visits are supported."},
    {"id": "close", "line": "s9", "kind": "video", "file": "announce.mp4", "ss": 1.12, "avail": 0.56,
     "stretch": 3.8, "fx": "hold", "zoom": (1.08, 1.16), "crop": (656, 0, 608, 1080),
     "shows": "The N1 again, tighter, under the line that this is not market approval."},
]

BG = None


def run(cmd):
    subprocess.run(cmd, check=True)


def dur(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def font(size):
    return ImageFont.truetype(FONT, size)


def words_of(sentence):
    chars, starts, ends = sentence["chars"], sentence["starts"], sentence["ends"]
    text = "".join(chars)
    words = []
    i = 0
    while i < len(chars):
        while i < len(chars) and chars[i].isspace():
            i += 1
        if i >= len(chars):
            break
        j = i
        while j < len(chars) and not chars[j].isspace():
            j += 1
        words.append((text[i:j], starts[i], ends[j - 1]))
        i = j
    return words


def caption_cards(sentence, t0):
    words = words_of(sentence)
    cap = (sentence.get("caption") or "").strip()
    n = len(cap.split())
    if 3 <= n <= 6 and words:
        return [(t0 + words[0][1], t0 + words[-1][2] + 0.06, cap)]
    cards, cur = [], []
    for w in words:
        cur.append(w)
        endish = w[0][-1:] in ".!?"
        if len(cur) >= 4 or (endish and len(cur) >= 3):
            cards.append(cur)
            cur = []
    if cur:
        if cards and len(cur) < 3:
            cards[-1].extend(cur)
        else:
            cards.append(cur)
    out = []
    for i, group in enumerate(cards):
        start = t0 + group[0][1]
        end = t0 + group[-1][2]
        if i + 1 < len(cards):
            end = max(end, t0 + cards[i + 1][0][1])
        else:
            end += 0.08
        shown = " ".join(w[0].strip(".,;:") for w in group)
        out.append((start, end, shown))
    return out


def draw_text(base, text, size, y, fill, max_w, stroke=None):
    d = ImageDraw.Draw(base)
    f = font(size)
    while f.size > 28 and d.textlength(text, font=f) > max_w:
        f = font(f.size - 4)
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text, font=f, fill=fill,
           stroke_width=stroke if stroke is not None else max(6, f.size // 14),
           stroke_fill=(0, 0, 0))
    return f.size


def overlay(im, caption, hook):
    if hook:
        draw_text(im, "FDA APPROVED", 58, 168, WHITE, W * 0.86)
        draw_text(im, "FIRST", 168, 250, YELLOW, W * 0.9)
        draw_text(im, "PIVOTAL TRIAL", 64, 450, WHITE, W * 0.9)
    if caption:
        words = caption.split()
        size = 64
        d = ImageDraw.Draw(im)
        max_w = W * 0.86
        while size > 42 and sum(d.textlength(w, font=font(size)) for w in words) + 12 * (len(words) - 1) > max_w:
            size -= 4
        f = font(size)
        gap = 12
        width = sum(d.textlength(w, font=f) for w in words) + gap * (len(words) - 1)
        x = (W - width) / 2
        y = 1420
        for w in words:
            fill = YELLOW if any(ch.isdigit() for ch in w) else WHITE
            d.text((x, y), w, font=f, fill=fill, stroke_width=8, stroke_fill=(0, 0, 0))
            x += d.textlength(w, font=f) + gap
    return im


def grade_frame(im):
    hi, lift, sat, contrast, head = 0.82, 0.06, 0.96, 1.06, 0.20
    lut = []
    for i in range(256):
        x = i / 255.0
        x = x + lift * (1.0 - x) ** 2
        if x > hi:
            t = (x - hi) / (1.0 - hi)
            x = hi + head * (t ** 0.75)
        lut.append(max(0, min(255, int(round(x * 255)))))
    im = im.point(lut * 3)
    im = ImageEnhance.Color(im).enhance(sat)
    im = ImageEnhance.Contrast(im).enhance(contrast)
    return im


def extract(shot, dest):
    x, y, w, h = shot["crop"]
    src_dur = float(shot["src_dur"])
    nframes = max(1, int(round(float(shot["dur"]) * FPS)))
    factor = nframes / (src_dur * FPS)
    ss = float(shot["ss"])
    pre = min(0.4, ss)
    vf = (f"trim=start={pre:.3f}:duration={src_dur:.5f},setpts=PTS-STARTPTS,"
          f"crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos,fps={FPS}")
    if abs(factor - 1.0) > 0.01:
        vf += f",setpts={factor:.6f}*PTS"
    vf += ",tpad=stop_mode=clone:stop_duration=0.08"
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss - pre:.3f}", "-i", str(CLIPS / shot["file"]),
         "-vf", vf, "-frames:v", str(nframes), "-an",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(dest)])


def appear(p, start, span=0.22):
    u = (p - start) / span
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    return 1 - (1 - u) ** 3


def paint_graphic(kind, p):
    im = BG.copy() if BG is not None else Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, int(W * min(1.0, p * 1.6)), 10), fill=YELLOW)
    if kind == "date":
        if appear(p, 0.0) > 0:
            draw_text(im, "ANNOUNCED", 48, 620, DIM, W * 0.8, stroke=0)
        if appear(p, 0.06) > 0:
            draw_text(im, "NOVEMBER 25", 92, 720, YELLOW, W * 0.92)
        if appear(p, 0.28) > 0:
            draw_text(im, "2026", 72, 860, WHITE, W * 0.6)
    elif kind == "thirty":
        if appear(p, 0.0) > 0:
            draw_text(im, "ALREADY IMPLANTED", 44, 560, DIM, W * 0.86, stroke=0)
        if appear(p, 0.08) > 0:
            draw_text(im, "30+", 200, 660, YELLOW, W * 0.9)
        if appear(p, 0.36) > 0:
            draw_text(im, "EARLIER PARTICIPANTS", 42, 940, WHITE, W * 0.9)
    elif kind == "cost":
        if appear(p, 0.0) > 0:
            draw_text(im, "ENROLLMENT", 56, 600, WHITE, W * 0.86)
        if appear(p, 0.12) > 0:
            draw_text(im, "OPEN", 120, 700, YELLOW, W * 0.8)
        if appear(p, 0.40) > 0:
            draw_text(im, "NO COST TO TAKE PART", 42, 900, WHITE, W * 0.9)
    elif kind == "travel":
        if appear(p, 0.0) > 0:
            draw_text(im, "TRAVEL", 100, 640, YELLOW, W * 0.86)
        if appear(p, 0.16) > 0:
            draw_text(im, "AND LODGING", 64, 790, WHITE, W * 0.86)
        if appear(p, 0.40) > 0:
            draw_text(im, "SUPPORTED", 56, 920, DIM, W * 0.8, stroke=0)
    return im


def encode_frames(frames_path, dest):
    run(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", str(frames_path), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "16", str(dest)])


def paint_video(src, dest, cards, hook, t0, zoom):
    raw = OUT / "raw.rgb"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", str(raw)])
    frame = W * H * 3
    nframes = raw.stat().st_size // frame
    graded = OUT / "graded.rgb"
    with raw.open("rb") as inp, graded.open("wb") as outp:
        n = 0
        while True:
            buf = inp.read(frame)
            if len(buf) < frame:
                break
            t = t0 + n / FPS
            im = Image.frombytes("RGB", (W, H), buf)
            z0, z1 = zoom or (1.0, 1.0)
            z = z0 + (z1 - z0) * (n / max(1, nframes - 1))
            if z > 1.01:
                cw = int(W / z)
                ch = int(H / z)
                cw -= cw % 2
                ch -= ch % 2
                x0 = (W - cw) // 2
                y0 = (H - ch) // 2
                im = im.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.Resampling.LANCZOS)
            im = grade_frame(im)
            cap = ""
            for a, b, text in cards:
                if a - 0.02 <= t < b:
                    cap = text
                    break
            overlay(im, cap, hook and n < nframes)
            outp.write(im.tobytes())
            n += 1
    raw.unlink(missing_ok=True)
    encode_frames(graded, dest)
    graded.unlink(missing_ok=True)


def render_graphic(shot, dest, cards, t0):
    raw = OUT / "graphic.rgb"
    nframes = max(1, int(round(shot["dur"] * FPS)))
    with raw.open("wb") as outp:
        for n in range(nframes):
            t = t0 + n / FPS
            p = n / max(1, nframes - 1)
            im = paint_graphic(shot["graphic"], p)
            cap = ""
            for a, b, text in cards:
                if a - 0.02 <= t < b:
                    cap = text
                    break
            overlay(im, cap, False)
            outp.write(im.tobytes())
    encode_frames(raw, dest)
    raw.unlink(missing_ok=True)


def lufs(path, extra_af=""):
    af = f"{extra_af},ebur128" if extra_af else "ebur128"
    proc = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", af, "-f", "null", "-"],
        capture_output=True, text=True)
    found = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", proc.stderr)
    if not found:
        raise SystemExit(f"no LUFS reading for {path}\n{proc.stderr[-400:]}")
    return float(found[-1])


def quietest_db(path, window=0.08):
    """Quietest short window, in dBFS. A music bed never lets this fall to silence."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True, check=True).stdout
    count = len(raw) // 2
    samples = struct.unpack("<" + "h" * count, raw[:count * 2])
    win = max(1, int(window * 16000))
    quiet = 0.0
    for i in range(0, count - win, win // 2):
        chunk = samples[i:i + win]
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
        if rms > 0.0 and (quiet == 0.0 or rms < quiet):
            quiet = rms
    if quiet <= 0.0:
        return -120.0
    return 20.0 * math.log10(quiet)


def build_background():
    global BG
    still = OUT / "bg.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-ss", "0.90", "-i", str(CLIPS / "announce.mp4"),
         "-frames:v", "1", "-vf", "crop=608:1080:656:0,scale=1080:1920", str(still)])
    im = Image.open(still).convert("RGB")
    im = im.filter(ImageFilter.GaussianBlur(radius=28))
    im = ImageEnhance.Brightness(im).enhance(0.62)
    im = ImageEnhance.Color(im).enhance(1.05)
    im = im.point(lambda i: max(i, 36))
    BG = im


def audit(path):
    raw = OUT / "audit.rgb"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", str(raw)])
    frame = W * H * 3
    step = 6
    worst_clip = (0.0, 0.0)
    worst_black = (0.0, 0.0)
    notes = []
    n = 0
    with raw.open("rb") as inp:
        while True:
            buf = inp.read(frame)
            if len(buf) < frame:
                break
            clip = black = seen = 0
            for i in range(0, frame, 3 * step):
                r, g, b = buf[i], buf[i + 1], buf[i + 2]
                seen += 1
                if r >= 250 and g >= 250 and b >= 250:
                    clip += 1
                if max(r, g, b) < 16:
                    black += 1
            c = clip / seen
            b = black / seen
            t = n / FPS
            if c > worst_clip[0]:
                worst_clip = (c, t)
            if b > worst_black[0]:
                worst_black = (b, t)
            if n % FPS == 0:
                notes.append({"t": round(t, 2), "clip": round(c, 4), "black": round(b, 4)})
            if c > 0.12:
                raise SystemExit(f"frame {t:.2f}s is {c:.1%} clipped white")
            n += 1
    raw.unlink(missing_ok=True)
    print(f"audit frames {n}  worst clip {worst_clip[0]:.1%} at {worst_clip[1]:.2f}s  "
          f"worst black {worst_black[0]:.1%} at {worst_black[1]:.2f}s", flush=True)
    return notes, worst_clip, worst_black


def timeline_of():
    alignment = json.loads((HERE / "out" / "alignment.json").read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in alignment["sentences"]}
    timeline = []
    t = 0.0
    for i, key in enumerate(LINES):
        s = by_id[key]
        length = dur(HERE / "out" / f"{s['id']}.mp3")
        timeline.append({**s, "t0": t, "length": length})
        t += length
        if i < len(LINES) - 1:
            t += 0.08
    return timeline, t


def fit_duration(timeline):
    by = {m["id"]: m for m in timeline}
    groups = []
    for key in LINES:
        shots = [s for s in SHOTS if s["line"] == key]
        if not shots:
            raise SystemExit(f"no shots for {key}")
        groups.append((by[key], shots))
    gap = 0.08
    for sent, shots in groups:
        need = sent["length"] + (0.0 if sent["id"] == "s9" else gap)
        if len(shots) == 1:
            shots[0]["dur"] = need
        else:
            weights = []
            for s in shots:
                weights.append(s["avail"] * s["stretch"] if s["kind"] == "video" else 2.4)
            scale = need / sum(weights)
            for s, w in zip(shots, weights):
                s["dur"] = w * scale
    for s in SHOTS:
        if s["dur"] > 3.15:
            raise SystemExit(f"{s['id']} is {s['dur']:.2f}s")
        if s["dur"] < 1.05:
            raise SystemExit(f"{s['id']} is only {s['dur']:.2f}s")
        if s["kind"] == "video":
            cap = s["avail"] * s["stretch"]
            if s["dur"] > cap + 0.02:
                raise SystemExit(f"{s['id']} needs {s['dur']:.2f}s but source allows {cap:.2f}s")
            s["src_dur"] = min(s["avail"], s["dur"])
    got = sum(s["dur"] for s in SHOTS)
    total = timeline[-1]["t0"] + timeline[-1]["length"]
    delta = total - got
    if abs(delta) > 0.02:
        raise SystemExit(f"timeline {got:.3f}s vs voice {total:.3f}s")
    SHOTS[-1]["dur"] += delta
    for s in SHOTS:
        s["dur"] = round(s["dur"], 3)
        if s["kind"] == "video":
            s["src_dur"] = round(min(s["avail"], s["src_dur"]), 3)


def main():
    if not (CLIPS / "announce.mp4").exists():
        raise SystemExit("missing /tmp/neuralink/announce.mp4")
    timeline, total = timeline_of()
    if not 24.0 <= total <= 40.0:
        raise SystemExit(f"voice length {total:.2f}s is outside 24-40s")
    OUT.mkdir(exist_ok=True)
    fit_duration(timeline)
    graphic = sum(s["dur"] for s in SHOTS if s["kind"] == "graphic")
    if graphic / total > 0.45:
        raise SystemExit(f"graphics are {graphic / total:.1%} of the runtime")
    print(f"voice {total:.2f}s  graphics {graphic:.2f}s ({graphic / total:.1%})", flush=True)
    for s in SHOTS:
        print(f"  plan {s['id']:8} {s['dur']:.2f}s", flush=True)
    build_background()

    by_id = {s["id"]: s for s in timeline}
    cards = []
    for i, m in enumerate(timeline):
        sent = dict(by_id[m["id"]])
        nxt = timeline[i + 1]["t0"] if i + 1 < len(timeline) else m["t0"] + m["length"] + 0.2
        for a, b, text in caption_cards(sent, m["t0"]):
            b = min(b, nxt)
            if b > a + 0.04:
                cards.append((a, b, text))

    segs = []
    t = 0.0
    for shot in SHOTS:
        graded = OUT / f"{shot['id']}.mp4"
        print(f"shot {shot['id']} {shot['dur']:.2f}s", flush=True)
        if shot["kind"] == "graphic":
            render_graphic(shot, graded, cards, t)
        else:
            plain = OUT / f"{shot['id']}-plain.mp4"
            extract(shot, plain)
            paint_video(plain, graded, cards, bool(shot.get("hook")), t, shot.get("zoom"))
            plain.unlink(missing_ok=True)
        segs.append(graded)
        t += shot["dur"]

    listing = OUT / "video.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in segs), encoding="utf-8")
    silent = OUT / "silent.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17", "-r", str(FPS), str(silent)])

    voice_inputs, voice_filters = [], []
    for i, m in enumerate(timeline):
        voice_inputs += ["-i", str(HERE / "out" / f"{m['id']}.mp3")]
        ms = int(round(m["t0"] * 1000))
        voice_filters.append(f"[{i}:a]adelay={ms}|{ms},apad=pad_dur=2[v{i}]")
    voice_mix = "".join(f"[v{i}]" for i in range(len(timeline))) + f"amix=inputs={len(timeline)}:normalize=0:duration=longest[voice]"
    voice = OUT / "voice.m4a"
    run(["ffmpeg", "-y", "-v", "error", *voice_inputs, "-filter_complex", ";".join(voice_filters) + ";" + voice_mix,
         "-map", "[voice]", "-t", f"{total:.3f}", "-c:a", "aac", "-b:a", "192k", str(voice)])

    voice_lufs = lufs(voice)
    voice_gain = -14.0 - voice_lufs
    print(f"voice {voice_lufs:.1f} LUFS gain {voice_gain:+.1f} dB  (no music bed)", flush=True)

    final = OUT / "neuralink-fda-link-trial-short.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(voice),
         "-filter_complex",
         f"[1:a]volume={voice_gain:.2f}dB,alimiter=limit=0.95:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])
    mix = lufs(final)
    floor = quietest_db(final)
    print(f"LUFS mix {mix:.1f}  quietest 80 ms {floor:.1f} dBFS", flush=True)
    if floor > -36.0:
        raise SystemExit(f"quietest window is {floor:.1f} dBFS, so a music bed or sound effect is still under the voice")

    thumb = OUT / "neuralink-fda-link-trial-thumb.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(thumb)])

    rows = []
    t = 0.0
    for g in SHOTS:
        rows.append({
            "id": g["id"], "line": g["line"], "file": g.get("file", ""),
            "source_ss": g.get("ss"), "video_in": round(t, 3), "video_out": round(t + g["dur"], 3),
            "duration": round(g["dur"], 3), "shows": g["shows"],
        })
        print(f"{t:6.2f}-{t + g['dur']:6.2f}  {g['id']:8} {g['dur']:.2f}s  {g['shows']}", flush=True)
        t += g["dur"]
    notes, worst_clip, worst_black = audit(final)
    (OUT / "shots.json").write_text(json.dumps({
        "duration": round(total, 3),
        "graphics_s": round(graphic, 3),
        "graphics_share": round(graphic / total, 4),
        "lufs": {"mix": mix, "voice_raw": voice_lufs, "voice_gain_db": round(voice_gain, 2),
                 "quietest_80ms_dbfs": round(floor, 2), "music": False},
        "worst_clip": {"share": worst_clip[0], "t": worst_clip[1]},
        "worst_black": {"share": worst_black[0], "t": worst_black[1]},
        "per_second": notes,
        "shots": rows,
        "footage": "https://x.com/neuralink/status/2125694580544680185",
        "rejected": "https://x.com/cb_doge/status/2125700784558166479 is a host plus Starlink satellites, not the implant",
    }, indent=2) + "\n", encoding="utf-8")
    print("RENDER", final, f"{total:.2f}s")


if __name__ == "__main__":
    main()
