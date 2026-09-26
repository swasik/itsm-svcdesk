# ai-generated: 100% - Claude Opus 5 wrote this file from design/LAB2.md section 4.2; the lecturer ran the tests
"""`GET /dora/ticket-events`: svcdesk's own tickets as a lifecycle event stream (design/LAB2.md 4.2).

Lab 7 consumes this stream and models it as `events_by_ticket` on a ScyllaDB ring, so the shape is a
contract from this lab onwards. There is deliberately no `in_progress` phase: Lab 1 records no timestamp
for that transition, and a stream may only carry instants the service actually holds.
"""

from __future__ import annotations

from collections.abc import Iterable

from .clock import format_instant
from .db import Ticket

# (phase, the attribute holding its instant, the ticket state at that instant)
PHASES = (
    ("created", "created_at", "new"),
    ("acknowledged", "acknowledged_at", "acknowledged"),
    ("resolved", "resolved_at", "resolved"),
    ("closed", "closed_at", "closed"),
)


def ticket_events(tickets: Iterable[Ticket]) -> list[dict]:
    """One event per lifecycle instant that has occurred, ordered by (`at`, `ticket_id`) ascending."""
    ordered = []
    for ticket in tickets:
        for phase, attribute, state in PHASES:
            instant = getattr(ticket, attribute)
            if instant is None:
                continue
            ordered.append(((instant, ticket.id), {
                "ticket_id": ticket.id,
                "at": format_instant(instant),
                "phase": phase,
                "priority": ticket.priority,
                "state": state,
            }))
    ordered.sort(key=lambda pair: pair[0])
    return [event for _, event in ordered]
