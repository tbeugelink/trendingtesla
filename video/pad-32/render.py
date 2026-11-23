"""Cut the pad-turnaround preview Short, version 5. Nothing is uploaded or published.

Picture is the two pad cameras (USSF-317 and NROL-136, both SLC-4E) and the
LZ-4 landing, plus four motion-graphics cards on a blurred pad frame. The
tracking shots are gone: a rocket smaller than the pad, or a frame that is
mostly black, does not stay in.

Voice is the existing Noah takes, shortened to the lines that fit 24-28 s.
No shot is longer than 3.0 s. The bed is the same midrange track as v4.
"""
import json
import math
import re
import struct
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
CLIPS = Path("/tmp/pad32")
OUT = HERE / "render-out"
W, H, FPS = 1080, 1920, 30
FONT = str(HERE.parent / "fonts" / "Inter-Black.otf")
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)
DIM = (186, 196, 210)
NAVY = (7, 10, 18)

# Spoken lines, in order. These are existing Noah takes. Four lines are left out
# so the cut fits 24-28 s. There is no key here to re-record a new sentence.
LINES = ("s1", "s2", "s3", "s4", "s5", "s9", "s10")

# dur is the picture length. The loop shot is rewritten to match the voice.
# crop is x, y, w, h on the 1920x1080 webcast. w/h is 9:16.
# zoom is the start and end scale of a slow push-in on that crop.
SHOTS = [
    {"id": "open", "kind": "video", "file": "ussf317-1080.mp4", "ss": 751.80, "dur": 3.00,
     "hook": True, "fx": "hold", "zoom": (1.00, 1.08), "crop": (707, 0, 506, 900), "mission": "USSF-317",
     "shows": "Friday pad, SLC-4E. Full Falcon 9, strongback, venting. Slow push-in. Hook."},
    {"id": "tight", "kind": "video", "file": "ussf317-1080.mp4", "ss": 744.20, "dur": 2.80,
     "fx": "hold", "zoom": (1.04, 1.14), "crop": (707, 0, 506, 900), "mission": "USSF-317",
     "shows": "Same Friday pad a few seconds earlier, pushed in closer. Full Falcon 9."},
    {"id": "timeline", "kind": "graphic", "graphic": "timeline", "dur": 2.50, "mission": "graphic",
     "shows": "Fri 20 Nov 20:20 PT to Sun 22 Nov 04:23 PT, over a blurred pad frame."},
    {"id": "stack", "kind": "video", "file": "nrol136-1080.mp4", "ss": 824.60, "dur": 2.80,
     "fx": "hold", "zoom": (1.00, 1.10), "crop": (790, 310, 320, 568), "mission": "NROL-136",
     "shows": "Sunday's Falcon 9 on SLC-4E, full stack, cropped above the webcast HUD."},
    {"id": "clock", "kind": "graphic", "graphic": "clock", "dur": 2.70, "mission": "graphic",
     "shows": "A clock racing up to 32:03:21, over a blurred pad frame."},
    {"id": "bars", "kind": "graphic", "graphic": "bars", "dur": 2.60, "mission": "graphic",
     "shows": "45 hours against 32 hours, bars growing, over a blurred pad frame."},
    {"id": "two", "kind": "graphic", "graphic": "two", "dur": 2.20, "mission": "graphic",
     "shows": "Two boosters, not one. B1097, flight 14. Over a blurred pad frame."},
    {"id": "land", "kind": "video", "file": "nrol136-1080.mp4", "ss": 1297.25, "dur": 1.60,
     "fx": "land", "zoom": (1.00, 1.04), "crop": (1250, 260, 260, 462), "mission": "NROL-136",
     "shows": "LZ-4, tight on the booster and the legs, cut before the booster drops out of frame."},
    {"id": "push", "kind": "video", "file": "nrol136-1080.mp4", "ss": 819.80, "dur": 3.00,
     "fx": "hold", "zoom": (1.00, 1.06), "crop": (805, 330, 290, 516), "mission": "NROL-136",
     "shows": "Sunday pad again, tighter and a few seconds earlier. Full Falcon 9."},
    {"id": "loop", "kind": "video", "file": "ussf317-1080.mp4", "ss": 749.60, "dur": 2.20,
     "fx": "hold", "zoom": (1.00, 1.06), "crop": (707, 0, 506, 900), "mission": "USSF-317",
     "shows": "The opening camera in the seconds before ignition, so the cut back continues."},
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
    """3 to 6 spoken words per card, timed from the voice."""
    words = words_of(sentence)
    cap = (sentence.get("caption") or "").strip()
    n = len(cap.split())
    if 3 <= n <= 6 and words:
        return [(t0 + words[0][1], t0 + words[-1][2] + 0.05, cap)]
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
    while f.size > 36 and d.textlength(text, font=f) > max_w:
        f = font(f.size - 4)
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text, font=f, fill=fill,
           stroke_width=stroke if stroke is not None else max(6, f.size // 14),
           stroke_fill=(0, 0, 0))
    return f.size


def overlay(im, caption, hook):
    if hook:
        draw_text(im, "32 HOURS", 156, 196, YELLOW, W * 0.86)
    if caption:
        words = caption.split()
        size = 72
        d = ImageDraw.Draw(im)
        max_w = W * 0.74
        while size > 48 and sum(d.textlength(w, font=font(size)) for w in words) + 16 * (len(words) - 1) > max_w:
            size -= 4
        f = font(size)
        gap = 16
        width = sum(d.textlength(w, font=f) for w in words) + gap * (len(words) - 1)
        x = (W - width) / 2
        y = 1188
        for w in words:
            fill = YELLOW if any(ch.isdigit() for ch in w) else WHITE
            d.text((x, y), w, font=f, fill=fill, stroke_width=8, stroke_fill=(0, 0, 0))
            x += d.textlength(w, font=f) + gap
    return im


def grade_frame(im, fx):
    """Restrained grade. No vibrance push. Highlights roll off so a flame cannot clip."""
    if fx == "pale":
        hi, lift, sat, contrast = 0.38, 0.0, 0.32, 1.06
        head = 0.18
    elif fx == "soft":
        hi, lift, sat, contrast = 0.55, 0.0, 0.58, 1.02
        head = 0.28
    elif fx == "land":
        # Lift the booster out of the black sky. Roll the flame off before it clips.
        hi, lift, sat, contrast = 0.48, 0.10, 0.46, 1.05
        head = 0.16
    else:
        hi, lift, sat, contrast = 0.72, 0.03, 0.86, 1.04
        head = 0.22
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
    xexpr = shot.get("xexpr")
    if xexpr:
        xexpr = xexpr.replace("FRAME", str(FPS))
        crop = f"crop={w}:{h}:{xexpr}:{y}"
    else:
        crop = f"crop={w}:{h}:{x}:{y}"
    vf = f"{crop},scale={W}:{H}:flags=lanczos,fps={FPS}"
    ss = float(shot["ss"])
    pre = min(1.0, ss)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss - pre:.3f}", "-i", str(CLIPS / shot["file"]),
         "-ss", f"{pre:.3f}", "-t", f"{shot['dur']:.3f}", "-vf", vf, "-an",
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
    d.rectangle((0, 0, int(W * min(1.0, p * 1.4)), 8), fill=YELLOW)
    if kind == "timeline":
        if appear(p, 0.0) > 0:
            draw_text(im, "ONE PAD", 54, 340 + int(40 * (1 - appear(p, 0.0))), DIM, W * 0.8, stroke=0)
        if appear(p, 0.08) > 0:
            dy = int(70 * (1 - appear(p, 0.08)))
            draw_text(im, "FRI 20 NOV", 64, 470 + dy, WHITE, W * 0.86)
            draw_text(im, "20:20 PT", 92, 560 + dy, YELLOW, W * 0.86)
        y = 740
        d.rounded_rectangle((140, y, W - 140, y + 10), radius=5, fill=(40, 48, 64))
        x = 140 + (W - 280) * min(1.0, p * 1.05)
        d.ellipse((x - 18, y - 14, x + 18, y + 22), fill=YELLOW)
        if appear(p, 0.28) > 0:
            dy = int(70 * (1 - appear(p, 0.28)))
            draw_text(im, "SUN 22 NOV", 64, 820 + dy, WHITE, W * 0.86)
            draw_text(im, "04:23 PT", 92, 910 + dy, YELLOW, W * 0.86)
        if appear(p, 0.45) > 0:
            draw_text(im, "SLC-4E  VANDENBERG", 36, 1060, DIM, W * 0.8, stroke=0)
    elif kind == "clock":
        total = 32 * 3600 + 3 * 60 + 21
        # Fast through the count, then hold 32:03:21 so the number can be read.
        shown = int(round(total * min(1.0, p / 0.62) ** 0.40))
        if p > 0.62:
            shown = total
        hh, rem = divmod(shown, 3600)
        mm, ss = divmod(rem, 60)
        if appear(p, 0.0) > 0:
            draw_text(im, "THE GAP", 54, 470 + int(36 * (1 - appear(p, 0.0))), DIM, W * 0.8, stroke=0)
        draw_text(im, f"{hh:02d}:{mm:02d}:{ss:02d}", 108, 640, YELLOW, W * 0.94)
        if appear(p, 0.55) > 0:
            draw_text(im, "ONE PAD", 48, 880, WHITE, W * 0.8)
    elif kind == "bars":
        if appear(p, 0.0) > 0:
            draw_text(im, "THE RECORD", 54, 420 + int(30 * (1 - appear(p, 0.0))), DIM, W * 0.8, stroke=0)
        d = ImageDraw.Draw(im)
        grow45 = min(1.0, max(0.0, p / 0.38))
        grow32 = min(1.0, max(0.0, (p - 0.28) / 0.40))
        d.rounded_rectangle((120, 620, 120 + max(8, int(840 * grow45)), 710), radius=14, fill=(70, 78, 92))
        if grow45 > 0.35:
            draw_text(im, "45 HOURS", 48, 730, WHITE, W * 0.8)
        d.rounded_rectangle((120, 880, 120 + max(8, int(840 * (32 / 45) * grow32)), 970), radius=14, fill=YELLOW)
        if grow32 > 0.35:
            draw_text(im, "32 HOURS", 48, 990, YELLOW, W * 0.8)
    elif kind == "two":
        lines = (
            (0.00, "TWO BOOSTERS", 72, 480, WHITE),
            (0.18, "NOT ONE", 78, 600, YELLOW),
            (0.40, "B1097", 96, 800, YELLOW),
            (0.58, "FLIGHT 14", 64, 940, WHITE),
        )
        for start, text, size, y, fill in lines:
            a = appear(p, start)
            if a <= 0:
                continue
            draw_text(im, text, size, y + int(64 * (1 - a)), fill, W * 0.92)
    return im


