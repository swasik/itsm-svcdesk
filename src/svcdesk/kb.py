# ai-generated: 100% - Claude Code (Opus 5.5) wrote this file from design/LAB3.md section 3.1; the lecturer reviews it
"""GET /kb/search: one call to the kb-index dependency per request (design/LAB3.md M-02).

No cache and no retry: the service's latency and error rate are the dependency's, which is what Lab 3 measures.
An upstream failure - a non-200, a timeout, a refused connection - is a 502 `upstream_unavailable`.
"""

from __future__ import annotations

import httpx

from .service import ApiError

MAX_QUERY = 200
TIMEOUT_SECONDS = 5.0


class KbClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            limits = httpx.Limits(max_connections=200, max_keepalive_connections=100)
            self._client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS, limits=limits)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search(self, q: str | None) -> dict:
        if not q:                      # M-02: 1..200 characters; a blank q is still a query
            raise ApiError(400, "invalid_query", "q: expected 1..200 characters")
        if len(q) > MAX_QUERY:
            raise ApiError(400, "invalid_query", f"q: at most {MAX_QUERY} characters, got {len(q)}")
        try:
            response = await self.client().get(f"{self.base_url}/search", params={"q": q})
        except httpx.HTTPError as exc:
            raise ApiError(502, "upstream_unavailable", f"kb-index did not answer: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise ApiError(502, "upstream_unavailable", f"kb-index answered {response.status_code}")
        try:
            hits = response.json()["hits"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ApiError(502, "upstream_unavailable", "kb-index answered something that is not a search result") from exc
        return {"query": q, "hits": hits}
