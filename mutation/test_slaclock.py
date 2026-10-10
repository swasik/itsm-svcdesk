# ai-generated: 100% - Claude Code wrote these tests from the docstrings of slaclock.py (every stated boundary)
"""Tests of slaclock.py, one group per function; each docstring boundary is tested on both sides."""

from datetime import datetime, timedelta

import pytest

import slaclock
from slaclock import (
    add_business_minutes,
    business_minutes_between,
    escalation_tier,
    is_business_time,
    parse_duration,
    priority_of,
    sla_state,
    targets,
)

# 2026-10-05 is a Monday.
MON = datetime(2026, 10, 5)
TUE = MON + timedelta(days=1)
WED = MON + timedelta(days=2)
FRI = MON + timedelta(days=4)
SAT = MON + timedelta(days=5)
SUN = MON + timedelta(days=6)
NEXT_MON = MON + timedelta(days=7)


def at(day, hour, minute=0, second=0, micro=0):
    return day.replace(hour=hour, minute=minute, second=second, microsecond=micro)


# --- priority_of ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "impact, urgency, expected",
    [(1, 1, "P1"), (1, 2, "P2"), (2, 1, "P2"), (1, 3, "P3"), (2, 2, "P3"), (3, 1, "P3"),
     (2, 3, "P4"), (3, 2, "P4"), (3, 3, "P4")],
)
def test_priority_matrix(impact, urgency, expected):
    assert priority_of(impact, urgency) == expected
    assert priority_of(impact, urgency, False) == expected
    assert priority_of(impact, urgency, vip=False) == expected


@pytest.mark.parametrize(
    "impact, urgency, expected",
    [(1, 1, "P1"), (1, 2, "P2"), (2, 1, "P2"), (1, 3, "P2"), (2, 2, "P2"), (3, 1, "P2"),
     (2, 3, "P2"), (3, 2, "P2"), (3, 3, "P2")],
)
def test_priority_vip(impact, urgency, expected):
    assert priority_of(impact, urgency, vip=True) == expected


def test_priority_default_is_not_vip():
    assert priority_of(3, 3) == "P4"
    assert priority_of(2, 2) == "P3"


@pytest.mark.parametrize("bad", [0, 4, -1, 2.0, 1.0, True, False, "1", None, 10])
def test_priority_rejects_bad_impact(bad):
    with pytest.raises(ValueError):
        priority_of(bad, 2)


@pytest.mark.parametrize("bad", [0, 4, -1, 2.0, 1.0, True, False, "1", None, 10])
def test_priority_rejects_bad_urgency(bad):
    with pytest.raises(ValueError):
        priority_of(2, bad)


def test_priority_rejects_bad_with_vip():
    with pytest.raises(ValueError):
        priority_of(4, 1, vip=True)
    with pytest.raises(ValueError):
        priority_of(1, 0, vip=True)


def test_priority_returns_str():
    assert isinstance(priority_of(1, 1), str)


# --- targets ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "priority, expected", [("P1", (15, 240)), ("P2", (60, 480)), ("P3", (240, 1440)), ("P4", (480, 4320))]
)
def test_targets(priority, expected):
    result = targets(priority)
    assert tuple(result) == expected
    assert result[0] == expected[0] and result[1] == expected[1]


@pytest.mark.parametrize("bad", ["p1", " P1", "P1 ", "P5", "P0", "", "P", "1"])
def test_targets_unknown(bad):
    with pytest.raises(ValueError):
        targets(bad)


