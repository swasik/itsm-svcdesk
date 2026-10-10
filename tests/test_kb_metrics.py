# ai-generated: 100% - Claude Code (Opus 5.5) wrote this file from design/LAB3.md sections 3.1 and 3.2; the lecturer reviews it
"""GET /kb/search and the RED histogram (design/LAB3.md M-02..M-06), in process against a fake kb-index."""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from conftest import requires_local

pytestmark = requires_local


class FakeIndex(BaseHTTPRequestHandler):
    calls: list[str] = []

    def do_GET(self) -> None:  # noqa: N802 - http.server's naming
        url = urlparse(self.path)
        q = parse_qs(url.query).get("q", [""])[0]
        FakeIndex.calls.append(q)
        if url.path != "/search":
            self.send_response(404)
            self.end_headers()
            return
        if q.startswith("force-error"):
            body, status = {"error": {"code": "index_unavailable", "message": "x"}}, 503
        else:
            body, status = {"query": q, "hits": [{"id": "KB-0001", "title": "t", "score": 0.9}]}, 200
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


@pytest.fixture(scope="module")
def fake_index():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeIndex)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def app_client(fake_index, tmp_path_factory):
    from svcdesk.app import create_app
    from svcdesk.config import Settings

    settings = Settings(test_clock=True, db_path=str(tmp_path_factory.mktemp("kb") / "svcdesk.db"),
                        kb_index_url=fake_index)
    with TestClient(create_app(settings)) as client:
        yield client


def samples(text: str, name: str) -> dict[tuple, float]:
    out = {}
    for line in text.splitlines():
        m = re.match(rf'^{re.escape(name)}\{{(.*)\}} (\S+)$', line)
        if m:
            labels = tuple(sorted(re.findall(r'(\w+)="([^"]*)"', m.group(1))))
            out[labels] = float(m.group(2))
    return out


def test_search_passes_the_upstream_hits_through(app_client):
    FakeIndex.calls.clear()
    r = app_client.get("/kb/search", params={"q": "vpn drops"})
    assert r.status_code == 200
    assert r.json() == {"query": "vpn drops", "hits": [{"id": "KB-0001", "title": "t", "score": 0.9}]}
    assert FakeIndex.calls == ["vpn drops"], "exactly one upstream call per request"


@pytest.mark.parametrize("q", [" ", "x" * 200])
def test_search_accepts_every_q_of_1_to_200_characters(app_client, q):
    FakeIndex.calls.clear()
    r = app_client.get("/kb/search", params={"q": q})
    assert r.status_code == 200 and FakeIndex.calls == [q], "M-02: a blank q of one character is still a query"


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "x" * 201}])
def test_search_rejects_a_bad_query(app_client, params):
    r = app_client.get("/kb/search", params=params)
    assert r.status_code in (400, 422)
    assert "error" in r.json()


def test_an_upstream_failure_is_a_502(app_client):
    r = app_client.get("/kb/search", params={"q": "force-error-test"})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "upstream_unavailable"


def test_an_unreachable_upstream_is_a_502(tmp_path):
    from svcdesk.app import create_app
    from svcdesk.config import Settings

    settings = Settings(db_path=str(tmp_path / "db"), kb_index_url="http://127.0.0.1:9")
    with TestClient(create_app(settings)) as client:
        r = client.get("/kb/search", params={"q": "x"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "upstream_unavailable"


def test_the_histogram_uses_route_templates_and_no_query_strings(app_client):
    app_client.get("/kb/search", params={"q": "one"})
    app_client.get("/tickets/does-not-exist-123")
    app_client.get("/no/such/path/4711")
    app_client.get("/health", params={"probe": "abc-987"})
    text = app_client.get("/metrics", headers={"Accept": "text/plain"}).text
    assert "# TYPE http_server_request_duration_seconds histogram" in text
    counts = samples(text, "http_server_request_duration_seconds_count")
    routes = {dict(k)["http_route"] for k in counts}
    assert {"/kb/search", "/tickets/{ticket_id}", "unmatched", "/health"} <= routes
    for key in counts:
        assert set(dict(key)) == {"http_request_method", "http_route", "http_response_status_code"}
    assert "does-not-exist-123" not in text and "4711" not in text and "abc-987" not in text
    assert not any("/metrics" == dict(k)["http_route"] for k in counts)


def test_the_ladder_is_small_and_holds_the_slo_threshold():
    from svcdesk.metrics import LADDER

    assert len(LADDER) <= 30 and list(LADDER) == sorted(set(LADDER))
    assert 0.3 in LADDER
    # the reference profile's p99 (about 0.231 s) lies in a bucket at most 10 % of it wide
    lo = max(b for b in LADDER if b < 0.231)
    hi = min(b for b in LADDER if b >= 0.231)
    assert (hi - lo) / 0.231 <= 0.1