def encode_frames(frames_path, dest, nframes):
    run(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", str(frames_path), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "16", str(dest)])


def grade_and_caption(src, dest, cards, hook_until, t0, fx, zoom=None):
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
            im = grade_frame(im, fx)
            cap = ""
            for a, b, text in cards:
                if a - 0.02 <= t < b:
                    cap = text
                    break
            overlay(im, cap, hook_until is not None and t < hook_until)
            outp.write(im.tobytes())
            n += 1
    raw.unlink(missing_ok=True)
    encode_frames(graded, dest, n)
    graded.unlink(missing_ok=True)


def render_graphic(shot, dest, cards, t0):
    frame = W * H * 3
    raw = OUT / "graphic.rgb"
    nframes = int(round(shot["dur"] * FPS))
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
    encode_frames(raw, dest, nframes)
    raw.unlink(missing_ok=True)


def clip_audio(shot, dest):
    if shot["kind"] != "video":
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
             f"anullsrc=r=44100:cl=stereo:d={shot['dur']:.3f}",
             "-c:a", "aac", "-b:a", "64k", str(dest)])
        return
    ss = float(shot["ss"])
    length = float(shot["dur"])
    pre = min(1.0, ss)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss - pre:.3f}", "-i", str(CLIPS / shot["file"]),
         "-ss", f"{pre:.3f}", "-t", f"{length:.3f}",
         "-af", "lowpass=f=240,highpass=f=40,volume=0.35,afade=t=in:d=0.04,afade=t=out:st="
                + f"{max(0.1, length - 0.1):.3f}:d=0.08",
         "-c:a", "aac", "-b:a", "128k", str(dest)])


