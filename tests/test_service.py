# ai-generated: 100% - Claude Code (Fable 5.1) wrote this test after the review of PR 2 (concurrent transitions); the lecturer ran it
"""The domain layer under concurrent transitions: read, check and write are one transaction.

Deterministic reproduction of the race the review found: `Database.get` is slowed down after its read so two
threads calling `act` on the same ticket overlap for sure. With the transaction the second thread waits for
the lock and reads `acknowledged` (409); without it both read `new` and both return the ticket (two 200s)."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

import pytest

from conftest import requires_local

pytestmark = requires_local


@pytest.fixture
def service(tmp_path):
    from svcdesk.config import Settings
    from svcdesk.db import Database
    from svcdesk.service import TicketService

    db = Database(str(tmp_path / "svcdesk.db"))
    try:
        yield TicketService(Settings(test_clock=True, db_path=str(tmp_path / "svcdesk.db")), db)
    finally:
        db.close()


def make_ticket(service, now: datetime):
    from svcdesk.models import TicketCreate

    data = TicketCreate.model_validate({"title": "race", "reporter": {"name": "Anna"}, "impact": 1, "urgency": 1})
    return service.create(data, now)


@pytest.mark.parametrize("action, setup", [
    ("ack", ()),
    ("start", ("ack",)),
    ("resolve", ("ack", "start")),
    ("close", ("ack", "start", "resolve")),
])
def test_overlapping_transitions_give_one_success_and_one_409(service, monkeypatch, action, setup):
    from svcdesk.db import Database
    from svcdesk.service import ApiError

    created = datetime(2026, 10, 16, 10, 0, tzinfo=UTC)
    ticket = make_ticket(service, created)
    for i, step in enumerate(setup, start=1):
        service.act(ticket.id, step, created.replace(minute=i))

    original_get = Database.get

    def slow_get(self, ticket_id):  # widen the window between the read and the write
        row = original_get(self, ticket_id)
        time.sleep(0.05)
        return row

    monkeypatch.setattr(Database, "get", slow_get)
    outcomes: list[int] = []
    lock = threading.Lock()

    def worker(minute: int) -> None:
        try:
            service.act(ticket.id, action, created.replace(minute=minute))
            status = 200
        except ApiError as exc:
            status = exc.status
        with lock:
            outcomes.append(status)

    threads = [threading.Thread(target=worker, args=(m,)) for m in (30, 45)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert sorted(outcomes) == [200, 409]


def test_transaction_rolls_back_a_refused_transition(service):
    from svcdesk.service import ApiError

    now = datetime(2026, 10, 16, 10, 0, tzinfo=UTC)
    ticket = make_ticket(service, now)
    with pytest.raises(ApiError) as excinfo:
        service.act(ticket.id, "close", now)
    assert excinfo.value.status == 409
    assert service.get(ticket.id).state == "new" and service.get(ticket.id).closed_at is None
