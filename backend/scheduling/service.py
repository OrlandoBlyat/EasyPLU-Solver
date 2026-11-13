"""Recent-test authorization and explicit schedule enrollment."""
import json
import time
from .credentials import cipher
from .repository import connect
from .state import lock as _lock, verified as _verified, running as _running
from .settings import settings

def verified_test(owner, user_id, email, password, login_method):
    with _lock:
        # Never retain SSO credentials, tokens, or cookies for automatic tests.
        _verified.pop(owner, None)
        if login_method not in ("easyplu", "easy-plu") or user_id is None:
            return
        now = time.time()
        for key in list(_verified):
            if _verified[key][2] < now:
                del _verified[key]
        credentials = {"email": email, "password": password, "login_method": "easyplu"}
        encrypted = cipher().encrypt(json.dumps(credentials).encode())
        _verified[owner] = (str(user_id), encrypted, now + 60)


def identity(owner):
    value = _verified.get(owner)
    if not value or value[2] < time.time():
        raise PermissionError("First complete a test using your EasyPLU email and password.")
    return value


def status(owner):
    with _lock:
        try:
            user_id, _, _ = identity(owner)
        except PermissionError:
            return {"verified": False, "enabled": False}
        with connect() as connection:
            row = connection.execute("SELECT next_run, state FROM schedules_credentials WHERE user_id = ?", (user_id,)).fetchone()
        return {"verified": True, "enabled": row is not None,
                "state": row[1] if row else None, "next_run": row[0] if row and row[1] == "active" else None}


def update(owner, enabled, consent=False):
    with _lock:
        user_id, auth, _ = identity(owner)
        with connect() as connection:
            if enabled:
                if consent is not True:
                    raise PermissionError("Accept the warning before saving credentials.")
                interval, _ = settings()
                encrypted = auth
                connection.execute("INSERT INTO schedules_credentials VALUES (?, ?, ?, 'active') ON CONFLICT(user_id) DO UPDATE SET auth=excluded.auth, next_run=excluded.next_run, state='active'",
                                   (user_id, encrypted, time.time() + interval))
            else:
                connection.execute("DELETE FROM schedules_credentials WHERE user_id = ?", (user_id,))
                if user_id in _running:
                    _running[user_id].set()
    return status(owner)


