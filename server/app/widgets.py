"""Dense, grayscale cards. Every datum and freshness label is rendered on the NAS."""
from datetime import datetime
from io import BytesIO
from math import ceil
from copy import copy
from PIL import Image, ImageDraw

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


def widget_slots(widgets):
    """Two-column grid; explicit cells are reserved before auto-placement."""
    if all(widget.row is None for widget in widgets):
        return [[(w, i, 1 if len(row) == 2 else 2) for i, w in enumerate(row)]
                for row in widget_rows(widgets)]
    cells, placements = set(), []
    for widget in sorted(widgets, key=lambda w: w.row is None):
        span = 2 if widget.width == "full" else 1
        if widget.row is not None:
            row, col = widget.row-1, widget.column-1
        else:
            row, col = next((r, c) for r in range(24) for c in range(3-span)
                            if all((r, c+i) not in cells for i in range(span)))
        cells.update((row, col+i) for i in range(span))
        placements.append((row, widget, col, span))
    return [[(w, col, span) for r, w, col, span in placements if r == row]
            for row in range(max(r for r, *_ in placements)+1)]


class Card:
    def __init__(self, canvas, bounds, size, density):
        self.destination = canvas
        self.origin = (round(bounds[0]), round(bounds[1]))
        self.x, self.y, self.w, self.h = 0, 0, bounds[2], bounds[3]
        self.c = copy(canvas)
        self.c.image = Image.new("L", (ceil(self.w), ceil(self.h)), 255)
        self.c.draw = ImageDraw.Draw(self.c.image)
        self.pad = min(22 * canvas.scale, self.w * .045)
        self.scale = min(canvas.width / 1236, canvas.height / 1400, self.w / 480, self.h / 190)
        self.type_scale = 1 if density == "compact" else 1.12
        self.title = ""
        self.c.draw.rounded_rectangle((0, 0, self.w-1, self.h-1),
                                      radius=max(3, int(22 * canvas.scale)), fill=250, outline=0, width=1)

    def finish(self):
        self.destination.image.paste(self.c.image, self.origin)

    def text(self, value, x, y, size=28, bold=False, shade=0, right=False, width=.92):
        if x == 0 and y == 0 and self.title:
            value = self.title
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
    if card.w > card.c.width*.65 and len(values) >= 3:
        columns = 3 if len(values) >= 9 or len(values) == 3 else 2
        count = ceil(len(values)/columns)
        step = .82/count
        factor = min(1, step*(card.h-2*card.pad)/(88*card.scale*card.type_scale))
        for i, (label, value) in enumerate(values):
            row, col = divmod(i, columns)
            x, y = col/columns, .14+row*step
            card.text(label, x, y, 23*factor, shade=65, width=.92/columns)
            card.text(value, x, y+step*.36, 34*factor, True, width=.92/columns)
        return
    columns = 1
    count = max(1, ceil(len(values)/columns))
    # Bound line spacing instead of spreading a handful of metrics down a whole screen.
    step = min(.80/max(3, count), 48*card.scale/(card.h-2*card.pad))
    start = max(.10, 42*card.scale/(card.h-2*card.pad))
    for i, (label, value) in enumerate(values):
        col, row = divmod(i, count)
        x = col*.53
        width = .47 if columns == 2 else 1
        y = start + row*step
        size = min(29, step*(card.h-2*card.pad)/(card.scale*1.5))
        card.text(label, x, y, size, shade=65, width=width*.49)
        card.text(value, x+width, y, size, True, right=True, width=width*.49)


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
    if card.w > card.c.width*.65 and card.h > 400*card.scale:
        # A dedicated weather page uses a hero and forecast tiles, not six stretched lines.
        y = .09
        for key in fields:
            if key == "forecast":
                continue
            card.text(values[key], 0, y, 76 if key == "temperature" else 29,
                      key in ("temperature", "condition"), width=1)
            y += .13 if key == "temperature" else .065
        if "forecast" in fields:
            y = max(.58, y+.04)
            card.rule(y-.03)
            forecasts = w.forecast[:4]
            for i, day in enumerate(forecasts):
                width = 1/max(1, len(forecasts))
                x = i*width
                card.text(day.day, x, y, 27, True, width=width*.94)
                card.text(day.condition, x, y+.075, 24, width=width*.94)
                card.text(temp(day.high), x, y+.15, 28, True, width=width*.94)
                card.text(temp(day.low), x, y+.22, 24, shade=65, width=width*.94)
            if not forecasts:
                card.text("Forecast unavailable", 0, y, 26)
        return
    y = .13
    # Give the temperature more room; field toggles reclaim the remaining space.
    weight = len(fields)+1.2*int("temperature" in fields)
    for key in fields:
        card.text(values[key], 0, y, 46 if key == "temperature" else 23,
                  key in ("temperature", "condition"), width=1)
        y += .79/max(1,weight)*(2.2 if key == "temperature" else 1)


