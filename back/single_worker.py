"""Prevent multiple backend workers from splitting in-memory job/OTP state."""
from contextlib import asynccontextmanager
from pathlib import Path
import fcntl
import os


@asynccontextmanager
async def lifespan(app):
    path = Path(__file__).resolve().parent.parent / ".backend.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Only one backend worker is supported. Stop the other backend or use --workers 1.") from None
        yield
    finally:
        os.close(fd)
