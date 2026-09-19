# ai-generated: 100% - Claude Code (Fable 5.1) wrote these HTTP tests from design/LAB1.md sections 1 to 3; the lecturer ran them under all eight combinations
"""HTTP-level tests of the svcdesk contract, one pass per resolution combination (see conftest.py).

Check ids in comments refer to LAB1.md section 3 (L1-CORE-2). Every request that depends on time carries
X-Test-Clock; clocks deliberately jump backwards between requests because the service must never compare
one request's clock with another's (section 1.7).
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime

import httpx
import pytest

from conftest import LocalServer, requires_local
from vectors import BY_ID, CELL_FOR, T1, VECTORS, act, body, clock, create, drive, plus, same_instant, sla_at

T1_ACK = plus(T1, minutes=5)
T1_START = plus(T1, minutes=6)
T1_RESOLVE = plus(T1, hours=1)
T1_CLOSE = plus(T1, hours=2)


def has_error(response: httpx.Response) -> bool:
    payload = response.json()
    return isinstance(payload, dict) and isinstance(payload.get("error"), dict)


# --- 2.01, 2.02: health and unknown routes -------------------------------------------------------------


def test_health(client, combo):
    response = client.get("/health", headers=clock(T1))
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok" and payload["service"] == "svcdesk"
    # extra fields are allowed; the reference reports the active combination for humans
    assert payload["resolutions"] == {"C1": combo[0], "C2": combo[1], "C3": combo[2]}


def test_unknown_path_is_404_json(client):
    response = client.get("/this-route-does-not-exist-9f3c", headers=clock(T1))
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert has_error(response)


def test_wrong_method_on_known_path_is_404_or_405_json(client):
    response = client.put("/tickets", headers=clock(T1))
    assert response.status_code in (404, 405)
    assert has_error(response)


# --- 2.03 to 2.06: create, clock, ids ----------------------------------------------------------------------


def test_create_returns_full_ticket(client):
    ticket = create(client, T1)
    assert isinstance(ticket["id"], str) and ticket["id"]
    assert ticket["state"] == "new"
    assert ticket["priority"] == "P1"
    assert same_instant(ticket["created_at"], T1)
    assert ticket["title"] == "printer on fire"
    assert ticket["reporter"] == {"name": "Anna Kowalska", "email": "anna@example.org", "vip": False}
    assert ticket["description"] == "created by the reference test suite"
    assert ticket["impact"] == 1 and ticket["urgency"] == 1
    for field in ("acknowledged_at", "resolved_at", "closed_at", "related_to"):
        assert ticket[field] is None
    assert set(ticket["sla"]) == {"ack_due_at", "resolve_due_at"}
    assert ticket["created_at"].endswith("Z")


def test_two_creates_have_distinct_ids(client):
    assert create(client, T1)["id"] != create(client, T1)["id"]


def test_defaults_for_optional_fields(client):
    minimal = {"title": "minimal", "reporter": {"name": "Jan"}, "impact": 2, "urgency": 2}
    response = client.post("/tickets", json=minimal, headers=clock(T1))
    assert response.status_code == 201, response.text
    ticket = response.json()
    assert ticket["description"] == ""
    assert ticket["reporter"] == {"name": "Jan", "email": None, "vip": False}
    assert ticket["related_to"] is None


def test_related_to_is_stored_but_not_validated(client):
    ticket = create(client, T1, related_to="not-a-real-ticket-id")
    assert ticket["related_to"] == "not-a-real-ticket-id"


def test_server_owned_and_unknown_fields_are_ignored(client):
    ticket = create(
        client, T1, impact=3, urgency=3,
        id="client-chosen-id", priority="P1", state="closed", created_at="2001-01-01T00:00:00Z",
        acknowledged_at="2001-01-01T00:00:00Z", resolved_at="2001-01-01T00:00:00Z", closed_at="2001-01-01T00:00:00Z",
        sla={"ack_due_at": "2001-01-01T00:00:00Z", "resolve_due_at": "2001-01-01T00:00:00Z"},
        totally_unknown_field={"nested": True},
    )
    assert ticket["id"] != "client-chosen-id"
    assert ticket["priority"] == "P4"
    assert ticket["state"] == "new"
    assert same_instant(ticket["created_at"], T1)
    assert ticket["acknowledged_at"] is None and ticket["resolved_at"] is None and ticket["closed_at"] is None
    assert not same_instant(ticket["sla"]["ack_due_at"], "2001-01-01T00:00:00Z")
    assert "totally_unknown_field" not in ticket


# --- 2.07 to 2.15: the matrix --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("impact", "urgency", "priority"),
    [(1, 1, "P1"), (1, 2, "P2"), (1, 3, "P3"), (2, 1, "P2"), (2, 2, "P3"), (2, 3, "P4"), (3, 1, "P3"), (3, 2, "P4"), (3, 3, "P4")],
)
def test_priority_matrix(client, impact, urgency, priority):
    assert create(client, T1, impact, urgency)["priority"] == priority


# --- 2.16 to 2.19: validation ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda b: b.pop("title"), id="missing-title"),
        pytest.param(lambda b: b.update(title=""), id="empty-title"),
        pytest.param(lambda b: b.update(title="x" * 201), id="201-char-title"),
        pytest.param(lambda b: b.update(title=123), id="numeric-title"),
        pytest.param(lambda b: b.update(description="d" * 4001), id="4001-char-description"),
        pytest.param(lambda b: b.pop("reporter"), id="missing-reporter"),
        pytest.param(lambda b: b["reporter"].pop("name"), id="missing-reporter-name"),
        pytest.param(lambda b: b["reporter"].update(name=""), id="empty-reporter-name"),
        pytest.param(lambda b: b.pop("impact"), id="missing-impact"),
        pytest.param(lambda b: b.update(impact=5), id="impact-5"),
        pytest.param(lambda b: b.update(impact=0), id="impact-0"),
        pytest.param(lambda b: b.update(urgency="high"), id="urgency-high"),
        pytest.param(lambda b: b.update(urgency="1"), id="urgency-string-1"),
        pytest.param(lambda b: b.update(urgency=1.0), id="urgency-float"),
        pytest.param(lambda b: b.update(urgency=True), id="urgency-bool"),
        pytest.param(lambda b: b.update(urgency=None), id="urgency-null"),
    ],
)
def test_validation_errors(client, mutate):
    payload = body()
    mutate(payload)
    response = client.post("/tickets", json=payload, headers=clock(T1))
    assert response.status_code in (400, 422), response.text
    assert has_error(response)


def test_malformed_json_body_is_400_or_422(client):
    response = client.post("/tickets", content=b"{not json", headers={**clock(T1), "content-type": "application/json"})
    assert response.status_code in (400, 422)
    assert has_error(response)


def test_boundary_lengths_are_accepted(client):
    ticket = create(client, T1, title="t" * 200, description="d" * 4000)
    assert len(ticket["title"]) == 200 and len(ticket["description"]) == 4000


# --- 2.20 to 2.23: get and list -----------------------------------------------------------------------------------


def test_get_ticket(client):
    created = create(client, T1, title="get me")
    response = client.get(f"/tickets/{created['id']}", headers=clock(T1))
    assert response.status_code == 200
    assert response.json()["id"] == created["id"] and response.json()["title"] == "get me"


def test_get_unknown_ticket_is_404_json(client):
    response = client.get("/tickets/does-not-exist-9f3c", headers=clock(T1))
    assert response.status_code == 404 and has_error(response)


def test_list_filters_by_state(client):
    created = create(client, T1)
    response = client.get("/tickets", params={"state": "new"}, headers=clock(T1))
    assert response.status_code == 200
    ids = [t["id"] for t in response.json()]
    assert created["id"] in ids
    assert all(t["state"] == "new" for t in response.json())


def test_list_filters_by_priority(client):
    p1 = create(client, T1, 1, 1)
    p4 = create(client, T1, 3, 3)
    ids = [t["id"] for t in client.get("/tickets", params={"priority": "P1"}, headers=clock(T1)).json()]
    assert p1["id"] in ids and p4["id"] not in ids


def test_list_filters_combine_and_unknown_values_match_nothing(client):
    created = create(client, T1, 3, 3)
    both = client.get("/tickets", params={"state": "new", "priority": "P4"}, headers=clock(T1)).json()
    assert created["id"] in [t["id"] for t in both]
    assert client.get("/tickets", params={"state": "bogus"}, headers=clock(T1)).json() == []


def test_list_returns_all_matching_tickets_without_pagination(client):
    marker = f"batch-{uuid.uuid4()}"
    for _ in range(25):
        create(client, T1, title=marker)
    response = client.get("/tickets", headers=clock(T1))
    assert response.status_code == 200 and isinstance(response.json(), list)
    assert sum(1 for t in response.json() if t["title"] == marker) == 25


def test_list_and_get_are_clock_independent(client):
    created = create(client, T1)
    later, earlier = plus(T1, days=400), "2000-01-01T00:00:00Z"
    for at in (later, earlier, None):
        assert client.get(f"/tickets/{created['id']}", headers=clock(at)).json() == created
        listed = [t for t in client.get("/tickets", headers=clock(at)).json() if t["id"] == created["id"]]
        assert listed == [created]


# --- 1.7: the test clock ----------------------------------------------------------------------------------------------


def test_clock_is_honoured_on_create(client):
    assert same_instant(create(client, BY_ID["T5"].created_at)["created_at"], BY_ID["T5"].created_at)


def test_clock_with_offset_is_normalised_to_utc(client):
    ticket = create(client, "2026-10-14T12:00:00+02:00")
    assert same_instant(ticket["created_at"], T1)
    assert ticket["created_at"].endswith("Z")


@pytest.mark.parametrize("value", ["yesterday", "2026-10-14T10:00:00", "2026-10-14", "", "1760436000"])
def test_malformed_clock_is_400_or_422(client, value):
    response = client.post("/tickets", json=body(), headers={"X-Test-Clock": value})
    assert response.status_code in (400, 422), response.text
    assert has_error(response)


def test_without_header_now_is_real_time(client):
    before = datetime.now(UTC).replace(microsecond=0)
    ticket = create(client, None)
    after = datetime.now(UTC)
    created = datetime.fromisoformat(ticket["created_at"])
    assert before <= created <= after


def test_clock_is_never_monotonic(client):
    ticket = create(client, T1)
    earlier = "2020-01-01T00:00:00Z"
    acked = drive(client, ticket["id"], ("ack", earlier))
    assert same_instant(acked["acknowledged_at"], earlier)
    assert same_instant(acked["created_at"], T1)
    resolved = drive(client, ticket["id"], ("start", plus(T1, days=30)), ("resolve", "1999-12-31T23:59:59Z"))
    assert same_instant(resolved["resolved_at"], "1999-12-31T23:59:59Z")


@requires_local
def test_clock_header_is_ignored_when_test_clock_is_off(combo, tmp_path):
    server = LocalServer(combo, str(tmp_path / "off.db"), test_clock=False).start()
    try:
        with httpx.Client(base_url=server.url, timeout=10) as http:
            assert http.get("/health").json()["test_clock"] is False
            before = datetime.now(UTC).replace(microsecond=0)
            response = http.post("/tickets", json=body(), headers={"X-Test-Clock": T1})
            assert response.status_code == 201
            created = datetime.fromisoformat(response.json()["created_at"])
            assert created >= before and not same_instant(response.json()["created_at"], T1)
            # a malformed header is ignored too, not rejected
            assert http.post("/tickets", json=body(), headers={"X-Test-Clock": "yesterday"}).status_code == 201
    finally:
        server.stop()


# --- 2.24 to 2.34, 2.49: the state machine --------------------------------------------------------------------------


def test_ack_sets_acknowledged_at(client):
    ticket = create(client, T1)
    acked = drive(client, ticket["id"], ("ack", T1_ACK))
    assert acked["state"] == "acknowledged" and same_instant(acked["acknowledged_at"], T1_ACK)
    assert acked["id"] == ticket["id"]


def test_ack_twice_is_409(client):
    ticket = create(client, T1)
    drive(client, ticket["id"], ("ack", T1_ACK))
    response = act(client, ticket["id"], "ack", T1_ACK)
    assert response.status_code == 409 and has_error(response)
    assert response.json()["error"]["code"] == "invalid_transition"


def test_concurrent_acks_yield_exactly_one_success(client, server):
    """Eight acknowledgements racing on one ticket (R-07, checks 2.24/2.25 under load): exactly one 200, the
    others 409, and acknowledged_at is the winner's clock. The reference serialises read, check and write in
    one transaction; without it two requests both read `new` and both succeed (review of PR 2)."""
    ticket = create(client, T1)
    n = 8
    barrier = threading.Barrier(n)
    outcomes: list[tuple[int, str]] = []
    lock = threading.Lock()

    def worker(minute: int) -> None:
        with httpx.Client(base_url=server.url, timeout=10.0) as http:
            barrier.wait()
            response = act(http, ticket["id"], "ack", plus(T1, minutes=minute))
            with lock:
                outcomes.append((response.status_code, response.json().get("acknowledged_at", "")))

    threads = [threading.Thread(target=worker, args=(minute,)) for minute in range(1, n + 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(code for code, _ in outcomes) == [200] + [409] * (n - 1), outcomes
    winner = next(stamp for code, stamp in outcomes if code == 200)
    assert same_instant(client.get(f"/tickets/{ticket['id']}", headers=clock(T1)).json()["acknowledged_at"], winner)


def test_start_then_resolve_then_close(client):
    ticket = create(client, T1)
    started = drive(client, ticket["id"], ("ack", T1_ACK), ("start", T1_START))
    assert started["state"] == "in_progress"
    resolved = drive(client, ticket["id"], ("resolve", T1_RESOLVE))
    assert resolved["state"] == "resolved" and same_instant(resolved["resolved_at"], T1_RESOLVE)
    closed = drive(client, ticket["id"], ("close", T1_CLOSE))
    assert closed["state"] == "closed" and same_instant(closed["closed_at"], T1_CLOSE)
    assert same_instant(closed["resolved_at"], T1_RESOLVE) and same_instant(closed["acknowledged_at"], T1_ACK)


@pytest.mark.parametrize(
    ("setup", "action"),
    [
        pytest.param((), "start", id="start-on-new"),
        pytest.param((), "resolve", id="resolve-on-new"),
        pytest.param((), "close", id="close-on-new"),
        pytest.param((), "reopen", id="reopen-on-new"),
        pytest.param((("ack", T1_ACK),), "resolve", id="resolve-on-acknowledged-no-start"),
        pytest.param((("ack", T1_ACK),), "close", id="close-on-acknowledged"),
        pytest.param((("ack", T1_ACK),), "reopen", id="reopen-on-acknowledged"),
        pytest.param((("ack", T1_ACK), ("start", T1_START)), "close", id="close-on-in-progress"),
        pytest.param((("ack", T1_ACK), ("start", T1_START)), "ack", id="ack-on-in-progress"),
        pytest.param((("ack", T1_ACK), ("start", T1_START)), "reopen", id="reopen-on-in-progress"),
        pytest.param((("ack", T1_ACK), ("start", T1_START), ("resolve", T1_RESOLVE)), "start", id="start-on-resolved"),
        pytest.param((("ack", T1_ACK), ("start", T1_START), ("resolve", T1_RESOLVE), ("close", T1_CLOSE)), "close", id="close-on-closed"),
        pytest.param((("ack", T1_ACK), ("start", T1_START), ("resolve", T1_RESOLVE), ("close", T1_CLOSE)), "ack", id="ack-on-closed"),
    ],
)
def test_invalid_transitions_are_409(client, setup, action):
    ticket = create(client, T1)
    state_before = "new"
    if setup:
        state_before = drive(client, ticket["id"], *setup)["state"]
    response = act(client, ticket["id"], action, T1_CLOSE)
    assert response.status_code == 409, response.text
    assert has_error(response)
    unchanged = client.get(f"/tickets/{ticket['id']}", headers=clock(T1)).json()
    assert unchanged["state"] == state_before


@pytest.mark.parametrize("action", ["ack", "start", "resolve", "close", "reopen"])
def test_actions_on_unknown_id_are_404(client, action):
    response = act(client, "does-not-exist-9f3c", action, T1)
    assert response.status_code == 404 and has_error(response)


def test_sla_of_unknown_id_is_404(client):
    response = client.get("/tickets/does-not-exist-9f3c/sla", headers=clock(T1))
    assert response.status_code == 404 and has_error(response)


def _resolved(client) -> dict:
    ticket = create(client, T1)
    return drive(client, ticket["id"], ("ack", T1_ACK), ("start", T1_START), ("resolve", T1_RESOLVE))


def _closed(client) -> dict:
    ticket = _resolved(client)
    return drive(client, ticket["id"], ("close", T1_CLOSE))


def test_reopen_resolved_within_window(client):
    ticket = _resolved(client)
    reopened = drive(client, ticket["id"], ("reopen", plus(T1_RESOLVE, days=6)))
    assert reopened["state"] == "in_progress"
    assert reopened["resolved_at"] is None and reopened["closed_at"] is None
    assert same_instant(reopened["acknowledged_at"], T1_ACK)
    assert reopened["sla"] == ticket["sla"]


def test_reopen_resolved_at_exactly_seven_days_is_allowed(client):
    ticket = _resolved(client)
    assert act(client, ticket["id"], "reopen", plus(T1_RESOLVE, days=7)).status_code == 200


def test_reopen_resolved_after_seven_days_is_409(client):
    ticket = _resolved(client)
    response = act(client, ticket["id"], "reopen", plus(T1_RESOLVE, days=7, seconds=1))
    assert response.status_code == 409 and has_error(response)
    assert client.get(f"/tickets/{ticket['id']}", headers=clock(T1)).json()["state"] == "resolved"


def test_reopen_with_a_clock_earlier_than_resolved_at_is_allowed(client):
    ticket = _resolved(client)
    assert act(client, ticket["id"], "reopen", "2000-01-01T00:00:00Z").status_code == 200


def test_reopened_ticket_can_be_resolved_again(client):
    ticket = _resolved(client)
    again = plus(T1_RESOLVE, days=2)
    drive(client, ticket["id"], ("reopen", plus(T1_RESOLVE, days=1)))
    resolved = drive(client, ticket["id"], ("resolve", again))
    assert resolved["state"] == "resolved" and same_instant(resolved["resolved_at"], again)
    assert resolved["sla"] == ticket["sla"]


def test_reopen_closed_one_day_later_follows_c2(client, c2):
    ticket = _closed(client)
    response = act(client, ticket["id"], "reopen", plus(T1_CLOSE, days=1))
    if c2 == "reopen":
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "in_progress"
        assert response.json()["closed_at"] is None and response.json()["resolved_at"] is None
    else:
        assert response.status_code == 409, response.text
        assert has_error(response)
        assert client.get(f"/tickets/{ticket['id']}", headers=clock(T1)).json()["state"] == "closed"


def test_reopen_closed_after_seven_days_is_409_under_both_c2(client):
    ticket = _closed(client)
    response = act(client, ticket["id"], "reopen", plus(T1_CLOSE, days=7, seconds=1))
    assert response.status_code == 409 and has_error(response)


def test_reopen_closed_at_exactly_seven_days_follows_c2(client, c2):
    ticket = _closed(client)
    response = act(client, ticket["id"], "reopen", plus(T1_CLOSE, days=7))
    assert response.status_code == (200 if c2 == "reopen" else 409)


# --- 2.36 to 2.41: SLA vectors and the C1 probe ----------------------------------------------------------------------


@pytest.mark.parametrize("vector", VECTORS, ids=[v.id for v in VECTORS])
def test_sla_vectors(client, c1, vector):
    impact, urgency = CELL_FOR[vector.priority]
    ticket = create(client, vector.created_at, impact, urgency)
    assert ticket["priority"] == vector.priority
    ack_due, resolve_due = vector.expected(c1)
    assert same_instant(ticket["sla"]["ack_due_at"], ack_due), (vector.id, ticket["sla"])
    assert same_instant(ticket["sla"]["resolve_due_at"], resolve_due), (vector.id, ticket["sla"])
    view = sla_at(client, ticket["id"], vector.created_at)
    assert same_instant(view["ack_due_at"], ack_due) and same_instant(view["resolve_due_at"], resolve_due)
    assert view["priority"] == vector.priority


def test_c1_probe_t3_matches_declared_resolution(client, c1):
    t3 = BY_ID["T3"]
    ticket = create(client, t3.created_at, 1, 1)
    pair = (ticket["sla"]["ack_due_at"], ticket["sla"]["resolve_due_at"])
    wall = (t3.ack_wall, t3.resolve_wall)
    business = (t3.ack_business, t3.resolve_business)
    observed = "wallclock" if all(same_instant(a, b) for a, b in zip(pair, wall)) else (
        "business" if all(same_instant(a, b) for a, b in zip(pair, business)) else "mixed"
    )
    assert observed in ("wallclock", "business"), pair
    assert observed == c1


def test_t1_is_identical_under_both_c1(client):
    t1 = BY_ID["T1"]
    ticket = create(client, t1.created_at, 1, 1)
    assert same_instant(ticket["sla"]["ack_due_at"], t1.ack_wall)
    assert same_instant(ticket["sla"]["resolve_due_at"], t1.resolve_wall)


# --- 2.42 to 2.45: breach and pause -----------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def shared_t2(client) -> dict:
    """A T2 ticket (P3, Friday 15:30 CEST) that is never acknowledged."""
    return create(client, BY_ID["T2"].created_at, 1, 3)


def test_ack_breached_after_due(client, shared_t2):
    view = sla_at(client, shared_t2["id"], "2026-10-19T09:31:00Z")
    assert view["ack_breached"] is True and view["resolve_breached"] is False


def test_ack_not_breached_before_due(client, shared_t2):
    assert sla_at(client, shared_t2["id"], "2026-10-19T09:00:00Z")["ack_breached"] is False


def test_equality_is_not_a_breach(client, shared_t2):
    view = sla_at(client, shared_t2["id"], "2026-10-19T09:30:00Z")
    assert view["ack_breached"] is False
    view = sla_at(client, shared_t2["id"], "2026-10-21T13:30:00Z")
    assert view["resolve_breached"] is False
    assert sla_at(client, shared_t2["id"], "2026-10-21T13:30:01Z")["resolve_breached"] is True


def test_ack_in_time_is_never_breached_later(client):
    ticket = create(client, BY_ID["T2"].created_at, 1, 3)
    drive(client, ticket["id"], ("ack", "2026-10-16T13:45:00Z"))
    assert sla_at(client, ticket["id"], "2026-10-19T12:00:00Z")["ack_breached"] is False


def test_ack_exactly_at_due_is_not_a_breach(client):
    ticket = create(client, BY_ID["T2"].created_at, 1, 3)
    drive(client, ticket["id"], ("ack", "2026-10-19T09:30:00Z"))
    assert sla_at(client, ticket["id"], "2027-01-01T00:00:00Z")["ack_breached"] is False


def test_late_ack_stays_breached(client):
    ticket = create(client, BY_ID["T2"].created_at, 1, 3)
    drive(client, ticket["id"], ("ack", "2026-10-19T09:30:01Z"))
    assert sla_at(client, ticket["id"], "2026-10-16T13:31:00Z")["ack_breached"] is True


def test_paused_on_saturday_for_business_clock(client, shared_t2):
    assert sla_at(client, shared_t2["id"], "2026-10-17T10:00:00Z")["paused"] is True
    assert sla_at(client, shared_t2["id"], "2026-10-19T09:00:00Z")["paused"] is False


def test_paused_respects_half_open_window(client, shared_t2):
    assert sla_at(client, shared_t2["id"], "2026-10-14T14:00:00Z")["paused"] is True  # 16:00:00 CEST
    assert sla_at(client, shared_t2["id"], "2026-10-14T13:59:59Z")["paused"] is False
    assert sla_at(client, shared_t2["id"], "2026-10-14T06:00:00Z")["paused"] is False  # 08:00:00 CEST
    assert sla_at(client, shared_t2["id"], "2026-10-14T05:59:59Z")["paused"] is True


def test_p1_paused_follows_c1(client, c1):
    ticket = create(client, BY_ID["T3"].created_at, 1, 1)
    assert sla_at(client, ticket["id"], "2026-10-17T10:00:00Z")["paused"] is (c1 == "business")


def test_resolved_and_closed_tickets_are_never_paused(client):
    ticket = create(client, T1, 1, 3)
    drive(client, ticket["id"], ("ack", T1_ACK), ("start", T1_START), ("resolve", T1_RESOLVE))
    assert sla_at(client, ticket["id"], "2026-10-17T10:00:00Z")["paused"] is False
    drive(client, ticket["id"], ("close", T1_CLOSE))
    assert sla_at(client, ticket["id"], "2026-10-17T10:00:00Z")["paused"] is False


def test_resolve_breach_uses_resolved_at_once_resolved(client):
    ticket = create(client, T1, 1, 1)  # P1: resolve due 14:00Z under both clocks
    drive(client, ticket["id"], ("ack", T1_ACK), ("start", T1_START), ("resolve", "2026-10-14T13:00:00Z"))
    assert sla_at(client, ticket["id"], "2026-12-01T00:00:00Z")["resolve_breached"] is False
    late = create(client, T1, 1, 1)
    drive(client, late["id"], ("ack", T1_ACK), ("start", T1_START), ("resolve", "2026-10-14T14:00:01Z"))
    assert sla_at(client, late["id"], T1)["resolve_breached"] is True


def test_reopen_makes_ticket_unresolved_again_with_unchanged_target(client):
    ticket = create(client, T1, 1, 1)
    drive(client, ticket["id"], ("ack", T1_ACK), ("start", T1_START), ("resolve", "2026-10-14T13:00:00Z"))
    drive(client, ticket["id"], ("reopen", "2026-10-14T13:30:00Z"))
    view = sla_at(client, ticket["id"], "2026-10-14T14:00:01Z")
    assert view["resolve_breached"] is True
    assert same_instant(view["resolve_due_at"], ticket["sla"]["resolve_due_at"])
    assert sla_at(client, ticket["id"], "2026-10-14T13:59:00Z")["resolve_breached"] is False


def test_sla_view_shape(client):
    ticket = create(client, T1)
    view = sla_at(client, ticket["id"], T1)
    assert set(view) == {"priority", "ack_due_at", "resolve_due_at", "ack_breached", "resolve_breached", "paused"}
    assert all(isinstance(view[k], bool) for k in ("ack_breached", "resolve_breached", "paused"))


# --- 2.46 to 2.48: VIP reporters -------------------------------------------------------------------------------------


def test_vip_low_ticket_follows_c3(client, c3):
    ticket = create(client, T1, 3, 3, vip=True)
    assert ticket["priority"] == ("P2" if c3 == "vip" else "P4")
    assert ticket["reporter"]["vip"] is True


@pytest.mark.parametrize(("impact", "urgency", "matrix_priority"), [(1, 3, "P3"), (2, 2, "P3"), (3, 1, "P3"), (2, 3, "P4"), (3, 2, "P4")])
def test_vip_uplift_applies_to_every_p3_and_p4_cell(client, c3, impact, urgency, matrix_priority):
    assert create(client, T1, impact, urgency, vip=True)["priority"] == ("P2" if c3 == "vip" else matrix_priority)


def test_vip_p1_and_p2_are_unchanged_under_both_c3(client):
    assert create(client, T1, 1, 1, vip=True)["priority"] == "P1"
    assert create(client, T1, 1, 2, vip=True)["priority"] == "P2"
    assert create(client, T1, 2, 1, vip=True)["priority"] == "P2"


def test_priority_in_body_is_ignored(client, c3):
    observed = create(client, T1, 3, 3, vip=True)["priority"]
    assert create(client, T1, 3, 3, vip=True, priority="P1")["priority"] == observed
    assert create(client, T1, 3, 3, priority="P1")["priority"] == "P4"


def test_vip_ticket_uses_the_uplifted_priority_for_sla(client, c3):
    t2 = BY_ID["T2"]
    ticket = create(client, t2.created_at, 1, 3, vip=True)
    if c3 == "vip":
        assert same_instant(ticket["sla"]["ack_due_at"], "2026-10-19T06:30:00Z")  # P2 business: 30 min Fri + 30 min Mon
    else:
        assert same_instant(ticket["sla"]["ack_due_at"], t2.ack_business)


# --- 1.9: persistence ------------------------------------------------------------------------------------------------


@requires_local
def test_tickets_survive_a_restart(combo, tmp_path):
    db_path = str(tmp_path / "persist.db")
    first = LocalServer(combo, db_path).start()
    try:
        with httpx.Client(base_url=first.url, timeout=10) as http:
            ticket = create(http, T1, title="survivor")
    finally:
        first.stop()
    second = LocalServer(combo, db_path).start()
    try:
        with httpx.Client(base_url=second.url, timeout=10) as http:
            response = http.get(f"/tickets/{ticket['id']}")
            assert response.status_code == 200 and response.json() == ticket
    finally:
        second.stop()