def draw_markets(card, snap, now, tickers, market_columns, fields):
    card.text("WATCHLIST", 0, 0, 23, True)
    quotes = {q.symbol:q for q in snap.quotes}
    columns = market_columns if card.w > card.c.width*.65 else 1
    count = ceil(len(tickers)/columns)
    step = .87/count
    factor = min(1, step*(card.h-2*card.pad)/(68*card.scale*card.type_scale))
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
    metric_labels={"memory_available_gib":"RAM available","memory_total_gib":"RAM total","pool_free_gib":"Pool free","pool_size_gib":"Pool size","cpu_temperature_c":"CPU temperature",
                   "network_rx_mbps":"Network down", "network_tx_mbps":"Network up",
                   "disk_read_mbps":"Disk read", "disk_write_mbps":"Disk write", "cpu_iowait_percent":"I/O wait"}
    values=[]
    for key in fields:
        value=getattr(n,key,None) if n and key in labels else n.metrics.get(key) if n else None
        suffix="%" if key.endswith("percent") else " GiB" if key.endswith("gib") else " Mb/s" if key.endswith("mbps") else " °C" if key.endswith("temperature_c") else ""
        values.append((labels.get(key,metric_labels.get(key,key.replace("_"," ").capitalize())),show(value,suffix)))
    lines(card,"HOME SERVER",values)


def draw_backup(card,snap,now,fields,index=0):
    backups=snap.nas.backups if snap.nas else []
    if index >= len(backups):
        lines(card,"BACKBLAZE",[("Backup", "Not connected")]); return
    b=backups[index]
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
    for key in ("external_power", "sleep_inhibited"):
        value=getattr(data,key,None)
        values[key]="Yes" if value is True else "No" if value is False else "Unknown"
    values["power_policy"]={"native-sleep":"Native sleep", "plugged-in":"Stay on when plugged"}.get(data.power_policy,"Unknown")
    for key in fields:
        if key not in values: values[key]=show(getattr(data,key,None))
    labels={"rssi":"Wi-Fi signal", "charging":"Power", "frontlight":"Frontlight", "uptime_seconds":"Uptime (s)",
            "storage_free_mib":"Free space (MiB)", "fetch_seconds":"Download (s)", "fetch_failures":"Fetch failures",
            "external_power":"External power", "sleep_inhibited":"Idle sleep held", "power_policy":"Power policy"}
    lines(card,"KINDLE",[(labels.get(key,key.replace("_"," ").capitalize()),values[key]) for key in fields])


def render_overview(data, settings, snapshot, now, layout):
    c=Canvas(data.width,data.height,settings)
    rows=widget_slots(layout.widgets)
    weights=[max(({"small":2,"medium":3,"large":7}[w.size] for w, _, _ in row), default=2) for row in rows]
    gap=.010 if layout.density=="compact" else .018
    available=.936-gap*(len(rows)-1)
    y=.016
    records=[]
    for row,weight in zip(rows,weights):
        h=available*weight/sum(weights)
        for widget,col,span in row:
            unit=(.956-gap)/2
            w=unit if span==1 else .956
            card=Card(c,((.022+col*(unit+gap))*c.width,y*c.height,w*c.width,h*c.height),widget.size,layout.density)
            card.title=widget.title
            fields=selected(widget)
            if widget.id=="weather":
                draw_weather(card,snapshot,now,widget.weather_units or layout.weather_units,fields); records.append(snapshot.weather)
            elif widget.id=="nas":
                draw_nas(card,snapshot,now,fields); records.append(snapshot.nas)
            elif widget.id=="backup":
                draw_backup(card,snapshot,now,fields,widget.backup_index); records.append(snapshot.nas)
            elif widget.id=="markets":
                tickers=widget.tickers or layout.tickers
                draw_markets(card,snapshot,now,tickers,widget.market_columns or layout.market_columns,fields)
                quotes={q.symbol:q for q in snapshot.quotes}
                records.extend(quotes.get(t) for t in tickers)
            elif widget.id=="notes": draw_notes(card,layout.model_copy(update={"notes":widget.notes}) if widget.notes is not None else layout,fields)
            elif widget.id=="markdown":
                from .markdown_widget import draw_markdown
                draw_markdown(card,widget.content if "content" in fields else "",widget.overflow)
            else: draw_device(card,data,now,fields)
            card.finish()
        y+=h+gap
    warning=" · Sample data" if snapshot.demo else ""
    stale=[r for r in records if r and r.status(now)!="CURRENT"]
    if stale: warning+=" · Older data " + min(r.as_of for r in stale).astimezone(now.tzinfo).strftime("%m/%d %H:%M")
    if any(r is None for r in records): warning+=" · Some data unavailable"
    c.text(f"Updated {now:%m/%d %H:%M %Z}"+warning,.024,.971,20,color=65,max_width=.952)
    output=BytesIO(); c.image.save(output,format="PNG")
    return output.getvalue()
