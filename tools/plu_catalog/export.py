"""Fetch EasyPLU products and create a categorized training handbook PDF."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import io
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from urllib.parse import urljoin, urlparse

from PIL import Image, ImageOps
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from back.plu.decryption import decryptPLU  # noqa: E402
from back.plu.solver import BASE_URL, login, session  # noqa: E402
from back.runtime.jobs import job_scope  # noqa: E402

SITE_URL = "https://easy-plu.knowledge-hero.com/"
CATEGORIES_URL = f"{BASE_URL}/plu-learn/product-categories"
CATEGORY_URL = f"{BASE_URL}/plu-learn/product-category/{{category_id}}"
CREATE_SESSION_URL = f"{BASE_URL}/plu-learn/create-new-session"
ITEMS_URL = f"{BASE_URL}/plu-learn/{{session_id}}/execution-items"

# EasyPLU does not currently return category translations from the catalogue
# endpoints for these Slovenian product groups. API names still take priority.
DEFAULT_CATEGORY_NAMES = {
    "1": "Zelenjava",
    "3": "Pekarna",
    "4": "Sadje",
    "13": "Oreščki",
}

CATEGORY_STYLES = {
    "Zelenjava": ("#2E7D32", "leaf"),
    "Pekarna": ("#B56820", "bread"),
    "Sadje": ("#C53D4D", "apple"),
    "Oreščki": ("#76513A", "acorn"),
}
DEFAULT_CATEGORY_STYLE = ("#365E54", "leaf")


@dataclass(frozen=True)
class Product:
    product_id: str
    plu: str
    name: str
    category: str
    image_url: str | None
    ignore: bool = False


def translated_name(value, fallback=None):
    if not isinstance(value, dict):
        return fallback
    translations = value.get("translations")
    if isinstance(translations, dict):
        translation = (
            translations.get("SI")
            or translations.get("sl")
            or translations.get("SL")
            or translations.get("DE")
            or translations.get("de")
        )
        if isinstance(translation, dict):
            name = translation.get("title") or translation.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    for key in ("title", "name"):
        name = value.get(key)
        if isinstance(name, str) and name.strip():
            return name.strip()
    return fallback


def find_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from find_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from find_dicts(child)


def fetch_categories():
    """Return platform category IDs and names; an empty map enables item fallback."""
    for payload in (
        {"activeLanguageLocale": "SI"},
        {"language_id": 1, "activeLanguageLocale": "SI"},
        {},
    ):
        response = session.post(CATEGORIES_URL, json=payload)
        if not response.ok:
            continue
        body = response.json()
        candidates = {}
        for value in find_dicts(body):
            category_id = value.get("id")
            if category_id is None:
                category_id = value.get("productCategoryId")
            if category_id is None:
                category_id = value.get("product_category_id")
            name = translated_name(value)
            if category_id is not None and name:
                candidates[str(category_id)] = name
        if candidates:
            return candidates
    return {}


def fetch_category_name(category_id):
    for payload in ({"activeLanguageLocale": "SI"}, {"language_id": 1}, {}):
        response = session.post(CATEGORY_URL.format(category_id=category_id), json=payload)
        if not response.ok:
            continue
        for value in find_dicts(response.json()):
            name = translated_name(value)
            if name:
                return name
    return None


def create_catalog_session(user_id, category_id=None):
    payload = {
        "product_category_id": category_id,
        "count_selection": 154,
        "user_id": user_id,
        "language_id": 1,
        "execution_type": 1,
        "execution_subtype": 0,
        "is_gold_plu": False,
        "new_plu": None,
        "plu_current_count": 1,
        "top_article_active": False,
        "attribute_group_id": None,
        "ean_active": False,
    }
    response = session.post(CREATE_SESSION_URL, json=payload)
    response.raise_for_status()
    return response.json()["data"]["session_id"]


def fetch_items(session_id):
    response = session.post(
        ITEMS_URL.format(session_id=session_id),
        json={"incrementCurrent": False, "activeLanguageLocale": "SI", "execution_type": 1},
    )
    response.raise_for_status()
    return response.json()["data"]["items"]


def image_url(product):
    keys = (
        "imageSrc", "image_src", "imageUrl", "image_url", "imagePath", "image_path",
        "image", "filename", "fileName", "file",
    )
    for key in keys:
        value = product.get(key)
        if isinstance(value, dict):
            value = value.get("url") or value.get("path") or value.get("filename")
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        if value.startswith(("http://", "https://")):
            return value
        if value.startswith("/"):
            return urljoin(SITE_URL, value)
        return urljoin(SITE_URL, f"plufiles/product/{value}")
    return None


def category_id(product, item):
    for source in (product, item):
        if not isinstance(source, dict):
            continue
        for key in ("productCategoryId", "product_category_id", "categoryId", "category_id"):
            if source.get(key) is not None:
                return str(source[key])
    return None


def item_category_name(product, item):
    for source in (product, item):
        for key in ("productCategory", "product_category", "category"):
            name = translated_name(source.get(key))
            if name:
                return name
    return None


def catalog_plu(product, item):
    """Accept both plaintext catalogue values and encrypted test values."""
    candidates = []
    for source in (product, item):
        if not isinstance(source, dict):
            continue
        for key in ("pluNumber", "plu_number", "number", "value"):
            if source.get(key) is not None:
                candidates.append(source[key])
    for value in candidates:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return str(value)
        if isinstance(value, str):
            value = value.strip()
            if value.isdigit():
                return value
            decrypted = decryptPLU(value)
            if decrypted:
                return decrypted
    return None


def products_from_items(items, categories, forced_category=None, missing_names=None):
    products = []
    skipped = Counter()
    product_keys = set()
    plu_value_types = Counter()
    for item in items:
        if not isinstance(item, dict):
            skipped["invalid item"] += 1
            continue
        raw = item.get("pluNumber") or {}
        if not isinstance(raw, dict):
            skipped["invalid product"] += 1
            continue
        product_keys.update(raw)
        plu_value_types[type(raw.get("pluNumber")).__name__] += 1
        plu = catalog_plu(raw, item)
        name = translated_name(raw)
        if not plu:
            skipped["missing or unreadable PLU"] += 1
        if not name:
            skipped["missing Slovenian name"] += 1
            if missing_names is not None:
                missing_names.append({
                    "category_hint": forced_category,
                    "product_keys": sorted(raw),
                    "item": item,
                })
        if not plu or not name:
            continue
        cat_id = category_id(raw, item)
        category = forced_category or categories.get(cat_id or "") or item_category_name(raw, item)
        if not category:
            category = f"Kategorija {cat_id}" if cat_id else "Brez kategorije"
        product_id = raw.get("id")
        if product_id is None:
            product_id = item.get("pluNumberId")
        if product_id is None:
            product_id = "name:" + name.casefold()
        products.append(Product(
            product_id=str(product_id), plu=plu, name=name, category=category,
            image_url=image_url(raw),
        ))
    if skipped:
        details = ", ".join(f"{count} {reason}" for reason, count in skipped.items())
        print(f"Warning: skipped products ({details})", flush=True)
        print(
            "Catalogue diagnostics: product keys=" + ",".join(sorted(product_keys))
            + "; pluNumber types=" + ",".join(f"{kind}:{count}" for kind, count in plu_value_types.items()),
            flush=True,
        )
    return products


def collect_products(user_id, missing_names=None):
    categories = fetch_categories()
    collected = {}
    if categories:
        print(f"Found {len(categories)} categories", flush=True)
        sources = [(category_id, name) for category_id, name in categories.items()]
    else:
        print("Category list unavailable; deriving categories from product items", flush=True)
        items = fetch_items(create_catalog_session(user_id))
        category_ids = sorted({
            value for item in items
            if isinstance(item, dict)
            for value in [category_id(item.get("pluNumber") or {}, item)]
            if value is not None
        })
        for index, cat_id in enumerate(category_ids, 1):
            print(f"Resolving category {index}/{len(category_ids)}", flush=True)
            name = fetch_category_name(cat_id)
            if name:
                categories[cat_id] = name
            elif cat_id in DEFAULT_CATEGORY_NAMES:
                categories[cat_id] = DEFAULT_CATEGORY_NAMES[cat_id]
        for product in products_from_items(items, categories, missing_names=missing_names):
            collected[product.product_id] = product
        sources = []

    for index, (cat_id, name) in enumerate(sources, 1):
        label = name or "all products"
        print(f"Fetching {index}/{len(sources)}: {label}", flush=True)
        items = fetch_items(create_catalog_session(user_id, cat_id))
        for product in products_from_items(items, categories, name, missing_names=missing_names):
            collected[product.product_id] = product
    if not collected:
        raise RuntimeError("EasyPLU returned no usable products")
    return sorted(collected.values(), key=lambda p: (p.category.casefold(), int(p.plu), p.name.casefold()))


def load_cache(path):
    if not path.exists():
        return {}
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict) or body.get("version") != 1 or not isinstance(body.get("products"), list):
        raise ValueError(f"Invalid catalogue cache format: {path}")
    products = {}
    for index, value in enumerate(body["products"], 1):
        if not isinstance(value, dict):
            raise ValueError(f"Cache product {index} must be an object")
        product_id = value.get("id")
        plu = value.get("plu_number")
        name = value.get("product_name")
        category = value.get("category")
        image = value.get("image_url")
        ignore = value.get("ignore", False)
        if not isinstance(product_id, str) or not product_id:
            raise ValueError(f"Cache product {index} has an invalid id")
        if not isinstance(plu, str) or not plu.isdigit():
            raise ValueError(f"Cache product {index} has an invalid plu_number")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Cache product {index} has an invalid product_name")
        if not isinstance(category, str) or not category.strip():
            raise ValueError(f"Cache product {index} has an invalid category")
        if image is not None and not isinstance(image, str):
            raise ValueError(f"Cache product {index} has an invalid image_url")
        if not isinstance(ignore, bool):
            raise ValueError(f"Cache product {index} has a non-boolean ignore field")
        if product_id in products:
            raise ValueError(f"Duplicate product id in cache: {product_id}")
        products[product_id] = Product(product_id, plu, name.strip(), category.strip(), image, ignore)
    return products


def save_cache(path, products):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "products": [
            {
                "id": product.product_id,
                "plu_number": product.plu,
                "product_name": product.name,
                "category": product.category,
                "image_url": product.image_url,
                "ignore": product.ignore,
            }
            for product in sorted(
                products, key=lambda p: (p.category.casefold(), int(p.plu), p.name.casefold())
            )
        ],
    }
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def save_missing_names(path, entries):
    """Save complete API items that did not contain an extractable Slovenian name."""
    path.parent.mkdir(parents=True, exist_ok=True)
    unique = {}
    for index, entry in enumerate(entries):
        item = entry.get("item") or {}
        identity = item.get("id") or item.get("pluNumberId") or f"item-{index}"
        unique[str(identity)] = entry
    body = {"version": 1, "count": len(unique), "items": list(unique.values())}
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def merge_cache(live_products, cached_products):
    merged = dict(cached_products)
    added = updated = protected = 0
    for live in live_products:
        cached = cached_products.get(live.product_id)
        if cached is None:
            merged[live.product_id] = live
            added += 1
            continue
        if cached.ignore:
            merged[live.product_id] = cached
            if cached != live:
                protected += 1
            continue
        if cached != live:
            updated += 1
        merged[live.product_id] = live
    print(
        f"Cache comparison: {added} added, {updated} updated, "
        f"{protected} protected by ignore=true, {len(merged)} total",
        flush=True,
    )
    return sorted(
        merged.values(), key=lambda p: (p.category.casefold(), int(p.plu), p.name.casefold())
    )


def cached_image(url, cache_dir):
    if not url:
        return None
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".webp"):
        suffix = ".img"
    path = cache_dir / (hashlib.sha256(url.encode()).hexdigest() + suffix)
    try:
        if not path.exists():
            response = session.get(url)
            response.raise_for_status()
            if len(response.content) > 10 * 1024 * 1024:
                return None
            Image.open(io.BytesIO(response.content)).verify()
            path.write_bytes(response.content)
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((900, 900))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    except Exception:
        return None


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


def main():
    parser = argparse.ArgumentParser(description="Create a categorized EasyPLU training PDF.")
    parser.add_argument("--username", help="EasyPLU email or 8-digit Lidl SSO number")
    parser.add_argument("--login-method", choices=("easyplu", "sso"), default="easyplu")
    parser.add_argument("--output", type=Path, default=ROOT / "var/plu-catalog/plu-catalog.pdf")
    parser.add_argument("--cache", type=Path, default=ROOT / "var/plu-catalog/cache.json")
    parser.add_argument(
        "--missing-names",
        type=Path,
        default=ROOT / "var/plu-catalog/missing-names.json",
        help="JSON output for API items without a Slovenian name",
    )
    args = parser.parse_args()
    if os.geteuid() == 0:
        print(
            "Warning: do not run this exporter with sudo; generated cache and PDF files will be owned by root.",
            file=sys.stderr, flush=True,
        )
    username = (args.username or input("EasyPLU email / Lidl SSO number: ")).strip()
    password = getpass.getpass("Password: ")
    if not username or not password:
        parser.error("username and password are required")

    output = args.output.resolve()
    cache_path = args.cache.resolve()
    missing_names_path = args.missing_names.resolve()
    cache_dir = ROOT / "var/plu-catalog/images"
    missing_names = []
    catalogue_fetched = False
    try:
        cached_products = load_cache(cache_path)
        with job_scope(Event(), deadline=time.monotonic() + 1800):
            user_id = login(username, password, login_method=args.login_method)
            catalogue_fetched = True
            live_products = collect_products(user_id, missing_names)
            products = merge_cache(live_products, cached_products)
            save_cache(cache_path, products)
            print(f"Rendering {len(products)} products...", flush=True)
            make_pdf(products, output, cache_dir)
    except KeyboardInterrupt:
        print("Cancelled", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Export failed: {error}", file=sys.stderr)
        return 1
    finally:
        if catalogue_fetched:
            try:
                save_missing_names(missing_names_path, missing_names)
                if missing_names:
                    print(f"Missing-name items saved to {missing_names_path}", flush=True)
            except (OSError, TypeError, ValueError) as error:
                print(f"Could not save missing-name diagnostics: {error}", file=sys.stderr)
    print(f"Cache saved to {cache_path}", flush=True)
    print(f"Created {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
