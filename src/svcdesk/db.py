# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md sections 1.1 and 1.9; the lecturer ran the tests
"""SQLite persistence for tickets (one table, one connection, one lock).

Instants are stored as RFC 3339 UTC strings. The file lives in a named Docker volume (LAB1.md section 1.9)
so tickets survive a restart of the container.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from datetime import datetime

from .clock import format_instant, parse_instant

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    reporter_name   TEXT NOT NULL,
    reporter_email  TEXT,
    reporter_vip    INTEGER NOT NULL DEFAULT 0,
    impact          INTEGER NOT NULL,
    urgency         INTEGER NOT NULL,
    priority        TEXT NOT NULL,
    state           TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    acknowledged_at TEXT,
    resolved_at     TEXT,
    closed_at       TEXT,
    related_to      TEXT,
    ack_due_at      TEXT NOT NULL,
    resolve_due_at  TEXT NOT NULL,
    resolve_clock   TEXT NOT NULL
);
"""

INSTANT_COLUMNS = ("created_at", "acknowledged_at", "resolved_at", "closed_at", "ack_due_at", "resolve_due_at")


@dataclass
class Ticket:
    id: str
    title: str
    description: str
    reporter_name: str
    reporter_email: str | None
    reporter_vip: bool
    impact: int
    urgency: int
    priority: str
    state: str
    created_at: datetime
    ack_due_at: datetime
    resolve_due_at: datetime
    resolve_clock: str
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    related_to: str | None = None
    _columns: tuple[str, ...] = field(default=(), repr=False, compare=False)

    def to_json(self) -> dict:
        """The wire representation of LAB1.md section 1.1."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "reporter": {"name": self.reporter_name, "email": self.reporter_email, "vip": self.reporter_vip},
            "impact": self.impact,
            "urgency": self.urgency,
            "priority": self.priority,
            "state": self.state,
            "created_at": format_instant(self.created_at),
            "acknowledged_at": _opt(self.acknowledged_at),
            "resolved_at": _opt(self.resolved_at),
            "closed_at": _opt(self.closed_at),
            "related_to": self.related_to,
            "sla": {"ack_due_at": format_instant(self.ack_due_at), "resolve_due_at": format_instant(self.resolve_due_at)},
        }


def _opt(instant: datetime | None) -> str | None:
    return None if instant is None else format_instant(instant)


COLUMNS = tuple(f.name for f in fields(Ticket) if not f.name.startswith("_"))


class Database:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            directory = os.path.dirname(os.path.abspath(path))
            os.makedirs(directory, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Serialises a read-check-write sequence: the lock is held for the whole block (the lock is
        re-entrant, so `get` and `update` inside it take it again without blocking) and the writes commit
        at its end. Without it two concurrent transitions read the same state and both succeed."""
        with self._lock, self._conn:
            yield

    def insert(self, ticket: Ticket) -> None:
        placeholders = ", ".join("?" for _ in COLUMNS)
        with self._lock, self._conn:
            self._conn.execute(
                f"INSERT INTO tickets ({', '.join(COLUMNS)}) VALUES ({placeholders})",
                _to_row(ticket),
            )

    def update(self, ticket: Ticket) -> None:
        assignments = ", ".join(f"{column} = ?" for column in COLUMNS if column != "id")
        values = [value for column, value in zip(COLUMNS, _to_row(ticket)) if column != "id"]
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE tickets SET {assignments} WHERE id = ?", [*values, ticket.id])

    def get(self, ticket_id: str) -> Ticket | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return None if row is None else _from_row(row)

    def list(self, state: str | None = None, priority: str | None = None) -> list[Ticket]:
        clauses, params = [], []
        if state is not None:
            clauses.append("state = ?")
            params.append(state)
        if priority is not None:
            clauses.append("priority = ?")
            params.append(priority)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(f"SELECT * FROM tickets{where} ORDER BY rowid", params).fetchall()
        return [_from_row(row) for row in rows]


def _to_row(ticket: Ticket) -> list:
    row = []
    for column in COLUMNS:
        value = getattr(ticket, column)
        if column in INSTANT_COLUMNS:
            value = _opt(value)
        elif column == "reporter_vip":
            value = int(value)
        row.append(value)
    return row


def _from_row(row: sqlite3.Row) -> Ticket:
    values = {}
    for column in COLUMNS:
        value = row[column]
        if column in INSTANT_COLUMNS:
            value = None if value is None else parse_instant(value)
        elif column == "reporter_vip":
            value = bool(value)
        values[column] = value
    return Ticket(**values)
