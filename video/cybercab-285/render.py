"""Cut the Cybercab 285 preview Short. Nothing is uploaded or published.

Picture is official Robotaxi footage of Cybercabs in Texas: the Austin
fleet film (rows, the line, the lot) and Giga Texas (a butterfly door
and the gold car driving past). No cabin interior. No music, no whistle,
no swoosh, no sound effect. The thumbnail is frame 0.

The voice is given the numbers as words. Captions stay numerals.
"""
import json
import math
import struct
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

HERE = Path(__file__).resolve().parent
CLIPS = Path("/tmp/cybercab")
OUT = HERE / "render-out"
W, H, FPS = 1080, 1920, 30
FONT = str(HERE.parent / "fonts" / "Inter-Black.otf")
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)

LINES = ("s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8")

# crop is x, y, w, h on the source. w/h is 9:16. avail is the clean window.
# stretch is how far that window may be slowed. No shot is a still or a fill.
SHOTS = [
    {"id": "open", "line": "s1", "file": "austin300-4k.mp4", "ss": 28.85, "avail": 2.15,
     "stretch": 1.30, "hook": True, "zoom": (1.00, 1.06), "crop": (1360, 0, 1216, 2160),
     "shows": "Rows of gold Cybercabs in Austin. Hook and thumbnail."},
    {"id": "nose", "line": "s1", "file": "austin300-4k.mp4", "ss": 25.55, "avail": 1.85,
     "stretch": 1.40, "hook": True, "zoom": (1.04, 1.10), "crop": (1280, 0, 1216, 2160),
     "shows": "One gold Cybercab from above, still on the opening line."},
    {"id": "factory", "line": "s2", "file": "austin300-4k.mp4", "ss": 0.50, "avail": 1.70,
     "stretch": 1.20, "zoom": (1.02, 1.08), "crop": (1288, 0, 1216, 2160),
     "shows": "A gold Cybercab on the line at Giga Texas."},
    {"id": "doors", "line": "s2", "file": "giga-4k.mp4", "ss": 0.42, "avail": 0.84,
     "stretch": 1.75, "zoom": (1.00, 1.05), "crop": (900, 180, 900, 1600),
     "shows": "Butterfly door with the Cybercab script. The crop stays off the people beside the car."},
    {"id": "lot", "line": "s3", "file": "austin300-4k.mp4", "ss": 36.30, "avail": 2.40,
     "stretch": 1.35, "zoom": (1.00, 1.05), "crop": (1180, 0, 1216, 2160),
     "shows": "Overhead lot of gold Cybercabs. First time past one thousand."},
    {"id": "lot2", "line": "s3", "file": "austin300-4k.mp4", "ss": 39.10, "avail": 2.30,
     "stretch": 1.35, "zoom": (1.00, 1.06), "crop": (1560, 0, 1216, 2160),
     "shows": "The same Austin lot, another row, as 1,107 is said."},
    {"id": "line", "line": "s4", "file": "austin300-4k.mp4", "ss": 6.90, "avail": 1.90,
     "stretch": 1.40, "zoom": (1.00, 1.06), "crop": (860, 0, 1216, 2160),
     "shows": "Cybercab body on the Giga Texas line."},
    {"id": "lot3", "line": "s4", "file": "austin300-4k.mp4", "ss": 41.15, "avail": 2.00,
     "stretch": 1.30, "zoom": (1.00, 1.06), "crop": (860, 0, 1216, 2160),
     "shows": "Another sharp overhead of the Austin Cybercab rows."},
    {"id": "rows", "line": "s4", "file": "austin300-4k.mp4", "ss": 29.70, "avail": 2.10,
     "stretch": 1.35, "zoom": (1.02, 1.08), "crop": (1900, 0, 1216, 2160),
     "shows": "Another angle on the Austin row, under the Waymo comparison."},
    {"id": "side", "line": "s5", "file": "giga-4k.mp4", "ss": 17.35, "avail": 0.62,
     "stretch": 2.80, "zoom": (1.00, 1.04), "crop": (1650, 320, 960, 1706),
     "shows": "Gold Cybercab driving past, the script on the door. No steering wheel in frame."},
    {"id": "fleet", "line": "s5", "file": "austin300-4k.mp4", "ss": 32.05, "avail": 2.05,
     "stretch": 1.15, "zoom": (1.00, 1.05), "crop": (1200, 0, 1216, 2160),
     "shows": "Austin rows of gold Cybercabs, on the line that the fleet has no steering wheel."},
    {"id": "ride", "line": "s6", "file": "austin300-4k.mp4", "ss": 34.20, "avail": 1.55,
     "stretch": 1.30, "zoom": (1.00, 1.05), "crop": (1000, 0, 1216, 2160),
     "shows": "More of the Austin Cybercab fleet that carries riders."},
    {"id": "ride2", "line": "s6", "file": "austin300-4k.mp4", "ss": 43.25, "avail": 1.20,
     "stretch": 1.45, "zoom": (1.02, 1.06), "crop": (1100, 0, 1216, 2160),
     "shows": "Another row of the same gold Cybercabs."},
    {"id": "yard", "line": "s7", "file": "austin300-4k.mp4", "ss": 2.45, "avail": 1.40,
     "stretch": 1.40, "zoom": (1.02, 1.08), "crop": (1200, 0, 1216, 2160),
     "shows": "A gold Cybercab still on the line. Registered, not on the road yet."},
    {"id": "park", "line": "s7", "file": "austin300-4k.mp4", "ss": 44.50, "avail": 0.80,
     "stretch": 1.80, "zoom": (1.00, 1.04), "crop": (1100, 0, 1216, 2160),
     "shows": "Parked Cybercab rows. Not every registered car is giving a ride."},
    {"id": "loop", "line": "s8", "file": "austin300-4k.mp4", "ss": 27.72, "avail": 1.15,
     "stretch": 1.70, "zoom": (1.00, 1.04), "crop": (1360, 0, 1216, 2160),
     "shows": "The opening row as it begins, so the cut back continues."},
]

