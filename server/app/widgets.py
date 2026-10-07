"""Dense, grayscale cards. Every datum and freshness label is rendered on the NAS."""
from datetime import datetime
from io import BytesIO
from math import ceil

from .renderer import Canvas, font


def widget_rows(widgets):
    rows = []
    for widget in widgets:
        if (widget.width == "half" and rows and len(rows[-1]) == 1
                and rows[-1][0].width == "half"):
            rows[-1].append(widget)
        else:
            rows.append([widget])
    return rows


class Card:
    def __init__(self, canvas, bounds, size, density):
        self.c = canvas
        self.x, self.y, self.w, self.h = bounds
        self.pad = min(22 * canvas.scale, self.w * .045)
        self.scale = min(canvas.scale, self.w / 480, self.h / {"small": 220, "medium": 340, "large": 600}[size])
        self.type_scale = 1 if density == "compact" else 1.12
        canvas.draw.rounded_rectangle((self.x, self.y, self.x+self.w, self.y+self.h),
                                      radius=max(3, int(22 * canvas.scale)), fill=246, outline=185, width=1)

    def text(self, value, x, y, size=28, bold=False, shade=0, right=False, width=.92):
        value = str(value)
        pixels = max(6, round(size * self.scale * self.type_scale))
        face = font(pixels, self.c.settings.font_path, bold)
        available = max(1, (self.w-2*self.pad)*width)
        while self.c.draw.textlength(value, font=face) > available and len(value) > 1:
            value = value[:-2] + "…"
        self.c.draw.text((self.x+self.pad+x*(self.w-2*self.pad), self.y+self.pad+y*(self.h-2*self.pad)),
                         value, font=face, fill=shade, anchor="rt" if right else "lt")

    def rule(self, y):
        yy = self.y+self.pad+y*(self.h-2*self.pad)
        self.c.draw.line((self.x+self.pad, yy, self.x+self.w-self.pad, yy), fill=205)


def record_time(record, now):
    return (f"{record.status(now)} · {record.as_of.astimezone(now.tzinfo):%m/%d %H:%M %Z}"
            if record else "NOT CONNECTED")


def temperatures(value, unit):
    c = value if unit == "C" else (value-32)*5/9
    return f"{c:.0f}°C / {c*9/5+32:.0f}°F"


def draw_weather(card, snap, now, units):
    w = snap.weather
    card.text("WEATHER", 0, 0, 23, True)
    card.text(w.location if w else "Set location on NAS", 0, .105, 24, shade=65)
    both = units == "both"
    card.text((temperatures(w.temperature, w.unit) if both else f"{w.temperature:.0f}°{w.unit}") if w else "—°", 0, .23, 49 if both else 76, True)
    card.text(w.condition if w else "No weather data", 0, .47, 27, True)
    card.text((f"H {temperatures(w.high,w.unit)} · L {temperatures(w.low,w.unit)}" if both else f"High {w.high:.0f}° / Low {w.low:.0f}°") if w else "Forecast will appear here", 0, .59, 21)
    forecast = "   ".join(f"{d.day[:3]} {d.high:.0f}°/{d.low:.0f}°" for d in w.forecast[:3]) if w else "Location and units configured on NAS"
    card.text(f"Rain {w.precipitation_percent}% · {forecast} ({w.unit})" if w else forecast, 0, .72, 18, shade=55)
    card.rule(.83)
    card.text(record_time(w, now), 0, .89, 18, shade=65)


