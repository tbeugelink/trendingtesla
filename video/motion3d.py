"""3D motion Short. Off unless MOTION3D=1.

    MOTION3D=1 python3 video/motion3d.py <slug>

Renders a vertical Short from a scene file in video/scenes/. Blender Eevee draws the
picture. Captions, the progress bar and the sound are added here. Voice uses the
existing ElevenLabs call at the VIVID speeds when that key is set. With no key, the
same speeds go to a free neural voice so a render can still be checked.

Only the no-legs scene is built. Other slugs stay on photos or licensed stock.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
VIDEO = Path(__file__).resolve().parent
SCENES = {
    "spacex-first-super-heavy-booster-catch-chopsticks-mechazilla-story": VIDEO / "scenes" / "no-legs.json",
}
OUT = ROOT / "video" / "out"
FPS = 24
W, H = 1080, 1920
SPEED = {"hook": 1.14, "tension": 1.08, "payoff": 1.02}
RED = (255, 45, 36)
CYAN = (0, 214, 232)
YEL = (255, 214, 0)
WHITE = (255, 255, 255)
FONT = str(VIDEO / "fonts" / "Inter-Black.otf")
FONT_SM = str(VIDEO / "fonts" / "Inter-ExtraBold.otf")


def duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def speak(text, speed, dest):
    """VIVID speeds. ElevenLabs when the daily secret is present, otherwise a free voice."""
    dest = Path(dest)
    if os.environ.get("ELEVENLABS_API_KEY", "").strip() and os.environ.get("ELEVENLABS_VOICE_ID", "").strip():
        sys.path.insert(0, str(VIDEO))
        import story
        story.tts(text, speed, dest)
        return "elevenlabs"
    rate = int(round((speed - 1.0) * 100))
    bin_ = os.path.expanduser("~/.local/bin/edge-tts")
    if not Path(bin_).exists():
        bin_ = "edge-tts"
    subprocess.run(
        [bin_, "--voice", "en-US-GuyNeural", f"--rate={rate:+d}%", "--text", text, "--write-media", str(dest)],
        check=True)
    return "edge-tts"


def fit_voice(src, dest, limit=2.0):
    """Keep each line inside a 1–2 s caption. Returns the duration used."""
    dur = duration(src)
    if dur <= limit:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-c:a", "aac", "-b:a", "128k", str(dest)],
            check=True)
        return dur
    tempo = dur / limit
    # atempo accepts 0.5–2. A line this short should not need more than 2x.
    tempo = min(2.0, tempo)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter:a", f"atempo={tempo:.4f}", "-c:a", "aac", "-b:a", "128k", str(dest)],
        check=True)
    return duration(dest)


def timeline(beats, tmp):
    engine = None
    t = 0.0
    timed = []
    for i, b in enumerate(beats):
        raw = tmp / f"raw-{i:02d}.mp3"
        fitted = tmp / f"line-{i:02d}.m4a"
        engine = speak(b["text"], SPEED[b["part"]], raw)
        spoken = fit_voice(raw, fitted, 1.45)
        span = min(1.5, max(1.0, spoken))
        row = dict(b)
        row["t0"] = round(t, 3)
        row["t1"] = round(t + span, 3)
        row["voice"] = str(fitted)
        timed.append(row)
        t += span
    return timed, round(t, 3), engine


def rumble(tmp, dur):
    f = tmp / "rumble.m4a"
    dur = max(1.0, dur)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"sine=frequency=42:duration={dur:.2f}:sample_rate=44100",
        "-f", "lavfi", "-i", f"anoisesrc=color=brown:duration={dur:.2f}:sample_rate=44100",
        "-filter_complex",
        "[0]volume=0.35,lowpass=f=120[a];"
        "[1]lowpass=f=180,volume=0.25[b];"
        "[a][b]amix=inputs=2:normalize=0,afade=t=in:d=0.3,afade=t=out:st=" + f"{max(0.2, dur - 0.6):.2f}:d=0.5",
        "-c:a", "aac", "-b:a", "128k", str(f),
    ], check=True)
    return f


def render_picture(timed, duration_s, clean):
    spec = {"fps": FPS, "duration": duration_s, "beats": [
        {"t0": b["t0"], "t1": b["t1"], "shot": b["shot"]} for b in timed]}
    path = clean.with_suffix(".beats.json")
    path.write_text(json.dumps(spec))
    subprocess.run([
        "blender", "-b", "-P", str(VIDEO / "blender" / "no_legs.py"),
        "--", "--beats", str(path), "--out", str(clean),
    ], check=True)


def font(size):
    from PIL import ImageFont
    return ImageFont.truetype(FONT, size)


def font_sm(size):
    from PIL import ImageFont
    return ImageFont.truetype(FONT_SM, size)


def word_color(word, beat):
    bare = word.strip(".,:;!?").lower()
    yellow = {w.lower() for w in beat.get("yellow") or []}
    red = {w.lower() for w in beat.get("red") or []}
    cyan = {w.lower() for w in beat.get("cyan") or []}
    if bare in yellow or any(ch.isdigit() for ch in bare):
        return YEL
    if bare in red:
        return RED
    if bare in cyan:
        return CYAN
    return WHITE


def caption(beat, age):
    face = font(78)
    words = beat["text"].split()
    # Wrap to two lines.
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if face.getlength(trial) <= W * 0.86 or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    line_h = 92
    block_h = line_h * len(lines) + 20
    img = Image.new("RGBA", (W, block_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    y = 0
    for ln in lines:
        ws = ln.split()
        widths = [face.getlength(w) for w in ws]
        gap = face.getlength(" ")
        total = sum(widths) + gap * (len(ws) - 1)
        x = (W - total) / 2
        for w, width in zip(ws, widths):
            col = word_color(w, beat)
            draw.text((x + 4, y + 5), w, font=face, fill=(0, 0, 0, 160))
            draw.text((x, y), w, font=face, fill=col, stroke_width=8, stroke_fill=(0, 0, 0))
            x += width + gap
        y += line_h
    if age < 0.16:
        sc = 1.0 + 0.14 * (1 - age / 0.16)
        grown = img.resize((max(1, int(W * sc)), max(1, int(block_h * sc))), Image.BILINEAR)
        left = max(0, (grown.width - W) // 2)
        img = grown.crop((left, 0, left + W, grown.height))
    return img


def brand():
    face = font_sm(46)
    img = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((48, 36), "Trending", font=face, fill=WHITE, stroke_width=2, stroke_fill=(20, 20, 24))
    d.text((48 + face.getlength("Trending"), 36), "Tesla", font=face, fill=RED, stroke_width=2, stroke_fill=(20, 20, 24))
    return img


def composite(clean, timed, total, out):
    cmd = ["ffmpeg", "-v", "error", "-i", str(clean), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    enc = subprocess.Popen([
        "ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-pix_fmt", "yuv420p", str(out),
    ], stdin=subprocess.PIPE)
    frame_bytes = W * H * 3
    logo = brand()
    caps = {}
    n = 0
    while True:
        buf = raw.stdout.read(frame_bytes)
        if len(buf) < frame_bytes:
            break
        t = n / FPS
        im = Image.frombytes("RGB", (W, H), buf).convert("RGBA")
        beat = timed[-1]
        for b in timed:
            if b["t0"] <= t < b["t1"]:
                beat = b
                break
        key = beat["text"]
        if key not in caps:
            caps[key] = caption(beat, 1.0)
        age = t - beat["t0"]
        cap = caption(beat, age) if age < 0.16 else caps[key]
        im.alpha_composite(cap, (0, int(H * 0.16)))
        if t >= 1.2:
            im.alpha_composite(logo, (0, 0))
        rgb = im.convert("RGB")
        ImageDraw.Draw(rgb).rectangle((0, H - 14, int(W * min(t, total) / total), H), fill=RED)
        enc.stdin.write(rgb.tobytes())
        n += 1
    raw.stdout.close()
    raw.wait()
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit("caption encode failed")


def mix(timed, total, tmp, picture, final):
    sys.path.insert(0, str(VIDEO))
    import vivid
    layers = [(Path(b["voice"]), b["t0"], 1.0) for b in timed]
    layers.append((vivid.local_bed(tmp, total), 0.0, 1.4))
    layers.append((vivid.local_hit(tmp), 0.0, 0.7))
    whoosh = vivid.local_whoosh(tmp)
    flight = next(b["t0"] for b in timed if b["shot"] == "flight")
    catch_end = max(b["t1"] for b in timed if b["shot"] == "catch")
    layers.append((rumble(tmp, catch_end - flight + 0.4), flight, 0.55))
    for b in timed:
        if b["t0"] > 0.3:
            layers.append((whoosh, b["t0"], 0.55))
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for path, _, _ in layers:
        cmd += ["-i", str(path)]
    filters = []
    for i, (_, start, vol) in enumerate(layers):
        ms = int(start * 1000)
        filters.append(
            f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,afade=t=in:d=0.02,"
            f"adelay={ms}|{ms},volume={vol}[a{i}]")
    mix_in = "".join(f"[a{i}]" for i in range(len(layers)))
    filters.append(
        f"{mix_in}amix=inputs={len(layers)}:normalize=0,alimiter=limit=0.95,"
        f"atrim=0:{total:.3f},afade=t=in:d=0.06,afade=t=out:st={max(0, total - 0.25):.3f}:d=0.25[out]")
    audio = tmp / "mix.m4a"
    subprocess.run(cmd + ["-filter_complex", ";".join(filters), "-map", "[out]", "-c:a", "aac", "-b:a", "192k", str(audio)], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(picture), "-i", str(audio),
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest",
        "-movflags", "+faststart", str(final),
    ], check=True)


def main():
    if os.environ.get("MOTION3D") != "1":
        raise SystemExit("MOTION3D is off. Set MOTION3D=1 to render a 3D Short. Photos and stock stay the default.")
    slug = sys.argv[1]
    scene = SCENES.get(slug)
    if scene is None:
        known = ", ".join(SCENES)
        raise SystemExit(f"No 3D scene for {slug}. Built so far: {known}. This slug keeps photos or licensed stock.")
    t0 = time.time()
    spec = json.loads(scene.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f"motion3d-{slug[:40]}"
    tmp.mkdir(parents=True, exist_ok=True)
    timed, total, engine = timeline(spec["beats"], tmp)
    if not 30 <= total <= 48:
        print(f"::warning::3D Short is {total:.1f}s (target 30-45)")
    clean = tmp / "clean.mp4"
    print(f"voice={engine} duration={total:.2f}s beats={len(timed)}", flush=True)
    render_picture(timed, total, clean)
    silent = tmp / "captioned.mp4"
    composite(clean, timed, total, silent)
    final = OUT / f"{slug}-en-short-3d.mp4"
    mix(timed, total, tmp, silent, final)
    report = {
        "file": str(final),
        "seconds": total,
        "beats": len(timed),
        "voice": engine,
        "render_s": round(time.time() - t0, 1),
        "fps": FPS,
        "size": f"{W}x{H}",
        "engine": "blender-eevee",
        "cost_usd": 0 if engine != "elevenlabs" else None,
    }
    (final.with_suffix(".json")).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
