"""Cut the pad-turnaround preview Short, version 3. Nothing is uploaded or published.

Picture is the official SpaceX webcast of USSF-317 and of NROL-136, both from pad 4E.
Voice is the Noah files in out/.

v3 drops the shots a review read as a Super Heavy cluster or a blown-out fireball
(the Merlin close-up and the entry-burn engine flower) and the booster cloud camera.
Every shot is 3.5 s or shorter, and two similar angles are not left back to back.
The grid-fin shots crush the highlights so clipped white stays under 20 percent.
The bed is original, written in this file, and sidechained under the voice.
"""
import json
import math
import re
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
# crop is x, y, w, h on the 1920x1080 webcast. w/h is 9:16. Telemetry stays outside the frame.
# No shot is longer than 3.5 s, and the loop shot is rewritten to fill the voice.
SHOTS = [
    {"id": "open", "file": "ussf317-1080.mp4", "ss": 757.15, "dur": 2.55, "hook": True,
     "crop": (730, 0, 506, 900), "mission": "USSF-317",
     "shows": "Pad camera, SLC-4E. Full Falcon 9, fairing, black interstage, strongback. Cut while the stack is still readable."},
    {"id": "streak", "file": "ussf317-1080.mp4", "ss": 862.00, "dur": 2.90,
     "crop": (707, 0, 506, 900), "mission": "USSF-317",
     "shows": "One distant plume on a black sky, before the camera cuts to the engine close-up."},
    {"id": "sunday", "file": "nrol136-1080.mp4", "ss": 840.15, "dur": 3.40,
     "crop": (750, 0, 506, 900), "mission": "NROL-136",
     "shows": "Sunday liftoff. Full Falcon 9 beside the strongback, coastal pad."},
    {"id": "track", "file": "nrol136-1080.mp4", "ss": 851.90, "dur": 3.30,
     "crop": (760, 50, 439, 780), "mission": "NROL-136",
     "shows": "Ground tracking. One flame, telemetry cropped off."},
    {"id": "stack", "file": "nrol136-1080.mp4", "ss": 832.80, "dur": 3.40,
     "crop": (750, 0, 506, 900), "mission": "NROL-136",
     "shows": "The second Falcon 9 on SLC-4E, full stack, before engine start. The Florida line is captioned over this."},
    {"id": "entry", "file": "nrol136-1080.mp4", "ss": 1283.05, "dur": 1.75,
     "crop": (0, 140, 400, 711), "xexpr": "max(0\\,210-120*n/FRAME)", "mission": "NROL-136",
     "shows": "Entry burn from the ground. The booster, its grid fins and one plume, followed as it drifts left."},
    {"id": "track2", "file": "nrol136-1080.mp4", "ss": 888.00, "dur": 3.05,
     "crop": (760, 50, 439, 780), "mission": "NROL-136",
     "shows": "The same climb later. One flame, still in the middle of the frame."},
    {"id": "fins", "file": "nrol136-1080.mp4", "ss": 1290.85, "dur": 2.00, "fx": "crush",
     "crop": (430, 0, 461, 820), "mission": "NROL-136",
     "shows": "One grid fin. Highlights crushed so the lattice stays visible and clipped white stays under 20 percent."},
    {"id": "wait", "file": "nrol136-1080.mp4", "ss": 836.20, "dur": 3.20,
     "crop": (750, 0, 506, 900), "mission": "NROL-136",
     "shows": "Falcon 9 on the pad, venting, stack still whole."},
    {"id": "early", "file": "nrol136-1080.mp4", "ss": 1278.90, "dur": 2.00, "fx": "crush",
     "crop": (430, 0, 461, 820), "mission": "NROL-136",
     "shows": "The same grid fin a few seconds earlier, also with the highlights crushed."},
    {"id": "track3", "file": "nrol136-1080.mp4", "ss": 855.35, "dur": 2.90,
     "crop": (760, 50, 439, 780), "mission": "NROL-136",
     "shows": "Ground tracking between the two pad views. One flame."},
    {"id": "pad2", "file": "ussf317-1080.mp4", "ss": 749.40, "dur": 3.40,
     "crop": (730, 0, 506, 900), "mission": "USSF-317",
     "shows": "Friday night stack on SLC-4E, engines not yet at full thrust. Clean, sharp."},
    {"id": "lz", "file": "nrol136-1080.mp4", "ss": 1296.45, "dur": 2.40,
     "crop": (1170, 190, 360, 640), "mission": "NROL-136",
     "shows": "Landing Zone 4 only. Booster, legs and one flame, while the vehicle is still readable."},
    {"id": "loop", "file": "ussf317-1080.mp4", "ss": 754.19, "dur": 2.96,
     "crop": (730, 0, 506, 900), "mission": "USSF-317",
     "shows": "The opening camera in the seconds before ignition, so the cut back continues into engine start."},
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


def crush_highlights(im):
    """Pull the top of the range down so a blown frame cannot stay clipped white.

    The curve tops out near 200, so a pixel cannot land on 250 or above.
    """
    lut = []
    for i in range(256):
        x = i / 255.0
        if x < 0.55:
            y = x * 0.85
        else:
            t = (x - 0.55) / 0.45
            y = 0.47 + 0.30 * (t ** 0.55)
        lut.append(max(0, min(255, int(round(y * 255)))))
    return im.point(lut * 3)


def clipped_white(im):
    """Share of pixels with all three channels at 250 or above. Sampled 1 in 4."""
    data = im.tobytes()
    n = white = 0
    for i in range(0, len(data) - 2, 12):
        r, g, b = data[i], data[i + 1], data[i + 2]
        n += 1
        if r >= 250 and g >= 250 and b >= 250:
            white += 1
    return white / n if n else 0.0


def extract(shot, dest):
    x, y, w, h = shot["crop"]
    xexpr = shot.get("xexpr")
    if xexpr:
        xexpr = xexpr.replace("FRAME", str(FPS))
        crop = f"crop={w}:{h}:{xexpr}:{y}"
    else:
        crop = f"crop={w}:{h}:{x}:{y}"
    sharp = "" if shot.get("fx") == "crush" else ",unsharp=3:3:0.4"
    vf = f"{crop},scale={W}:{H}:flags=lanczos,fps={FPS}{sharp}"
    ss = float(shot["ss"])
    pre = min(1.0, ss)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss - pre:.3f}", "-i", str(CLIPS / shot["file"]),
         "-ss", f"{pre:.3f}", "-t", f"{shot['dur']:.3f}", "-vf", vf, "-an",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(dest)])


