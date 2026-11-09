"""A4 handbook layout and rendering."""
import io
from pathlib import Path
from collections import defaultdict
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from .images import cached_image

CATEGORY_STYLES = {
    "Zelenjava": ("#2E7D32", "leaf"),
    "Pekarna": ("#B56820", "bread"),
    "Sadje": ("#C53D4D", "apple"),
    "Oreščki": ("#76513A", "acorn"),
}
DEFAULT_CATEGORY_STYLE = ("#365E54", "leaf")


def font_names():
    candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf"),
    )
    regular = next((path for path in candidates if path.exists()), None)
    bold_candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf"),
    )
    bold = next((path for path in bold_candidates if path.exists()), regular)
    if regular and bold:
        pdfmetrics.registerFont(TTFont("CatalogRegular", str(regular)))
        pdfmetrics.registerFont(TTFont("CatalogBold", str(bold)))
        return "CatalogRegular", "CatalogBold"
    return "Helvetica", "Helvetica-Bold"


def fit_lines(text, font, size, width, maximum=2):
    words = text.split()
    lines = []
    current = ""
    while words and len(lines) < maximum:
        word = words.pop(0)
        candidate = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
                current = word
            else:
                lines.append(word)
                current = ""
    if current and len(lines) < maximum:
        lines.append(current)
    if words and lines:
        while lines[-1] and pdfmetrics.stringWidth(lines[-1] + "…", font, size) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


def draw_category_icon(canvas, icon, x, y, size, color):
    """Draw a consistent line icon in a rounded category-color tile."""
    canvas.saveState()
    canvas.setFillColor(HexColor(color))
    canvas.roundRect(x, y, size, size, size * 0.28, fill=1, stroke=0)
    pad = size * 0.2
    ix, iy, inner = x + pad, y + pad, size - 2 * pad
    canvas.setFillColor(HexColor("#FFFFFF"))
    canvas.setStrokeColor(HexColor("#FFFFFF"))
    canvas.setLineWidth(max(1.4, size * 0.075))
    canvas.setLineCap(1)
    canvas.setLineJoin(1)
    if icon == "bread":
        canvas.roundRect(ix, iy + inner * 0.08, inner, inner * 0.72, inner * 0.22, fill=0, stroke=1)
        for offset in (0.34, 0.58, 0.78):
            canvas.line(ix + inner * offset, iy + inner * 0.66, ix + inner * (offset - 0.1), iy + inner * 0.48)
    elif icon == "apple":
        path = canvas.beginPath()
        path.moveTo(ix + inner * 0.5, iy + inner * 0.74)
        path.curveTo(ix + inner * 0.2, iy + inner, ix - inner * 0.05, iy + inner * 0.62, ix + inner * 0.12, iy + inner * 0.25)
        path.curveTo(ix + inner * 0.28, iy - inner * 0.08, ix + inner * 0.45, iy + inner * 0.08, ix + inner * 0.5, iy + inner * 0.1)
        path.curveTo(ix + inner * 0.58, iy + inner * 0.08, ix + inner * 0.75, iy - inner * 0.08, ix + inner * 0.9, iy + inner * 0.25)
        path.curveTo(ix + inner * 1.07, iy + inner * 0.62, ix + inner * 0.8, iy + inner, ix + inner * 0.5, iy + inner * 0.74)
        canvas.drawPath(path, fill=0, stroke=1)
        canvas.line(ix + inner * 0.5, iy + inner * 0.73, ix + inner * 0.58, iy + inner)
        canvas.ellipse(ix + inner * 0.56, iy + inner * 0.78, ix + inner * 0.92, iy + inner, fill=0, stroke=1)
    elif icon == "acorn":
        canvas.ellipse(ix + inner * 0.2, iy, ix + inner * 0.82, iy + inner * 0.72, fill=0, stroke=1)
        canvas.roundRect(ix + inner * 0.1, iy + inner * 0.58, inner * 0.82, inner * 0.27, inner * 0.1, fill=0, stroke=1)
        canvas.line(ix + inner * 0.53, iy + inner * 0.84, ix + inner * 0.64, iy + inner)
    else:
        path = canvas.beginPath()
        path.moveTo(ix, iy + inner * 0.08)
        path.curveTo(ix, iy + inner * 0.66, ix + inner * 0.42, iy + inner, ix + inner, iy + inner * 0.92)
        path.curveTo(ix + inner, iy + inner * 0.35, ix + inner * 0.58, iy, ix, iy + inner * 0.08)
        canvas.drawPath(path, fill=0, stroke=1)
        canvas.line(ix + inner * 0.14, iy + inner * 0.16, ix + inner * 0.82, iy + inner * 0.82)
    canvas.restoreState()