def draw_nas(card, snap, now):
    n = snap.nas
    card.text("HOME SERVER", 0, 0, 23, True)
    card.text(n.name if n else "NAS health", 0, .105, 24, shade=65)
    card.text(n.pool_health if n else "NO DATA", 0, .255, 40, True)
    for i, (label, value) in enumerate((("Storage", n.used_percent if n else None), ("CPU", n.cpu_percent if n else None), ("Memory", n.memory_percent if n else None))):
        y = .44 + i*.12
        card.text(label, 0, y, 24)
        card.text(f"{value:.0f}%" if value is not None else "—", 1, y, 24, True, right=True, width=.25)
        left = card.x+card.pad+(card.w-2*card.pad)*.43
        top = card.y+card.pad+y*(card.h-2*card.pad)+5*card.scale
        length = (card.w-2*card.pad)*.29
        card.c.draw.rectangle((left, top, left+length, top+8*card.scale), fill=215)
        if value:
            card.c.draw.rectangle((left, top, left+length*value/100, top+8*card.scale), fill=20)
    card.text(f"{n.alerts} alerts · Up {n.uptime}" if n else "Host metrics unavailable", 0, .80, 21)
    card.text(record_time(n, now), 0, .92, 18, shade=65)


def draw_markets(card, snap, now, tickers, market_columns):
    card.text("WATCHLIST", 0, 0, 23, True)
    card.text("USD · equities: prev close / crypto: 24h", 1, .005, 18, right=True, width=.65)
    quotes = {q.symbol: q for q in snap.quotes}
    columns = market_columns if card.w > card.c.width*.65 else 1
    count = ceil(len(tickers)/columns)
    step = .83/count
    # Larger watchlists need smaller rows, without reducing other widgets' text.
    dense = count > 6
    factor = min(1, 9/count) if dense else 1
    for i, symbol in enumerate(tickers):
        col, row = divmod(i, count)
        width = (1-.04*(columns-1))/columns
        x = col*(width+.04)
        y = .10 + row*step
        q = quotes.get(symbol)
        card.text(symbol, x, y, 30*factor, True, width=width*.50)
        card.text(f"{q.price:,.2f}" if q else "—", x+width, y, 29*factor, True, right=True, width=width*.48)
        if dense:
            card.text(f"{q.change_percent:+.2f}%" if q else "NO DATA", x, y+step*.52, 21*factor, width=width*.27)
            detail = (f"{q.status(now)}{' D' if q.delayed else ''} · {q.as_of.astimezone(now.tzinfo):%m/%d %H:%M}" if q else "Not connected")
            card.text(detail, x+width, y+step*.55, 16*factor, shade=65, right=True, width=width*.70)
        else:
            card.text(f"{q.change:+,.2f}" if q else "Not connected", x, y+step*.32, 23*factor, width=width*.55)
            card.text(f"{q.change_percent:+.2f}%" if q else "NO DATA", x+width, y+step*.32, 23*factor, right=True, width=width*.42)
            detail = record_time(q, now) + (" · DELAYED" if q and q.delayed else "")
            card.text(detail, x, y+step*.64, 17*factor, shade=65, width=width)
    sources = sorted({q.source for q in snap.quotes if q.symbol in tickers})
    card.text("Sources: " + (", ".join(sources) if sources else "not connected") + (" · D = delayed" if dense else ""), 0, .965, 17, shade=65)


def draw_chatgpt(card, snapshot, now):
    usage = snapshot.chatgpt
    card.text("CHATGPT USAGE", 0, 0, 23, True)
    if usage is None:
        card.text("Not connected", 0, .25, 29, True)
        card.text("Sync from your signed-in PC", 0, .52, 22)
        card.text("No account data on this NAS", 0, .88, 18, shade=65)
        return
    def compact(number):
        if number is None: return "—"
        if number >= 1e9: return f"{number/1e9:.1f}B"
        if number >= 1e6: return f"{number/1e6:.1f}M"
        if number >= 1e3: return f"{number/1e3:.0f}K"
        return str(number)
    card.text(f"{compact(usage.lifetime_tokens)} lifetime tokens", 0, .21, 29, True)
    card.text(f"Peak {compact(usage.peak_daily_tokens)}/day · Streak {usage.current_streak_days if usage.current_streak_days is not None else '—'}d", 0, .43, 22)
    limits = f"{usage.limit_name}: {usage.used_percent:.0f}% used" if usage.used_percent is not None else "Usage limits not reported"
    card.text(limits, 0, .63, 22)
    reset = f"Reset {usage.resets_at.astimezone(now.tzinfo):%m/%d %H:%M %Z}" if usage.resets_at else "PC sync; not live"
    card.text(reset, 0, .80, 17, shade=65)
    card.text(record_time(usage, now), 0, .94, 16, shade=65)


