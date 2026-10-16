import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Far above any real request to this API, whose largest bodies are a few
# kilobytes of text, and far below what it would take to exhaust memory.
MAX_REQUEST_BODY_BYTES = 1024 * 1024

_TOO_LARGE_BODY = json.dumps({"detail": "Request body is too large"}).encode()


class BodySizeLimitMiddleware:
    """Refuse a request whose body is larger than a limit, before the application parses it.

    A declared Content-Length over the limit is refused without reading
    anything. A body sent without one (chunked) is read only up to the limit.
    In both cases the client receives 413 and the application never sees the
    request. A body within the limit is passed on unchanged.
    """

    def __init__(self, app: ASGIApp, max_body_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared_length = dict(scope["headers"]).get(b"content-length")
        if declared_length is not None:
            try:
                is_too_large = int(declared_length) > self.max_body_bytes
            except ValueError:
                is_too_large = True
            if is_too_large:
                await self._refuse(send)
                return

        body_messages: list[Message] = []
        received_bytes = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                # The client went away. There is nothing left to serve.
                return
            received_bytes += len(message.get("body", b""))
            if received_bytes > self.max_body_bytes:
                await self._refuse(send)
                return
            body_messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay_body() -> Message:
            if body_messages:
                return body_messages.pop(0)
            return await receive()

        await self.app(scope, replay_body, send)

    @staticmethod
    async def _refuse(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_TOO_LARGE_BODY)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _TOO_LARGE_BODY})