SOURCES = {
    "austin300-4k.mp4": {
        "post": "https://x.com/robotaxi/status/2108981691436224816",
        "file": "https://video.twimg.com/amplify_video/2108981082184196096/vid/avc1/3840x2160/JMXBg-QsjE5QIYbt.mp4",
        "what": "Robotaxi, 10 Oct 2026, 300+ Cybercabs serving Austin, 45 s, 4K",
    },
    "giga-4k.mp4": {
        "post": "https://x.com/robotaxi/status/2075766457242415386",
        "file": "https://video.twimg.com/amplify_video/2075766313142845440/vid/avc1/3840x2026/o3gSBKFtdG087qgx.mp4",
        "what": "Robotaxi, 11 Jul 2026, Cool news from Giga Texas, 47 s, 4K",
    },
}


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


# Longer phrases first, so "two hundred" does not swallow "two hundred eighty-five".
NUMERALS = (
    (["two", "hundred", "and", "eighty", "five"], "285"),
    (["two", "hundred", "eighty", "five"], "285"),
    (["eleven", "hundred", "and", "seven"], "1,107"),
    (["eighteen", "hundred", "and", "forty", "one"], "1,841"),
    (["eighteen", "hundred", "forty", "one"], "1,841"),
    (["fourteen", "hundred", "and", "nine"], "1,409"),
    (["fourteen", "hundred", "nine"], "1,409"),
    (["two", "hundred"], "200"),
    (["one", "thousand"], "1,000"),
    (["sixty"], "60"),
)


def _pieces(token):
    core = token.strip(".,;:!?")
    return [p.lower() for p in core.replace("-", " ").split() if p]


