import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from backend.scheduling import credentials as schedules
from backend.infrastructure.limits import JobLimiter
from backend.catalog import images as export


class SecurityTests(unittest.TestCase):
    def test_download_limits_do_not_consume_test_capacity(self):
        from backend.infrastructure.limits import limiter, pdf_limiter
        self.assertIsNot(limiter, pdf_limiter)
        downloads = JobLimiter(max_active=1)
        tests = JobLimiter(max_active=1)
        release_download = downloads.acquire("client")
        release_test = tests.acquire("client")
        release_test()
        release_download()

    def test_rejects_unapproved_image_destinations(self):
        for url in ("http://easy-plu.knowledge-hero.com/a", "https://127.0.0.1/a", "https://evil.example/a", "https://user@easy-plu.knowledge-hero.com/a"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                export.validate_image_url(url)
        with patch.object(export.socket, "getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                export.validate_image_url("https://easy-plu.knowledge-hero.com/a")

    def response(self, status=200, headers=None, chunks=()):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = status
        response.headers = headers or {}
        response.iter_content.return_value = iter(chunks)
        return response

    def test_redirect_target_is_checked_before_second_request(self):
        first = self.response(302, {"Location": "https://127.0.0.1/private"})
        with patch.object(export.socket, "getaddrinfo", return_value=[(None, None, None, None, ("8.8.8.8", 443))]), patch.object(export.requests, "Session") as factory:
            downloader = factory.return_value.__enter__.return_value
            downloader.get.return_value = first
            with self.assertRaises(ValueError):
                export.download_image("https://easy-plu.knowledge-hero.com/a")
            self.assertEqual(downloader.get.call_count, 1)

    def test_stream_limit_without_content_length(self):
        response = self.response(chunks=[b"1234", b"5678", b"unread"])
        with patch.object(export, "validate_image_url"), patch.object(export, "MAX_IMAGE_BYTES", 5), patch.object(export.requests, "Session") as factory:
            downloader = factory.return_value.__enter__.return_value
            downloader.get.return_value = response
            with self.assertRaisesRegex(ValueError, "size limit"):
                export.download_image("https://easy-plu.knowledge-hero.com/a")
            self.assertEqual(next(response.iter_content.return_value), b"unread")
            self.assertTrue(downloader.get.call_args.kwargs["stream"])
            self.assertFalse(downloader.get.call_args.kwargs["allow_redirects"])

    def test_external_key_migration_preserves_enrollments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            home = Path(directory) / "home"
            key = Fernet.generate_key()
            encrypted = Fernet(key).encrypt(b"saved-credentials")
            legacy = root / ".schedule-key"
            legacy.write_bytes(key)
            with patch.object(schedules, "ROOT", root), patch.object(Path, "home", return_value=home), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(schedules.cipher().decrypt(encrypted), b"saved-credentials")
                self.assertFalse(legacy.exists())
                target = home / ".config/easyplu-solver/schedule.key"
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                self.assertEqual(schedules.cipher().decrypt(encrypted), b"saved-credentials")
                with patch.dict(os.environ, {"SCHEDULE_KEY_FILE": str(root / "bad-key")}):
                    with self.assertRaises(RuntimeError):
                        schedules.cipher()
