# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md sections 1.4 and 1.5 and section 2; the lecturer ran the tests
"""The domain layer: ticket creation, the state machine, the reopen window and the SLA view.

Everything here takes `now` as an argument (the per-request clock of LAB1.md section 1.7) and never reads
the real time itself, so the same code serves the test clock and production.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from . import sla
from .clock import format_instant
from .config import Settings
from .db import Database, Ticket
from .models import TicketCreate
from .priority import priority_for

REOPEN_WINDOW = timedelta(days=7)

# action -> (from state, to state, timestamp field set to now or None)   (R-07)
SIMPLE_TRANSITIONS: dict[str, tuple[str, str, str | None]] = {
    "ack": ("new", "acknowledged", "acknowledged_at"),
    "start": ("acknowledged", "in_progress", None),
    "resolve": ("in_progress", "resolved", "resolved_at"),
    "close": ("resolved", "closed", "closed_at"),
}

ACTIONS = (*SIMPLE_TRANSITIONS, "reopen")


class ApiError(Exception):
    """An error the HTTP layer renders as `{"error": {"code": ..., "message": ...}}` with `status`."""

    def __init__(self, status: int, code: str, message: str, **extra: object) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra

    def body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, **self.extra}}


class NotFound(ApiError):
    def __init__(self, ticket_id: str) -> None:
        super().__init__(404, "not_found", f"ticket {ticket_id!r} does not exist")


class TicketService:
    def __init__(self, settings: Settings, db: Database) -> None:
        self.settings = settings
        self.db = db

    def create(self, data: TicketCreate, now: datetime) -> Ticket:
        priority = priority_for(data.impact, data.urgency, data.reporter.vip, self.settings.c3)
        ack_due_at, resolve_due_at, clock = sla.due_instants(priority, now, self.settings.c1)
        ticket = Ticket(
            id=str(uuid.uuid4()),
            title=data.title,
            description=data.description or "",
            reporter_name=data.reporter.name,
            reporter_email=data.reporter.email,
            reporter_vip=data.reporter.vip,
            impact=data.impact,
            urgency=data.urgency,
            priority=priority,
            state="new",
            created_at=now,
            ack_due_at=ack_due_at,
            resolve_due_at=resolve_due_at,
            resolve_clock=clock,
            related_to=data.related_to,
        )
        self.db.insert(ticket)
        return ticket

    def get(self, ticket_id: str) -> Ticket:
        ticket = self.db.get(ticket_id)
        if ticket is None:
            raise NotFound(ticket_id)
        return ticket

    def list(self, state: str | None, priority: str | None) -> list[Ticket]:
        return self.db.list(state=state, priority=priority)

    def act(self, ticket_id: str, action: str, now: datetime) -> Ticket:
        # Read, check and write under one transaction: FastAPI runs these synchronous handlers on a thread
        # pool, so two acknowledgements of one ticket can overlap; without the transaction both read `new`,
        # both succeed and the second overwrites `acknowledged_at` (review of PR 2). The state machine (R-07)
        # promises one 200 and one 409.
        with self.db.transaction():
            ticket = self.get(ticket_id)
            if action == "reopen":
                self._reopen(ticket, now)
            else:
                from_state, to_state, stamp = SIMPLE_TRANSITIONS[action]
                if ticket.state != from_state:
                    raise _invalid(action, ticket.state, f"{action} is allowed only from {from_state!r}")
                ticket.state = to_state
                if stamp is not None:
                    setattr(ticket, stamp, now)
            self.db.update(ticket)
        return ticket

    def _reopen(self, ticket: Ticket, now: datetime) -> None:
        if ticket.state == "resolved":
            assert ticket.resolved_at is not None
            if now > ticket.resolved_at + REOPEN_WINDOW:
                raise ApiError(409, "reopen_window_expired", "a resolved ticket can be reopened for 7 days only",
                               state=ticket.state, resolved_at=_iso(ticket.resolved_at))
        elif ticket.state == "closed":
            if self.settings.c2 == "immutable":
                raise ApiError(409, "ticket_closed",
                               "a closed ticket is immutable; open a new ticket with related_to set to this id",
                               state=ticket.state)
            assert ticket.closed_at is not None
            if now > ticket.closed_at + REOPEN_WINDOW:
                raise ApiError(409, "reopen_window_expired", "a closed ticket can be reopened for 7 days only",
                               state=ticket.state, closed_at=_iso(ticket.closed_at))
        else:
            raise _invalid("reopen", ticket.state, "reopen is allowed only from 'resolved' or 'closed'")
        ticket.state = "in_progress"
        ticket.resolved_at = None
        ticket.closed_at = None

    def sla_view(self, ticket_id: str, now: datetime) -> dict:
        ticket = self.get(ticket_id)
        flags = sla.evaluate(
            now=now,
            state=ticket.state,
            clock=ticket.resolve_clock,
            ack_due_at=ticket.ack_due_at,
            resolve_due_at=ticket.resolve_due_at,
            acknowledged_at=ticket.acknowledged_at,
            resolved_at=ticket.resolved_at,
        )
        return {
            "priority": ticket.priority,
            "ack_due_at": _iso(ticket.ack_due_at),
            "resolve_due_at": _iso(ticket.resolve_due_at),
            **flags,
        }


def _invalid(action: str, state: str, message: str) -> ApiError:
    return ApiError(409, "invalid_transition", f"cannot {action} a ticket in state {state!r}: {message}", state=state)


def _iso(instant: datetime) -> str:
    return format_instant(instant)
