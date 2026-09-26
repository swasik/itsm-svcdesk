# ai-generated: 100% - Claude Opus 5 wrote this file from design/LAB2.md section 4; the lecturer ran it
"""The two Lab 2 endpoints over HTTP (design/LAB2.md 4.1 and 4.2).

`test_dora.py` proves the arithmetic; this file proves the endpoint contract the checker relies on, and it
speaks only HTTP, so it would run against any implementation of the API.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PRACTICE = Path(__file__).resolve().parents[1] / "fixtures"   # copied into the repo, as a student copies it
WINDOW = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}
REQUIRED = ("spec_version", "window", "deployment_frequency_per_day", "change_lead_time_seconds_p50",
            "failed_deployment_recovery_time_seconds_p50", "change_fail_rate", "deployment_rework_rate",
            "counts", "anomalies", "ground_truth")


@pytest.fixture(scope="session")
def practice_events() -> list[dict]:
    text = (PRACTICE / "events-practice.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@pytest.fixture(scope="session")
def practice_expected() -> dict:
    return json.loads((PRACTICE / "metrics-practice.json").read_text(encoding="utf-8"))


def metrics(client, events, window=None):
    body = {"events": events}
    if window is not None:
        body["window"] = window
    return client.post("/dora/metrics", json=body, timeout=30.0)


def test_the_practice_fixture_gives_the_published_numbers(client, practice_events, practice_expected):
    resp = metrics(client, practice_events, WINDOW)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    for key in REQUIRED:
        assert key in body, key
    assert body == practice_expected


def test_the_endpoint_is_a_pure_function(client, practice_events):
    first = metrics(client, practice_events, WINDOW).json()
    second = metrics(client, practice_events, WINDOW).json()
    assert first == second


def test_order_and_duplicates_do_not_matter(client, practice_events):
    """R-05 and the fact that a log is a set of events, not a sequence."""
    baseline = metrics(client, practice_events, WINDOW).json()
    assert metrics(client, list(reversed(practice_events)), WINDOW).json() == baseline
    assert metrics(client, practice_events + practice_events, WINDOW).json() == baseline


def test_an_empty_log(client):
    body = metrics(client, [], WINDOW).json()
    assert body["deployment_frequency_per_day"] == 0
    assert body["change_lead_time_seconds_p50"] is None
    assert body["change_fail_rate"] is None
    assert body["counts"]["deployments"] == 0
    assert body["ground_truth"]["changes_delivered"] == 0


@pytest.mark.parametrize("body", [
    {"events": []},                                                        # no window
    {"window": WINDOW},                                                    # no events
    {"window": WINDOW, "events": {"not": "an array"}},
    {"window": {"from": WINDOW["to"], "to": WINDOW["to"]}, "events": []},   # empty window
    {"window": {"from": "yesterday", "to": WINDOW["to"]}, "events": []},
    {"window": WINDOW, "events": [{"event_id": "x", "type": "nope", "at": WINDOW["from"]}]},
])
def test_malformed_requests_are_rejected(client, body):
    resp = client.post("/dora/metrics", json=body, timeout=30.0)
    assert resp.status_code in (400, 422), resp.text
    assert "error" in resp.json()


def test_a_dangling_revert_is_rejected(client):
    events = [{"event_id": "c-1", "type": "commit", "at": "2026-09-02T00:00:00Z", "sha": "aaa",
               "branch": "main", "change_id": None, "reverts": "not-in-the-log"}]
    resp = metrics(client, events, WINDOW)
    assert resp.status_code in (400, 422)
    assert "error" in resp.json()


def test_ticket_events_stream(client):
    created = client.post("/tickets", json={
        "title": "lab2 stream", "reporter": {"name": "tester"}, "impact": 1, "urgency": 1},
        headers={"X-Test-Clock": "2026-10-14T10:00:00Z"}).json()
    client.post(f"/tickets/{created['id']}/ack", headers={"X-Test-Clock": "2026-10-14T10:05:00Z"})

    resp = client.get("/dora/ticket-events")
    assert resp.status_code == 200
    events = resp.json()
    assert isinstance(events, list)

    mine = [event for event in events if event["ticket_id"] == created["id"]]
    assert [event["phase"] for event in mine] == ["created", "acknowledged"]
    assert [event["state"] for event in mine] == ["new", "acknowledged"]
    assert all(event["priority"] == created["priority"] for event in mine)

    keys = [(event["at"], event["ticket_id"]) for event in events]
    assert keys == sorted(keys), "the stream must be ordered by (at, ticket_id) ascending"


def test_ticket_events_omits_instants_the_service_does_not_hold(client):
    """There is deliberately no `in_progress` phase: Lab 1 records no timestamp for it."""
    phases = {event["phase"] for event in client.get("/dora/ticket-events").json()}
    assert phases <= {"created", "acknowledged", "resolved", "closed"}
