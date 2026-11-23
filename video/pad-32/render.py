"""Cut the pad-turnaround preview Short, version 2. Nothing is uploaded or published.

Picture is the official SpaceX webcast of USSF-317 and of NROL-136, both from pad 4E.
Voice is the Noah files in out/. The grade is video/vivid.py.

v1 opened on NROL-136 at 843 s (T+5). That is a Falcon 9, but the tight crop sat in the
engine glare and on the strongback as it fell away, and the grade made that lattice read
as a Super Heavy hot-staging ring. v2 opens earlier, on the whole stack, and no shot runs
longer than about 3.5 s. The onboard landing view is one 3.4 s shot with the highlights
pulled down. The music bed is original (written in this file), so it is not a Content ID
track, and it is sidechained under the voice.
"""
import json
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import vivid  # noqa: E402

CLIPS = Path("/tmp/pad32")
OUT = HERE / "render-out"
W, H, FPS = 1080, 1920, 30
FONT = str(HERE.parent / "fonts" / "Inter-Black.otf")
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)

# crop is x, y, w, h on the 1920x1080 webcast, already 9:16, telemetry left outside the frame.
# dur is the picture length. The last shot is trimmed so the picture matches the voice.
SHOTS = [
    {"id": "open", "file": "ussf317-1080.mp4", "ss": 757.15, "dur": 3.45, "hook": True,
     "crop": (730, 0, 506, 900), "mission": "USSF-317",
     "shows": "Pad camera, SLC-4E, ignition. Full Falcon 9: fairing, black interstage, strongback. About T-1 to T+2."},
    {"id": "rise", "file": "ussf317-1080.mp4", "ss": 760.35, "dur": 3.30,
     "crop": (690, 0, 506, 900), "mission": "USSF-317",
     "shows": "Same pad camera as the rocket leaves the tower. Friday night liftoff."},
    {"id": "sunday", "file": "nrol136-1080.mp4", "ss": 840.80, "dur": 3.40,
     "crop": (750, 0, 506, 900), "mission": "NROL-136",
     "shows": "Pad camera, SLC-4E, Sunday liftoff. Full Falcon 9 beside the strongback, coastal berm."},
    {"id": "track", "file": "nrol136-1080.mp4", "ss": 851.90, "dur": 3.30,
     "crop": (760, 50, 439, 780), "mission": "NROL-136",
     "shows": "Ground tracking of the climb, one flame streak. Telemetry cropped off."},
    {"id": "sep", "file": "ussf317-1080.mp4", "ss": 869.20, "dur": 3.40,
     "crop": (900, 0, 506, 900), "mission": "USSF-317",
     "shows": "Stage separation. The single Merlin Vacuum bell, from below."},
    {"id": "coast", "file": "ussf317-1080.mp4", "ss": 888.40, "dur": 3.30,
     "crop": (720, 20, 484, 860), "mission": "USSF-317",
     "shows": "Booster camera looking out at cloud and the coast. Not the engine glare."},
    {"id": "return", "file": "nrol136-1080.mp4", "ss": 888.00, "dur": 3.40,
     "crop": (760, 50, 439, 780), "mission": "NROL-136",
     "shows": "Ground tracking later in the climb. One flame, held in the middle of the frame."},
    {"id": "fins", "file": "nrol136-1080.mp4", "ss": 1291.20, "dur": 3.40, "fx": "deglare",
     "crop": (600, 0, 461, 820), "mission": "NROL-136",
     "shows": "Onboard landing view, one grid fin, gamma pulled down so the engine bloom does not wash the frame. 3.4 seconds."},
    {"id": "lz", "file": "nrol136-1080.mp4", "ss": 1296.40, "dur": 3.50,
     "crop": (1170, 190, 360, 640), "mission": "NROL-136",
     "shows": "Landing Zone 4 camera only (the right panel of the split). Legs and one flame, at Vandenberg."},
    {"id": "entry", "file": "ussf317-1080.mp4", "ss": 896.20, "dur": 3.40,
     "crop": (790, 0, 439, 780), "mission": "USSF-317",
     "shows": "Entry burn. The engine cluster against black sky. Telemetry cropped off."},
    {"id": "stack", "file": "nrol136-1080.mp4", "ss": 833.90, "dur": 3.20,
     "crop": (750, 0, 506, 900), "mission": "NROL-136",
     "shows": "The second Falcon 9 still on SLC-4E, full stack and strongback, just before engine start."},
    {"id": "loop", "file": "ussf317-1080.mp4", "ss": 754.79, "dur": 2.36,
     "crop": (730, 0, 506, 900), "mission": "USSF-317",
     "shows": "The same pad camera in the seconds before ignition, so the loop lands on the engine start."},
]


