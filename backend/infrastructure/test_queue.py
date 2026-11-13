"""Bounded FIFO admission for interactive tests, without a thread per waiter."""
import os
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException
from .limits import limiter, SmsLimiter, STARTS_PER_MINUTE

MAX_QUEUE_SECONDS = max(1, int(os.getenv("MAX_QUEUE_SECONDS", "3600")))


class TestQueue:
    def __init__(self, capacity_limiter, max_waiting=20, max_pending_per_client=2, admissions_per_minute=STARTS_PER_MINUTE):
        self.limiter = capacity_limiter
        self.max_waiting = max_waiting
        self.max_pending_per_client = max_pending_per_client
        self.admission_limiter = SmsLimiter(
            per_minute=admissions_per_minute,
            message="Too many starts. Please try again in a minute.",
        )
        self.waiting = deque()
        self.owners = set()
        self.lock = Lock()

    def enqueue(self, owner, rate_key):
        with self.lock:
            if owner in self.owners:
                raise HTTPException(409, "A test is already running or queued in this browser.")
            if len(self.waiting) >= self.max_waiting:
                raise HTTPException(429, "The queue is full. Please try again later.", headers={"Retry-After": "30"})
            if sum(ticket.rate_key == rate_key for ticket in self.waiting) >= self.max_pending_per_client:
                raise HTTPException(429, "Too many queued requests. Please try again later.", headers={"Retry-After": "30"})
            # Check before reserving queue space, independently of worker capacity.
            self.admission_limiter.check(rate_key)
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
    # Fail closed when the proxy hides client IPs: share its budget rather than
    # allowing attackers to reset limits by discarding their browser cookie.
    return address
