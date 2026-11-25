"""Cut the Texas-register preview Short. Nothing is uploaded or published.

Picture is Tesla's own Austin footage: the Robotaxi account's Cybercab fleet film,
Tesla's Austin Cybercab engineering test, and the unsupervised Austin Robotaxi ride
Tesla quoted. Three cards sit on a blurred Cybercab frame. No shot is longer than
3 seconds. The bed is midrange music only: no whistle, no chirp, no hat.
"""
import json
import math
import re
import struct
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
CLIPS = Path("/tmp/tesla-footage")
OUT = HERE / "render-out"
W, H, FPS = 1080, 1920, 30
FONT = str(HERE.parent / "fonts" / "Inter-Black.otf")
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)
DIM = (186, 196, 210)
RED = (196, 32, 38)
NAVY = (10, 14, 22)

LINES = ("s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8")

# crop is x, y, w, h on the source. w/h is 9:16.
# blur is x, y, w, h in the 1080x1920 frame. lock keeps a shot inside a clean source window.
SHOTS = [
    {"id": "open", "kind": "video", "file": "austin300.mp4", "ss": 25.80, "dur": 2.40,
     "hook": True, "fx": "hold", "zoom": (1.00, 1.04), "crop": (700, 0, 608, 1080),
     "blur": (0, 1020, 1080, 900), "mission": "Robotaxi Austin fleet",
     "credit": "https://x.com/robotaxi/status/2108981691436224816",
     "shows": "Gold Cybercab, overhead, Austin fleet lot. Plate blurred. Hook numbers."},
    {"id": "exit", "kind": "video", "file": "austin300.mp4", "ss": 23.70, "dur": 1.60, "lock": True,
     "fx": "hold", "zoom": (1.02, 1.08), "crop": (656, 0, 608, 1080), "mission": "Robotaxi Austin fleet",
     "credit": "https://x.com/robotaxi/status/2108981691436224816",
     "shows": "Cybercab driving out of the Austin fleet building, rear, large. Cut before the film changes shot."},
    {"id": "bars", "kind": "graphic", "graphic": "bars", "dur": 2.80, "mission": "graphic",
     "shows": "Tesla 1,556 against Waymo 1,405, bars growing."},
    {"id": "road", "kind": "video", "file": "engtest.mp4", "ss": 6.80, "dur": 2.70,
     "fx": "hold", "zoom": (1.00, 1.05), "crop": (762, 0, 396, 704), "mission": "Tesla Austin engineering test",
     "credit": "https://x.com/Tesla/status/2071810353156194719",
     "shows": "Cybercab driving an Austin street. Road and screen. Tesla's film labels a safety monitor."},
    {"id": "plus", "kind": "graphic", "graphic": "plus", "dur": 2.70, "mission": "graphic",
     "shows": "+49 on Tuesday night, 1,507 to 1,556."},
    {"id": "road2", "kind": "video", "file": "engtest.mp4", "ss": 15.40, "dur": 2.60,
     "fx": "hold", "zoom": (1.00, 1.05), "crop": (720, 0, 396, 704), "mission": "Tesla Austin engineering test",
     "credit": "https://x.com/Tesla/status/2071810353156194719",
     "shows": "Same Austin Cybercab test, later on the road, under the Cybercab count."},
    {"id": "split", "kind": "graphic", "graphic": "split", "dur": 2.50, "mission": "graphic",
     "shows": "822 Cybercabs and 734 Model Ys."},
    {"id": "red", "kind": "video", "file": "joe_ext.mp4", "ss": 4.48, "dur": 2.20, "src_dur": 1.12, "lock": True,
     "fx": "hold", "zoom": (1.00, 1.04), "crop": (602, 200, 494, 878), "mission": "Austin Robotaxi ride",
     "credit": "https://x.com/Tesla/status/2014422061687701979",
     "shows": "Red Model Y with Robotaxi on the door, Austin street, before a truck crosses. Tesla quoted this ride."},
    {"id": "doors", "kind": "video", "file": "cab67.mp4", "ss": 1.10, "dur": 1.50, "mission": "Robotaxi Austin fleet",
     "fx": "hold", "zoom": (1.00, 1.04), "crop": (656, 0, 608, 1080),
     "credit": "https://x.com/robotaxi/status/2102222880553787723",
     "shows": "Cybercab 67, Austin fleet, front, daylight. The bumper mark reads Cybercab, not a registration number."},
    {"id": "loop", "kind": "video", "file": "austin300.mp4", "ss": 26.30, "dur": 2.40,
     "fx": "hold", "zoom": (1.00, 1.04), "crop": (1040, 0, 608, 1080),
     "blur": (0, 880, 1080, 1040), "mission": "Robotaxi Austin fleet",
     "credit": "https://x.com/robotaxi/status/2108981691436224816",
     "shows": "Second gold Cybercab in the Austin lot, plates blurred, under the registration caveat."},
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
    while f.size > 36 and d.textlength(text, font=f) > max_w:
        f = font(f.size - 4)
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text, font=f, fill=fill,
           stroke_width=stroke if stroke is not None else max(6, f.size // 14),
           stroke_fill=(0, 0, 0))
    return f.size


def overlay(im, caption, hook):
    if hook:
        draw_text(im, "TESLA LEADS", 64, 150, YELLOW, W * 0.86)
        draw_text(im, "1,556", 168, 250, YELLOW, W * 0.92)
        draw_text(im, "WAYMO  1,405", 64, 450, WHITE, W * 0.86)
    if caption:
        words = caption.split()
        size = 68
        d = ImageDraw.Draw(im)
        max_w = W * 0.86
        while size > 46 and sum(d.textlength(w, font=font(size)) for w in words) + 14 * (len(words) - 1) > max_w:
            size -= 4
        f = font(size)
        gap = 14
        width = sum(d.textlength(w, font=f) for w in words) + gap * (len(words) - 1)
        x = (W - width) / 2
        y = 1460
        for w in words:
            fill = YELLOW if any(ch.isdigit() for ch in w) else WHITE
            d.text((x, y), w, font=f, fill=fill, stroke_width=8, stroke_fill=(0, 0, 0))
            x += d.textlength(w, font=f) + gap
    return im


def grade_frame(im, fx):
    if fx == "lift":
        hi, lift, sat, contrast = 0.78, 0.10, 0.90, 1.04
        head = 0.20
    else:
        hi, lift, sat, contrast = 0.80, 0.08, 0.92, 1.05
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


def blur_box(im, box):
    if not box:
        return im
    x, y, w, h = box
    x = max(0, min(W - 2, int(x)))
    y = max(0, min(H - 2, int(y)))
    w = max(2, min(W - x, int(w)))
    h = max(2, min(H - y, int(h)))
    patch = im.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(radius=28))
    im.paste(patch, (x, y))
    return im