def run(cmd):
    subprocess.run(cmd, check=True)


def dur(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def font(size):
    from PIL import ImageFont
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


def draw_text(base, text, size, y, fill, max_w):
    d = ImageDraw.Draw(base)
    f = font(size)
    while f.size > 48 and d.textlength(text, font=f) > max_w:
        f = font(f.size - 4)
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text, font=f, fill=fill, stroke_width=max(8, f.size // 10), stroke_fill=(0, 0, 0))


def overlay(im, caption, hook):
    # Hook sits below the top UI. Captions stay in the middle band, clear of the
    # right-hand buttons and the bottom description.
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


def extract(shot, dest):
    x, y, w, h = shot["crop"]
    fx = shot.get("fx")
    extra = ""
    if fx == "deglare":
        # Ease the engine bloom without flattening the whole frame to grey.
        extra = ",eq=gamma=0.82:contrast=1.12:saturation=0.85"
    elif fx == "lift":
        extra = ",eq=gamma=1.12:brightness=0.02"
    vf = f"crop={w}:{h}:{x}:{y}{extra},scale={W}:{H}:flags=lanczos,fps={FPS},unsharp=3:3:0.4"
    # Accurate seek: keyframe seek, then a short decode to the exact time.
    ss = float(shot["ss"])
    pre = min(1.0, ss)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss - pre:.3f}", "-i", str(CLIPS / shot["file"]),
         "-ss", f"{pre:.3f}", "-t", f"{shot['dur']:.3f}", "-vf", vf, "-an",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(dest)])


def grade_and_caption(src, dest, cards, hook, t0):
    raw = OUT / "raw.rgb"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", str(raw)])
    frame = W * H * 3
    graded = OUT / "graded.rgb"
    with raw.open("rb") as inp, graded.open("wb") as outp:
        n = 0
        while True:
            buf = inp.read(frame)
            if len(buf) < frame:
                break
            t = t0 + n / FPS
            im = Image.frombytes("RGB", (W, H), buf)
            im = vivid.grade(im)
            cap = ""
            for a, b, text in cards:
                if a - 0.02 <= t < b:
                    cap = text
                    break
            overlay(im, cap, hook and t < 3.45)
            outp.write(im.tobytes())
            n += 1
    raw.unlink(missing_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", str(graded), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "16", str(dest)])
    graded.unlink(missing_ok=True)


def clip_audio(shot, dest):
    ss = float(shot["ss"])
    length = float(shot["dur"])
    pre = min(1.0, ss)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss - pre:.3f}", "-i", str(CLIPS / shot["file"]),
         "-ss", f"{pre:.3f}", "-t", f"{length:.3f}",
         "-af", "lowpass=f=240,highpass=f=40,volume=0.45,afade=t=in:d=0.04,afade=t=out:st="
                + f"{max(0.1, length - 0.1):.3f}:d=0.08",
         "-c:a", "aac", "-b:a", "128k", str(dest)])


def write_bed(path, seconds):
    """Original 108 BPM bed written for this Short.

    It is not taken from a music library, so it is not registered with Content ID.
    The channel owns it and it needs no royalty. Am, F, C, G under a kick and a hat.
    """
    sr = 44100
    n = int(seconds * sr)
    bpm = 108.0
    beat = 60.0 / bpm
    # One chord per bar. Roots are an octave down for the bass.
    chords = (
        (110.00, 130.81, 164.81),
        (87.31, 110.00, 130.81),
        (130.81, 164.81, 196.00),
        (98.00, 123.47, 146.83),
    )
    samples = []
    for i in range(n):
        t = i / sr
        chord = chords[int(t / (beat * 4)) % 4]
        ph = t % beat
        k = 0.0
        if ph < 0.15:
            freq = 95.0 - 55.0 * (ph / 0.15)
            k = math.sin(2 * math.pi * freq * t) * math.exp(-ph / 0.038)
        half = beat / 2.0
        hp = t % half
        hat = 0.0
        if hp < 0.016 and int(t / half) % 2 == 1:
            noise = (((i * 1103515245 + 12345) & 0x7fffffff) / 2147483647.0) - 0.5
            hat = noise * math.exp(-hp / 0.005) * 0.45
        bph = t % (beat * 2)
        bass = math.sin(2 * math.pi * (chord[0] / 2.0) * t) * math.exp(-min(bph, 0.4) / 0.16) * 0.5
        pad = sum(math.sin(2 * math.pi * f * t) for f in chord) * 0.035
        s = (0.72 * k + bass + pad + hat) * 0.48
        samples.append(max(-1.0, min(1.0, s)))
    # Fade the ends so the loop into the voice is not a click.
    fade = int(0.25 * sr)
    for i in range(fade):
        g = i / fade
        samples[i] *= g
        samples[-1 - i] *= g
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(s * 28000)) for s in samples))