# --- sla_state -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "elapsed, target, expected",
    [
        (0, 15, "ok"), (11, 15, "ok"), (12, 15, "warning"), (15, 15, "warning"), (16, 15, "breached"),
        (74, 100, "ok"), (75, 100, "warning"), (76, 100, "warning"), (99, 100, "warning"), (100, 100, "warning"),
        (101, 100, "breached"), (0, 1, "ok"), (1, 1, "warning"), (2, 1, "breached"),
        (2, 4, "ok"), (3, 4, "warning"), (4, 4, "warning"), (5, 4, "breached"),
        (179, 240, "ok"), (180, 240, "warning"), (240, 240, "warning"), (241, 240, "breached"),
        (1000, 240, "breached"), (0, 4320, "ok"),
    ],
)
def test_sla_state(elapsed, target, expected):
    assert sla_state(elapsed, target) == expected


@pytest.mark.parametrize("elapsed, target", [(-1, 10), (0, 0), (5, 0), (5, -1), (-1, 0), (-5, -5)])
def test_sla_state_rejects(elapsed, target):
    with pytest.raises(ValueError):
        sla_state(elapsed, target)


def test_sla_state_zero_elapsed_is_valid():
    assert sla_state(0, 1) == "ok"


def test_warning_percent_constant():
    assert slaclock.WARNING_PERCENT == 75


# --- is_business_time ------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "moment, expected",
    [
        (at(MON, 7, 59), False), (at(MON, 8, 0), True), (at(MON, 8, 1), True), (at(MON, 12, 0), True),
        (at(MON, 15, 59), True), (at(MON, 16, 0), False), (at(MON, 16, 1), False), (at(MON, 0, 0), False),
        (at(MON, 23, 59), False), (at(FRI, 8, 0), True), (at(FRI, 15, 59), True), (at(FRI, 16, 0), False),
        (at(SAT, 10, 0), False), (at(SUN, 10, 0), False), (at(SAT, 8, 0), False), (at(SUN, 15, 59), False),
        (at(WED, 9, 30), True), (at(TUE, 7, 0), False), (at(MON, 7, 59, 59), False), (at(MON, 15, 59, 59), True),
    ],
)
def test_is_business_time(moment, expected):
    assert is_business_time(moment) is expected


# --- add_business_minutes --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "start, minutes, expected",
    [
        (at(MON, 9), 0, at(MON, 9)),
        (at(MON, 8), 0, at(MON, 8)),
        (at(MON, 15, 59), 0, at(MON, 15, 59)),
        (at(MON, 16), 0, at(TUE, 8)),
        (at(MON, 7), 0, at(MON, 8)),
        (at(SAT, 10), 0, at(NEXT_MON, 8)),
        (at(FRI, 16), 0, at(NEXT_MON, 8)),
        (at(MON, 9), 1, at(MON, 9, 1)),
        (at(MON, 9), 60, at(MON, 10)),
        (at(MON, 8), 480, at(MON, 16)),
        (at(MON, 15), 60, at(MON, 16)),
        (at(MON, 15), 61, at(TUE, 8, 1)),
        (at(MON, 8), 481, at(TUE, 8, 1)),
        (at(MON, 15, 59), 1, at(MON, 16)),
        (at(MON, 15, 59), 2, at(TUE, 8, 1)),
        (at(MON, 7), 30, at(MON, 8, 30)),
        (at(MON, 0), 480, at(MON, 16)),
        (at(MON, 17), 30, at(TUE, 8, 30)),
        (at(MON, 23, 59), 1, at(TUE, 8, 1)),
        (at(FRI, 15), 120, at(NEXT_MON, 9)),
        (at(FRI, 15), 60, at(FRI, 16)),
        (at(FRI, 17), 10, at(NEXT_MON, 8, 10)),
        (at(SAT, 12), 480, at(NEXT_MON, 16)),
        (at(SUN, 23), 1, at(NEXT_MON, 8, 1)),
        (at(MON, 9), 480 * 5, at(NEXT_MON, 9)),
        (at(MON, 8), 480 * 5, at(FRI, 16)),
        (at(MON, 8), 480 * 5 + 1, at(NEXT_MON, 8, 1)),
        (at(MON, 9), 4320, at(MON + timedelta(days=11), 9)),
        (at(WED, 12), 240, at(WED, 16)),
        (at(WED, 12), 241, at(MON + timedelta(days=3), 8, 1)),
    ],
)
def test_add_business_minutes(start, minutes, expected):
    assert add_business_minutes(start, minutes) == expected


