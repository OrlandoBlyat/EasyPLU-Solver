import asyncio
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes=8192):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        async def reject(status, message):
            await JSONResponse({"detail": message}, status_code=status)(scope, receive, send)
        length = headers.get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > self.max_bytes):
            return await reject(413, "Zahteva je prevelika.")
        if headers.get(b"content-type", b"").split(b";")[0].strip().lower() != b"application/json":
            return await reject(415, "Zahteva mora biti JSON.")
        body = bytearray()
        try:
            deadline = asyncio.get_running_loop().time() + 10
            while True:
                message = await asyncio.wait_for(receive(), timeout=max(0, deadline - asyncio.get_running_loop().time()))
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > self.max_bytes:
                    return await reject(413, "Zahteva je prevelika.")
                if not message.get("more_body", False):
                    break
        except asyncio.TimeoutError:
            return await reject(408, "Čas pošiljanja je potekel.")
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)
