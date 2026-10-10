# ai-generated: 100% - Claude Code (Opus 5.5) wrote this file from design/LAB3.md section 3.2; the lecturer reviews it
"""RED instrumentation: one request histogram, recorded by a pure ASGI middleware, exposed on GET /metrics.

The names follow the OpenTelemetry HTTP semantic conventions in their Prometheus form (design/LAB3.md M-04):
`http_server_request_duration_seconds` with `http_request_method`, `http_route`, `http_response_status_code`.
`http_route` is the matched route's template, never the raw path, so ids and query strings never become labels
(M-05); a request that matches no route is recorded as `unmatched`.

The ladder is designed for this repository's kb-index profile (login `itsm-reference`, p99 about 231 ms): coarse
where nothing needs resolving, a boundary every 10 ms from 180 to 280 ms, and 0.3 s exact for the latency SLI
(slo.md). See slo.md for the defence.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from prometheus_client import CONTENT_TYPE_PLAIN_0_0_4, REGISTRY, Histogram, generate_latest

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable[[], Awaitable[Message]], Callable[[Message], Awaitable[None]]], Awaitable[None]]

LADDER = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.15,
    0.18, 0.19, 0.2, 0.21, 0.22, 0.23, 0.24, 0.25, 0.26, 0.27, 0.28, 0.3,
    0.4, 0.5, 1.0, 2.5, 5.0,
)

UNMATCHED = "unmatched"

REQUEST_DURATION = Histogram(
    "http_server_request_duration_seconds",
    "Duration of HTTP server requests, from the first byte received to the last byte sent.",
    ("http_request_method", "http_route", "http_response_status_code"),
    buckets=LADDER,
)


def route_template(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path else UNMATCHED


class MetricsMiddleware:
    """Times every HTTP request except GET /metrics itself; the status is the one the response started with."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive, send) -> None:
        if scope.get("type") != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message.get("type") == "http.response.start":
                status = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            REQUEST_DURATION.labels(
                http_request_method=scope.get("method", "GET"),
                http_route=route_template(scope),
                http_response_status_code=str(status),
            ).observe(time.perf_counter() - start)


def exposition() -> tuple[bytes, str]:
    """The text format 0.0.4 the lab's checker and any Prometheus read."""
    return generate_latest(REGISTRY), CONTENT_TYPE_PLAIN_0_0_4