def extract(shot, dest):
    x, y, w, h = shot["crop"]
    src_dur = float(shot.get("src_dur", shot["dur"]))
    nframes = max(1, int(round(float(shot["dur"]) * FPS)))
    factor = nframes / (src_dur * FPS)
    # trim counts source time, so the stretch cannot be clipped by an output -t.
    ss = float(shot["ss"])
    pre = min(1.0, ss)
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
    d.rectangle((0, 0, int(W * min(1.0, p * 1.4)), 10), fill=YELLOW)
    if kind == "bars":
        if appear(p, 0.0) > 0:
            draw_text(im, "TEXAS REGISTER", 48, 430, DIM, W * 0.8, stroke=0)
        grow_t = min(1.0, max(0.0, p / 0.45))
        grow_w = min(1.0, max(0.0, (p - 0.22) / 0.45))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((120, 620, 120 + max(8, int(840 * grow_t)), 720), radius=16, fill=YELLOW)
        if grow_t > 0.4:
            draw_text(im, "TESLA  1,556", 52, 740, YELLOW, W * 0.86)
        d.rounded_rectangle((120, 900, 120 + max(8, int(840 * (1405 / 1556) * grow_w)), 1000), radius=16, fill=(70, 78, 92))
        if grow_w > 0.4:
            draw_text(im, "WAYMO  1,405", 52, 1020, WHITE, W * 0.86)
        if appear(p, 0.62) > 0:
            draw_text(im, "LEADS BY 151", 56, 1160, YELLOW, W * 0.86)
    elif kind == "plus":
        if appear(p, 0.0) > 0:
            draw_text(im, "TUESDAY NIGHT", 48, 480, DIM, W * 0.8, stroke=0)
        if appear(p, 0.08) > 0:
            draw_text(im, "+49", 180, 580, YELLOW, W * 0.9)
        if appear(p, 0.32) > 0:
            draw_text(im, "1,507  →  1,556", 64, 860, WHITE, W * 0.92)
        if appear(p, 0.55) > 0:
            draw_text(im, "TESLA ROBOTAXI LLC", 40, 1000, DIM, W * 0.86, stroke=0)
    elif kind == "split":
        lines = (
            (0.00, "822", 150, 520, YELLOW),
            (0.12, "CYBERCABS", 56, 700, WHITE),
            (0.32, "734", 150, 860, YELLOW),
            (0.44, "MODEL Ys", 56, 1040, WHITE),
        )
        for start, text, size, y, fill in lines:
            a = appear(p, start)
            if a <= 0:
                continue
            draw_text(im, text, size, y + int(48 * (1 - a)), fill, W * 0.92)
        if appear(p, 0.62) > 0:
            draw_text(im, "OF 1,556 REGISTERED", 40, 1180, DIM, W * 0.86, stroke=0)
    return im


