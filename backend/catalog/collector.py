"""Collect and normalize products from EasyPLU."""
from collections import Counter
from urllib.parse import urljoin
from backend.tests_runner.decryption import decryptPLU
from backend.auth.client import BASE_URL, session
from .models import Product

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


