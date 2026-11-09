"""Validated catalogue persistence and override-aware merging."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .models import Product

def load_cache(path):
    if not path.exists():
        seed = Path(__file__).resolve().parents[2] / "data/catalog-seed.json"
        default = Path(__file__).resolve().parents[2] / "var/plu-catalog/cache.json"
        if path == default and seed.exists():
            return load_cache(seed)
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


