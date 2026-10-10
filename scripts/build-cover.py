"""Render the original library cover and embed it in the Kindle scriptlet."""
import base64
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCALE = 2
im = Image.new("L", (384 * SCALE, 587 * SCALE), 255)
d = ImageDraw.Draw(im)


def box(rect, radius=14, fill=255, outline=0, width=2):
    d.rounded_rectangle(tuple(int(v*SCALE) for v in rect), radius*SCALE,
                        fill=fill, outline=outline, width=width*SCALE)


def line(points, width=3, fill=0):
    d.line([(int(x*SCALE), int(y*SCALE)) for x, y in points], fill=fill, width=width*SCALE)


def text(value, x, y, size):
    for name in ("DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf"):
        try:
            font = ImageFont.truetype(name, size*SCALE)
            break
        except OSError:
            continue
    else:
        raise RuntimeError("Install DejaVu Sans or Segoe UI to rebuild the cover")
    d.text((x*SCALE, y*SCALE), value, font=font, anchor="mt", fill=0)


box((7, 7, 377, 580), radius=19, width=3)
# Leave the upper-right corner clear for Kindle's reading-progress badge.
text("DASH", 192, 29, 35)
text("BOARD", 192, 65, 35)
line([(30, 102), (354, 102)], width=2)
box((30, 126, 184, 260), fill=242)
box((198, 126, 354, 260))
# Weather: sun and cloud, legible at thumbnail size.
d.ellipse((70*SCALE, 155*SCALE, 110*SCALE, 195*SCALE), fill=0)
for n in range(8):
    a = n*math.pi/4
    line([(90+27*math.cos(a), 175+27*math.sin(a)),
          (90+36*math.cos(a), 175+36*math.sin(a))])
box((75, 195, 155, 225), radius=15, width=3)
box((94, 183, 137, 220), radius=18, width=3)
d.rectangle((85*SCALE, 208*SCALE, 145*SCALE, 218*SCALE), fill=255)
# Markets: a bold sparkline, no invented prices.
line([(219, 224), (239, 201), (256, 210), (279, 177), (300, 188), (331, 156)], width=5)
line([(314, 156), (331, 156), (331, 174)], width=4)
box((30, 286, 354, 436))
for y, length in ((314, 190), (350, 245), (386, 150)):
    d.ellipse((48*SCALE, y*SCALE, 58*SCALE, (y+10)*SCALE), fill=0)
    line([(77, y+5), (length, y+5)], width=6)
box((286, 314, 329, 407), radius=5, fill=235)
line([(297, 335), (317, 335)], width=3)
line([(297, 355), (317, 355)], width=3)
text("WEATHER  /  MARKETS", 192, 481, 18)
text("HOME SERVER", 192, 523, 20)
# Match the installed KWordle scriptlet: 454x694, RGB PNG (neutral colors).
im = im.resize((454, 694), Image.Resampling.LANCZOS)
# Keep the inline metadata compact, using the panel's 16 grayscale levels.
im = im.point(lambda pixel: round(pixel / 17) * 17).convert("RGB")
path = ROOT / "docs/assets/dashboard-cover.png"
path.parent.mkdir(parents=True, exist_ok=True)
im.save(path, optimize=True)
launcher = ROOT / "kindle-client/documents/Dashboard.sh"
lines = [s for s in launcher.read_text(encoding="utf-8").splitlines() if not s.startswith("# Icon:")]
lines.insert(4, "# Icon: data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii"))
launcher.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
print(f"Embedded grayscale cover: {im.width}x{im.height}, {path.stat().st_size} bytes")
