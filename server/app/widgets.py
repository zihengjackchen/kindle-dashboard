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
                                      radius=max(3, int(22 * canvas.scale)), fill=250, outline=0, width=1)

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


def temperatures(value, unit):
    c = value if unit == "C" else (value-32)*5/9
    return f"{c:.0f}°C / {c*9/5+32:.0f}°F"


def selected(widget):
    from .layout import DEFAULT_FIELDS
    return DEFAULT_FIELDS[widget.id] if widget.fields is None else widget.fields


def lines(card, title, values):
    card.text(title, 0, 0, 23, True)
    step = .80/max(3, len(values))
    for i, (label, value) in enumerate(values):
        y = .16 + i*step
        size = min(29, 145/max(5, len(values)))
        card.text(label, 0, y, size, shade=65, width=.48)
        card.text(value, 1, y, size, True, right=True, width=.49)


def show(value, suffix=""):
    if value is None: return "—"
    if isinstance(value, float): return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def draw_weather(card, snap, now, units, fields):
    w = snap.weather
    card.text("WEATHER", 0, 0, 23, True)
    if not w:
        card.text("Weather unavailable", 0, .28, 30, True)
        return
    temp = lambda v: temperatures(v, w.unit) if units == "both" else f"{v:.0f}°{w.unit}"
    values = {"location":w.location,"temperature":temp(w.temperature),"condition":w.condition,
              "high_low":f"H {temp(w.high)}  L {temp(w.low)}",
              "feels_like":f"Feels like {temp(w.feels_like)}" if w.feels_like is not None else "Feels like —",
              "precipitation":f"Rain {w.precipitation_percent}%",
              "forecast":"   ".join(f"{d.day[:3]} {temp(d.high)}" for d in w.forecast[:2])}
    y = .13
    # Give the temperature more room; field toggles reclaim the remaining space.
    weight = len(fields)+1.2*int("temperature" in fields)
    for key in fields:
        card.text(values[key], 0, y, 48 if key == "temperature" else 24,
                  key in ("temperature", "condition"), width=1)
        y += .79/max(1,weight)*(2.2 if key == "temperature" else 1)


def draw_markets(card, snap, now, tickers, market_columns, fields):
    card.text("WATCHLIST", 0, 0, 23, True)
    quotes = {q.symbol:q for q in snap.quotes}
    columns = market_columns if card.w > card.c.width*.65 else 1
    count = ceil(len(tickers)/columns)
    step = .87/count
    factor = min(1, 10/count)
    for i, symbol in enumerate(tickers):
        col,row = divmod(i,count)
        width = (1-.045*(columns-1))/columns
        x,y = col*(width+.045), .10+row*step
        q = quotes.get(symbol)
        card.text(symbol, x, y, 31*factor, True, width=width*.50)
        if "price" in fields:
            card.text(f"{q.price:,.2f}" if q else "—", x+width, y, 30*factor, True, right=True, width=width*.49)
        if "change" in fields:
            card.text(f"{q.change:+,.2f}" if q else "—", x, y+step*.44, 24*factor, width=width*.49)
        if "percent" in fields:
            card.text(f"{q.change_percent:+.2f}%" if q else "—", x+width, y+step*.44, 24*factor, right=True, width=width*.49)
        if row < count-1:
            yy = card.y+card.pad+(y+step*.85)*(card.h-2*card.pad)
            left=card.x+card.pad+x*(card.w-2*card.pad)
            card.c.draw.line((left,yy,left+width*(card.w-2*card.pad),yy),fill=210)


def draw_nas(card, snap, now, fields):
    n = snap.nas
    labels={"pool_health":"Pool", "used_percent":"Storage used", "cpu_percent":"CPU", "memory_percent":"Memory used", "alerts":"Alerts", "uptime":"Uptime", "version":"TrueNAS"}
    metric_labels={"memory_available_gib":"RAM available","memory_total_gib":"RAM total","pool_free_gib":"Pool free","pool_size_gib":"Pool size","cpu_temperature_c":"CPU temperature"}
    values=[]
    for key in fields:
        value=getattr(n,key,None) if n and key in labels else n.metrics.get(key) if n else None
        suffix="%" if key.endswith("percent") else " GiB" if key.endswith("gib") else " Mb/s" if key.endswith("mbps") else " °C" if key.endswith("temperature_c") else ""
        values.append((labels.get(key,metric_labels.get(key,key.replace("_"," ").capitalize())),show(value,suffix)))
    lines(card,"HOME SERVER",values)


