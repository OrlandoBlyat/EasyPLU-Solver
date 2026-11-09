import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.catalog import service as catalog
from backend.catalog.models import Product
from backend.catalog.images import cached_image
from backend.catalog.cache import load_cache, save_cache
from PIL import Image


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.saved_pdf_cache = catalog._pdf_cache
        catalog._pdf_cache = None
        self.addCleanup(setattr, catalog, "_pdf_cache", self.saved_pdf_cache)

    def test_pdf_reuse_and_product_change_invalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            product = Product("1", "100", "Jabolko", "Sadje", None)
            save_cache(cache, [product])
            def render(products, output, images):
                self.assertTrue(catalog._lock.acquire(blocking=False))
                catalog._lock.release()
                output.write_bytes(b"%PDF-test-" + products[0].plu.encode())
            with patch.object(catalog, "CACHE", cache), patch(
                "backend.catalog.pdf.make_pdf", side_effect=render,
            ) as make_pdf:
                first = catalog.export_catalog()
                # A refresh with identical product data should reuse the PDF.
                save_cache(cache, [product])
                self.assertEqual(catalog.export_catalog(), first)
                self.assertEqual(make_pdf.call_count, 1)
                save_cache(cache, [Product("1", "200", "Jabolko", "Sadje", None)])
                self.assertNotEqual(catalog.export_catalog(), first)
                self.assertEqual(make_pdf.call_count, 2)

    def test_processed_image_reused_without_opening_original(self):
        with tempfile.TemporaryDirectory() as directory:
            images = Path(directory)
            url = "https://example.com/apple.png"
            key = hashlib.sha256(url.encode()).hexdigest()
            Image.new("RGB", (1200, 1000), "red").save(images / (key + ".png"))
            first = cached_image(url, images)
            self.assertIsNotNone(first)
            self.assertTrue((images / (key + ".pdf-v1.jpg")).exists())
            with patch("backend.catalog.images.Image.open", side_effect=AssertionError("Reprocessed image")):
                self.assertEqual(cached_image(url, images), first)

    def test_refresh_preserves_overrides_and_missing_products(self):
        protected = Product("1", "100", "Protected", "Sadje", None, True)
        missing = Product("2", "200", "Missing", "Sadje", None)
        added = Product("3", "300", "New", "Sadje", None)
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            save_cache(cache, [protected, missing])
            with patch.object(catalog, "CACHE", cache), patch(
                "backend.catalog.collector.collect_products",
                return_value=[Product("1", "999", "Changed", "Sadje", None), added],
            ) as collect:
                catalog.refresh_catalog("user")
            collect.assert_called_once_with("user")
            self.assertEqual(load_cache(cache), {"1": protected, "2": missing, "3": added})

    def test_export_produces_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            save_cache(cache, [Product("1", "100", "Jabolko", "Sadje", None)])
            with patch.object(catalog, "CACHE", cache):
                content = catalog.export_catalog()
            self.assertTrue(content.startswith(b"%PDF-"))
            self.assertTrue(content.rstrip().endswith(b"%%EOF"))

    def test_empty_catalog_requires_test(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(catalog, "CACHE", Path(directory) / "missing.json"):
                with self.assertRaisesRegex(ValueError, "Najprej"):
                    catalog.export_catalog()


if __name__ == "__main__":
    unittest.main()