def encode_frames(frames_path, dest):
    run(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", str(frames_path), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "16", str(dest)])


def paint_video(src, dest, cards, hook, t0, fx, zoom, blur):
    raw = OUT / "raw.rgb"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", str(raw)])
    frame = W * H * 3
    nframes = raw.stat().st_size // frame
    graded = OUT / "graded.rgb"
    # Scale a source-crop blur box up to the 1080x1920 frame. The crop was scaled to fill.
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
            if blur:
                # blur was measured on the unscaled crop; the crop is scaled to the full frame.
                im = blur_box(im, blur_scaled(blur))
            cap = ""
            for a, b, text in cards:
                if a - 0.02 <= t < b:
                    cap = text
                    break
            overlay(im, cap, hook and t < (hook if isinstance(hook, float) else 2.4))
            outp.write(im.tobytes())
            n += 1
    raw.unlink(missing_ok=True)
    encode_frames(graded, dest)
    graded.unlink(missing_ok=True)


def blur_scaled(box):
    """Source-crop blur box, mapped onto the full 1080x1920 frame.

    The crops are already 9:16, so the scale is uniform.
    """
    return box  # boxes below are already in output pixels


def render_graphic(shot, dest, cards, t0):
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
    encode_frames(raw, dest)
    raw.unlink(missing_ok=True)


def write_bed(path, seconds):
    """Midrange bed only. No chirp, no hat, no noise, nothing above the arp's low harmonics."""
    sr = 44100
    n = int(seconds * sr)
    bpm = 112.0
    beat = 60.0 / bpm
    eighth = beat / 2.0
    notes = (392.00, 440.0, 523.25, 659.25, 523.25, 440.0, 392.00, 349.23)
    pad = (196.00, 246.94, 293.66)
    samples = []
    for i in range(n):
        t = i / sr
        ph = t % beat
        click = 0.0
        if ph < 0.04:
            click = math.sin(2 * math.pi * 180.0 * t) * math.exp(-ph / 0.02)
        step = int(t / eighth) % len(notes)
        note = notes[step]
        off = t % eighth
        pluck = math.sin(2 * math.pi * note * t) * math.exp(-off / 0.07)
        pluck += 0.25 * math.sin(2 * math.pi * note * 2 * t) * math.exp(-off / 0.05)
        pad_env = 0.88 + 0.12 * math.sin(2 * math.pi * 0.22 * t)
        pad_s = pad_env * sum(math.sin(2 * math.pi * f * t) for f in pad) / len(pad)
        s = 0.35 * click + 0.55 * pluck + 0.28 * pad_s
        samples.append(s)
    peak = max(1e-6, max(abs(s) for s in samples))
    scale = 0.9 / peak
    fade = int(0.12 * sr)
    end = int(0.30 * sr)
    for i in range(n):
        g = scale
        if i < fade:
            g *= i / fade
        if i > n - end:
            g *= max(0.0, (n - 1 - i) / end)
        samples[i] = max(-1.0, min(1.0, samples[i] * g))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 28000)) for s in samples))


