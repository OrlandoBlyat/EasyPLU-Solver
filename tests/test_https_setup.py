import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/setup-https.py"
SPEC = importlib.util.spec_from_file_location("setup_https", SCRIPT)
setup_https = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_https)


class HttpsSetupTests(unittest.TestCase):
    def test_cloudflare_setup_requires_origin_ca_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            certificate = root / "origin.pem"
            key = root / "origin-key.pem"
            certificate.write_text("certificate")
            key.write_text("private key")
            with self.assertRaisesRegex(ValueError, "install-cloudflare-origin-ca.bash"):
                setup_https.validate({
                    "mode": "cloudflare",
                    "host": "app.example.com",
                    "port": 8443,
                    "certificate": str(certificate),
                    "key": str(key),
                    "ca_pool": str(root / "origin-ca.pem"),
                })

    def test_cloudflare_caddy_config_uses_loopback_without_port_80_redirect(self):
        settings = {
            "mode": "cloudflare",
            "host": "app.example.com",
            "port": 8443,
            "certificate": "/etc/easyplu/origin.pem",
            "key": "/etc/easyplu/origin-key.pem",
            "ca_pool": "/etc/cloudflare/origin-ca.pem",
        }
        with tempfile.TemporaryDirectory() as directory:
            caddyfile = Path(directory) / "Caddyfile"
            with patch.object(setup_https, "validate", return_value=("cloudflare", "app.example.com", 8443)):
                setup_https.generate(settings, 3000, caddyfile)
            contents = caddyfile.read_text()
            self.assertIn("auto_https disable_redirects", contents)
            self.assertIn("bind 127.0.0.1", contents)
            self.assertIn("https://app.example.com:8443", contents)


if __name__ == "__main__":
    unittest.main()