def make_pdf(products, output, cache_dir):
    regular, bold = font_names()
    width, height = A4
    margin = 34
    header_height = 48
    columns, rows = 3, 4
    gap = 10
    card_width = (width - 2 * margin - (columns - 1) * gap) / columns
    card_height = (height - 2 * margin - header_height - (rows - 1) * gap) / rows
    per_page = columns * rows
    grouped = defaultdict(list)
    for product in products:
        grouped[product.category].append(product)

    output.parent.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(output), pagesize=A4, pageCompression=1)
    page_number = 0
    for category in sorted(grouped, key=str.casefold):
        accent, icon = CATEGORY_STYLES.get(category, DEFAULT_CATEGORY_STYLE)
        category_products = grouped[category]
        for offset in range(0, len(category_products), per_page):
            page_number += 1
            header_baseline = height - margin - 1
            draw_category_icon(canvas, icon, margin, header_baseline - 8, 24, accent)
            canvas.setFillColor(HexColor(accent))
            canvas.setFont(bold, 17)
            canvas.drawString(margin + 34, header_baseline, category)
            canvas.setFillColor(HexColor(accent))
            canvas.roundRect(margin, header_baseline - 17, width - 2 * margin, 3, 1.5, fill=1, stroke=0)
            canvas.setFillColor(HexColor("#66736D"))
            canvas.setFont(regular, 8)
            canvas.drawRightString(width - margin, header_baseline, str(page_number))

            for position, product in enumerate(category_products[offset:offset + per_page]):
                row, column = divmod(position, columns)
                x = margin + column * (card_width + gap)
                y = height - margin - header_height - (row + 1) * card_height - row * gap
                canvas.setFillColor(HexColor("#F4F7F5"))
                canvas.roundRect(x, y, card_width, card_height, 8, fill=1, stroke=0)
                canvas.setFillColor(HexColor(accent))
                canvas.roundRect(x, y + card_height - 4, card_width, 4, 2, fill=1, stroke=0)

                image_data = cached_image(product.image_url, cache_dir)
                image_h = card_height * 0.57
                if image_data:
                    with Image.open(io.BytesIO(image_data)) as image:
                        iw, ih = image.size
                    scale = min((card_width - 18) / iw, (image_h - 10) / ih)
                    draw_w, draw_h = iw * scale, ih * scale
                    canvas.drawImage(
                        ImageReader(io.BytesIO(image_data)), x + (card_width - draw_w) / 2,
                        y + card_height - image_h + (image_h - draw_h) / 2,
                        draw_w, draw_h, preserveAspectRatio=True, mask="auto",
                    )
                else:
                    canvas.setFillColor(HexColor("#DDE5E0"))
                    canvas.roundRect(x + 9, y + card_height - image_h + 5, card_width - 18, image_h - 10, 5, fill=1, stroke=0)

                canvas.setFillColor(HexColor(accent))
                canvas.setFont(bold, 19)
                canvas.drawString(x + 10, y + 35, product.plu)
                canvas.setFillColor(HexColor("#27342E"))
                canvas.setFont(regular, 8.5)
                for line_index, line in enumerate(fit_lines(product.name, regular, 8.5, card_width - 20)):
                    canvas.drawString(x + 10, y + 22 - line_index * 10, line)
            canvas.showPage()
    canvas.save()