def lufs(path, extra_af=""):
    af = f"{extra_af},ebur128" if extra_af else "ebur128"
    proc = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", af, "-f", "null", "-"],
        capture_output=True, text=True)
    found = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", proc.stderr)
    if not found:
        raise SystemExit(f"no LUFS reading for {path}\n{proc.stderr[-400:]}")
    return float(found[-1])


def build_background():
    global BG
    still = OUT / "bg.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-ss", "26.0", "-i", str(CLIPS / "austin300.mp4"),
         "-frames:v", "1", "-vf", "crop=608:1080:748:0,scale=1080:1920", str(still)])
    im = Image.open(still).convert("RGB")
    im = im.filter(ImageFilter.GaussianBlur(radius=26))
    im = ImageEnhance.Brightness(im).enhance(0.55)
    im = ImageEnhance.Color(im).enhance(0.9)
    # Keep the card background out of the near-black range.
    im = im.point(lambda i: max(i, 32))
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
                if max(r, g, b) < 22:
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
            if c > 0.08:
                raise SystemExit(f"frame {t:.2f}s is {c:.1%} clipped white")
            if b > 0.12:
                raise SystemExit(f"frame {t:.2f}s is {b:.1%} near-black")
            n += 1
    raw.unlink(missing_ok=True)
    print(f"audit frames {n}  worst clip {worst_clip[0]:.1%} at {worst_clip[1]:.2f}s  "
          f"worst black {worst_black[0]:.1%} at {worst_black[1]:.2f}s", flush=True)
    return notes, worst_clip, worst_black


def timeline_of():
    alignment = json.loads((HERE / "out" / "alignment.json").read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in alignment["sentences"]}
    alignment = {**alignment, "sentences": [by_id[i] for i in LINES]}
    timeline = []
    t = 0.0
    for i, s in enumerate(alignment["sentences"]):
        length = dur(HERE / "out" / f"{s['id']}.mp3")
        timeline.append({**s, "t0": t, "length": length})
        gap = 0.0 if i == 0 else 0.07
        t += length + gap
    total = timeline[-1]["t0"] + timeline[-1]["length"]
    return alignment, timeline, total


def fit_duration(total):
    """Lengthen unlocked shots up to 3s, then give the rest to the last shot."""
    fixed = SHOTS[:-1]
    base = sum(s["dur"] for s in fixed)
    loop = total - base
    if loop > 3.0:
        extra = loop - 3.0
        for s in fixed:
            if s.get("lock"):
                continue
            room = round(3.0 - s["dur"], 3)
            take = min(room, extra)
            if take > 0:
                s["dur"] = round(s["dur"] + take, 3)
                extra = round(extra - take, 3)
            if extra <= 0.02:
                break
        base = sum(s["dur"] for s in fixed)
        loop = total - base
    SHOTS[-1]["dur"] = round(loop, 3)
    if not 1.2 <= SHOTS[-1]["dur"] <= 3.0:
        raise SystemExit(f"loop length {SHOTS[-1]['dur']} is outside 1.2-3.0 (voice {total:.2f}s)")
    for s in SHOTS:
        if s["dur"] > 3.0 + 1e-6:
            raise SystemExit(f"{s['id']} is {s['dur']}s")


