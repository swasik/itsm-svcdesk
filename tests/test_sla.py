# ai-generated: 100% - Claude Code (Fable 5.1) wrote these unit tests from design/LAB1.md sections 1.2 to 1.4 and 1.7; the lecturer ran them
"""Unit tests of the pure functions: SLA arithmetic (T1-T8 under both clocks), the priority matrix, instants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from svcdesk import sla
from svcdesk.clock import format_instant, parse_instant
from svcdesk.priority import MATRIX, priority_for
from vectors import VECTORS, instant


@pytest.mark.parametrize("vector", VECTORS, ids=[v.id for v in VECTORS])
def test_wallclock_targets(vector):
    ack, resolve = sla.TARGETS[vector.priority]
    created = instant(vector.created_at)
    assert format_instant(sla.wallclock_due(created, ack)) == vector.ack_wall
    assert format_instant(sla.wallclock_due(created, resolve)) == vector.resolve_wall


@pytest.mark.parametrize("vector", VECTORS, ids=[v.id for v in VECTORS])
def test_business_targets(vector):
    ack, resolve = sla.TARGETS[vector.priority]
    created = instant(vector.created_at)
    assert format_instant(sla.business_due(created, ack)) == vector.ack_business
    assert format_instant(sla.business_due(created, resolve)) == vector.resolve_business


@pytest.mark.parametrize("vector", VECTORS, ids=[v.id for v in VECTORS])
@pytest.mark.parametrize("c1", ["wallclock", "business"])
def test_due_instants_follow_c1(vector, c1):
    ack_due, resolve_due, clock = sla.due_instants(vector.priority, instant(vector.created_at), c1)
    assert (format_instant(ack_due), format_instant(resolve_due)) == vector.expected(c1)
    assert clock == ("wallclock" if c1 == "wallclock" and vector.priority == "P1" else "business")


def test_tie_at_closing_is_due_at_closing_not_next_opening():
    # T4: 8 h from Monday 08:00 CEST ends exactly at 16:00 CEST = 14:00Z
    due = sla.business_due(instant("2026-10-19T06:00:00Z"), timedelta(hours=8))
    assert format_instant(due) == "2026-10-19T14:00:00Z"
    # one second more rolls over to the next opening
    due = sla.business_due(instant("2026-10-19T06:00:00Z"), timedelta(hours=8, seconds=1))
    assert format_instant(due) == "2026-10-20T06:00:01Z"


def test_created_before_opening_starts_at_opening_today():
    # Wednesday 07:30 CEST = 05:30Z; 1 h target -> 09:00 CEST = 07:00Z
    due = sla.business_due(instant("2026-10-14T05:30:00Z"), timedelta(hours=1))
    assert format_instant(due) == "2026-10-14T07:00:00Z"


def test_created_at_exact_closing_starts_next_business_day():
    # Friday 16:00:00 CEST is outside the half-open window; next opening is Monday 08:00 CEST
    due = sla.business_due(instant("2026-10-16T14:00:00Z"), timedelta(minutes=15))
    assert format_instant(due) == "2026-10-19T06:15:00Z"


@pytest.mark.parametrize(
    ("text", "inside"),
    [
        ("2026-10-14T06:00:00Z", True),  # Wed 08:00:00 CEST, opening is inside
        ("2026-10-14T05:59:59Z", False),  # Wed 07:59:59 CEST
        ("2026-10-14T13:59:59Z", True),  # Wed 15:59:59 CEST
        ("2026-10-14T14:00:00Z", False),  # Wed 16:00:00 CEST, closing is outside
        ("2026-10-17T10:00:00Z", False),  # Saturday
        ("2026-10-18T10:00:00Z", False),  # Sunday
        ("2027-01-14T07:00:00Z", True),  # Thu 08:00:00 CET
        ("2027-01-14T15:00:00Z", False),  # Thu 16:00:00 CET
    ],
)
def test_business_window_is_half_open(text, inside):
    assert sla.in_business_window(instant(text)) is inside


@pytest.mark.parametrize(("impact", "urgency", "priority"), [(k[0], k[1], v) for k, v in MATRIX.items()])
def test_matrix(impact, urgency, priority):
    assert priority_for(impact, urgency, False, "matrix") == priority
    assert priority_for(impact, urgency, False, "vip") == priority
    assert priority_for(impact, urgency, True, "matrix") == priority


@pytest.mark.parametrize(
    ("impact", "urgency", "expected"),
    [(1, 1, "P1"), (1, 2, "P2"), (2, 1, "P2"), (1, 3, "P2"), (2, 2, "P2"), (3, 1, "P2"), (2, 3, "P2"), (3, 3, "P2")],
)
def test_vip_uplift(impact, urgency, expected):
    assert priority_for(impact, urgency, True, "vip") == expected


def test_evaluate_equality_is_not_a_breach():
    due = instant("2026-10-14T10:15:00Z")
    flags = sla.evaluate(now=due, state="new", clock="business", ack_due_at=due, resolve_due_at=due,
                         acknowledged_at=None, resolved_at=None)
    assert flags["ack_breached"] is False and flags["resolve_breached"] is False
    flags = sla.evaluate(now=due + timedelta(days=3), state="acknowledged", clock="business", ack_due_at=due,
                         resolve_due_at=due + timedelta(days=9), acknowledged_at=due, resolved_at=None)
    assert flags["ack_breached"] is False


def test_evaluate_paused_only_for_business_clock_and_open_tickets():
    saturday = instant("2026-10-17T10:00:00Z")
    common = dict(ack_due_at=saturday, resolve_due_at=saturday, acknowledged_at=None, resolved_at=None)
    assert sla.evaluate(now=saturday, state="new", clock="business", **common)["paused"] is True
    assert sla.evaluate(now=saturday, state="new", clock="wallclock", **common)["paused"] is False
    assert sla.evaluate(now=saturday, state="closed", clock="business", **common)["paused"] is False
    assert sla.evaluate(now=saturday, state="resolved", clock="business", **common)["paused"] is False


@pytest.mark.parametrize("text", ["2026-10-14T10:00:00Z", "2026-10-14T12:00:00+02:00", "2026-10-14T10:00:00.250Z"])
def test_parse_instant_accepts_offsets(text):
    parsed = parse_instant(text)
    assert parsed.tzinfo is UTC
    assert parsed == datetime.fromisoformat(text)


@pytest.mark.parametrize("text", ["yesterday", "", "2026-10-14T10:00:00", "2026-10-14", "10:00:00Z", "now"])
def test_parse_instant_rejects_malformed_and_naive(text):
    with pytest.raises(ValueError):
        parse_instant(text)


def test_format_instant_is_utc_with_z():
    assert format_instant(datetime.fromisoformat("2026-10-14T12:00:00+02:00")) == "2026-10-14T10:00:00Z"
