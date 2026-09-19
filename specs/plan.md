<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote this implementation plan from design/LAB1.md section 7.4; the lecturer reviewed it -->
# Implementation plan

## Stack

Python 3.13, FastAPI, pydantic v2, uvicorn, SQLite through the standard library, `zoneinfo` with the `tzdata`
package for Europe/Warsaw. Tests: pytest and httpx. Packaging: hatchling, a plain `uv venv` workflow
(`[tool.uv] managed = false`), pip inside the image.

## Module layout (`src/svcdesk/`)

| module | responsibility |
|---|---|
| `config.py` | `Settings` from `SVCDESK_C1/C2/C3`, `SVCDESK_TEST_CLOCK`, `SVCDESK_DB`; rejects inadmissible values at startup |
| `clock.py` | `parse_instant` (RFC 3339 with offset, naive rejected), `format_instant` (UTC, `Z`), `real_now` |
| `priority.py` | the matrix and the C3 uplift |
| `sla.py` | business windows in Europe/Warsaw, `business_due` with the closing-time tie rule, `due_instants` per C1, `evaluate` for breach and pause |
| `db.py` | the `tickets` table, a `Ticket` dataclass and its JSON shape |
| `models.py` | `TicketCreate` validation (strict ints, length limits, extras ignored) |
| `service.py` | create, get, list, the state machine, the reopen window per C2, the SLA view |
| `app.py` | routes, JSON error handlers (422 / 404 / 405 / 409 / 400), the app-wide `X-Test-Clock` dependency |
| `main.py`, `healthcheck.py` | ASGI entry point and the container healthcheck |

## Key design decisions

- All SLA arithmetic runs on aware UTC datetimes; Europe/Warsaw is used only to locate window boundaries, so
  DST transitions (always Sunday 02:00/03:00 local) never fall inside an arithmetic step.
- The clock is an app-wide dependency: any request with a malformed header is a 400, requests without the
  header use real UTC, and `now` is stored on `request.state` so every handler sees the same instant.
- The ticket stores which clock its resolution target used (`resolve_clock`) so that `paused` is evaluated
  against the clock the target was computed with, even if the service is later restarted with another C1.
- The three resolutions are settings, not branches of the code base: one image, eight behaviours, and
  `make_decisions.py` writes the matching `DECISIONS.md`.
- The test suite is HTTP-only and starts real uvicorn servers in-process, so the same tests run natively under
  all eight combinations and, through the compose `tests` service, against the container.

## Risks

- A wrong tie rule at closing time (T4) or a wrong half-open window edge is the most likely defect; both have
  dedicated unit tests beyond the vectors.
- `python:3.13-slim` ships no system zoneinfo; the `tzdata` dependency covers it.
