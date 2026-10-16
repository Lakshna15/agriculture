from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Added to every response.
SECURITY_HEADERS = {
    # Browsers must treat a response as the type it declares, never sniff another.
    "X-Content-Type-Options": "nosniff",
    # No page of this API has a reason to appear inside a frame.
    "X-Frame-Options": "DENY",
    # Links followed from API pages reveal nothing about where they came from.
    "Referrer-Policy": "no-referrer",
    # Responses carry personal data such as reservations and notifications,
    # so neither browsers nor shared proxies may keep a copy.
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware:
    """Adds SECURITY_HEADERS to every HTTP response, without overriding one already set."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._encoded_headers = [
            (name.lower().encode("latin-1"), value.encode("latin-1"))
            for name, value in SECURITY_HEADERS.items()
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _value in headers}
                headers.extend(
                    (name, value) for name, value in self._encoded_headers if name not in present
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
