"""Cut the pad-turnaround preview Short. Nothing is uploaded or published.

Picture is the official SpaceX webcast of USSF-317 and of NROL-136, both from pad 4E.
Voice is the Noah files in out/. VIVID grade and the original music bed come from video/vivid.py.
"""
import json
import subprocess
import sys
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

# Each group is one camera. A camera is listed at most twice. ss is seconds into that webcast.
# crop is x, y, w, h in the 3840x2160 frame, chosen to keep the rocket and drop the telemetry bar.
GROUPS = [
    {"ids": ["s1"], "file": "nrol136.mp4", "ss": 843.0, "crop": (1460, 0, 920, 1560),
     "mission": "NROL-136", "shows": "NROL-136 liftoff, T+5 s, SLC-4E, 22 Nov 2026. Full Falcon 9, flame, tower."},
    {"ids": ["s2"], "file": "ussf317.mp4", "ss": 766.0, "crop": (1400, 40, 980, 1580),
     "mission": "USSF-317", "shows": "USSF-317 liftoff, T+8 s, SLC-4E, 20 Nov 2026. Night flame and the pad."},
    {"ids": ["s3"], "file": "nrol136.mp4", "ss": 848.5, "crop": (1500, 0, 900, 1520),
     "mission": "NROL-136", "shows": "NROL-136, T+10 s, same pad camera a few seconds later. Second use of this angle."},
    {"ids": ["s4", "s5"], "file": "ussf317.mp4", "ss": 777.0, "crop": (1450, 80, 1000, 1600),
     "mission": "USSF-317", "shows": "USSF-317 engine close-up, about T+19 s. The rocket climbing."},
    {"ids": ["s6"], "file": "ussf317.mp4", "ss": 792.0, "crop": (1300, 200, 1100, 1500),
     "mission": "USSF-317", "shows": "USSF-317 long lens, about T+34 s. The climb over the coast."},
    {"ids": ["s7"], "file": "ussf317.mp4", "ss": 1262.0, "crop": (1960, 180, 1500, 1200),
     "mission": "USSF-317", "shows": "USSF-317 booster landing on Of Course I Still Love You, about T+8:24. Right-hand deck camera."},
    {"ids": ["s8", "s9", "s10", "s11"], "file": "nrol136.mp4", "ss": 1276.0, "crop": (1200, 80, 1200, 1600),
     "mission": "NROL-136", "shows": "NROL-136 booster B1097 landing burn at Landing Zone 4, about T+7:18 to T+7:40."},
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
    # Prefer the written caption when it is 3-6 words; time it across the whole sentence.
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


def draw_text(base, text, size, y, fill):
    d = ImageDraw.Draw(base)
    f = font(size)
    while f.size > 48 and d.textlength(text, font=f) > W * 0.92:
        f = font(f.size - 4)
    x = (W - d.textlength(text, font=f)) / 2
    d.text((x, y), text, font=f, fill=fill, stroke_width=max(8, f.size // 10), stroke_fill=(0, 0, 0))


def overlay(im, caption, hook):
    if hook:
        draw_text(im, "32 HOURS", 168, 150, YELLOW)
    if caption:
        # Numbers stay yellow, the rest white. Draw word by word on one line, wrap if needed.
        words = caption.split()
        size = 78
        f = font(size)
        d = ImageDraw.Draw(im)
        while size > 52 and sum(d.textlength(w, font=font(size)) for w in words) + 22 * (len(words) - 1) > W * 0.9:
            size -= 4
        f = font(size)
        gap = 18
        width = sum(d.textlength(w, font=f) for w in words) + gap * (len(words) - 1)
        x = (W - width) / 2
        y = 1240
        for w in words:
            fill = YELLOW if any(ch.isdigit() for ch in w) else WHITE
            d.text((x, y), w, font=f, fill=fill, stroke_width=8, stroke_fill=(0, 0, 0))
            x += d.textlength(w, font=f) + gap
    return im


def extract(group, length, dest):
    x, y, w, h = group["crop"]
    vf = f"crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos,fps={FPS}"
    # -ss after -i so the cut lands on the rocket, not the previous keyframe.
    run(["ffmpeg", "-y", "-v", "error", "-i", str(CLIPS / group["file"]),
         "-ss", f"{group['ss']:.3f}", "-t", f"{length:.3f}",
         "-vf", vf, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(dest)])


def grade_and_caption(src, dest, cards, hook, t0, length):
    """Read frames, apply the VIVID grade, burn the caption and the hook number."""
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
            show_hook = hook and (t - t0) < max(2.2, 0.0)
            # The number stays up for the whole hook sentence, which is this shot.
            show_hook = hook
            overlay(im, cap, show_hook)
            outp.write(im.tobytes())
            n += 1
    raw.unlink(missing_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", str(graded), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "16", str(dest)])
    graded.unlink(missing_ok=True)


def clip_audio(group, length, dest):
    """Engine rumble from the webcast. Speech is cut by the low pass so two narrators do not talk at once."""
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{group['ss']:.3f}", "-t", f"{length:.3f}",
         "-i", str(CLIPS / group["file"]),
         "-af", "lowpass=f=280,highpass=f=35,volume=0.55,afade=t=in:d=0.05,afade=t=out:st="
                + f"{max(0.1, length - 0.12):.3f}:d=0.1",
         "-c:a", "aac", "-b:a", "128k", str(dest)])


def main():
    if not (CLIPS / "nrol136.mp4").exists() or not (CLIPS / "ussf317.mp4").exists():
        raise SystemExit(f"missing webcasts in {CLIPS}")
    alignment = json.loads((HERE / "out" / "alignment.json").read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in alignment["sentences"]}
    OUT.mkdir(exist_ok=True)
    # Place sentences back to back. No pause after the hook, so the next line does not undercut it.
    timeline = []
    t = 0.0
    for i, s in enumerate(alignment["sentences"]):
        length = dur(HERE / "out" / f"{s['id']}.mp3")
        timeline.append({**s, "t0": t, "length": length})
        gap = 0.0 if i == 0 else 0.06
        t += length + gap
    total = timeline[-1]["t0"] + timeline[-1]["length"]
    print(f"voice {total:.2f}s")

    segs = []
    for gi, group in enumerate(GROUPS):
        members = [next(x for x in timeline if x["id"] == i) for i in group["ids"]]
        t0 = members[0]["t0"]
        t1 = members[-1]["t0"] + members[-1]["length"]
        length = t1 - t0
        cards = []
        for m in members:
            cards += caption_cards(by_id[m["id"]] | {"caption": m.get("caption"), "hook": m.get("hook")}, m["t0"])
        # caption_cards uses sentence-relative times plus t0. by_id has chars; timeline has t0.
        cards = []
        for m in members:
            sent = dict(by_id[m["id"]])
            sent["caption"] = m.get("caption") or sent.get("caption")
            cards += caption_cards(sent, m["t0"])
        hook = any(m.get("hook") for m in members)
        plain = OUT / f"g{gi}-plain.mp4"
        graded = OUT / f"g{gi}.mp4"
        audio = OUT / f"g{gi}.m4a"
        print(f"shot {gi} {group['mission']} {group['ss']:.1f}s for {length:.2f}s ({', '.join(group['ids'])})")
        extract(group, length, plain)
        grade_and_caption(plain, graded, cards, hook, t0, length)
        clip_audio(group, length, audio)
        plain.unlink(missing_ok=True)
        segs.append({"video": graded, "audio": audio, "t0": t0, "length": length, "group": group})

    # Concat picture.
    listing = OUT / "video.txt"
    listing.write_text("".join(f"file '{s['video'].resolve()}'\n" for s in segs), encoding="utf-8")
    silent = OUT / "silent.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17", "-r", str(FPS), str(silent)])

    # Voice, one file per sentence, delayed to its start.
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

    bed = vivid.local_bed(OUT, total + 0.4)
    final = OUT / "spacex-one-pad-32-hours-short.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(voice), "-i", str(rumble), "-i", str(bed),
         "-filter_complex",
         "[1:a]volume=1.0[v];[2:a]volume=0.42[r];[3:a]volume=0.55[b];"
         "[v][r][b]amix=inputs=3:normalize=0:duration=first,alimiter=limit=0.89:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])

    # Thumbnail: the hook frame, already graded inside the video, plus the number is burned in.
    thumb = OUT / "spacex-one-pad-32-hours-thumb.jpg"
    run(["ffmpeg", "-y", "-v", "error", "-ss", "0.35", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(thumb)])

    rows = []
    for s in segs:
        g = s["group"]
        rows.append({
            "mission": g["mission"], "file": g["file"], "source_ss": g["ss"],
            "video_t0": round(s["t0"], 3), "duration": round(s["length"], 3), "shows": g["shows"],
        })
    (OUT / "shots.json").write_text(json.dumps({"duration": round(total, 3), "shots": rows}, indent=2) + "\n", encoding="utf-8")
    print("RENDER", final, f"{total:.2f}s")


if __name__ == "__main__":
    main()
