"""Session-scoped PLU decoding. Crypto is imported only in decryption mode."""
import base64
import binascii
import json
import re
from back.core.debug import log

_KEY = b"U2x2QdvosFTtk5nL0ejrKqLFP1tUDtSt"
_IV = _KEY[:16]


def decryptPLU(encrypted_value):
    if not isinstance(encrypted_value, str) or not encrypted_value or len(encrypted_value) > 4096:
        return None
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7
        inner = base64.b64decode(encrypted_value, validate=True)
        ciphertext = base64.b64decode(inner, validate=True)
        if not ciphertext or len(ciphertext) % 16:
            return None
        decryptor = Cipher(algorithms.AES(_KEY), modes.CBC(_IV)).decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = PKCS7(128).unpadder()
        value = (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")
        # The website may encode a JSON string; keep plain digit strings intact.
        if value.startswith('"'):
            value = json.loads(value)
        return value if isinstance(value, str) and re.fullmatch(r"[0-9]+", value) else None
    except ImportError:
        raise RuntimeError("Decryption mode requires cryptography; run scripts/install.bash") from None
    except (ValueError, UnicodeError, binascii.Error):
        return None


class DecryptedProducts:
    def __init__(self):
        self.session_id = None
        self.products = {}

    def update(self, session_id, items):
        # Each response is a snapshot; replace it to avoid stale entries.
        products = {}
        for item in items:
            product = item.get("pluNumber") or {}
            if not isinstance(product, dict):
                product = {}
            product_id = item.get("pluNumberId")
            encrypted = product.get("pluNumber")
            plu = decryptPLU(encrypted)
            translations = product.get("translations") or {}
            translation = (translations.get("SI") or {}) if isinstance(translations, dict) else {}
            name = (translation.get("title") or translation.get("name")) if isinstance(translation, dict) else None
            if product_id is not None:
                products[str(product_id)] = {"id": product_id, "name": name,
                                             "encrypted": encrypted, "plu": plu}
            if plu is None:
                log("solver", "[PLU] Decryption failed for product", product_id)
        self.session_id = session_id
        self.products = products
        log("solver", f"[PLU] Loaded {len(products)} products")
        if products and all(product["plu"] is not None for product in products.values()):
            log("solver", "[PLU] Decryption successful")

    def get(self, product_id):
        return self.products.get(str(product_id), {}).get("plu")
