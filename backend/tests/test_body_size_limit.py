"""The size limit as a plain ASGI component, for cases a test client cannot send."""

import asyncio

from starlette.types import Message, Receive, Scope, Send

from app.middleware.body_size_limit import BodySizeLimitMiddleware

LIMIT = 10


def http_scope(headers: list[tuple[bytes, bytes]] | None = None) -> Scope:
    return {"type": "http", "method": "POST", "path": "/", "headers": headers or []}


class RecordingApp:
    """Stands in for the application: reads the whole body and remembers it."""

    def __init__(self) -> None:
        self.called = False
        self.body = b""
        self.message_after_body: Message | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.called = True
        while True:
            message = await receive()
            self.body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        # An application that keeps listening after the body, as a streaming
        # response does, must reach the server's own receive.
        self.message_after_body = await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})


def run(scope: Scope, incoming: list[Message]) -> tuple[RecordingApp, list[Message]]:
    application = RecordingApp()
    sent: list[Message] = []

    async def receive() -> Message:
        return incoming.pop(0) if incoming else {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    asyncio.run(BodySizeLimitMiddleware(application, max_body_bytes=LIMIT)(scope, receive, send))
    return application, sent


def test_an_unreadable_content_length_is_refused() -> None:
    application, sent = run(http_scope([(b"content-length", b"lots")]), [])

    assert not application.called
    assert sent[0]["status"] == 413


def test_a_client_that_disconnects_mid_body_is_not_served() -> None:
    application, sent = run(
        http_scope(),
        [{"type": "http.request", "body": b"abc", "more_body": True}, {"type": "http.disconnect"}],
    )

    assert not application.called
    assert sent == []


def test_a_body_exactly_at_the_limit_is_passed_on_in_full() -> None:
    application, sent = run(
        http_scope(),
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"67890", "more_body": False},
        ],
    )

    assert application.body == b"1234567890"
    assert application.message_after_body == {"type": "http.disconnect"}
    assert sent[0]["status"] == 200


def test_one_byte_over_the_limit_is_refused() -> None:
    application, sent = run(
        http_scope(),
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"678901", "more_body": False},
        ],
    )

    assert not application.called
    assert sent[0]["status"] == 413