def draw_notes(card, layout):
    card.text(layout.notes_title.upper(), 0, 0, 23, True)
    lines = layout.notes or ["Make room for your day.", "Add notes in the web editor."]
    step = .71/max(3, len(lines))
    for i, line in enumerate(lines):
        card.text("· " + line, 0, .22+i*step, 24, width=1)
    card.text("MANUAL NOTES", 0, .94, 16, shade=70)


def draw_device(card, data, now):
    card.text("KINDLE", 0, 0, 23, True)
    status = "Charging" if data.charging else ("On battery" if data.charging is not None else "Power unknown")
    card.text(f"{data.battery}% · {status}" if data.battery is not None else "Battery not reported", 0, .23, 30, True)
    card.text(f"{data.width} × {data.height} · Wi-Fi {str(data.rssi)+' dBm' if data.rssi is not None else '—'}", 0, .48, 22)
    card.text(f"Prior fetch: {data.fetch_seconds}s · Failures: {data.fetch_failures}" if data.fetch_seconds is not None else "Refresh manually from KUAL", 0, .66, 21)
    success = datetime.fromtimestamp(data.last_success_epoch, now.tzinfo).strftime("%m/%d %H:%M") if data.last_success_epoch else "not reported"
    card.text(f"Prior successful fetch: {success}", 0, .87, 18, shade=65)


def render_overview(data, settings, snapshot, now, layout):
    c = Canvas(data.width, data.height, settings)
    c.text("DAYLIGHT / PERSONAL DASHBOARD", .035, .021, 22, True, max_width=.70)
    c.text(f"{data.battery}%" if data.battery is not None else "BATTERY —", .965, .021, 24, True, right=True, max_width=.21)
    c.text(layout.title, .035, .052, 66, True, max_width=.70)
    c.text(now.strftime("%H:%M"), .965, .06, 47, True, right=True, max_width=.23)
    c.text(now.strftime("%A, %B %d, %Y"), .035, .104, 24, color=60, max_width=.65)
    c.text("SAMPLE DATA" if snapshot.demo else "MANUAL REFRESH", .965, .106, 19, True, right=True, max_width=.28)
    rows = widget_rows(layout.widgets)
    weights = [max({"small": 2, "medium": 3, "large": 5}[w.size] for w in row) for row in rows]
    gap = .011 if layout.density == "compact" else .019
    available = .791-gap*(len(rows)-1)
    y = .144
    for row, weight in zip(rows, weights):
        h = available*weight/sum(weights)
        for col, widget in enumerate(row):
            # A lone half card fills the row so it never wastes half the screen.
            w = (.93-gap)/2 if len(row) == 2 else .93
            x = .035+col*(w+gap)
            card = Card(c, (x*c.width, y*c.height, w*c.width, h*c.height), widget.size, layout.density)
            if widget.id == "weather": draw_weather(card, snapshot, now, layout.weather_units)
            elif widget.id == "nas": draw_nas(card, snapshot, now)
            elif widget.id == "markets": draw_markets(card, snapshot, now, layout.tickers, layout.market_columns)
            elif widget.id == "notes": draw_notes(card, layout)
            elif widget.id == "chatgpt": draw_chatgpt(card, snapshot, now)
            else: draw_device(card, data, now)
        y += h+gap
    c.text(f"IMAGE {now:%Y-%m-%d %H:%M %Z} · STATUS AT GENERATION", .035, .952, 19, color=55, max_width=.93)
    c.text("Cached image · KUAL → Dashboard: Next / Previous / Stop", .035, .976, 18, color=55, max_width=.93)
    output = BytesIO()
    c.image.save(output, format="PNG")
    return output.getvalue()
