"""Credential encryption and migration to an external private key."""
import os
from pathlib import Path
from threading import Lock
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
_key_lock = Lock()

def cipher():
    # An operator can provision this outside the checkout using an OS secret service.
    configured = os.environ.get("SCHEDULE_KEY_FILE")
    path = Path(configured) if configured else Path.home() / ".config/easyplu-solver/schedule.key"
    if not path.is_absolute() or path.resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError("Schedule key must be stored outside the checkout")
    with _key_lock:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        legacy = ROOT / ".schedule-key"
        if not path.exists():
            # Preserve existing encrypted enrollments when moving the legacy key.
            key = legacy.read_bytes().strip() if not configured and legacy.exists() else Fernet.generate_key()
            Fernet(key)  # Validate before changing anything.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(key)
                output.flush()
                os.fsync(output.fileno())
        if path.stat().st_mode & 0o077:
            raise RuntimeError("Schedule encryption key must have private permissions (600)")
        value = path.read_bytes().strip()
        if not configured and legacy.exists():
            if legacy.read_bytes().strip() != value:
                raise RuntimeError("Conflicting legacy schedule key; migration requires operator review")
            legacy.unlink()
        return Fernet(value)


