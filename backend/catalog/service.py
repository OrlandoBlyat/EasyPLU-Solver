"""Shared catalogue refresh and downloadable handbook generation."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "var/plu-catalog/cache.json"
_lock = Lock()
_pdf_lock = Lock()
# Keep only the latest handbook in memory; timestamps do not invalidate it.
_pdf_cache = None


def refresh_catalog(user_id):
    from .collector import collect_products
    from .cache import load_cache, merge_cache, save_cache

    live = collect_products(user_id)
    with _lock:
        save_cache(CACHE, merge_cache(live, load_cache(CACHE)))


def export_catalog():
    from .cache import load_cache
    from .pdf import make_pdf

    global _pdf_cache
    # Only hold the catalogue lock while taking a consistent snapshot.
    with _lock:
        products = sorted(load_cache(CACHE).values(), key=lambda product: product.product_id)
    if not products:
        raise ValueError("The catalog is empty. Run a test first.")
    fingerprint = hashlib.sha256(json.dumps(
        [asdict(product) for product in products], sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()
    # Serialize rendering and font registration, without blocking catalogue updates.
    with _pdf_lock:
        if _pdf_cache is not None and _pdf_cache[0] == fingerprint:
            return _pdf_cache[1]
        with TemporaryDirectory(prefix="easyplu-pdf-") as directory:
            output = Path(directory) / "plu-catalog.pdf"
            products.sort(key=lambda product: (product.category.casefold(), int(product.plu), product.name.casefold()))
            make_pdf(products, output, ROOT / "var/plu-catalog/images")
            content = output.read_bytes()
        _pdf_cache = (fingerprint, content)
        return content
