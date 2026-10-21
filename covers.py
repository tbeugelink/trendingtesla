"""Generates a cover image (1200x630 JPEG) for each article and language.

The images are original graphics (title, category colour and an abstract motif),
so they carry no third-party copyright. They are used on the site and as the
social-media preview image (og:image).
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).resolve().parent / "static" / "fonts"
W, H = 1200, 630
BG = (6, 8, 12)
RED = (226, 40, 34)


def _font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _wrap(draw, text, font, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=font) <= width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _motif(layer, kind, color):
    """Abstract background motif on the right-hand side, drawn in the category colour."""
    d = ImageDraw.Draw(layer)
    c = color + (255,)
    cx, cy = 1010, 315
    if kind == "bars":            # earnings: rising bar chart
        for i, h in enumerate([120, 190, 160, 260, 330, 420]):
            x = 760 + i * 72
            d.rounded_rectangle([x, 560 - h, x + 46, 560], radius=8, fill=color + (60 + i * 25,))
        d.line([(760, 470), (880, 400), (980, 430), (1120, 250)], fill=c, width=6)
    elif kind == "radar":         # fsd: sensor rings
        for i, r in enumerate(range(60, 520, 70)):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color + (200 - i * 25,), width=4)
        for a in (20, 75, 140, 210, 290):
            rr = 130 + (a % 4) * 70
            x, y = cx + rr * math.cos(math.radians(a)), cy + rr * math.sin(math.radians(a))
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=c)
    elif kind == "road":          # robotaxi / charging: perspective road lines
        vx, vy = 1000, 120
        for x0 in (620, 820, 1180, 1380):
            d.line([(vx, vy), (x0, 640)], fill=color + (150,), width=5)
        for i in range(7):
            t = (i / 7) ** 1.6
            y = vy + (640 - vy) * t
            hw = 6 + 40 * t
            d.rectangle([vx - 3 - t * 2, y, vx + 3 + t * 2, y + hw * 0.9], fill=color + (230,))
    elif kind == "grid":          # optimus / software: dot grid
        for gx in range(720, 1200, 44):
            for gy in range(40, 620, 44):
                dist = math.hypot(gx - cx, gy - cy)
                a = max(0, 255 - int(dist * 0.9))
                if a:
                    r = 3 + a / 80
                    d.ellipse([gx - r, gy - r, gx + r, gy + r], fill=color + (a,))
    elif kind == "energy":        # energy: stacked battery cells with a bolt
        for i in range(5):
            y = 120 + i * 82
            d.rounded_rectangle([820, y, 1160, y + 60], radius=10, outline=color + (220,), width=4)
            d.rounded_rectangle([830, y + 10, 830 + 60 * (5 - i), y + 50], radius=6, fill=color + (70 + i * 30,))
        d.polygon([(1010, 90), (930, 330), (1000, 330), (960, 560), (1080, 280), (1005, 280), (1060, 90)],
                  fill=(255, 255, 255, 40))
    else:                         # news / models / guides: sweeping arcs
        for i, r in enumerate(range(140, 900, 90)):
            d.arc([cx - r, cy - r + 300, cx + r, cy + r + 300], 190, 350, fill=color + (210 - i * 22,), width=5)


MOTIFS = {
    "earnings": "bars", "fsd": "radar", "robotaxi": "road", "charging": "road",
    "optimus": "grid", "software": "grid", "energy": "energy",
}


def make_cover(path, title, category_label, category_key, color_hex, date_label, with_text=True):
    """with_text=False gives a clean visual for use on the site, next to the HTML headline."""
    color = RED
    img = Image.new("RGB", (W, H), BG)

    # Soft colour glow behind the motif
    dx = 0 if with_text else -410   # centre the visual when there is no text
    LW = W - dx                      # layers wide enough that the shift never shows an edge
    glow = Image.new("RGBA", (LW, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([650, -150, 1400, 780], fill=color + (90,))
    g = glow.filter(ImageFilter.GaussianBlur(120))
    img.paste(g, (dx, 0), g)

    motif = Image.new("RGBA", (LW, H), (0, 0, 0, 0))
    _motif(motif, MOTIFS.get(category_key, "arcs"), color)
    img.paste(motif, (dx, 0), motif)

    if not with_text:
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "JPEG", quality=84, optimize=True, progressive=True)
        return

    # Dark fade on the left so the text stays readable
    fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    for x in range(W):
        a = int(max(0, min(1, 1.25 - x / 760)) * 235)
        fd.line([(x, 0), (x, H)], fill=BG + (a,))
    img.paste(fade, (0, 0), fade)

    d = ImageDraw.Draw(img)
    # Category pill
    f_cat = _font("manrope-latin-800-normal.woff2", 24)
    label = category_label.upper()
    tw = d.textlength(label, font=f_cat)
    d.rounded_rectangle([64, 64, 64 + tw + 36, 108], radius=22, fill=color)
    d.text((82, 72), label, font=f_cat, fill=(255, 255, 255))

    # Title: largest size that fits in 4 lines
    for size in (66, 60, 54, 48, 44):
        f_title = _font("manrope-latin-800-normal.woff2", size)
        lines = _wrap(d, title, f_title, 760)
        if len(lines) <= 4:
            break
    lines = lines[:4]
    lh = int(size * 1.16)
    y = 150 + (4 - len(lines)) * lh // 2
    for line in lines:
        d.text((64, y), line, font=f_title, fill=(240, 242, 245))
        y += lh

    # Wordmark and date
    f_logo = _font("manrope-latin-800-normal.woff2", 34)
    d.text((64, 540), "Trending", font=f_logo, fill=(240, 242, 245))
    d.text((64 + d.textlength("Trending", font=f_logo), 540), "Tesla", font=f_logo, fill=RED)
    f_date = _font("manrope-latin-600-normal.woff2", 24)
    d.text((W - 64 - d.textlength(date_label, font=f_date), 548), date_label, font=f_date, fill=(170, 176, 184))

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=84, optimize=True, progressive=True)
