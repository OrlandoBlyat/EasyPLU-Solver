"""Bounded FIFO admission for interactive tests, without a thread per waiter."""
import os
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException
from .limits import limiter

MAX_QUEUE_SECONDS = max(1, int(os.getenv("MAX_QUEUE_SECONDS", "3600")))


class TestQueue:
    def __init__(self, capacity_limiter, max_waiting=20):
        self.limiter = capacity_limiter
        self.max_waiting = max_waiting
        self.waiting = deque()
        self.owners = set()
        self.lock = Lock()

    def enqueue(self, owner, rate_key):
        with self.lock:
            if owner in self.owners:
                raise HTTPException(409, "V tem brskalniku se test že izvaja ali čaka v vrsti.")
            if len(self.waiting) >= self.max_waiting:
                raise HTTPException(429, "Čakalna vrsta je polna. Poskusite pozneje.", headers={"Retry-After": "30"})
            ticket = Ticket(self, owner, rate_key)
            self.waiting.append(ticket)
            self.owners.add(owner)
            return ticket

    def has_waiters(self):
        with self.lock:
            return bool(self.waiting)


class Ticket:
    def __init__(self, queue, owner, rate_key):
        self.queue = queue
        self.owner = owner
        self.rate_key = rate_key
        self.created = time.monotonic()
        self.state = "waiting"
        self.release_slot = None

    def try_start(self):
        with self.queue.lock:
            if self.state == "active":
                return True
            if self.state != "waiting" or self.queue.waiting[0] is not self:
                return False
            try:
                self.release_slot = self.queue.limiter.acquire(self.rate_key)
            except HTTPException as exc:
                if exc.status_code == 429:
                    return False
                raise
            self.queue.waiting.popleft()
            self.state = "active"
            return True

    def cancel(self):
        with self.queue.lock:
            if self.state == "waiting":
                self.queue.waiting.remove(self)
                self.queue.owners.discard(self.owner)
                self.state = "cancelled"

    def release(self):
        with self.queue.lock:
            if self.state == "active":
                self.release_slot()
                self.queue.owners.discard(self.owner)
                self.state = "finished"


test_queue = TestQueue(limiter, max_waiting=max(1, int(os.getenv("MAX_QUEUED_JOBS", "20"))))


def rate_key(request, owner):
    from .limits import client_ip
    address = client_ip(request)
    # Without a trusted edge, loopback identifies the proxy rather than the user.
    return "browser:" + owner if address in ("127.0.0.1", "::1") else address