def write_bed(path, seconds):
    """Original 124 BPM bed. The audible part is midrange, so a phone speaker has something to play.

    Arp and pad sit between 300 Hz and 2 kHz. The clap is a stack of tones from
    1.2 kHz to 3 kHz. A chirp rises into the open and again into the last line.
    A short 700 Hz click marks the beat, because a sub kick does not come out of a phone.
    """
    sr = 44100
    n = int(seconds * sr)
    bpm = 124.0
    beat = 60.0 / bpm
    eighth = beat / 2.0
    notes = (440.0, 523.25, 659.25, 783.99, 880.0, 659.25, 523.25, 392.00)
    pad = (440.0, 523.25, 659.25)
    clap_f = (1200.0, 1600.0, 2000.0, 2500.0, 3000.0)
    samples = []
    rise_phase = 0.0
    pay_phase = 0.0
    for i in range(n):
        t = i / sr
        ph = t % beat
        beat_i = int(t / beat)
        # Click on every beat, in the band a phone reproduces.
        click = 0.0
        if ph < 0.045:
            click = math.sin(2 * math.pi * 720.0 * t) * math.exp(-ph / 0.012)
            click += 0.35 * math.sin(2 * math.pi * 220.0 * t) * math.exp(-ph / 0.03)
        clap = 0.0
        if beat_i % 2 == 1 and ph < 0.08:
            env = math.exp(-ph / 0.015)
            clap = env * sum(math.sin(2 * math.pi * f * t) for f in clap_f) / len(clap_f)
        hp = t % eighth
        hat = 0.0
        if hp < 0.02:
            hat = math.sin(2 * math.pi * 3400.0 * t) * math.exp(-hp / 0.005)
            hat *= 0.7 if int(t / eighth) % 2 else 0.35
        step = int(t / eighth) % len(notes)
        note = notes[step]
        off = t % eighth
        pluck = math.sin(2 * math.pi * note * t) * math.exp(-off / 0.055)
        if note * 2 < 3600:
            pluck += 0.35 * math.sin(2 * math.pi * note * 2 * t) * math.exp(-off / 0.04)
        pad_env = 0.85 + 0.15 * math.sin(2 * math.pi * 0.25 * t)
        pad_s = pad_env * sum(math.sin(2 * math.pi * f * t) for f in pad) / len(pad)
        # Riser into the hook, and again into the final line.
        rise = 0.0
        if t < 1.7:
            u = t / 1.7
            freq = 380.0 * ((2600.0 / 380.0) ** u)
            rise_phase += 2 * math.pi * freq / sr
            rise = math.sin(rise_phase) * (0.15 + 0.85 * u) * 0.9
        pay0 = seconds - 2.6
        if pay0 < t < pay0 + 2.3:
            u = (t - pay0) / 2.3
            freq = 420.0 * ((3200.0 / 420.0) ** u)
            pay_phase += 2 * math.pi * freq / sr
            pay = math.sin(pay_phase) * (0.2 + 0.8 * u) * 0.85
        else:
            pay = 0.0
        s = 0.55 * click + 0.50 * clap + 0.16 * hat + 0.42 * pluck + 0.20 * pad_s + 0.55 * rise + 0.55 * pay
        samples.append(s)
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = 0.92 / peak
    fade = int(0.08 * sr)
    end = int(0.25 * sr)
    for i in range(n):
        g = scale
        if i < fade:
            g *= i / fade
        if i > n - end:
            g *= (n - 1 - i) / end
        samples[i] = max(-1.0, min(1.0, samples[i] * g))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 30000)) for s in samples))