def test_add_business_minutes_ignores_seconds():
    assert add_business_minutes(at(MON, 9, 0, 59, 999), 10) == at(MON, 9, 10)
    assert add_business_minutes(at(MON, 15, 59, 30), 1) == at(MON, 16)
    assert add_business_minutes(at(MON, 9, 0, 30), 0) == at(MON, 9)


def test_add_business_minutes_negative():
    with pytest.raises(ValueError):
        add_business_minutes(at(MON, 9), -1)


def test_add_business_minutes_max_days():
    # 366 calendar days from Monday 2026-10-05 is Tuesday 2027-10-06; one business year is about 261 days.
    days_ok = add_business_minutes(at(MON, 8), 480 * 250)
    assert days_ok > at(MON, 8)
    assert (days_ok.date() - MON.date()).days <= slaclock.MAX_DAYS
    with pytest.raises(ValueError):
        add_business_minutes(at(MON, 8), 480 * 300)


def test_add_business_minutes_max_days_boundary():
    start = at(MON, 8)
    last_day = MON + timedelta(days=366)  # 2027-10-06, a Wednesday
    assert last_day.weekday() < 5
    total = business_minutes_between(start, at(last_day, 16))
    assert add_business_minutes(start, total) == at(last_day, 16)
    with pytest.raises(ValueError):
        add_business_minutes(start, total + 1)


def test_add_business_minutes_returns_datetime():
    assert isinstance(add_business_minutes(at(MON, 9), 5), datetime)


# --- business_minutes_between ----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "start, end, expected",
    [
        (at(MON, 9), at(MON, 9), 0),
        (at(MON, 9), at(MON, 10), 60),
        (at(MON, 8), at(MON, 16), 480),
        (at(MON, 7), at(MON, 17), 480),
        (at(MON, 7), at(MON, 8), 0),
        (at(MON, 7), at(MON, 8, 1), 1),
        (at(MON, 15, 59), at(MON, 16), 1),
        (at(MON, 16), at(MON, 17), 0),
        (at(MON, 15), at(TUE, 9), 120),
        (at(FRI, 15), at(NEXT_MON, 9), 120),
        (at(SAT, 9), at(SUN, 17), 0),
        (at(MON, 0), at(TUE, 0), 480),
        (at(MON, 9), at(NEXT_MON, 9), 2400),
        (at(MON, 12), at(WED, 12), 960),
        (at(MON, 16), at(TUE, 8), 0),
        (at(SAT, 0), at(NEXT_MON, 8, 30), 30),
        (at(MON, 9), at(MON, 9, 1), 1),
    ],
)
def test_business_minutes_between(start, end, expected):
    assert business_minutes_between(start, end) == expected


def test_business_minutes_between_ignores_seconds():
    assert business_minutes_between(at(MON, 9, 0, 59), at(MON, 9, 10, 1)) == 10
    assert business_minutes_between(at(MON, 9, 0, 30), at(MON, 9, 0, 10)) == 0


def test_business_minutes_between_end_before_start():
    with pytest.raises(ValueError):
        business_minutes_between(at(MON, 10), at(MON, 9, 59))
    with pytest.raises(ValueError):
        business_minutes_between(at(TUE, 9), at(MON, 9))


def test_business_minutes_between_max_days():
    start = at(MON, 9)
    ok_end = at(MON + timedelta(days=366), 9)
    assert business_minutes_between(start, ok_end) > 0
    with pytest.raises(ValueError):
        business_minutes_between(start, at(MON + timedelta(days=367), 9))
    with pytest.raises(ValueError):
        business_minutes_between(at(MON, 23), at(MON + timedelta(days=367), 0, 30))


