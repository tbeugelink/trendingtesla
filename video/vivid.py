"""Optional picture and sound treatment for Shorts and long videos.

Off unless the environment variable VIVID is "1". Nothing here calls a paid API.
The music bed, hit and whoosh are synthesized in ffmpeg (original, not a copied track).
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

# Brand accents used on captions when VIVID is on. Numbers stay yellow in the renderer.
RED = (255, 45, 36)
CYAN = (0, 214, 232)


def grade(im):
    """Lift shadows, raise contrast, then push dull colour harder than already-vivid pixels.

    A flat saturation slider turns red paint neon and leaves grey paint grey. This curve
    opens the dark end (the lower half of many frames sits near black) and a vibrance
    pass boosts low-saturation pixels more than pixels that are already strong.
    """
    curve = []
    for i in range(256):
        x = i / 255.0
        x = x + 0.07 * (1.0 - x) ** 2          # shadow lift
        x = (x - 0.46) * 1.16 + 0.46           # contrast around a slightly lifted mid
        curve.append(max(0, min(255, int(round(x * 255)))))
    im = im.point(curve * 3)
    r, g, b = im.split()
    # Cyan in the shadows, a little extra red in the highlights. Tables, not Python per pixel.
    blue_lift = [min(255, i + int(22 * (1 - i / 150.0) ** 1.4)) if i < 150 else i for i in range(256)]
    green_lift = [min(255, i + int(10 * (1 - i / 180.0) ** 2)) if i < 180 else i for i in range(256)]
    red_push = [min(255, i + (8 if i > 150 else 0)) for i in range(256)]
    im = Image.merge("RGB", (r.point(red_push), g.point(green_lift), b.point(blue_lift)))
    im = ImageEnhance.Color(im).enhance(1.55)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    im = ImageEnhance.Sharpness(im).enhance(1.25)
    return im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=80, threshold=2))


def _ffmpeg(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def local_bed(tmp, dur):
    """A quiet 96 BPM pulse: low sine, a fifth, and a soft hat. Original synthesis."""
    f = Path(tmp) / "vivid-bed.m4a"
    dur = max(1.0, float(dur))
    fade = max(0.2, dur - 0.7)
    _ffmpeg([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"sine=frequency=65:duration={dur:.3f}:sample_rate=44100",
        "-f", "lavfi", "-i", f"sine=frequency=98:duration={dur:.3f}:sample_rate=44100",
        "-f", "lavfi", "-i", f"anoisesrc=color=pink:duration={dur:.3f}:sample_rate=44100",
        "-filter_complex",
        "[0]volume=0.20,tremolo=f=1.6:d=0.75,lowpass=f=180[a];"
        "[1]volume=0.05,tremolo=f=1.6:d=0.45,lowpass=f=420[b];"
        "[2]highpass=f=2800,lowpass=f=6500,volume=0.045,tremolo=f=6.4:d=0.9[c];"
        f"[a][b][c]amix=inputs=3:normalize=0,volume=0.85,afade=t=in:d=0.35,afade=t=out:st={fade:.3f}:d=0.55",
        "-c:a", "aac", "-b:a", "128k", str(f),
    ])
    return f


def local_hit(tmp):
    """Short low impact for the first frame. Original synthesis."""
    f = Path(tmp) / "vivid-hit.m4a"
    if f.exists():
        return f
    _ffmpeg([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "sine=frequency=72:duration=0.38:sample_rate=44100",
        "-af", "lowpass=f=200,afade=t=in:d=0.005,afade=t=out:st=0.04:d=0.32,volume=0.7",
        "-c:a", "aac", "-b:a", "128k", str(f),
    ])
    return f


def local_whoosh(tmp):
    """A 140 ms noise swipe for a cut. Original synthesis, reused at each beat."""
    f = Path(tmp) / "vivid-whoosh.m4a"
    if f.exists():
        return f
    _ffmpeg([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "anoisesrc=color=white:duration=0.16:sample_rate=44100",
        "-af", "highpass=f=700,lowpass=f=4500,afade=t=in:d=0.015,afade=t=out:st=0.05:d=0.10,volume=0.55",
        "-c:a", "aac", "-b:a", "96k", str(f),
    ])
    return f
