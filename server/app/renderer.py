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
    snapshot = snapshot if snapshot is not None else load_snapshot(settings.snapshot_path)
    if data.page == "overview":
        from .layout import Layout
        from .widgets import render_overview
        return render_overview(data, settings, snapshot, now, layout or Layout())
    c = Canvas(data.width, data.height, settings)
    c.text("DAYLIGHT / PERSONAL DASHBOARD", .065, .037, 25, bold=True, max_width=.64)
    battery = "BATTERY —" if data.battery is None else f"{data.battery}%" + (" +" if data.charging else "")
    c.text(battery, .935, .037, 28, bold=True, right=True, max_width=.18)
    c.line(.077, shade=0, thick=3)
    c.text(now.strftime("%A, %B %d").upper(), .065, .105, 29, color=70, max_width=.66)
    c.text(now.strftime("%H:%M"), .935, .105, 34, bold=True, right=True, max_width=.22)
    c.text(TITLES[data.page], .065, .146, 96, bold=True)
    if snapshot.demo:
        c.box(.065, .224, .87, .035, 0)
        c.text("SAMPLE DATA / DESIGN PREVIEW", .083, .233, 24, bold=True, color=255, max_width=.82)
    else:
        subtitle = {"overview": "A quieter view of your day.", "weather": "Outside, today and tomorrow.",
                    "markets-1": "WATCHLIST 01 / USD", "markets-2": "WATCHLIST 02 / USD", "nas": "Your infrastructure, at a glance."}[data.page]
        c.text(subtitle, .065, .232, 30, color=70)
    if data.page == "weather":
        draw_weather(c, snapshot, now, tz)
    elif data.page.startswith("markets"):
        draw_markets(c, snapshot, now, tz, 0 if data.page == "markets-1" else 6)
    else:
        draw_nas(c, snapshot, now, tz, data)
    c.line(.907, shade=0)
    c.text(f"IMAGE {now:%Y-%m-%d %H:%M %Z} / STATUS AT GENERATION", .065, .925, 22, color=55, max_width=.87)
    c.text("CACHED PAGES / MANUAL REFRESH", .065, .961, 21, color=70, max_width=.65)
    c.text(f"{PAGE_IDS.index(data.page)+1:02d} / {len(PAGE_IDS):02d}", .935, .958, 27, bold=True, right=True, max_width=.17)
    output = BytesIO()
    c.image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def draw_weather(c, snapshot, now, tz):
    from .widgets import temperatures
    w = snapshot.weather
    c.text(w.location.upper() if w else "CHOOSE A WEATHER LOCATION", .065, .295, 30, bold=True)
    c.text(temperatures(w.temperature,w.unit) if w else "—°", .065, .354, 110, bold=True, max_width=.87)
    c.text(w.condition if w else "Weather source not connected", .065, .493, 46, bold=True)
    metrics = ((f"HIGH / LOW ({w.unit})" if w else "HIGH / LOW", f"{w.high:.0f}° / {w.low:.0f}°" if w else "— / —"),
               ("RAIN CHANCE", f"{w.precipitation_percent}%" if w else "—"),
               ("FEELS LIKE", f"{w.feels_like:.0f}°" if w and w.feels_like is not None else "—"))
    for i, (label, value) in enumerate(metrics):
        x = .065 + i*.3
        c.text(label, x, .559, 23, color=70, max_width=.27)
        c.text(value, x, .59, 43, bold=True, max_width=.27)
    c.line(.646)
    c.text("THE NEXT FEW DAYS", .065, .673, 26, bold=True)
    for i in range(3):
        d = w.forecast[i] if w and i < len(w.forecast) else None
        y = .716 + i*.044
        c.text(d.day if d else "—", .065, y, 28, bold=True, max_width=.16)
        c.text(d.condition if d else "Forecast unavailable", .26, y, 27, max_width=.38)
        c.text(f"{d.high:.0f}° / {d.low:.0f}°" if d else "—", .935, y, 28, right=True, max_width=.23)
    c.text(stamp(w, now, tz), .065, .868, 22, color=65)


def draw_markets(c, snapshot, now, tz, start):
    quotes = {q.symbol: q for q in snapshot.quotes}
    c.text("INSTRUMENT / DATA AS OF", .065, .286, 22, color=70, max_width=.47)
    c.text("PRICE / CHANGE", .935, .286, 22, color=70, right=True, max_width=.4)
    for i, symbol in enumerate(WATCHLIST[start:start+6]):
        q = quotes.get(symbol)
        y = .333 + i*.089
        c.text(symbol, .065, y, 48, bold=True, max_width=.41)
        c.text(f"{q.price:,.2f}" if q else "—", .935, y, 48, bold=True, right=True, max_width=.42)
        c.text(f"{q.as_of.astimezone(tz):%Y-%m-%d %H:%M %Z} / {q.session}" if q else "Source not connected", .065, y+.036, 20, color=65, max_width=.43)
        c.text(f"{q.change:+,.2f} ({q.change_percent:+.2f}%)" if q else "NO QUOTE", .935, y+.035, 27, right=True, max_width=.42)
        state = f"{q.status(now)}{' / DELAYED' if q.delayed else ''} / {q.basis} / {q.source}" if q else "UNAVAILABLE"
        c.text(state, .065, y+.058, 19, color=70, max_width=.86)
        if i < 5:
            c.line(y+.078, shade=195)
    c.text("Equities: previous close. Crypto: rolling 24h.", .065, .881, 20, color=70)


def draw_nas(c, snapshot, now, tz, data):
    n = snapshot.nas
    c.box(.065, .294, .87, .18, 0)
    c.text(n.name.upper() if n else "DASHBOARD SERVICE", .09, .318, 28, color=255, bold=True)
    c.text(n.pool_health if n else "RESPONDING", .09, .368, 75, bold=True, color=255, max_width=.81)
    c.text(n.version if n else "Host health has not been connected", .09, .437, 24, color=230, max_width=.8)
    for i, (label, value) in enumerate((("STORAGE USED", n.used_percent if n else None), ("CPU", n.cpu_percent if n else None), ("MEMORY", n.memory_percent if n else None))):
        y = .516 + i*.093
        c.text(label, .065, y, 27, bold=True)
        c.text(f"{value:.0f}%" if value is not None else "—", .935, y, 34, right=True, bold=True)
        c.bar(y+.039, value)
    c.text(f"{n.alerts} active alerts" if n else "Alerts unavailable", .065, .798, 27, bold=True, max_width=.44)
    c.text(f"Up {n.uptime}" if n else "Uptime unavailable", .935, .798, 25, right=True, max_width=.4)
    contact = f"KINDLE CONTACT {now:%H:%M %Z}" if data.device_id else "PREVIEW / NO KINDLE CONTACT"
    if data.rssi is not None: contact += f" / WIFI {data.rssi} dBm"
    if data.fetch_failures is not None: contact += f" / PRIOR FAILURES {data.fetch_failures}"
    c.text(contact, .065, .835, 20, color=60)
    success = datetime.fromtimestamp(data.last_success_epoch, tz).strftime("%Y-%m-%d %H:%M %Z") if data.last_success_epoch else "NOT REPORTED"
    c.text(f"PRIOR VALIDATED FETCH {success}", .065, .859, 19, color=60)
    c.text(stamp(n, now, tz), .065, .884, 20, color=65)