def collapse_numbers(words):
    """Swap a spoken quantity for the numeral caption, keeping the spoken timing."""
    out = []
    i = 0
    while i < len(words):
        hit = None
        for phrase, numeral in NUMERALS:
            got, acc = [], []
            k = i
            while len(got) < len(phrase):
                if k >= len(words):
                    break
                piece = _pieces(words[k][0])
                if phrase[len(got):len(got) + len(piece)] != piece:
                    break
                got.extend(piece)
                acc.append(words[k])
                k += 1
            if got == phrase and acc:
                punct = acc[-1][0][-1:] if acc[-1][0][-1:] in ".!?" else ""
                hit = ((numeral + punct, acc[0][1], acc[-1][2]), k)
                break
        if hit:
            out.append(hit[0])
            i = hit[1]
        else:
            out.append(words[i])
            i += 1
    return out


def caption_cards(sentence, t0):
    """3 to 5 words per card. Spoken quantities are drawn as numerals when they are said."""
    words = collapse_numbers(words_of(sentence))
    cards, cur = [], []

    def flush():
        nonlocal cur
        if cur:
            cards.append(cur)
            cur = []

    for w in words:
        is_num = any(ch.isdigit() for ch in w[0])
        if is_num and len(cur) >= 2:
            flush()
        cur.append(w)
        endish = w[0][-1:] in ".!?"
        if len(cur) >= 4 or (endish and (len(cur) >= 3 or is_num)):
            flush()
    if cur:
        lone = len(cur) == 1 and not any(ch.isdigit() for ch in cur[0][0])
        if cards and lone:
            cards[-1].extend(cur)
        else:
            cards.append(cur)
    out = []
    for i, group in enumerate(cards):
        start = t0 + group[0][1]
        end = t0 + group[-1][2]
        if i + 1 < len(cards):
            end = min(max(end, t0 + cards[i + 1][0][1] - 0.04), t0 + cards[i + 1][0][1])
        else:
            end += 0.06
        shown = " ".join(w[0].strip(".,;:!?") for w in group)
        out.append((start, end, shown))
    return out


def draw_text(base, text, size, y, fill, max_w, stroke=None):
    d = ImageDraw.Draw(base)
    f = font(size)
    while f.size > 28 and d.textlength(text, font=f) > max_w:
        f = font(f.size - 4)
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text, font=f, fill=fill,
           stroke_width=stroke if stroke is not None else max(8, f.size // 12),
           stroke_fill=(0, 0, 0))
    return f.size


def overlay(im, caption, hook):
    if hook:
        draw_text(im, "285", 248, 150, YELLOW, W * 0.92)
        draw_text(im, "IN ONE DAY", 52, 420, WHITE, W * 0.86)
    if caption:
        words = caption.split()
        size = 68
        d = ImageDraw.Draw(im)
        max_w = W * 0.88
        while size > 42 and sum(d.textlength(w, font=font(size)) for w in words) + 14 * (len(words) - 1) > max_w:
            size -= 4
        f = font(size)
        gap = 14
        width = sum(d.textlength(w, font=f) for w in words) + gap * (len(words) - 1)
        x = (W - width) / 2
        y = 1500
        for w in words:
            fill = YELLOW if any(ch.isdigit() for ch in w) else WHITE
            d.text((x, y), w, font=f, fill=fill, stroke_width=8, stroke_fill=(0, 0, 0))
            x += d.textlength(w, font=f) + gap
    return im


def grade_frame(im):
    hi, lift, sat, contrast, head = 0.90, 0.035, 1.04, 1.05, 0.16
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
    if w % 2 or h % 2:
        raise SystemExit(f"{shot['id']} crop {w}x{h} is not even")
    if abs((w / h) - (9 / 16)) > 0.004:
        raise SystemExit(f"{shot['id']} crop is {w/h:.4f}, not 9:16")
    src_dur = float(shot["src_dur"])
    nframes = max(1, int(round(float(shot["dur"]) * FPS)))
    factor = nframes / (src_dur * FPS)
    ss = float(shot["ss"])
    pre = min(0.25, ss)
    vf = (f"trim=start={pre:.3f}:duration={src_dur:.5f},setpts=PTS-STARTPTS,"
          f"crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos,fps={FPS}")
    if abs(factor - 1.0) > 0.01:
        vf += f",setpts={factor:.6f}*PTS"
    vf += ",tpad=stop_mode=clone:stop_duration=0.08"
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss - pre:.3f}", "-i", str(CLIPS / shot["file"]),
         "-vf", vf, "-frames:v", str(nframes), "-an",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(dest)])


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
            if z > 1.005:
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
            overlay(im, cap, hook)
            outp.write(im.tobytes())
            n += 1
    raw.unlink(missing_ok=True)
    encode_frames(graded, dest)
    graded.unlink(missing_ok=True)