def timeline_of():
    alignment = json.loads((HERE / "out" / "alignment.json").read_text(encoding="utf-8"))
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
        if not (CLIPS / shot["file"]).exists():
            raise SystemExit(f"missing {CLIPS / shot['file']}")
    alignment, timeline, total = timeline_of()
    OUT.mkdir(exist_ok=True)
    # Fit the picture to the voice. The loop shot takes whatever is left.
    fixed = sum(s["dur"] for s in SHOTS[:-1])
    SHOTS[-1]["dur"] = round(total - fixed, 3)
    SHOTS[-1]["ss"] = round(SHOTS[0]["ss"] - SHOTS[-1]["dur"], 3)
    if SHOTS[-1]["dur"] < 1.2 or SHOTS[-1]["dur"] > 4.0:
        raise SystemExit(f"loop length {SHOTS[-1]['dur']} is outside 1.2-4.0s")
    print(f"voice {total:.2f}s  loop {SHOTS[-1]['ss']:.2f}+{SHOTS[-1]['dur']:.2f}")

    by_id = {s["id"]: s for s in alignment["sentences"]}
    cards = []
    for m in timeline:
        sent = dict(by_id[m["id"]])
        sent["caption"] = m.get("caption") or sent.get("caption")
        cards += caption_cards(sent, m["t0"])

    segs = []
    t = 0.0
    for shot in SHOTS:
        plain = OUT / f"{shot['id']}-plain.mp4"
        graded = OUT / f"{shot['id']}.mp4"
        audio = OUT / f"{shot['id']}.m4a"
        print(f"shot {shot['id']} {shot['mission']} {shot['ss']:.2f}s for {shot['dur']:.2f}s")
        extract(shot, plain)
        run(["ffmpeg", "-y", "-v", "error", "-i", str(plain), "-frames:v", "1", "-q:v", "3",
             str(OUT / f"{shot['id']}-first.jpg")])
        grade_and_caption(plain, graded, cards, bool(shot.get("hook")), t)
        clip_audio(shot, audio)
        plain.unlink(missing_ok=True)
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
    write_bed(bed_wav, total + 0.3)
    bed = OUT / "bed.m4a"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(bed_wav), "-c:a", "aac", "-b:a", "160k", str(bed)])

    final = OUT / "spacex-one-pad-32-hours-short-v2.mp4"
    # Voice leads. Rumble stays low. The bed is sidechained to the voice so it ducks on every word.
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(voice), "-i", str(rumble), "-i", str(bed),
         "-filter_complex",
         "[1:a]asplit=2[vo][sc];"
         "[3:a]volume=0.40,highpass=f=70[bed];"
         "[bed][sc]sidechaincompress=threshold=0.02:ratio=8:attack=12:release=280:makeup=1.0[ducked];"
         "[vo]volume=1.0[v];"
         "[2:a]volume=0.26[r];"
         "[v][r][ducked]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.89:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])

    thumb = OUT / "spacex-one-pad-32-hours-thumb-v2.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-ss", "0.90", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(thumb)])

    rows = []
    for s in segs:
        g = s["shot"]
        rows.append({
            "id": g["id"], "mission": g["mission"], "file": g["file"], "source_ss": g["ss"],
            "video_t0": round(s["t0"], 3), "duration": round(s["length"], 3), "shows": g["shows"],
            "crop": list(g["crop"]), "fx": g.get("fx") or "",
        })
    (OUT / "shots-v2.json").write_text(
        json.dumps({"duration": round(total, 3), "shots": rows}, indent=2) + "\n", encoding="utf-8")
    print("RENDER", final, f"{total:.2f}s")


if __name__ == "__main__":
    main()
