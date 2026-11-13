"""One-off: turn a photo + person mask into avatar images that match the card palette.

  python3 scripts/stylize_photo.py photo.png mask.png
writes assets/photo-dark.jpg and assets/photo-light.jpg (needs Pillow; run locally, output is committed).
The mask can come from macOS Vision (see README) or any background-removal tool.
"""
import pathlib, sys
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
SIZE = 600
STYLES = {  # gradient map stops (shadow -> highlight), background, glow, dot colour
    "dark": dict(stops=["#05070d", "#141c46", "#36399a", "#3a86c8", "#78d6f2", "#d8f4ff"], bg="#151b23",
                 glow="#4cc9f0", dot="#2a313c", rim="#4cc9f0"),
    "light": dict(stops=["#0b0e16", "#18235a", "#4134a6", "#2f78bf", "#6cc6ec", "#d4efff"], bg="#f6f8fa",
                  glow="#0a72b5", dot="#d6dbe1", rim="#0a72b5"),
}


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def gradient_lut(stops):
    cols = [hexrgb(c) for c in stops]
    lut = []
    for ch in range(3):
        for v in range(256):
            pos = v / 255 * (len(cols) - 1)
            i = min(int(pos), len(cols) - 2)
            f = pos - i
            lut.append(round(cols[i][ch] * (1 - f) + cols[i + 1][ch] * f))
    return lut


def render(photo, mask, s):
    gray = ImageOps.autocontrast(ImageOps.grayscale(photo), cutoff=1)
    # soft S-curve, highlights compressed so the white shirt doesn't blow out
    gray = gray.point(lambda v: round(255 * (0.5 - 0.5 * __import__("math").cos(3.14159 * (v / 255) ** 0.9)) * .93))
    person = Image.merge("RGB", (gray, gray, gray)).point(gradient_lut(s["stops"]))

    bg = Image.new("RGB", (SIZE, SIZE), hexrgb(s["bg"]))
    d = ImageDraw.Draw(bg)
    for y in range(9, SIZE, 18):
        for x in range(9, SIZE, 18):
            d.ellipse((x - 1.6, y - 1.6, x + 1.6, y + 1.6), fill=hexrgb(s["dot"]))
    glow = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(glow).ellipse((SIZE * .1, SIZE * .05, SIZE * .9, SIZE * .85), fill=110)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    bg = Image.composite(Image.new("RGB", bg.size, hexrgb(s["glow"])), bg, glow)

    m = mask.convert("L").resize((SIZE, SIZE), Image.LANCZOS)
    rim = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(6))
    rim = ImageChops.subtract(rim, m.filter(ImageFilter.GaussianBlur(2)))
    bg = Image.composite(Image.new("RGB", bg.size, hexrgb(s["rim"])), bg, rim.point(lambda v: min(255, int(v * 1.3))))
    return Image.composite(person, bg, m.filter(ImageFilter.GaussianBlur(1.2)))


if __name__ == "__main__":
    photo = Image.open(sys.argv[1]).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    mask = Image.open(sys.argv[2])
    for theme, s in STYLES.items():
        out = ROOT / "assets" / f"photo-{theme}.jpg"
        render(photo, mask, s).save(out, quality=86, optimize=True, progressive=True)
        print(out, out.stat().st_size)