def grade_and_caption(src, dest, cards, hook_until, t0, crush=False):
    raw = OUT / "raw.rgb"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", str(raw)])
    frame = W * H * 3
    graded = OUT / "graded.rgb"
    hottest = 0.0
    with raw.open("rb") as inp, graded.open("wb") as outp:
        n = 0
        while True:
            buf = inp.read(frame)
            if len(buf) < frame:
                break
            t = t0 + n / FPS
            im = Image.frombytes("RGB", (W, H), buf)
            if crush:
                im = crush_highlights(im)
                hottest = max(hottest, clipped_white(im))
            else:
                im = vivid.grade(im)
            cap = ""
            for a, b, text in cards:
                if a - 0.02 <= t < b:
                    cap = text
                    break
            overlay(im, cap, hook_until is not None and t < hook_until)
            outp.write(im.tobytes())
            n += 1
    raw.unlink(missing_ok=True)
    if crush and hottest > 0.20:
        raise SystemExit(f"clipped white {hottest:.1%} exceeds 20% in a crushed shot")
    run(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", str(graded), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "16", str(dest)])
    graded.unlink(missing_ok=True)
    return hottest


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
    """Original 118 BPM bed written for this Short.

    Kick on every beat, a clap on 2 and 4, hats on the eighths, and a bass note
    that holds through the bar. Not a library track, so it is not in Content ID.
    """
    sr = 44100
    n = int(seconds * sr)
    bpm = 118.0
    beat = 60.0 / bpm
    roots = (55.0, 43.65, 65.41, 49.0)  # A, F, C, G
    samples = []
    for i in range(n):
        t = i / sr
        bar = int(t / (beat * 4)) % 4
        root = roots[bar]
        ph = t % beat
        beat_i = int(t / beat)
        k = 0.0
        if ph < 0.12:
            freq = 140.0 - 100.0 * (ph / 0.12)
            k = math.sin(2 * math.pi * freq * t) * math.exp(-ph / 0.028)
        clap = 0.0
        if beat_i % 2 == 1 and ph < 0.045:
            noise = (((i * 1103515245 + 12345) & 0x7fffffff) / 2147483647.0) - 0.5
            clap = noise * math.exp(-ph / 0.012)
        eighth = beat / 2.0
        hp = t % eighth
        hat = 0.0
        if hp < 0.012:
            noise = (((i * 1664525 + 1013904223) & 0x7fffffff) / 2147483647.0) - 0.5
            hat = noise * math.exp(-hp / 0.004) * (0.55 if int(t / eighth) % 2 else 0.28)
        # Bass holds, so the bed is not just a click between silences.
        bass_ph = t % (beat * 2)
        bass_env = 0.55 + 0.45 * math.exp(-bass_ph / 0.22)
        bass = math.sin(2 * math.pi * root * t) * bass_env
        bass += 0.35 * math.sin(2 * math.pi * root * 2 * t) * bass_env
        pluck = 0.0
        off = (t + beat / 2) % beat
        if off < 0.08:
            pluck = math.sin(2 * math.pi * (root * 4) * t) * math.exp(-off / 0.03)
        s = 0.85 * k + 0.42 * clap + 0.22 * hat + 0.34 * bass + 0.16 * pluck
        samples.append(max(-1.0, min(1.0, s * 0.72)))
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


def lufs(path):
    proc = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True)
    found = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", proc.stderr)
    if not found:
        raise SystemExit(f"no LUFS reading for {path}\n{proc.stderr[-400:]}")
    return float(found[-1])


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
    if SHOTS[-1]["dur"] < 1.2 or SHOTS[-1]["dur"] > 3.50:
        raise SystemExit(f"loop length {SHOTS[-1]['dur']} is outside 1.2-3.5s")
    for shot in SHOTS:
        if shot["dur"] > 3.50:
            raise SystemExit(f"{shot['id']} is {shot['dur']}s, longer than 3.5")
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
        print(f"shot {shot['id']} {shot['mission']} {shot['ss']:.2f}s for {shot['dur']:.2f}s", flush=True)
        extract(shot, plain)
        run(["ffmpeg", "-y", "-v", "error", "-i", str(plain), "-frames:v", "1", "-q:v", "3",
             str(OUT / f"{shot['id']}-first.jpg")])
        hot = grade_and_caption(plain, graded, cards, SHOTS[0]["dur"] if shot.get("hook") else None, t,
                                crush=shot.get("fx") == "crush")
        if shot.get("fx") == "crush":
            print(f"  clipped white max {hot:.1%}", flush=True)
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
    run(["ffmpeg", "-y", "-v", "error", "-i", str(bed_wav), "-c:a", "aac", "-b:a", "192k", str(bed)])

    voice_lufs = lufs(voice)
    bed_lufs = lufs(bed)
    # Voice sits near -14 LUFS. The unducked bed sits near -18 so the beat is obvious,
    # and the sidechain pulls it toward -24 while the voice is speaking.
    voice_gain = -14.0 - voice_lufs
    bed_gain = -18.0 - bed_lufs
    print(f"voice {voice_lufs:.1f} LUFS gain {voice_gain:+.1f} dB", flush=True)
    print(f"bed   {bed_lufs:.1f} LUFS gain {bed_gain:+.1f} dB", flush=True)

    voice_out = OUT / "voice-14.m4a"
    bed_out = OUT / "bed-stem.m4a"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(voice), "-af", f"volume={voice_gain:.2f}dB",
         "-c:a", "aac", "-b:a", "192k", str(voice_out)])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(bed), "-af", f"volume={bed_gain:.2f}dB,highpass=f=70",
         "-c:a", "aac", "-b:a", "192k", str(bed_out)])

    ducked = OUT / "bed-ducked.m4a"
    # Fast release so the beat opens up between words. Ratio 2.5 keeps it present.
    run(["ffmpeg", "-y", "-v", "error", "-i", str(bed_out), "-i", str(voice_out),
         "-filter_complex",
         "[0:a][1:a]sidechaincompress=threshold=0.04:ratio=2.5:attack=8:release=90:makeup=1[d]",
         "-map", "[d]", "-c:a", "aac", "-b:a", "192k", str(ducked)])
    ducked_lufs = lufs(ducked)
    stem_lufs = lufs(bed_out)
    print(f"music stem {stem_lufs:.1f} LUFS, ducked {ducked_lufs:.1f} LUFS", flush=True)

    final = OUT / "spacex-one-pad-32-hours-short-v3.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(voice_out), "-i", str(rumble), "-i", str(ducked),
         "-filter_complex",
         "[1:a]volume=1.0[v];"
         "[2:a]volume=0.18[r];"
         "[3:a]volume=1.0[m];"
         "[v][r][m]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.89:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])
    mix_lufs = lufs(final)
    voice_now = lufs(voice_out)
    print(f"LUFS voice {voice_now:.1f}  music-stem {stem_lufs:.1f}  ducked {ducked_lufs:.1f}  mix {mix_lufs:.1f}", flush=True)

    # The v2 thumbnail was the one the review kept. Copy those pixels.
    thumb_src = OUT / "spacex-one-pad-32-hours-thumb-v2.jpg"
    thumb = OUT / "spacex-one-pad-32-hours-thumb-v3.jpg"
    thumb.write_bytes(thumb_src.read_bytes())

    rows = []
    t = 0.0
    for g in SHOTS:
        rows.append({
            "id": g["id"], "mission": g["mission"], "file": g["file"], "source_ss": g["ss"],
            "video_in": round(t, 3), "video_out": round(t + g["dur"], 3),
            "duration": round(g["dur"], 3), "shows": g["shows"],
            "crop": list(g["crop"]), "fx": g.get("fx") or "",
        })
        t += g["dur"]
    (OUT / "shots-v3.json").write_text(
        json.dumps({
            "duration": round(total, 3),
            "lufs": {"voice": voice_now, "music_stem": stem_lufs, "music_ducked": ducked_lufs, "mix": mix_lufs},
            "shots": rows,
        }, indent=2) + "\n", encoding="utf-8")
    print("RENDER", final, f"{total:.2f}s")


if __name__ == "__main__":
    main()