def lufs(path):
    proc = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "ebur128=framelog=verbose", "-f", "null", "-"],
        capture_output=True, text=True)
    found = []
    for line in proc.stderr.splitlines():
        if "I:" in line and "LUFS" in line and "Summary" not in line:
            # integrated summary is the last I: line that is not a short-term frame
            pass
    import re
    found = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", proc.stderr)
    if not found:
        raise SystemExit(f"no LUFS reading for {path}\n{proc.stderr[-400:]}")
    return float(found[-1])


def quietest_db(path, window=0.08):
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
    if alignment.get("voice_id") != "q1OMOTZNtqpS50TIQtu4":
        raise SystemExit(f"voice is {alignment.get('voice_id')}, not Tony Smyles")
    if alignment.get("model") != "eleven_multilingual_v2":
        raise SystemExit(f"model is {alignment.get('model')}")
    settings = alignment.get("voice_settings") or {}
    print(
        "voice id=q1OMOTZNtqpS50TIQtu4 model=eleven_multilingual_v2 "
        f"stability={settings.get('stability')} similarity_boost={settings.get('similarity_boost')} "
        f"style={settings.get('style')} use_speaker_boost={str(settings.get('use_speaker_boost')).lower()} "
        f"speed={settings.get('speed')} no_delivery_tags=true music=off",
        flush=True,
    )
    by_id = {s["id"]: s for s in alignment["sentences"]}
    timeline = []
    t = 0.0
    for i, key in enumerate(LINES):
        s = by_id[key]
        length = dur(HERE / "out" / f"{s['id']}.mp3")
        timeline.append({**s, "t0": t, "length": length})
        t += length
        if i < len(LINES) - 1:
            t += 0.06
    return timeline, t


def fit_duration(timeline):
    by = {m["id"]: m for m in timeline}
    groups = []
    for key in LINES:
        shots = [s for s in SHOTS if s["line"] == key]
        if not shots:
            raise SystemExit(f"no shots for {key}")
        groups.append((by[key], shots))
    gap = 0.06
    for sent, shots in groups:
        need = sent["length"] + (0.0 if sent["id"] == LINES[-1] else gap)
        weights = [s["avail"] * s["stretch"] for s in shots]
        scale = need / sum(weights)
        for s, w in zip(shots, weights):
            s["dur"] = w * scale
    for s in SHOTS:
        if s["dur"] > 3.05:
            raise SystemExit(f"{s['id']} is {s['dur']:.2f}s")
        if s["dur"] < 1.15:
            raise SystemExit(f"{s['id']} is only {s['dur']:.2f}s")
        cap = s["avail"] * s["stretch"]
        if s["dur"] > cap + 0.04:
            raise SystemExit(f"{s['id']} needs {s['dur']:.2f}s but source allows {cap:.2f}s")
        s["src_dur"] = min(s["avail"], s["dur"])
    got = sum(s["dur"] for s in SHOTS)
    total = timeline[-1]["t0"] + timeline[-1]["length"]
    delta = total - got
    if abs(delta) > 0.05:
        raise SystemExit(f"timeline {got:.3f}s vs voice {total:.3f}s")
    SHOTS[-1]["dur"] += delta
    for s in SHOTS:
        s["dur"] = round(s["dur"], 3)
        s["src_dur"] = round(min(s["avail"], s["src_dur"]), 3)


