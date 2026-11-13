import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from starlette.requests import Request
from backend.infrastructure.limits import JobLimiter
from backend.infrastructure.test_queue import TestQueue, rate_key
from backend.api.schemas import SessionRequest
from backend.tests_runner import service


class QueueTests(unittest.TestCase):
    def test_fifo_and_active_capacity(self):
        capacity = JobLimiter(max_active=1, starts_per_minute=100)
        queue = TestQueue(capacity)
        first = queue.enqueue("first", "first")
        second = queue.enqueue("second", "second")
        third = queue.enqueue("third", "third")
        self.assertFalse(second.try_start())
        self.assertTrue(first.try_start())
        self.assertFalse(second.try_start())
        first.release()
        first.release()
        self.assertFalse(third.try_start())
        self.assertTrue(second.try_start())
        self.assertEqual(capacity.active, 1)
        second.release()
        self.assertTrue(third.try_start())
        third.release()
        self.assertEqual(capacity.active, 0)

    def test_cancellation_removes_waiter_but_keeps_running_capacity(self):
        capacity = JobLimiter(max_active=1)
        queue = TestQueue(capacity)
        first = queue.enqueue("first", "first")
        second = queue.enqueue("second", "second")
        first.cancel()
        first.cancel()
        self.assertTrue(second.try_start())
        second.cancel()
        self.assertEqual(capacity.active, 1)
        second.release()
        self.assertFalse(queue.has_waiters())
        self.assertFalse(queue.owners)

    def test_queue_bound_and_duplicate_browser(self):
        queue = TestQueue(JobLimiter(), max_waiting=1)
        first = queue.enqueue("same", "same")
        with self.assertRaises(HTTPException) as duplicate:
            queue.enqueue("same", "same")
        self.assertEqual(duplicate.exception.status_code, 409)
        with self.assertRaises(HTTPException) as full:
            queue.enqueue("other", "other")
        self.assertEqual(full.exception.status_code, 429)
        first.cancel()
        queue.enqueue("other", "other").cancel()


class QueueAbuseTests(unittest.TestCase):
    def test_fresh_sessions_cannot_fill_queue_from_one_client(self):
        queue = TestQueue(JobLimiter(), max_waiting=20)
        for index in range(2):
            queue.enqueue(f"owner-{index}", "192.0.2.1")
        with self.assertRaises(HTTPException) as rejected:
            queue.enqueue("fresh-owner", "192.0.2.1")
        self.assertEqual(rejected.exception.status_code, 429)
        self.assertIn("Retry-After", rejected.exception.headers)
        self.assertEqual(len(queue.waiting), 2)
        queue.enqueue("other-client", "192.0.2.2")
        self.assertEqual(len(queue.waiting), 3)

    def test_cancelled_requests_still_consume_admission_budget(self):
        queue = TestQueue(JobLimiter(), admissions_per_minute=2)
        with patch("backend.infrastructure.limits.time.monotonic", return_value=100):
            for index in range(2):
                queue.enqueue(f"owner-{index}", "client").cancel()
            with self.assertRaises(HTTPException) as rejected:
                queue.enqueue("fresh-owner", "client")
        self.assertEqual(rejected.exception.status_code, 429)
        self.assertFalse(queue.waiting)
        self.assertFalse(queue.owners)
        with patch("backend.infrastructure.limits.time.monotonic", return_value=161):
            queue.enqueue("after-window", "client").cancel()

    def test_cookie_rotation_does_not_change_proxy_budget(self):
        request = Request({"type": "http", "headers": [(b"x-edge-client-ip", b"192.0.2.99")], "client": ("127.0.0.1", 1234)})
        with patch.dict("os.environ", {"TRUST_EDGE_CLIENT_IP": "0"}):
            self.assertEqual(rate_key(request, "first-owner"), "127.0.0.1")
            self.assertEqual(rate_key(request, "fresh-owner"), "127.0.0.1")
        with patch.dict("os.environ", {"TRUST_EDGE_CLIENT_IP": "1"}):
            self.assertEqual(rate_key(request, "first-owner"), "192.0.2.99")


class StreamQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_notice_and_disconnect_cleanup_without_running_solver(self):
        capacity = JobLimiter(max_active=1)
        release = capacity.acquire("busy")
        queue = TestQueue(capacity)
        request = Request({"type": "http", "headers": [(b"x-run-owner", b"a" * 64)], "client": ("127.0.0.1", 1234)})
        request.is_disconnected = AsyncMock(return_value=False)
        data = SessionRequest(email="test@example.com", password="secret-password")
        with patch.object(service, "test_queue", queue), patch.object(service, "run_session") as solver:
            response = await service.run_plu_session_stream(data, request)
            stream = response.body_iterator
            self.assertIn("connected", await anext(stream))
            notice = await anext(stream)
            self.assertIn('"stage": "queued"', notice)
            self.assertIn('"message_key": "You are in the queue.', notice)
            solver.assert_not_called()
            await stream.aclose()
        self.assertFalse(queue.has_waiters())
        self.assertFalse(queue.owners)
        self.assertEqual(capacity.active, 1)
        release()

    async def test_queued_request_starts_automatically_when_capacity_is_released(self):
        capacity = JobLimiter(max_active=1)
        release = capacity.acquire("busy")
        queue = TestQueue(capacity)
        request = Request({"type": "http", "headers": [(b"x-run-owner", b"c" * 64)], "client": ("127.0.0.1", 1234)})
        request.is_disconnected = AsyncMock(return_value=False)
        data = SessionRequest(email="test@example.com", password="secret-password", mode="knowledge")
        result = {"user_id": "123", "user_knowledge": 100}
        with patch.object(service, "test_queue", queue), patch.object(service, "run_session", return_value=result) as solver, patch("backend.scheduling.service.verified_test"):
            response = await service.run_plu_session_stream(data, request)
            stream = response.body_iterator
            await anext(stream)
            self.assertIn('"stage": "queued"', await anext(stream))
            release()
            stages = []
            async for message in stream:
                stages.append(message)
            self.assertTrue(any('"stage": "final"' in message for message in stages))
            solver.assert_called_once()
            for _ in range(100):
                if capacity.active == 0:
                    break
                await asyncio.sleep(0.01)
        self.assertEqual(capacity.active, 0)
        self.assertFalse(queue.owners)

    async def test_wait_timeout_cleans_up_reservation(self):
        capacity = JobLimiter(max_active=1)
        release = capacity.acquire("busy")
        queue = TestQueue(capacity)
        request = Request({"type": "http", "headers": [(b"x-run-owner", b"b" * 64)], "client": ("127.0.0.1", 1234)})
        request.is_disconnected = AsyncMock(return_value=False)
        data = SessionRequest(email="test@example.com", password="secret-password")
        with patch.object(service, "test_queue", queue), patch.object(service, "MAX_QUEUE_SECONDS", 0):
            response = await service.run_plu_session_stream(data, request)
            stream = response.body_iterator
            await anext(stream)
            self.assertIn('"stage": "error"', await anext(stream))
            with self.assertRaises(StopAsyncIteration):
                await anext(stream)
        self.assertFalse(queue.has_waiters())
        self.assertFalse(queue.owners)
        release()
