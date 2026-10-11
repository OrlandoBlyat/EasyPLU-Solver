"""Admission limits for a single backend process."""
from collections import deque
from threading import Lock
import os
import time
from fastapi import HTTPException

MAX_ACTIVE = max(1, int(os.getenv("MAX_ACTIVE_JOBS", "2")))
STARTS_PER_MINUTE = max(1, int(os.getenv("JOB_STARTS_PER_MINUTE", "3")))


class JobLimiter:
    def __init__(self, max_active=MAX_ACTIVE, starts_per_minute=STARTS_PER_MINUTE):
        self.max_active = max_active
        self.starts_per_minute = starts_per_minute
        self.active = 0
        self.starts = {}
        self.lock = Lock()

    def acquire(self, ip):
        now = time.monotonic()
        with self.lock:
            self.starts = {key: deque(t for t in values if t > now - 60)
                           for key, values in self.starts.items() if values and values[-1] > now - 60}
            history = self.starts.get(ip, deque())
            if len(history) >= self.starts_per_minute:
                retry = max(1, int(60 - (now - history[0])) + 1)
                raise HTTPException(429, "Preveč zagonov. Poskusite čez minuto.", headers={"Retry-After": str(retry)})
            if self.active >= self.max_active or len(self.starts) >= 10000 and ip not in self.starts:
                raise HTTPException(429, "Strežnik je zaseden. Poskusite pozneje.", headers={"Retry-After": "10"})
            history.append(now)
            self.starts[ip] = history
            self.active += 1
        released = False

        def release():
            nonlocal released
            with self.lock:
                if not released:
                    self.active -= 1
                    released = True
        return release


limiter = JobLimiter()


class SmsLimiter:
    def __init__(self, per_minute=None):
        self.per_minute = per_minute if per_minute is not None else max(1, int(os.getenv("SMS_SUBMISSIONS_PER_MINUTE", "10")))
        self.history = {}
        self.lock = Lock()

    def check(self, ip):
        now = time.monotonic()
        with self.lock:
            self.history = {key: deque(t for t in values if t > now - 60)
                            for key, values in self.history.items() if values and values[-1] > now - 60}
            entries = self.history.get(ip, deque())
            if len(entries) >= self.per_minute or len(self.history) >= 10000 and ip not in self.history:
                raise HTTPException(429, "Preveč SMS zahtev. Poskusite čez minuto.", headers={"Retry-After": "60"})
            entries.append(now)
            self.history[ip] = entries


sms_limiter = SmsLimiter()


def client_ip(request):
    # Only enable behind an edge proxy that overwrites the configured IP header.
    if os.getenv("TRUST_EDGE_CLIENT_IP") == "1":
        import ipaddress
        value = request.headers.get("x-edge-client-ip", "")
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"