def lufs(path, extra_af=""):
    af = f"{extra_af},ebur128" if extra_af else "ebur128"
    proc = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", af, "-f", "null", "-"],
        capture_output=True, text=True)
    found = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", proc.stderr)
    if not found:
        raise SystemExit(f"no LUFS reading for {path}\n{proc.stderr[-500:]}")
    return float(found[-1])


def build_background():
    """One darkened, blurred pad frame behind every graphic, so the cards are not flat black."""
    global BG
    still = OUT / "pad-bg.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-ss", "752.2", "-i", str(CLIPS / "ussf317-1080.mp4"),
         "-frames:v", "1", "-vf", "crop=506:900:707:0,scale=1080:1920", str(still)])
    im = Image.open(still).convert("RGB")
    im = im.filter(ImageFilter.GaussianBlur(radius=22))
    im = ImageEnhance.Brightness(im).enhance(0.36)
    im = ImageEnhance.Color(im).enhance(0.75)
    BG = im


def audit(path):
    """Every frame: clipped white (all channels >= 250) and near-black (max channel < 22)."""
    raw = OUT / "audit.rgb"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", str(raw)])
    frame = W * H * 3
    step = 4
    worst_clip = (0.0, 0.0)
    worst_black = (0.0, 0.0)
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
                if r < 22 and g < 22 and b < 22:
                    black += 1
            c = clip / seen
            b = black / seen
            t = n / FPS
            if c > worst_clip[0]:
                worst_clip = (c, t)
            if b > worst_black[0]:
                worst_black = (b, t)
            if c > 0.20:
                raise SystemExit(f"frame {t:.2f}s is {c:.1%} clipped white")
            n += 1
    raw.unlink(missing_ok=True)
    print(f"audit frames {n}  worst clip {worst_clip[0]:.1%} at {worst_clip[1]:.2f}s  "
          f"worst black {worst_black[0]:.1%} at {worst_black[1]:.2f}s", flush=True)


