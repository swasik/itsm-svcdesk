<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from specs/plan.md; the lecturer reviewed it -->
# src/

The `svcdesk` package. This README is the only file allowed under `src/` before the specs receipt (course rule
L1-CORE-5); everything else here is implementation.

| module | what it does |
|---|---|
| `svcdesk/config.py` | settings from the environment: `SVCDESK_C1`, `SVCDESK_C2`, `SVCDESK_C3`, `SVCDESK_TEST_CLOCK`, `SVCDESK_DB` |
| `svcdesk/clock.py` | RFC 3339 parsing and formatting, real UTC time |
| `svcdesk/priority.py` | the impact x urgency matrix and the VIP uplift (C3) |
| `svcdesk/sla.py` | business hours in Europe/Warsaw, the two clocks (C1), breach and pause |
| `svcdesk/db.py` | SQLite table, `Ticket` dataclass, JSON shape |
| `svcdesk/models.py` | request validation for `POST /tickets` |
| `svcdesk/service.py` | create, get, list, the state machine and the reopen window (C2), the SLA view |
| `svcdesk/app.py` | FastAPI routes, error bodies, the per-request test clock |
| `svcdesk/main.py` | `app` for uvicorn |
| `svcdesk/healthcheck.py` | the container healthcheck (`python -m svcdesk.healthcheck`) |

Run it natively with `SVCDESK_TEST_CLOCK=1 SVCDESK_DB=./data/svcdesk.db uv run uvicorn svcdesk.main:app --port 18080`
from the repository root; see the root README.md for everything else.
