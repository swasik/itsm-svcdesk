# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md sections 1.3 and 1.4; the lecturer ran it against the test vectors T1-T8
"""SLA targets, the two clocks (wall-clock and business-hours) and breach/pause evaluation.

Business hours: Monday to Friday, the half-open window [08:00:00, 16:00:00) in Europe/Warsaw, DST-aware,
no public holidays. A target that ends exactly at closing time is due at 16:00:00 of that day (LAB1.md T4).
All arithmetic is done on aware UTC datetimes; Europe/Warsaw is used only to find window boundaries.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
OPENING = time(8, 0, 0)
CLOSING = time(16, 0, 0)

# priority -> (acknowledge within, resolve within)   (R-12)
TARGETS: dict[str, tuple[timedelta, timedelta]] = {
    "P1": (timedelta(minutes=15), timedelta(hours=4)),
    "P2": (timedelta(hours=1), timedelta(hours=8)),
    "P3": (timedelta(hours=4), timedelta(hours=24)),
    "P4": (timedelta(hours=8), timedelta(hours=72)),
}

WALLCLOCK = "wallclock"
BUSINESS = "business"


def is_business_day(day: date) -> bool:
    return day.weekday() < 5


def window(day: date) -> tuple[datetime, datetime]:
    """The business window of a calendar day as (opening, closing) UTC instants."""
    opening = datetime.combine(day, OPENING, tzinfo=WARSAW).astimezone(UTC)
    closing = datetime.combine(day, CLOSING, tzinfo=WARSAW).astimezone(UTC)
    return opening, closing


def in_business_window(instant: datetime) -> bool:
    """True when the instant lies inside [08:00, 16:00) Europe/Warsaw on a Monday to Friday."""
    local = instant.astimezone(WARSAW)
    return is_business_day(local.date()) and OPENING <= local.time() < CLOSING


def next_business_day(day: date) -> date:
    day += timedelta(days=1)
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def next_opening(instant: datetime) -> datetime:
    """The instant itself when it is inside a window, otherwise the next opening (08:00 today if before
    opening on a business day, else 08:00 of the next business day)."""
    local = instant.astimezone(WARSAW)
    day = local.date()
    if is_business_day(day):
        if local.time() < OPENING:
            return window(day)[0]
        if local.time() < CLOSING:
            return instant.astimezone(UTC)
    return window(next_business_day(day))[0]


def wallclock_due(created_at: datetime, target: timedelta) -> datetime:
    return created_at.astimezone(UTC) + target


def business_due(created_at: datetime, target: timedelta) -> datetime:
    """Consume `target` from consecutive business windows starting at the next opening after `created_at`.

    `remaining <= available` (not `<`) is the tie rule: a target that ends exactly at closing time is due
    at closing time of that day, not at the next opening.
    """
    cursor = next_opening(created_at)
    day = cursor.astimezone(WARSAW).date()
    remaining = target
    while True:
        closing = window(day)[1]
        available = closing - cursor
        if remaining <= available:
            return cursor + remaining
        remaining -= available
        day = next_business_day(day)
        cursor = window(day)[0]


def clock_for(priority: str, c1: str) -> str:
    """Which clock a priority's targets run on under contradiction C1.

    wallclock: P1 on the wall clock, P2 to P4 on business hours.  business: everything on business hours.
    """
    if c1 == WALLCLOCK and priority == "P1":
        return WALLCLOCK
    return BUSINESS


def due_instants(priority: str, created_at: datetime, c1: str) -> tuple[datetime, datetime, str]:
    """(ack_due_at, resolve_due_at, clock) for a ticket of `priority` created at `created_at`."""
    ack_target, resolve_target = TARGETS[priority]
    clock = clock_for(priority, c1)
    if clock == WALLCLOCK:
        return wallclock_due(created_at, ack_target), wallclock_due(created_at, resolve_target), clock
    return business_due(created_at, ack_target), business_due(created_at, resolve_target), clock


def evaluate(
    *,
    now: datetime,
    state: str,
    clock: str,
    ack_due_at: datetime,
    resolve_due_at: datetime,
    acknowledged_at: datetime | None,
    resolved_at: datetime | None,
) -> dict[str, bool]:
    """Breach and pause flags of LAB1.md section 1.4, evaluated at `now`. Equality is never a breach."""
    if acknowledged_at is None:
        ack_breached = now > ack_due_at
    else:
        ack_breached = acknowledged_at > ack_due_at
    if resolved_at is None:
        resolve_breached = now > resolve_due_at
    else:
        resolve_breached = resolved_at > resolve_due_at
    paused = state not in ("resolved", "closed") and clock == BUSINESS and not in_business_window(now)
    return {"ack_breached": ack_breached, "resolve_breached": resolve_breached, "paused": paused}