def timeline_of():
    alignment = json.loads((HERE / "out" / "alignment.json").read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in alignment["sentences"]}
    alignment = {**alignment, "sentences": [by_id[i] for i in LINES]}
    timeline = []
    t = 0.0
    for i, s in enumerate(alignment["sentences"]):
        length = dur(HERE / "out" / f"{s['id']}.mp3")
        timeline.append({**s, "t0": t, "length": length})
        gap = 0.0 if i == 0 else 0.06
        t += length + gap
    total = timeline[-1]["t0"] + timeline[-1]["length"]
    return alignment, timeline, total


def main():
    for shot in SHOTS:
        if shot["kind"] == "video" and not (CLIPS / shot["file"]).exists():
            raise SystemExit(f"missing {CLIPS / shot['file']}")
    alignment, timeline, total = timeline_of()
    OUT.mkdir(exist_ok=True)
    fixed = sum(s["dur"] for s in SHOTS[:-1])
    SHOTS[-1]["dur"] = round(total - fixed, 3)
    if SHOTS[-1]["dur"] > 3.0:
        # A long loop means the shots before it are short. Lengthen the pad push.
        spare = next(s for s in SHOTS if s["id"] == "push")
        room = round(3.0 - spare["dur"], 3)
        spare["dur"] = round(spare["dur"] + min(room, SHOTS[-1]["dur"] - 2.95), 3)
        fixed = sum(s["dur"] for s in SHOTS[:-1])
        SHOTS[-1]["dur"] = round(total - fixed, 3)
    SHOTS[-1]["ss"] = round(SHOTS[0]["ss"] - SHOTS[-1]["dur"], 3)
    if not 1.2 <= SHOTS[-1]["dur"] <= 3.0:
        raise SystemExit(f"loop length {SHOTS[-1]['dur']} is outside 1.2-3.0s")
    graphic = sum(s["dur"] for s in SHOTS if s["kind"] == "graphic")
    if graphic / total > 0.45:
        raise SystemExit(f"graphics are {graphic / total:.1%} of the runtime")
    build_background()
    for shot in SHOTS:
        if shot["dur"] > 3.0 + 1e-6:
            raise SystemExit(f"{shot['id']} is {shot['dur']}s, longer than 3.0")
    print(f"voice {total:.2f}s  graphics {graphic:.2f}s ({graphic / total:.1%})  loop {SHOTS[-1]['ss']:.2f}+{SHOTS[-1]['dur']:.2f}")

    by_id = {s["id"]: s for s in alignment["sentences"]}
    cards = []
    for m in timeline:
        sent = dict(by_id[m["id"]])
        sent["caption"] = m.get("caption") or sent.get("caption")
        cards += caption_cards(sent, m["t0"])

    segs = []
    t = 0.0
    for shot in SHOTS:
        graded = OUT / f"{shot['id']}.mp4"
        audio = OUT / f"{shot['id']}.m4a"
        print(f"shot {shot['id']} {shot['mission']} {shot['dur']:.2f}s", flush=True)
        if shot["kind"] == "graphic":
            render_graphic(shot, graded, cards, t)
        else:
            plain = OUT / f"{shot['id']}-plain.mp4"
            extract(shot, plain)
            grade_and_caption(plain, graded, cards, SHOTS[0]["dur"] if shot.get("hook") else None, t,
                              shot.get("fx") or "hold", shot.get("zoom"))
            plain.unlink(missing_ok=True)
        clip_audio(shot, audio)
        segs.append({"video": graded, "audio": audio, "t0": t, "length": shot["dur"], "shot": shot})
        t += shot["dur"]

    listing = OUT / "video.txt"
    listing.write_text("".join(f"file '{s['video'].resolve()}'\n" for s in segs), encoding="utf-8")
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

    rumble_inputs, rumble_filters = [], []
    for i, s in enumerate(segs):
        rumble_inputs += ["-i", str(s["audio"])]
        ms = int(round(s["t0"] * 1000))
        rumble_filters.append(f"[{i}:a]adelay={ms}|{ms},apad=pad_dur=2[r{i}]")
    rumble_mix = "".join(f"[r{i}]" for i in range(len(segs))) + f"amix=inputs={len(segs)}:normalize=0:duration=longest[rumble]"
    rumble = OUT / "rumble.m4a"
    run(["ffmpeg", "-y", "-v", "error", *rumble_inputs, "-filter_complex", ";".join(rumble_filters) + ";" + rumble_mix,
         "-map", "[rumble]", "-t", f"{total:.3f}", "-c:a", "aac", "-b:a", "128k", str(rumble)])

    bed_wav = OUT / "bed.wav"
    print("writing bed", flush=True)
    write_bed(bed_wav, total + 0.4)
    bed = OUT / "bed.m4a"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(bed_wav), "-c:a", "aac", "-b:a", "192k", str(bed)])

    band = "highpass=f=300,lowpass=f=4000"
    voice_lufs = lufs(voice)
    bed_band = lufs(bed, band)
    voice_gain = -14.0 - voice_lufs
    # Start the unducked midrange near -16 so the pauses are obviously louder than the ducked bed.
    bed_gain = -16.0 - bed_band
    print(f"voice {voice_lufs:.1f} LUFS gain {voice_gain:+.1f} dB", flush=True)
    print(f"bed 300-4k {bed_band:.1f} LUFS gain {bed_gain:+.1f} dB", flush=True)

    voice_out = OUT / "voice-14.m4a"
    bed_out = OUT / "bed-stem.m4a"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(voice), "-af", f"volume={voice_gain:.2f}dB",
         "-c:a", "aac", "-b:a", "192k", str(voice_out)])

    ducked = OUT / "bed-ducked.m4a"
    ducked_band = None
    for _ in range(3):
        run(["ffmpeg", "-y", "-v", "error", "-i", str(bed),
             "-af", f"volume={bed_gain:.2f}dB,highpass=f=180",
             "-c:a", "aac", "-b:a", "192k", str(bed_out)])
        # Ratio 1.8 is inside the 1.5-2 range. Release is long enough to open between phrases.
        run(["ffmpeg", "-y", "-v", "error", "-i", str(bed_out), "-i", str(voice_out),
             "-filter_complex",
             "[0:a][1:a]sidechaincompress=threshold=0.025:ratio=1.8:attack=12:release=180:makeup=1[d]",
             "-map", "[d]", "-c:a", "aac", "-b:a", "192k", str(ducked)])
        ducked_band = lufs(ducked, band)
        print(f"  ducked 300-4k {ducked_band:.1f} LUFS (bed gain {bed_gain:+.1f} dB)", flush=True)
        if abs(ducked_band - (-22.0)) < 0.8:
            break
        bed_gain += -22.0 - ducked_band

    stem_lufs = lufs(bed_out)
    stem_band = lufs(bed_out, band)
    ducked_lufs = lufs(ducked)

    final = OUT / "spacex-one-pad-32-hours-short-v5.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(voice_out), "-i", str(rumble), "-i", str(ducked),
         "-filter_complex",
         "[1:a]volume=1.0[v];"
         "[2:a]volume=0.10[r];"
         "[3:a]volume=1.0[m];"
         "[v][r][m]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.95:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])
    mix_lufs = lufs(final)
    voice_now = lufs(voice_out)
    print(f"LUFS voice {voice_now:.1f}  music-stem {stem_lufs:.1f}  stem-300-4k {stem_band:.1f}  "
          f"ducked {ducked_lufs:.1f}  ducked-300-4k {ducked_band:.1f}  mix {mix_lufs:.1f}", flush=True)

    thumb_src = OUT / "spacex-one-pad-32-hours-thumb-v2.jpg"
    thumb = OUT / "spacex-one-pad-32-hours-thumb-v5.jpg"
    if thumb_src.exists():
        thumb.write_bytes(thumb_src.read_bytes())

    rows = []
    t = 0.0
    for g in SHOTS:
        rows.append({
            "id": g["id"], "mission": g["mission"], "file": g.get("file", ""),
            "source_ss": g.get("ss"), "video_in": round(t, 3), "video_out": round(t + g["dur"], 3),
            "duration": round(g["dur"], 3), "shows": g["shows"],
        })
        print(f"{t:6.2f}-{t + g['dur']:6.2f}  {g['id']:10} {g['dur']:.2f}s  {g['shows']}", flush=True)
        t += g["dur"]
    audit(final)
    (OUT / "shots-v5.json").write_text(json.dumps({
        "duration": round(total, 3),
        "graphics_s": round(graphic, 3),
        "graphics_share": round(graphic / total, 4),
        "lufs": {
            "voice": voice_now,
            "music_stem": stem_lufs,
            "music_stem_300_4k": stem_band,
            "music_ducked": ducked_lufs,
            "music_ducked_300_4k": ducked_band,
            "mix": mix_lufs,
        },
        "shots": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print("RENDER", final, f"{total:.2f}s")


if __name__ == "__main__":
    main()
