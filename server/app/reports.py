"""Read the existing Discord publisher archive and paginate its exact Markdown.

No Discord credentials, model calls, URL fetches, or report rewriting.
"""
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
import json
import logging
from pathlib import Path
import re
from threading import Lock

from PIL import Image, ImageDraw, ImageFont

from .markdown_widget import measure

MAX_SOURCE_BYTES = 1_000_000
MAX_TEXT_CHARS = 40_000
MAX_REPORT_PAGES = 27  # Five dashboard pages plus reports: 32 validated client pages.
logger = logging.getLogger("dashboard")


@dataclass(frozen=True)
class Report:
    day: str
    generated_at: str
    content: str


class ReportStore:
    def __init__(self, directory=""):
        self.directory = Path(directory) if directory else None
        self.previous = None
        self.lock = Lock()

    def get(self):
        with self.lock:
            if self.directory is None:
                return self.previous
            try:
                candidates = sorted((p for p in self.directory.iterdir()
                                     if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", p.name)), reverse=True)
                for path in candidates:
                    try:
                        if path.is_symlink() or not path.is_file():
                            continue
                        with path.open("rb") as stream:
                            raw = stream.read(MAX_SOURCE_BYTES + 1)
                        if len(raw) > MAX_SOURCE_BYTES:
                            raise ValueError("Archive exceeds size limit")
                        value = json.loads(raw)
                        day = date.fromisoformat(value["local_date"]).isoformat()
                        created = value["created_at"]
                        if day != path.stem or datetime.fromisoformat(created.replace("Z", "+00:00")).tzinfo is None:
                            raise ValueError("Invalid report timestamp")
                        text = value["content"]
                        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_CHARS:
                            raise ValueError("Invalid Markdown length")
                        self.previous = Report(day, created, text)
                        return self.previous
                    except (KeyError, TypeError, ValueError, OSError):
                        logger.warning("Invalid digest archive date=%s; retaining older report", path.stem)
            except OSError:
                logger.warning("Digest archive unavailable; retaining previous report")
            return self.previous


@lru_cache(maxsize=64)
def report_font(size, bold=False, italic=False, cjk=False):
    if cjk:
        suffix = "Bold" if bold else "Regular"
        paths = [f"/usr/share/fonts/opentype/noto/NotoSansCJK-{suffix}.ttc", "C:/Windows/Fonts/msyh.ttc"]
    else:
        suffix = "-BoldItalic" if bold and italic else "-Bold" if bold else "-Italic" if italic else ""
        paths = [f"/usr/share/fonts/truetype/dejavu/DejaVuSerif{suffix}.ttf",
                 "C:/Windows/Fonts/" + ("georgiaz.ttf" if bold and italic else "georgiab.ttf" if bold else "georgiai.ttf" if italic else "georgia.ttf")]
    for path in paths:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    if cjk:
        raise ValueError("Report needs an installed CJK font")
    return ImageFont.load_default(size=size)


def paginate(rows, height):
    pages, current, used = [], [], 0
    for line, line_height in rows:
        if line_height > height:
            raise ValueError("Report line exceeds page height")
        if current and used + line_height > height:
            pages.append(current)
            current, used = [], 0
        # Keep all text; only discard whitespace at page boundaries.
        if not current and not line:
            continue
        current.append((line, line_height))
        used += line_height
    if current:
        pages.append(current)
    if len(pages) > MAX_REPORT_PAGES:
        raise ValueError("Report exceeds 27 pages; previous bundle retained")
    return pages or [[]]


@lru_cache(maxsize=2)
def render_report(report, width, height, base=30):
    # Fixed readable type; no shrink-to-fit or truncation. Images contain only
    # the Markdown and a small source-date/page footer, never an added title.
    scale = width / 1056
    size = max(14, round(base * scale))
    margin = max(10, round(24 * scale))
    footer = max(25, round(40 * scale))
    content_height = height - 2 * margin - footer
    cjk = any("\u2e80" <= c <= "\u9fff" for c in report.content)
    face = lambda pixels, bold, italic: report_font(pixels, bold, italic, cjk)
    rows = measure(ImageDraw.Draw(Image.new("L", (1, 1))), report.content,
                   width - 2 * margin, size, "", face)
    pages = paginate(rows, content_height)
    images = []
    for index, page in enumerate(pages):
        image = Image.new("L", (width, height), 255)
        draw = ImageDraw.Draw(image)
        y = margin
        for line, line_height in page:
            for x, text, font, shaded in line:
                if shaded:
                    draw.rectangle((margin+x, y, margin+x+draw.textlength(text, font=font), y+line_height-1), fill=235)
                draw.text((round(margin+x), y), text, font=font, fill=0, anchor="lt")
            y += line_height
        bottom = height-margin-footer
        draw.line((margin, bottom, width-margin, bottom), fill=160)
        small = report_font(max(11, round(19*scale)))
        draw.text((margin, bottom+8), "Report " + report.day, font=small, fill=60, anchor="lt")
        draw.text((width-margin, bottom+8), f"{index+1} / {len(pages)}", font=small, fill=60, anchor="rt")
        out = BytesIO()
        image.save(out, format="PNG", optimize=True)
        images.append(out.getvalue())
    return tuple(images)
