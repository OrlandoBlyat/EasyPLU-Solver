"""Exercise middleware and routing without a live server or upstream accounts."""
import asyncio
import json
import unittest
from unittest.mock import patch

from backend import app as application


async def request_response(path, headers=()):
    messages = []
    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Event().wait()

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
             "query_string": b"", "root_path": "", "headers": list(headers),
             "client": ("127.0.0.1", 1234), "server": ("localhost", 8000)}
    await application.app(scope, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, json.loads(body) if body else None


async def request(path, headers=()):
    return (await request_response(path, headers))[0]


class RouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_internal_key_remains_required(self):
        with patch.object(application, "_internal_key", "test-key"):
            self.assertEqual(await request("/health"), 401)
            self.assertEqual(await request("/health", [(b"x-internal-key", b"test-key")]), 200)

    async def test_schedule_requires_browser_owner(self):
        from fastapi import HTTPException
        from starlette.requests import Request
        from backend.api.schedules import get_schedule
        with self.assertRaises(HTTPException) as rejected:
            get_schedule(Request({"type": "http", "headers": []}))
        self.assertEqual(rejected.exception.status_code, 403)

    async def test_api_errors_stay_english_regardless_of_language(self):
        from starlette.requests import Request
        for locale in ("en", "sl"):
            request = Request({"type": "http", "headers": [(b"accept-language", locale.encode())]})
            response = await application.invalid_request(request, None)
            self.assertEqual(json.loads(response.body)["detail"], "Invalid request data.")

    def test_endpoint_contract_survives_reorganization(self):
        paths = application.app.openapi()["paths"]
        self.assertEqual(set(paths), {"/health", "/catalog-pdf", "/schedule", "/submit-otp", "/run-session", "/run-session-stream"})
        self.assertEqual(set(paths["/schedule"]), {"get", "post"})
