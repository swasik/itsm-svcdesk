<!-- ai-generated: 100% - drafted by Claude Code from specs/001-svcdesk-api/spec.md and docs/lab1 (API.md, CHECKS.md, template Dockerfile.example) -->
# Implementation plan - 001-svcdesk-api

Input: [spec.md](spec.md), [data-model.md](data-model.md), [contracts/http-api.md](contracts/http-api.md).
Output: `src/`, `Dockerfile`, `requirements.txt`, and the Compose service already sketched in
`docker-compose.yml`. Tasks are in [tasks.md](tasks.md).

## 1. Technical context

| | |
|---|---|
| **Language** | Python 3.13 |
| **Framework** | FastAPI (routing, request parsing) on uvicorn |
| **Storage** | SQLite through the standard-library `sqlite3`, file at `$SVCDESK_DB` (default `/data/svcdesk.db`) |
| **Time zone** | `zoneinfo.ZoneInfo("Europe/Warsaw")`; `python:3.13-slim` is Debian-based and ships the IANA database |
| **Base image** | `python:3.13-slim`, as in `Dockerfile.example` |
| **Tests** | `httpx` against a live service, driven by `SVCDESK_URL`; plus pure-function tests of the SLA calculator |
| **Dependencies** | `fastapi`, `uvicorn`, `httpx` (tests only), all pinned, all installed at build time |

Why this stack: it is the one the template's `Dockerfile.example` and `docker-compose.yml` already assume, so the
packaging work is a copy rather than a rewrite; `zoneinfo` and `sqlite3` are in the standard library, so the whole
dependency surface is a web framework and a server, both installed while the image builds (constitution P5).

## 2. Constitution check

| principle | how this plan satisfies it |
|---|---|
| P1 specification before code | This plan and the specification are committed and receipted before the first file under `src/`. |
| P2 API.md is the contract | The eight vectors of spec.md FR-026 become unit tests of the SLA module before the HTTP layer exists. |
| P3 contradictions in the open | C1, C2 and C3 are three named constants in one module (`decisions.py`), read by the priority rule, the clock selector and the reopen rule. Changing a decision is a one-line change plus the matching edit in `DECISIONS.md`. |
| P4 determinism | `now` is resolved once per request by a single dependency and passed explicitly into every function that needs it. No module calls `datetime.now()` except that dependency. |
| P5 everything at build time | `pip install` runs in the Dockerfile; nothing is fetched at start-up. Volumes are named. |
| P6 errors are part of the interface | One exception type per failure class and one handler that renders `{"error": {...}}`; FastAPI's own 422 and 404 bodies are replaced. |
| P7 disclosure | Every `.py` and `.md` file gets the header as it is created, not afterwards. |

## 3. Module layout

```
src/
  README.md                 (course file, already present)
  svcdesk/
    __init__.py             the disclosure header and nothing else
    main.py                 FastAPI app, routes, exception handlers, startup
    decisions.py            C1, C2, C3 as constants, with the requirement ids they resolve
    models.py               the Ticket dataclass, serialisation to the wire shape
    validation.py           parse and validate the create body; raise ValidationError
    priority.py             the matrix and the VIP rule (C3)
    sla.py                  business-hours arithmetic, due instants (C1), breach and pause
    clock.py                X-Test-Clock parsing, SVCDESK_TEST_CLOCK, resolve now
    store.py                SQLite: schema, insert, get, list with filters, update
    errors.py               the exception types and the error body
    tests/
      __init__.py
      run.py                the S3 runner: prints ITSMLAB-TESTS: passed=<n> failed=0
      test_sla.py           the eight vectors and the tie rule, as pure functions
      test_api.py           the HTTP suite against SVCDESK_URL
```

Dependencies run one way: `main` → everything; `sla` → `decisions`; `priority` → `decisions`; `store` → `models`;
nothing imports `main`. `sla.py` and `priority.py` are pure: instants in, instants out, no I/O, no ambient clock.

## 4. Approach, in the order the work is done

### 4.1 The SLA calculator first

The riskiest part is the business-hours arithmetic, and it is the part that is fully specified by published
vectors, so it is built first and alone, as pure functions with no HTTP around them:

```python
def next_opening(local: datetime) -> datetime          # 08:00 today or the next business day
def business_due(start_utc: datetime, delta: timedelta) -> datetime
def wallclock_due(start_utc: datetime, delta: timedelta) -> datetime
def due_instants(priority: str, created_at: datetime) -> tuple[datetime, datetime]
def in_business_window(instant_utc: datetime) -> bool
```

Rules that decide the implementation:

- Work in `Europe/Warsaw` local time and convert back to UTC only at the end; a business window is eight hours of
  local clock time, and both DST transitions in the semester fall on a Sunday, so no window straddles one.
- The tie rule is the comparison `left <= available`, not `left < available`. T4 is the test that catches it.
- `next_opening` skips Saturday and Sunday and nothing else: Polish holidays are business days.
- The eight vectors of spec.md FR-026 are the first test file, written before `business_due` has a body. T4 pins
  the tie rule, T8 pins the DST weekend, T3 and T6 pin C1 = `wallclock`.

### 4.2 The clock

One dependency resolves `now`:

```python
def resolve_now(x_test_clock: str | None) -> datetime:
    if not test_clock_enabled():        # SVCDESK_TEST_CLOCK in {"1", "true"}
        return datetime.now(timezone.utc)
    if x_test_clock is None:
        return datetime.now(timezone.utc)
    return parse_offset_aware(x_test_clock)   # raises ValidationError on failure
```

