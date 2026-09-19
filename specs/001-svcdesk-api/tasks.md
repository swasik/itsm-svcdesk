<!-- ai-generated: 100% - drafted by Claude Code from specs/001-svcdesk-api/plan.md and docs/lab1/CHECKS.md -->
# Tasks - 001-svcdesk-api

Ordered. `[P]` marks a task that touches no file another `[P]` task in the same phase touches, so the two can run
in parallel. Every task names the checks that prove it, using the ids of `docs/lab1/CHECKS.md`.

**Gate:** phases 1 onwards create files under `src/`. None of them starts before `specs/` is pushed and the
`specs` receipt comment has appeared (constitution P1, Core spec L1-CORE-5).

## Phase 0 - before the receipt (no file under `src/`)

- [ ] **T001** Write `specs/constitution.md`, `specs/001-svcdesk-api/spec.md`, `data-model.md`,
      `contracts/http-api.md`, `plan.md` and this file. Every one carries the AI-disclosure header.
- [ ] **T002** Fill `DECISIONS.md`: front matter `C1: wallclock`, `C2: immutable`, `C3: vip`, and the five labels
      in each of the three sections with at least 20 characters of real text each. *Checks L1-CORE-3.01..3.03.*
- [ ] **T003** Confirm `itsmlab.yaml` names the repository, and `docker-compose.yml` still has a `svcdesk`
      service with `build:`, port 8080, `SVCDESK_TEST_CLOCK: "1"` and no bind mount. *Checks 1.01, 1.02.*
- [ ] **T004** Commit and push `main`; run `./itsmlab.sh submit 1 --kind specs`, file the issue, wait for the
      receipt comment. **Nothing below starts before it appears.**

## Phase 1 - skeleton and packaging

- [ ] **T005** Create `src/svcdesk/__init__.py` (disclosure header only) and `requirements.txt` with pinned
      `fastapi` and `uvicorn`.
- [ ] **T006** Copy `Dockerfile.example` to `Dockerfile`; confirm `CMD` points at `svcdesk.main:app` and that
      `SVCDESK_DB=/data/svcdesk.db`.
- [ ] **T007** `src/svcdesk/main.py` with `GET /health` only. `docker compose up --build` and curl it.
      *Checks 1.03, 1.04, 2.01.*
- [ ] **T008** Uncomment the healthcheck in `docker-compose.yml` so `up --wait` waits for readiness.
      *Check 1.03.*

## Phase 2 - the SLA calculator, before any ticket exists

- [ ] **T009** `src/svcdesk/decisions.py`: `C1 = "wallclock"`, `C2 = "immutable"`, `C3 = "vip"`, each with a
      comment naming the requirements it resolves.
- [ ] **T010** `src/tests/test_sla.py`: the eight vectors of spec.md FR-026, plus the tie rule and the
      `next_opening` cases, as assertions against functions that do not exist yet.
- [ ] **T011** `src/svcdesk/sla.py`: `next_opening`, `business_due`, `wallclock_due`, `due_instants`,
      `in_business_window`. Iterate until T010 passes. The tie rule is `left <= available`.
      *Checks 2.36..2.41.*

## Phase 3 - the ticket

- [ ] **T012** [P] `src/svcdesk/errors.py`: `SvcdeskError` and the four subclasses, plus the error-body renderer.
      *Checks 2.16, 2.21, and every 409.*
- [ ] **T013** [P] `src/svcdesk/clock.py`: `test_clock_enabled`, `parse_offset_aware` (rejecting naive
      timestamps), `resolve_now`. *Checks 2.03, 2.04.*
- [ ] **T014** [P] `src/svcdesk/priority.py`: the nine-entry matrix and the C3 rule.
      *Checks 2.07..2.15, 2.46, 2.47.*
- [ ] **T015** `src/svcdesk/models.py`: the `Ticket` dataclass, the wire serialiser, the `TRANSITIONS` table.
- [ ] **T016** `src/svcdesk/validation.py`: `parse_create`, with the boolean/float/string traps of plan.md 4.3,
      ignoring server-owned and unknown fields. *Checks 2.16..2.19, 2.48.*
