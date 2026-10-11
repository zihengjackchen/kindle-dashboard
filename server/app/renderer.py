"""High-contrast editorial layouts, drawn natively in grayscale for e-ink."""
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
from .config import Settings
from .models import DashboardRequest, PAGE_IDS
from .snapshots import Snapshot, WATCHLIST, load_snapshot

TITLES = {"overview": "At a glance", "weather": "Weather", "markets-1": "Markets", "markets-2": "Markets", "nas": "Home server"}


@lru_cache(maxsize=96)
def font(size: int, configured_path: str, bold: bool = False):
    if configured_path:
        return ImageFont.truetype(configured_path, size)
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    packaged = Path("/usr/share/fonts/truetype/dejavu") / name
    if packaged.is_file():
        return ImageFont.truetype(str(packaged), size)
    return ImageFont.load_default(size=size)


class Canvas:
    def __init__(self, width, height, settings):
        self.image = Image.new("L", (width, height), 255)
        self.draw = ImageDraw.Draw(self.image)
        self.width, self.height, self.settings = width, height, settings
        self.scale = min(width / 1236, height / 1648)

    def text(self, value, x, y, size=34, bold=False, color=0, right=False, max_width=.88):
        value = str(value)
        pixels = max(8, round(size * self.scale))
        face = font(pixels, self.settings.font_path, bold)
        while self.draw.textlength(value, font=face) > self.width * max_width and pixels > 8:
            pixels -= 1
            face = font(pixels, self.settings.font_path, bold)
        while self.draw.textlength(value, font=face) > self.width * max_width and len(value) > 1:
            value = value[:-2] + "…"
        self.draw.text((round(x*self.width), round(y*self.height)), value, font=face,
                       fill=color, anchor="rt" if right else "lt")

    def line(self, y, shade=190, thick=2):
        self.draw.line((.065*self.width, y*self.height, .935*self.width, y*self.height),
                       fill=shade, width=max(1, round(thick*self.scale)))

    def box(self, x, y, w, h, shade=240):
        self.draw.rounded_rectangle((x*self.width, y*self.height, (x+w)*self.width, (y+h)*self.height),
                                    radius=max(2, round(16*self.scale)), fill=shade)

    def bar(self, y, value):
        self.box(.065, y, .87, .012, 225)
        if value is not None and value > 0:
            self.box(.065, y, .87*value/100, .012, 0)


def stamp(record, now, tz):
    if record is None:
        return "SOURCE NOT CONNECTED"
    return f"{record.status(now)} / {record.as_of.astimezone(tz):%Y-%m-%d %H:%M %Z} / {record.source}"


def render_dashboard(data: DashboardRequest, settings: Settings, now: datetime | None = None, snapshot: Snapshot | None = None, layout=None) -> bytes:
    tz = ZoneInfo(settings.timezone)
    now = (now or datetime.now(tz)).astimezone(tz)
    snapshot = snapshot if snapshot is not None else load_snapshot(settings.snapshot_path, settings.codex_usage_path)
    from .layout import Layout
    from .widgets import render_overview
    return render_overview(data, settings, snapshot, now, (layout or Layout()).for_page(data.page))