def test_business_minutes_between_max_days_exact_count():
    start = at(MON, 8)
    end = at(MON + timedelta(days=366), 16)
    # 2026-10-05 .. 2027-10-06 inclusive: 367 days, 53 weeks less 4 days -> count weekdays directly
    weekdays = sum(1 for d in range(367) if (MON + timedelta(days=d)).weekday() < 5)
    assert business_minutes_between(start, end) == weekdays * 480


@pytest.mark.parametrize(
    "start, minutes",
    [(at(MON, 9), 0), (at(MON, 9), 1), (at(MON, 15), 61), (at(FRI, 15, 30), 600), (at(SAT, 3), 1000),
     (at(MON, 7, 15), 480), (at(TUE, 16), 0), (at(WED, 11, 11), 4321)],
)
def test_round_trip(start, minutes):
    assert business_minutes_between(start, add_business_minutes(start, minutes)) == minutes


# --- escalation_tier -------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "priority, breached, reopens, expected",
    [
        ("P1", False, 0, 1), ("P2", False, 0, 1), ("P3", False, 0, 0), ("P4", False, 0, 0),
        ("P1", True, 0, 3), ("P2", True, 0, 2), ("P3", True, 0, 1), ("P4", True, 0, 1),
        ("P1", False, 1, 1), ("P2", False, 1, 1), ("P3", False, 1, 0), ("P4", False, 1, 0),
        ("P1", False, 2, 2), ("P2", False, 2, 2), ("P3", False, 2, 1), ("P4", False, 2, 1),
        ("P1", True, 2, 3), ("P2", True, 2, 3), ("P3", True, 2, 2), ("P4", True, 2, 2),
        ("P1", False, 5, 2), ("P3", True, 7, 2), ("P2", True, 1, 2), ("P1", True, 1, 3),
    ],
)
def test_escalation_tier(priority, breached, reopens, expected):
    assert escalation_tier(priority, breached, reopens) == expected


@pytest.mark.parametrize("priority", ["P5", "p1", "", " P1", "P0"])
def test_escalation_unknown_priority(priority):
    with pytest.raises(ValueError):
        escalation_tier(priority, False, 0)


def test_escalation_negative_reopens():
    with pytest.raises(ValueError):
        escalation_tier("P3", False, -1)
    with pytest.raises(ValueError):
        escalation_tier("P1", True, -1)


def test_escalation_zero_reopens_valid():
    assert escalation_tier("P4", False, 0) == 0


# --- parse_duration --------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("90m", 90), ("4h", 240), ("1h30m", 90), ("2d", 2880), ("1d4h", 1680), ("1d0h5m", 1445),
        ("1h59m", 119), ("60m", 60), ("0h60m", 60), ("1m", 1), ("  15m ", 15), ("\t1h\n", 60),
        ("1d", 1440), ("1d59m", 1499), ("0d1m", 1), ("0d0h1m", 1), ("1d1h1m", 1501), ("120m", 120),
        ("0h1m", 1), ("1h0m", 60), ("0d60m", 60), ("10h", 600), ("3d2h", 4440), ("12m", 12), ("01m", 1),
    ],
)
def test_parse_duration(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "0m", "1.5h", "30m1h", "-5m", "1 h", "1h60m", "1d60m", "1d0h60m", "0h0m", "0d", "0h", "h", "m",
     "1H", "1M", "1D", "1h 30m", "abc", "5", "1h1h", "1w", "   ", "1m1d", "1h1d", "1d2d"],
)
def test_parse_duration_rejects(text):
    with pytest.raises(ValueError):
        parse_duration(text)


def test_parse_duration_returns_int():
    assert type(parse_duration("1h30m")) is int


# --- constants the docstrings state -------------------------------------------------------------------------------

def test_targets_constant_matches_function():
    for priority in ("P1", "P2", "P3", "P4"):
        assert targets(priority) == slaclock.TARGETS[priority]