def main():
    for shot in SHOTS:
        if shot["kind"] == "video" and not (CLIPS / shot["file"]).exists():
            raise SystemExit(f"missing {CLIPS / shot['file']}")
    alignment, timeline, total = timeline_of()
    if not 24.0 <= total <= 36.0:
        raise SystemExit(f"voice length {total:.2f}s is outside 24-36s")
    OUT.mkdir(exist_ok=True)
    fit_duration(total)
    graphic = sum(s["dur"] for s in SHOTS if s["kind"] == "graphic")
    if graphic / total > 0.45:
        raise SystemExit(f"graphics are {graphic / total:.1%} of the runtime")
    print(f"voice {total:.2f}s  graphics {graphic:.2f}s ({graphic / total:.1%})", flush=True)
    build_background()

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
        print(f"shot {shot['id']} {shot['dur']:.2f}s", flush=True)
        if shot["kind"] == "graphic":
            render_graphic(shot, graded, cards, t)
        else:
            plain = OUT / f"{shot['id']}-plain.mp4"
            extract(shot, plain)
            # Map a source-crop blur into output pixels. Crop is scaled uniformly to WxH.
            blur = shot.get("blur")
            paint_video(plain, graded, cards, shot["dur"] if shot.get("hook") else None, t,
                        shot.get("fx") or "hold", shot.get("zoom"), blur)
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

    bed_wav = OUT / "bed.wav"
    write_bed(bed_wav, total + 0.4)
    bed = OUT / "bed.m4a"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(bed_wav), "-af", "lowpass=f=2800",
         "-c:a", "aac", "-b:a", "192k", str(bed)])

    voice_lufs = lufs(voice)
    bed_lufs = lufs(bed)
    voice_gain = -13.0 - voice_lufs
    bed_gain = -22.0 - bed_lufs
    print(f"voice {voice_lufs:.1f} LUFS gain {voice_gain:+.1f} dB", flush=True)
    print(f"bed {bed_lufs:.1f} LUFS gain {bed_gain:+.1f} dB", flush=True)

    final = OUT / "tesla-passed-waymo-texas-short.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(voice), "-i", str(bed),
         "-filter_complex",
         f"[1:a]volume={voice_gain:.2f}dB[v];"
         f"[2:a]volume={bed_gain:.2f}dB[m];"
         "[v][m]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])
    mix = lufs(final)
    # Whistles live in the bed, not in speech. Measure the bed after the lowpass.
    hi = lufs(bed, "highpass=f=4000")
    print(f"LUFS mix {mix:.1f}  bed above-4kHz {hi:.1f}", flush=True)
    if hi > -45.0:
        raise SystemExit(f"bed high band {hi:.1f} LUFS is loud enough to be a whistle or chirp")

    thumb = OUT / "tesla-passed-waymo-texas-thumb.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(thumb)])

    rows = []
    t = 0.0
    for g in SHOTS:
        rows.append({
            "id": g["id"], "mission": g["mission"], "file": g.get("file", ""),
            "source_ss": g.get("ss"), "video_in": round(t, 3), "video_out": round(t + g["dur"], 3),
            "duration": round(g["dur"], 3), "shows": g["shows"], "credit": g.get("credit", ""),
        })
        print(f"{t:6.2f}-{t + g['dur']:6.2f}  {g['id']:8} {g['dur']:.2f}s  {g['shows']}", flush=True)
        t += g["dur"]
    notes, worst_clip, worst_black = audit(final)
    (OUT / "shots.json").write_text(json.dumps({
        "duration": round(total, 3),
        "graphics_s": round(graphic, 3),
        "graphics_share": round(graphic / total, 4),
        "lufs": {"mix": mix, "voice_raw": voice_lufs, "bed_raw": bed_lufs, "bed_above_4khz": hi,
                 "voice_gain_db": round(voice_gain, 2), "bed_gain_db": round(bed_gain, 2)},
        "worst_clip": {"share": worst_clip[0], "t": worst_clip[1]},
        "worst_black": {"share": worst_black[0], "t": worst_black[1]},
        "per_second": notes,
        "shots": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print("RENDER", final, f"{total:.2f}s")


if __name__ == "__main__":
    main()
