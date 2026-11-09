"""Bounded, validated image downloads and processed-image caching."""
import hashlib
import io
import ipaddress
import socket
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin, urlparse
import requests
from PIL import Image, ImageOps

IMAGE_HOSTS = frozenset({"easy-plu.knowledge-hero.com"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def validate_image_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in IMAGE_HOSTS
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443)):
        raise ValueError("Unapproved image URL")
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Image host resolves to a non-public address")


def download_image(url):
    # Use a separate session: never send authenticated EasyPLU headers or cookies.
    with requests.Session() as downloader:
        downloader.trust_env = False
        for _ in range(4):
            validate_image_url(url)
            with downloader.get(url, stream=True, allow_redirects=False, timeout=(5, 20)) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise ValueError("Missing image redirect target")
                    url = urljoin(url, location)
                    continue
                response.raise_for_status()
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > MAX_IMAGE_BYTES:
                    raise ValueError("Image exceeds size limit")
                content = bytearray()
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if len(content) + len(chunk) > MAX_IMAGE_BYTES:
                        raise ValueError("Image exceeds size limit")
                    content.extend(chunk)
                return bytes(content)
        raise ValueError("Too many image redirects")


def cached_image(url, cache_dir):
    if not url:
        return None
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg", ".webp"):
        suffix = ".img"
    image_key = hashlib.sha256(url.encode()).hexdigest()
    path = cache_dir / (image_key + suffix)
    # Version this suffix whenever resize or encoding settings change.
    processed = cache_dir / (image_key + ".pdf-v1.jpg")
    try:
        if processed.exists():
            return processed.read_bytes()
        if not path.exists():
            content = download_image(url)
            Image.open(io.BytesIO(content)).verify()
            path.write_bytes(content)
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((900, 900))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            content = output.getvalue()
        # A unique temporary file also keeps concurrent CLI/web exports safe.
        with NamedTemporaryFile(dir=cache_dir, suffix=".tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            try:
                temporary.write(content)
                temporary.close()
                temporary_path.replace(processed)
            finally:
                temporary_path.unlink(missing_ok=True)
        return content
    except Exception:
        return None


