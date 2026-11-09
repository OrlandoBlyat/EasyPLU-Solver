"""Cooperative job cancellation and bounded upstream requests."""
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event
import requests
import os
import time

MAX_JOB_SECONDS = max(1, int(os.getenv("MAX_JOB_SECONDS", "600")))


class JobCancelled(Exception):
    pass


_cancel = ContextVar("job_cancel", default=None)
_session = ContextVar("job_session", default=None)
_deadline = ContextVar("job_deadline", default=None)


def check_cancelled():
    deadline = _deadline.get()
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("Job deadline exceeded")
    event = _cancel.get()
    if event is not None and event.is_set():
        raise JobCancelled("Client disconnected")


def wait(seconds):
    event = _cancel.get()
    if event is None:
        event = Event()
    deadline = _deadline.get()
    event.wait(min(seconds, max(0, deadline - time.monotonic())) if deadline is not None else seconds)
    check_cancelled()


class TimedSession(requests.Session):
    def request(self, *args, **kwargs):
        check_cancelled()
        remaining = max(0.001, _deadline.get() - time.monotonic()) if _deadline.get() else 20
        kwargs["timeout"] = (min(5, remaining), min(20, remaining))
        response = super().request(*args, **kwargs)
        if _cancel.get() is not None and _cancel.get().is_set():
            response.close()
            check_cancelled()
        check_cancelled()
        return response


class SessionProxy:
    def __getattr__(self, name):
        current = _session.get()
        if current is None:
            current = TimedSession()
            _session.set(current)
        return getattr(current, name)


@contextmanager
def job_scope(cancel, deadline=None):
    cancel_token = _cancel.set(cancel)
    deadline_token = _deadline.set(deadline if deadline is not None else time.monotonic() + MAX_JOB_SECONDS)
    current = TimedSession()
    session_token = _session.set(current)
    try:
        check_cancelled()
        yield
    finally:
        current.close()
        _session.reset(session_token)
        _cancel.reset(cancel_token)
        _deadline.reset(deadline_token)