- [ ] **T017** `src/svcdesk/store.py`: schema creation at start-up, `insert`, `get`, `list(state, priority)`,
      `update`. *Checks 2.20, 2.22, 2.23; R-23.*

## Phase 4 - the HTTP layer

- [ ] **T018** `POST /tickets`: validate, compute priority, compute both due instants, insert, 201 with the full
      ticket. *Checks 2.05, 2.06, 2.03.*
- [ ] **T019** `GET /tickets/{id}` and `GET /tickets` with the two filters. *Checks 2.20, 2.22, 2.23.*
- [ ] **T020** The four table-driven transitions `ack`, `start`, `resolve`, `close`.
      *Checks 2.24..2.31, 2.49.*
- [ ] **T021** `reopen`: from `resolved` within 7 days, 409 after it, 409 from `closed` (C2 = `immutable`), and
      the clearing of `resolved_at` and `closed_at` without touching `resolve_due_at`.
      *Checks 2.32, 2.33, 2.34, 2.35.*
- [ ] **T022** `GET /tickets/{id}/sla`: the two due instants, the two breach flags, the pause flag.
      *Checks 2.42..2.45.*
- [ ] **T023** Exception handlers for `SvcdeskError`, `RequestValidationError` and `StarletteHTTPException`, so
      every refusal carries a top-level `error` object and an unknown path is a JSON 404.
      *Checks 2.02, 2.21.*

## Phase 5 - verify, decide, submit

- [ ] **T024** `./itsmlab.sh verify 1` until every Core spec passes and L1-CORE-5 is `skip`.
- [ ] **T025** Compare the run's `observations` line with the `DECISIONS.md` front matter; they must read
      `C1=wallclock C2=immutable C3=vip`. *Checks 4.01..4.03.*
- [ ] **T026** Check the AI-disclosure advisory in `report.json`: no file under `src/` or `specs/`, and not
      `DECISIONS.md`, is listed.
- [ ] **T027** Commit, push, re-run `verify 1` on a clean tree (the `commit` line must not say `(dirty)`), tag
      `lab1/v1`, push the tag, `./itsmlab.sh submit 1 --kind submission --tag lab1/v1`, file the issue.

## Phase 6 - stretch (any two of three lift the band)

- [ ] **T028** [P] **S3** `src/tests/test_api.py` and `src/tests/run.py`: at least ten assertions against
      `SVCDESK_URL`, retrying `/health` first, printing `ITSMLAB-TESTS: passed=<n> failed=0` as the last stdout
      line; uncomment the `tests` service in `docker-compose.yml` with `profiles: ["tests"]` and `httpx` pinned
      in the build. *Check L1-STRETCH-3.01.*
- [ ] **T029** [P] **S2** `CLAUDE.md`, `.claude/agents/reviewer.md` with at least three `disallowedTools`
      entries in its front matter, and `AGENT-POLICY.md` with a line `- <entry verbatim>: <20+ characters>` for
      each. *Check L1-STRETCH-2.01.*
- [ ] **T030** **S1** After the code exists and passes: `specs/001-svcdesk-api/converge.md`, at least 400
      characters, comparing this specification with what was built and naming at least three distinct ids from
      R-01..R-25 (and no id outside that range). **Trap:** the check matches the bare pattern `R-\d\d`, so an
      `FR-001` written in that file reads as `R-00` and fails it - refer to this specification's clauses as
      "requirement FR 001" or by section, never as `FR-0nn`. *Check L1-STRETCH-1.01.*

## Dependency order

```
T001..T004  (receipt gate)
   └── T005 ── T006 ── T007 ── T008
         └── T009 ── T010 ── T011
               └── T012 [P] T013 [P] T014
                     └── T015 ── T016 ── T017
                           └── T018 ── T019 ── T020 ── T021 ── T022 ── T023
                                 └── T024 ── T025 ── T026 ── T027
                                       └── T028 [P] T029 [P] T030
```