def main():
    for name in SOURCES:
        if not (CLIPS / name).exists():
            raise SystemExit(f"missing {CLIPS / name}")
    timeline, total = timeline_of()
    if not 22.0 <= total <= 32.0:
        raise SystemExit(f"voice length {total:.2f}s is outside 22-32s")
    OUT.mkdir(exist_ok=True)
    fit_duration(timeline)
    print(f"voice {total:.2f}s  shots {len(SHOTS)}  graphics 0", flush=True)
    for s in SHOTS:
        print(f"  plan {s['id']:8} {s['dur']:.2f}s  src {s['src_dur']:.2f}s", flush=True)

    by_id = {s["id"]: s for s in timeline}
    cards = []
    for i, m in enumerate(timeline):
        sent = dict(by_id[m["id"]])
        nxt = timeline[i + 1]["t0"] if i + 1 < len(timeline) else m["t0"] + m["length"] + 0.2
        for a, b, text in caption_cards(sent, m["t0"]):
            b = min(b, nxt - 0.02)
            if b > a + 0.04:
                cards.append((a, b, text))

    segs = []
    t = 0.0
    for shot in SHOTS:
        graded = OUT / f"{shot['id']}.mp4"
        print(f"shot {shot['id']} {shot['dur']:.2f}s", flush=True)
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

    final = OUT / "cybercab-285-one-day-short.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(voice),
         "-filter_complex",
         f"[1:a]volume={voice_gain:.2f}dB,alimiter=limit=0.95:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])
    mix = lufs(final)
    floor = quietest_db(final)
    print(f"LUFS mix {mix:.1f}  quietest 80 ms {floor:.1f} dBFS", flush=True)
    if floor > -36.0:
        raise SystemExit(f"quietest window is {floor:.1f} dBFS, so a bed or a sound effect is still under the voice")

    thumb = OUT / "cybercab-285-one-day-thumb.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(thumb)])

    rows = []
    t = 0.0
    for g in SHOTS:
        src = SOURCES[g["file"]]
        rows.append({
            "id": g["id"], "line": g["line"], "file": g["file"],
            "source_ss": g["ss"], "video_in": round(t, 3), "video_out": round(t + g["dur"], 3),
            "duration": round(g["dur"], 3), "shows": g["shows"],
            "post": src["post"], "source_file": src["file"],
        })
        print(f"{t:6.2f}-{t + g['dur']:6.2f}  {g['id']:8} {g['dur']:.2f}s  {g['shows']}", flush=True)
        t += g["dur"]
    notes, worst_clip, worst_black = audit(final)
    (OUT / "shots.json").write_text(json.dumps({
        "duration": round(total, 3),
        "graphics_s": 0,
        "lufs": {"mix": mix, "voice_raw": voice_lufs, "voice_gain_db": round(voice_gain, 2),
                 "quietest_80ms_dbfs": round(floor, 2), "music": False},
        "voice": "q1OMOTZNtqpS50TIQtu4 eleven_multilingual_v2 stability 0.45 similarity_boost 0.8 style 0.3 use_speaker_boost true speed 1.07",
        "worst_clip": {"share": worst_clip[0], "t": worst_clip[1]},
        "worst_black": {"share": worst_black[0], "t": worst_black[1]},
        "per_second": notes,
        "shots": rows,
        "sources": SOURCES,
        "rejected": "The Howdy Dallas interior and the Giga cabin point of view are a Model Y cabin with a hand on a steering wheel, so neither is in the cut. The 20 Nov trumpet clip is a rider in a dark cabin. The wide Giga door shot includes two people and plate 007; the cut uses only the door. The front-on drive-by shows plate 003, so that angle is out. The side pass at 17.35 seconds is the driving shot.",
    }, indent=2) + "\n", encoding="utf-8")
    print("RENDER", final, f"{total:.2f}s")


if __name__ == "__main__":
    main()
