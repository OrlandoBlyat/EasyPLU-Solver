"""Private SQLite storage for encrypted enrollments."""
from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "var/schedules/accounts.sqlite3"

@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(DB)
    os.chmod(DB, 0o600)
    connection.execute("PRAGMA secure_delete=ON")
    # Retire all token-based schedules, including SSO sessions.
    connection.execute("DROP TABLE IF EXISTS schedules")
    connection.execute("CREATE TABLE IF NOT EXISTS schedules_credentials (user_id TEXT PRIMARY KEY, auth BLOB NOT NULL, next_run REAL NOT NULL, state TEXT NOT NULL)")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


