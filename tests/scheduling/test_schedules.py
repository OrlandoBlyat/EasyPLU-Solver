import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from cryptography.fernet import Fernet
from backend.scheduling import service as schedules, repository, credentials, worker
from backend.infrastructure.jobs import job_scope
from backend.tests_runner.solver import session


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.patch = patch.object(repository, "DB", Path(self.directory.name) / "schedules.sqlite3")
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.encryption = patch.object(credentials, "cipher", return_value=Fernet(Fernet.generate_key()))
        encryption = self.encryption.start()
        service_encryption = patch.object(schedules, "cipher", encryption)
        service_encryption.start()
        self.addCleanup(service_encryption.stop)
        self.addCleanup(self.encryption.stop)
        schedules._verified.clear()
        schedules._running.clear()

    def verify(self, owner="owner", user_id="123"):
        with job_scope(Event()):
            session.headers["Authorization"] = "Bearer secret-token"
            schedules.verified_test(owner, user_id, "test@example.com", "secret-password", "easyplu")

    def due(self):
        with schedules.connect() as connection:
            connection.execute("UPDATE schedules_credentials SET next_run=0")

    def test_sso_is_not_retained_or_allowed_to_enroll(self):
        self.verify()
        schedules.verified_test("owner", "123", "12345678", "sso-password", "sso")
        self.assertNotIn("owner", schedules._verified)
        with self.assertRaises(PermissionError):
            schedules.update("owner", True, consent=True)

    def test_legacy_token_schedules_are_deleted(self):
        import sqlite3
        with sqlite3.connect(repository.DB) as connection:
            connection.execute("CREATE TABLE schedules (auth BLOB)")
            connection.execute("INSERT INTO schedules VALUES (?)", (b"old-sso-token",))
        connection.close()
        with schedules.connect() as connection:
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='schedules'").fetchone())

    def test_enrollment_requires_explicit_consent(self):
        self.verify()
        with self.assertRaises(PermissionError):
            schedules.update("owner", True)
        self.assertFalse(schedules.status("owner")["enabled"])

    def test_management_expires_after_one_minute(self):
        self.verify()
        expires = schedules._verified["owner"][2]
        with patch("backend.scheduling.service.time.time", return_value=expires + 1):
            self.assertFalse(schedules.status("owner")["verified"])
            with self.assertRaises(PermissionError):
                schedules.update("owner", True, consent=True)
            with self.assertRaises(PermissionError):
                schedules.update("owner", False)

    def test_requires_successful_test(self):
        self.assertFalse(schedules.status("stranger")["verified"])
        with self.assertRaises(PermissionError):
            schedules.update("stranger", True)

    def test_encrypted_opt_in_and_account_scoped_removal(self):
        self.verify()
        self.assertFalse(schedules.status("owner")["enabled"])
        self.assertTrue(schedules.update("owner", True, consent=True)["enabled"])
        with schedules.connect() as connection:
            encrypted = connection.execute("SELECT auth FROM schedules_credentials").fetchone()[0]
        self.assertNotIn(b"secret-password", encrypted)
        self.verify("other", "456")
        schedules.update("other", False)
        self.assertTrue(schedules.status("owner")["enabled"])
        self.verify("new-browser", "123")
        schedules.update("new-browser", False)
        self.assertFalse(schedules.status("owner")["enabled"])

    def test_due_run_logs_in_fresh_and_reschedules(self):
        self.verify()
        schedules.update("owner", True, consent=True)
        self.due()
        def run(*args, **kwargs):
            self.assertEqual(args, ("test@example.com", "secret-password"))
            self.assertEqual(kwargs["user_id"], "123")
        stop = Event()
        stop.wait = lambda delay: True
        with patch("backend.auth.easyplu.login", return_value="123") as login, patch("backend.tests_runner.solver.run_session", side_effect=run) as runner, patch("backend.infrastructure.limits.limiter.acquire", return_value=lambda: None):
            worker.run_due(stop)
        login.assert_called_once_with("test@example.com", "secret-password", login_method="easyplu")
        runner.assert_called_once()
        self.assertGreater(schedules.status("owner")["next_run"], time.time())

    def test_failed_session_pauses_and_remove_cancels(self):
        self.verify()
        schedules.update("owner", True, consent=True)
        self.due()
        stop = Event()
        stop.wait = lambda delay: True
        with patch("backend.auth.easyplu.login", side_effect=RuntimeError("rejected")), patch("backend.infrastructure.limits.limiter.acquire", return_value=lambda: None):
            worker.run_due(stop)
        self.assertEqual(schedules.status("owner")["state"], "reauth_required")
        cancel = Event()
        schedules._running["123"] = cancel
        schedules.update("owner", False)
        self.assertTrue(cancel.is_set())


if __name__ == "__main__":
    unittest.main()