def draw_backup(card,snap,now,fields):
    backups=snap.nas.backups if snap.nas else []
    if not backups:
        lines(card,"BACKBLAZE",[("Backup", "Not connected")]); return
    b=backups[0]
    def stamp(value):
        return value.astimezone(now.tzinfo).strftime("%b %d %H:%M") if value else "Unknown"
    values={"name":b.name,"state":b.state,"last_success":stamp(b.last_success),"last_run":stamp(b.last_run),
            "duration":show(b.duration_seconds," s"),"schedule":b.schedule,"progress":show(b.percent,"%"),
            "transfer":b.transfer or "—","enabled":"Yes" if b.enabled else "No"}
    lines(card,"BACKBLAZE",[(key.replace("_"," ").capitalize(),values[key]) for key in fields])


def draw_notes(card,layout,fields):
    card.text(layout.notes_title.upper(),0,0,23,True)
    if "notes" in fields:
        for i,line in enumerate(layout.notes): card.text("· "+line,0,.20+i*.15,24,width=1)


def draw_device(card,data,now,fields):
    values={"battery":show(data.battery,"%"),"charging":"Charging" if data.charging else "On battery" if data.charging is not None else "Unknown",
            "rssi":show(data.rssi," dBm"),"resolution":f"{data.width} × {data.height}",
            "last_success":datetime.fromtimestamp(data.last_success_epoch,now.tzinfo).strftime("%m/%d %H:%M") if data.last_success_epoch else "—"}
    for key in fields:
        if key not in values: values[key]=show(getattr(data,key,None))
    lines(card,"KINDLE",[(key.replace("_"," ").capitalize(),values[key]) for key in fields])


def render_overview(data, settings, snapshot, now, layout):
    c=Canvas(data.width,data.height,settings)
    rows=widget_rows(layout.widgets)
    weights=[max({"small":2,"medium":3,"large":7}[w.size] for w in row) for row in rows]
    gap=.010 if layout.density=="compact" else .018
    available=.936-gap*(len(rows)-1)
    y=.016
    records=[]
    for row,weight in zip(rows,weights):
        h=available*weight/sum(weights)
        for col,widget in enumerate(row):
            w=(.956-gap)/2 if len(row)==2 else .956
            card=Card(c,((.022+col*(w+gap))*c.width,y*c.height,w*c.width,h*c.height),widget.size,layout.density)
            fields=selected(widget)
            if widget.id=="weather":
                draw_weather(card,snapshot,now,layout.weather_units,fields); records.append(snapshot.weather)
            elif widget.id=="nas":
                draw_nas(card,snapshot,now,fields); records.append(snapshot.nas)
            elif widget.id=="backup":
                draw_backup(card,snapshot,now,fields); records.append(snapshot.nas)
            elif widget.id=="markets":
                draw_markets(card,snapshot,now,layout.tickers,layout.market_columns,fields)
                quotes={q.symbol:q for q in snapshot.quotes}
                records.extend(quotes.get(t) for t in layout.tickers)
            elif widget.id=="notes": draw_notes(card,layout,fields)
            else: draw_device(card,data,now,fields)
        y+=h+gap
    warning=" · Sample data" if snapshot.demo else ""
    stale=[r for r in records if r and r.status(now)!="CURRENT"]
    if stale: warning+=" · Older data " + min(r.as_of for r in stale).astimezone(now.tzinfo).strftime("%m/%d %H:%M")
    if any(r is None for r in records): warning+=" · Some data unavailable"
    c.text(f"Updated {now:%m/%d %H:%M %Z}"+warning,.024,.971,20,color=65,max_width=.952)
    output=BytesIO(); c.image.save(output,format="PNG")
    return output.getvalue()