`parse_offset_aware` rejects a timestamp with no offset: `datetime.fromisoformat` accepts `2026-10-16 15:30:00`
and returns a naive value, which API.md calls malformed, so the result is checked for `tzinfo` and rejected when
it is absent. Every handler takes `now` as an argument; no other code reads a clock (constitution P4).

### 4.3 Validation

The create body is validated by hand rather than by a Pydantic model, for three reasons: the error body must be
`{"error": {...}}` rather than FastAPI's `detail`, unknown and server-owned fields must be ignored rather than
rejected or echoed, and `impact`/`urgency` must reject booleans and numeric strings, which lax coercion would
accept. The route takes the raw `Request`, reads `await request.json()`, and calls
`validation.parse_create(body)`, which returns a normalised value object or raises `ValidationError`.

Explicit traps to cover:

- `isinstance(True, int)` is true in Python: check `type(v) is int` for `impact` and `urgency`.
- A float that happens to be integral (`2.0`) is not an integer.
- A malformed JSON body is a 400 with the same error shape, not an unhandled exception.
- Length is counted with `len()` on the decoded string, i.e. in code points (spec.md A-02).

### 4.4 Priority and the state machine

`priority.compute(impact, urgency, vip)` is a lookup in a nine-entry dict followed by the C3 rule. The state
machine is a table in `models.py`:

```python
TRANSITIONS = {"ack": ("new", "acknowledged", "acknowledged_at"),
               "start": ("acknowledged", "in_progress", None),
               "resolve": ("in_progress", "resolved", "resolved_at"),
               "close": ("resolved", "closed", "closed_at")}
```

One handler serves all four: load the ticket (404 if absent), compare the state (409 if it differs), set the
timestamp, write, return. `reopen` is separate because it has the window rule and the C2 rule.

### 4.5 Errors

```python
class SvcdeskError(Exception): status: int; code: str
class ValidationError(SvcdeskError): status = 422
class NotFound(SvcdeskError): status = 404
class InvalidTransition(SvcdeskError): status = 409
```

One `@app.exception_handler(SvcdeskError)` renders `{"error": {"code": ..., "message": ...}}`. Handlers for
`RequestValidationError` and `StarletteHTTPException` are registered too, so a 404 from the router and any 422
FastAPI raises on its own come back in the same shape (spec.md FR-003, FR-013).

### 4.6 Storage

`store.py` opens one SQLite connection per request (`check_same_thread=False` is not needed then), creates the
schema at start-up if it is absent, and exposes `insert`, `get`, `list(state, priority)` and `update`. The schema
is in [data-model.md](data-model.md) section 5. Rows are converted to and from the `Ticket` dataclass in one
place, so the wire shape is defined once.

### 4.7 Packaging

`Dockerfile` is `Dockerfile.example` with the module path confirmed as `svcdesk.main:app`. `requirements.txt`
pins `fastapi` and `uvicorn`. `docker-compose.yml` already satisfies FR-035 and FR-036; the work there is to
uncomment the healthcheck (so `up --wait` waits for readiness rather than for the port) and, for S3, the `tests`
service.

## 5. Risks

| risk | consequence | mitigation |
|---|---|---|
| The tie rule implemented as `<` | T4 (check 2.39) fails and nothing else does | the vector test is written before the function |
| Missing tzdata in the image | the first `POST /tickets` fails and most of L1-CORE-2 errors out | `python:3.13-slim` ships it; the smoke test creates a ticket |
| FastAPI's `detail` body | checks 2.16, 2.21 and the 409s fail on a missing `error` key | exception handlers registered for the framework's own errors, not only for ours |
| `impact: true` accepted | check 2.17/2.18 neighbours; a real defect even if unchecked | `type(v) is int` |
| `DECISIONS.md` drifts from the code | L1-CORE-4 fails while every conformance check passes | the three values live in `decisions.py`, and the verify run's `observations` line is compared with the front matter before tagging |
| Bind mount sneaking in through an override | check 1.02 fails | no `*.override.*` file is added; the volume stays named |

## 6. Verification

1. `python -m tests.test_sla` locally: the eight vectors pass as pure functions.
2. `docker compose up --build`, then the HTTP suite against `http://localhost:8080`.
3. `./itsmlab.sh verify 1`: every Core spec passes, L1-CORE-5 is `skip`.
4. The run's `observations` line reads `C1=wallclock C2=immutable C3=vip` and matches `DECISIONS.md`.

## 7. Stretch

| option | plan |
|---|---|
| S1 `converge-report` | after the implementation, write `specs/001-svcdesk-api/converge.md`: a comparison of this specification with what was built, naming the requirement ids it checked (at least three of R-01..R-25, and only ids in that range), at least 400 characters. It is written **after** the code exists; writing it now would be fiction. |
| S2 `agent-config` | `CLAUDE.md`, one sub-agent under `.claude/agents/` whose front matter lists at least three `disallowedTools`, and `AGENT-POLICY.md` with one justified line per entry. Out of scope for this feature's tasks; tracked separately. |
| S3 `own-tests` | the `tests` service in `docker-compose.yml` under `profiles: ["tests"]`, running `src/tests/run.py`, which executes the suite against `SVCDESK_URL` and prints `ITSMLAB-TESTS: passed=<n> failed=0` as its last stdout line with n at least 10. The image installs `httpx` at build time. |
