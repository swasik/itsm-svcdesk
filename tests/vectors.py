# ai-generated: 100% - Claude Code (Fable 5.1) copied these vectors from design/LAB1.md section 1.3; the lecturer ran them
"""The test vectors of LAB1.md section 1.3 and a few shared helpers used by the API and SLA tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx


@dataclass(frozen=True)
class Vector:
    id: str
    priority: str
    created_at: str
    ack_wall: str
    ack_business: str
    resolve_wall: str
    resolve_business: str

    def expected(self, c1: str) -> tuple[str, str]:
        """(ack_due_at, resolve_due_at) under contradiction C1."""
        if c1 == "wallclock" and self.priority == "P1":
            return self.ack_wall, self.resolve_wall
        return self.ack_business, self.resolve_business


VECTORS = [
    Vector("T1", "P1", "2026-10-14T10:00:00Z", "2026-10-14T10:15:00Z", "2026-10-14T10:15:00Z", "2026-10-14T14:00:00Z", "2026-10-14T14:00:00Z"),
    Vector("T2", "P3", "2026-10-16T13:30:00Z", "2026-10-16T17:30:00Z", "2026-10-19T09:30:00Z", "2026-10-17T13:30:00Z", "2026-10-21T13:30:00Z"),
    Vector("T3", "P1", "2026-10-16T15:00:00Z", "2026-10-16T15:15:00Z", "2026-10-19T06:15:00Z", "2026-10-16T19:00:00Z", "2026-10-19T10:00:00Z"),
    Vector("T4", "P2", "2026-10-17T10:00:00Z", "2026-10-17T11:00:00Z", "2026-10-19T07:00:00Z", "2026-10-17T18:00:00Z", "2026-10-19T14:00:00Z"),
    Vector("T5", "P4", "2027-01-14T14:30:00Z", "2027-01-14T22:30:00Z", "2027-01-15T14:30:00Z", "2027-01-17T14:30:00Z", "2027-01-27T14:30:00Z"),
    Vector("T6", "P1", "2027-01-15T15:50:00Z", "2027-01-15T16:05:00Z", "2027-01-18T07:15:00Z", "2027-01-15T19:50:00Z", "2027-01-18T11:00:00Z"),
    Vector("T7", "P2", "2026-10-14T10:00:00Z", "2026-10-14T11:00:00Z", "2026-10-14T11:00:00Z", "2026-10-14T18:00:00Z", "2026-10-15T10:00:00Z"),
    Vector("T8", "P3", "2026-10-23T13:00:00Z", "2026-10-23T17:00:00Z", "2026-10-26T10:00:00Z", "2026-10-24T13:00:00Z", "2026-10-28T14:00:00Z"),
]
BY_ID = {v.id: v for v in VECTORS}

# a non-VIP (impact, urgency) pair that lands on each priority
CELL_FOR = {"P1": (1, 1), "P2": (1, 2), "P3": (1, 3), "P4": (2, 3)}

T1 = BY_ID["T1"].created_at


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text).astimezone(UTC)


def same_instant(a: str, b: str) -> bool:
    return instant(a) == instant(b)


def plus(text: str, **delta: float) -> str:
    return (instant(text) + timedelta(**delta)).isoformat().replace("+00:00", "Z")


def clock(text: str | None) -> dict[str, str]:
    return {} if text is None else {"X-Test-Clock": text}


def body(impact: int = 1, urgency: int = 1, *, vip: bool = False, title: str = "printer on fire", **extra: object) -> dict:
    payload = {
        "title": title,
        "description": "created by the reference test suite",
        "reporter": {"name": "Anna Kowalska", "email": "anna@example.org", "vip": vip},
        "impact": impact,
        "urgency": urgency,
    }
    payload.update(extra)
    return payload


def create(client: httpx.Client, at: str | None = T1, impact: int = 1, urgency: int = 1, **kwargs: object) -> dict:
    response = client.post("/tickets", json=body(impact, urgency, **kwargs), headers=clock(at))
    assert response.status_code == 201, response.text
    return response.json()


def act(client: httpx.Client, ticket_id: str, action: str, at: str) -> httpx.Response:
    return client.post(f"/tickets/{ticket_id}/{action}", headers=clock(at))


def drive(client: httpx.Client, ticket_id: str, *steps: tuple[str, str]) -> dict:
    """Apply (action, clock) steps, asserting each succeeds; return the final ticket."""
    ticket = None
    for action, at in steps:
        response = act(client, ticket_id, action, at)
        assert response.status_code == 200, f"{action} at {at}: {response.status_code} {response.text}"
        ticket = response.json()
    assert ticket is not None
    return ticket


def sla_at(client: httpx.Client, ticket_id: str, at: str) -> dict:
    response = client.get(f"/tickets/{ticket_id}/sla", headers=clock(at))
    assert response.status_code == 200, response.text
    return response.json()
