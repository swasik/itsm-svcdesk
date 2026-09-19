<!-- ai-generated: 100% - drafted by Claude Code from docs/lab1 API.md section 2 and REQUIREMENTS.md R-03, R-07, R-17, R-18, R-23 -->
# Data model - svcdesk

Derived from [spec.md](spec.md) section 7. One aggregate (Ticket), one embedded value (Reporter), one derived
value stored with the ticket (the SLA block) and one value computed per request and never stored (the SLA report).

## 1. Ticket

| field | type | source | rules |
|---|---|---|---|
| `id` | string | server | opaque, unique, non-empty; UUIDv4 rendered as its canonical 36-character string. Never read from the request. |
| `title` | string | client, required | 1..200 code points |
| `description` | string | client, optional | 0..4000 code points; default `""` |
| `reporter` | Reporter | client, required | see section 2 |
| `impact` | integer | client, required | 1, 2 or 3 |
| `urgency` | integer | client, required | 1, 2 or 3 |
| `priority` | string | server | `P1`..`P4`; derived at creation from `impact`, `urgency`, `reporter.vip`; never recomputed |
| `state` | string | server | `new`, `acknowledged`, `in_progress`, `resolved`, `closed`; `new` at creation |
| `created_at` | instant | server | the `now` of the create request |
| `acknowledged_at` | instant or null | server | the `now` of the `ack` request; `null` until then and after a reopen |
| `resolved_at` | instant or null | server | the `now` of the `resolve` request; cleared by a reopen |
| `closed_at` | instant or null | server | the `now` of the `close` request; cleared by a reopen (unreachable under C2 = `immutable`, kept for symmetry) |
| `related_to` | string or null | client, optional | stored and echoed verbatim; not validated in Lab 1; default `null` |
| `sla.ack_due_at` | instant | server | derived at creation; immutable |
| `sla.resolve_due_at` | instant | server | derived at creation; immutable |

Instants are emitted as RFC 3339 in UTC with a `Z` suffix and whole seconds, for example
`2026-10-14T10:00:00Z`.

## 2. Reporter (embedded value)

| field | type | rules |
|---|---|---|
| `name` | string, required | 1..100 code points |
| `email` | string or null, optional | default `null`; not validated as an address in Lab 1 |
| `vip` | boolean, optional | default `false`; stored on every ticket, used by the priority rule under C3 = `vip` |

## 3. Derived values

### Priority

```
matrix[impact][urgency]:
    (1,1) P1   (1,2) P2   (1,3) P3
    (2,1) P2   (2,2) P3   (2,3) P4
    (3,1) P3   (3,2) P4   (3,3) P4

priority = matrix[impact][urgency]
if reporter.vip and priority in {P3, P4}:      # C3 = vip
    priority = P2
```

### SLA due instants

```
targets:  P1 (15 min, 4 h)   P2 (1 h, 8 h)   P3 (4 h, 24 h)   P4 (8 h, 72 h)

clock(priority) = wallclock if priority == P1 else business      # C1 = wallclock

ack_due_at     = due(created_at, targets[priority].ack,     clock(priority))
resolve_due_at = due(created_at, targets[priority].resolve, clock(priority))
```

`due(start, duration, wallclock)` is `start + duration`.

`due(start, duration, business)` walks the Europe/Warsaw business calendar:

```
local   = start converted to Europe/Warsaw
cursor  = local if local is inside a business window else next_opening(local)
left    = duration
loop:
    close_at  = 16:00:00 local on cursor's date
    available = close_at - cursor
    if left <= available:                 # the tie rule lives here: <=, not <
        return (cursor + left) converted to UTC
    left   -= available
    cursor  = next_opening(close_at)      # 08:00:00 of the next business day
```

`next_opening(t)` is 08:00:00 on `t`'s own date when `t` is a Monday-to-Friday local time before 08:00:00, and
08:00:00 on the next Monday-to-Friday date otherwise. All arithmetic on `cursor` is done on local wall time with
a DST-aware conversion back to UTC at the end, so a window is always exactly eight hours of local clock time.
Polish public holidays are business days for the whole course.

### SLA report (computed per request, never stored)

```
ack_breached     = acknowledged_at > ack_due_at            if acknowledged_at is not null
                   now > ack_due_at                        otherwise
resolve_breached = resolved_at > resolve_due_at            if resolved_at is not null
                   now > resolve_due_at                    otherwise
paused           = state not in {resolved, closed}
                   and clock(priority) == business
                   and now (in Europe/Warsaw) is outside a business window
```

Equality is never a breach. A reopened ticket has `resolved_at == null` and `state == in_progress`, so it is
"not resolved" again and is measured against the unchanged `resolve_due_at`.

## 4. State machine

```
            ack            start           resolve          close
   new ──────────> acknowledged ──────> in_progress ──────> resolved ──────> closed
                                             ^                  │
                                             └──────────────────┘
                                                 reopen (<= 7 days after resolved_at)

   closed ──reopen──> 409          # C2 = immutable
```

Every arrow not drawn is a 409. `reopen` from `resolved` clears `resolved_at` and `closed_at`; it changes nothing
else, and in particular leaves `priority`, `created_at` and the `sla` block alone.

| from \ action | ack | start | resolve | close | reopen |
|---|---|---|---|---|---|
| `new` | acknowledged | 409 | 409 | 409 | 409 |
| `acknowledged` | 409 | in_progress | 409 | 409 | 409 |
| `in_progress` | 409 | 409 | resolved | 409 | 409 |
| `resolved` | 409 | 409 | 409 | closed | in_progress within 7 days, else 409 |
| `closed` | 409 | 409 | 409 | 409 | 409 (C2 = `immutable`) |

An action on an id that does not exist is 404, whatever the action.

## 5. Storage

SQLite, one file at `$SVCDESK_DB` (default `/data/svcdesk.db`), inside the named volume `svcdesk-data`, so
tickets survive a restart of the container (R-23).

```sql
CREATE TABLE IF NOT EXISTS tickets (
    id              TEXT PRIMARY KEY,
    title           TEXT    NOT NULL,
    description     TEXT    NOT NULL DEFAULT '',
    reporter_name   TEXT    NOT NULL,
    reporter_email  TEXT,
    reporter_vip    INTEGER NOT NULL DEFAULT 0,   -- 0 / 1
    impact          INTEGER NOT NULL,
    urgency         INTEGER NOT NULL,
    priority        TEXT    NOT NULL,             -- P1..P4
    state           TEXT    NOT NULL,             -- new | acknowledged | in_progress | resolved | closed
    created_at      TEXT    NOT NULL,             -- RFC 3339, UTC, Z
    acknowledged_at TEXT,
    resolved_at     TEXT,
    closed_at       TEXT,
    related_to      TEXT,
    ack_due_at      TEXT    NOT NULL,
    resolve_due_at  TEXT    NOT NULL
);
```

Notes.

- Timestamps are stored as UTC `Z` strings; because they all carry the same fixed format they also sort
  lexicographically, but the service parses them into instants before any comparison (constitution P4).
- No index beyond the primary key: the desk is small and `GET /tickets` returns everything (R-19, NFR-003).
- Every write is a single `INSERT` or `UPDATE` in its own transaction; a transition reads the row, checks the
  state, and writes the new state and its timestamp.
- The schema is created at start-up if it is absent, so a fresh volume needs no migration step.
