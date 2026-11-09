"""Backend-managed automatic test worker and lifecycle."""
import json
import time
from threading import Event, Thread
from backend.infrastructure.jobs import job_scope
from backend.infrastructure.logging import log
from . import credentials
from .repository import connect
from .settings import settings
from .state import lock as _lock, running as _running

def run_due(stop):
    from backend.auth.easyplu import login
    from backend.tests_runner.solver import run_session
    from backend.infrastructure.limits import limiter
    from backend.infrastructure.test_queue import test_queue
    from backend.infrastructure.jobs import MAX_JOB_SECONDS
    with connect() as connection:
        rows = connection.execute("SELECT user_id, auth FROM schedules_credentials WHERE state='active' AND next_run <= ? ORDER BY next_run", (time.time(),)).fetchall()
    for user_id, encrypted in rows:
        if stop.is_set():
            return
        if test_queue.has_waiters():
            return
        try:
            release = limiter.acquire("scheduled-tests")
        except Exception:
            return  # Leave due entries untouched while interactive jobs occupy capacity.
        cancel = Event()
        try:
            with _lock:
                with connect() as connection:
                    current = connection.execute("SELECT auth FROM schedules_credentials WHERE user_id=? AND state='active'", (user_id,)).fetchone()
                if not current or current[0] != encrypted:
                    continue
                _running[user_id] = cancel
            auth = json.loads(credentials.cipher().decrypt(encrypted))
            with job_scope(cancel, time.monotonic() + MAX_JOB_SECONDS):
                if auth.get("login_method") != "easyplu":
                    raise ValueError("Only EasyPLU credential schedules are supported")
                authenticated = login(auth["email"], auth["password"], login_method="easyplu")
                if str(authenticated) != user_id:
                    raise ValueError("Scheduled login account does not match enrollment")
                run_session(auth["email"], auth["password"], user_id=authenticated, mode="knowledge")
            interval, delay = settings()
            with connect() as connection:
                connection.execute("UPDATE schedules_credentials SET next_run=? WHERE user_id=? AND auth=?", (time.time() + interval, user_id, encrypted))
        except Exception:
            # No repeated unattended authentication attempts or SMS prompts.
            with connect() as connection:
                connection.execute("UPDATE schedules_credentials SET state='reauth_required' WHERE user_id=? AND auth=?", (user_id, encrypted))
            log("solver", "Scheduled test paused; a new authenticated test is required")
        finally:
            with _lock:
                _running.pop(user_id, None)
            release()
        _, delay = settings()
        if stop.wait(delay):
            return


def start_scheduler():
    credentials.cipher()
    with connect():
        pass  # Retire legacy tokens immediately, before the first scheduled poll.
    stop = Event()
    def work():
        while not stop.wait(5):
            try:
                run_due(stop)
            except Exception:
                log("solver", "Schedule worker failed; retrying later")
    worker = Thread(target=work, name="scheduled-tests", daemon=True)
    worker.start()
    def shutdown():
        stop.set()
        with _lock:
            for cancel in _running.values():
                cancel.set()
        worker.join(timeout=1)
    return shutdown


