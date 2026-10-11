"""Small Markdown-to-Pillow renderer: no HTML engine, remote assets or execution.

Headings, lists, quotes, bold, inline/fenced code and link labels are supported.
Layout is measured before drawing and always clipped to the widget's content box.
"""
import re
from PIL import Image, ImageDraw
from .renderer import font


def blocks(source):
    fenced = False
    for line in source.expandtabs(4).splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            yield line or " ", 1, False, True
            continue
        heading = re.match(r"^\s{0,3}(#{1,3})\s+(.*)", line)
        if heading:
            yield heading[2], {1: 1.45, 2: 1.25, 3: 1.1}[len(heading[1])], True, False
        else:
            line = re.sub(r"^\s*[-*+]\s+", "\u2022 ", line)
            line = re.sub(r"^\s*>\s?", "\u2502 ", line)
            # Links/images become their labels. URLs are never fetched.
            line = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", line)
            yield line, 1, False, False


def runs(text, bold, code):
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        strong = part.startswith("**") and part.endswith("**")
        mono = part.startswith("`") and part.endswith("`")
        yield part[2:-2] if strong else part[1:-1] if mono else part, bold or strong, code or mono


def measure(draw, source, width, base, path):
    result = []
    for text, factor, strong, code in blocks(source):
        pixels = max(8, round(base*factor))
        line, x = [], 0
        line_height = max(10, round(pixels*1.4))
        if not text:
            result.append(([], max(6, round(base*.5))))
            continue
        for part, bold, shaded in runs(text, strong, code):
            face = font(pixels, path, bold)
            for word in re.findall(r"\s+|\S+", part):
                length = draw.textlength(word, font=face)
                if x and x+length > width:
                    result.append((line, line_height)); line, x = [], 0
                if not x and word.isspace():
                    continue
                # Hard-wrap long tokens as well as ordinary words.
                while word:
                    low, high = 1, len(word)
                    while low < high:
                        mid = (low+high+1)//2
                        if draw.textlength(word[:mid], font=face) <= width-x:
                            low = mid
                        else:
                            high = mid-1
                    take = low
                    piece = word[:take]
                    length = draw.textlength(piece, font=face)
                    line.append((x, piece, face, shaded)); x += length
                    word = word[take:]
                    if word:
                        result.append((line, line_height)); line, x = [], 0
        if line:
            result.append((line, line_height))
    return result


def markdown_image(source, width, height, path="", base=24, overflow="shrink"):
    image = Image.new("L", (max(1, width), max(1, height)), 250)
    draw = ImageDraw.Draw(image)
    minimum = max(8, round(base*.72))
    sizes = range(base, minimum-1, -1) if overflow == "shrink" else [base]
    for size in sizes:
        rows = measure(draw, source, image.width, size, path)
        if sum(h for _, h in rows) <= image.height:
            break
    truncated = sum(h for _, h in rows) > image.height
    marker_height = round(size*1.4) if truncated else 0
    y = 0
    for line, line_height in rows:
        if y+line_height > image.height-marker_height:
            break
        for x, text, face, shaded in line:
            if shaded:
                draw.rectangle((x, y, x+draw.textlength(text,font=face), y+line_height-1), fill=226)
            draw.text((round(x), y), text, font=face, fill=0, anchor="lt")
        y += line_height
    if truncated and image.height >= marker_height:
        draw.text((0, min(y, image.height-marker_height)), "\u2026", font=font(size,path), fill=50, anchor="lt")
    return image, truncated


def draw_markdown(card, source, overflow):
    heading = card.title or "NOTES"
    card.text(heading, 0, 0, 23, True)
    top = round(card.pad + 36*card.scale)
    width = max(1, int(card.w-2*card.pad))
    height = max(1, int(card.h-card.pad-top))
    image, _ = markdown_image(source, width, height, card.c.settings.font_path,
                              max(10, round(28*card.scale*card.type_scale)), overflow)
    card.c.image.paste(image, (round(card.pad), top))
