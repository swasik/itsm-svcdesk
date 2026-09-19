<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote this task list from specs/plan.md; the lecturer ticked the boxes after running the suite -->
# Tasks

Status legend: [x] done and covered by a test, [ ] open.

## Phase 1 - foundation
- [x] T-01 Package skeleton, `pyproject.toml` with pinned dependencies, `uv venv` workflow (`src/svcdesk/__init__.py`)
- [x] T-02 `Settings.from_env` with admissibility checks (`config.py`; `tests/test_repo.py` and the API suite)
- [x] T-03 Instants: parse with offset, reject naive, format as UTC `Z` (`clock.py`; `tests/test_sla.py`)

## Phase 2 - domain
- [x] T-04 Priority matrix and VIP uplift (`priority.py`; `test_matrix`, `test_vip_uplift`)
- [x] T-05 Business windows, `next_opening`, `business_due` with the closing-time tie (`sla.py`; T1 to T8 under both clocks)
- [x] T-06 Breach and pause evaluation (`sla.evaluate`; equality, half-open window, wall-clock never paused)
- [x] T-07 SQLite storage with a named-volume path (`db.py`; `test_tickets_survive_a_restart`)
- [x] T-08 State machine and reopen window per C2 (`service.py`; the 409 matrix in `test_api.py`)

## Phase 3 - HTTP
- [x] T-09 Routes and JSON error bodies for 400, 404, 405, 409, 422 (`app.py`)
- [x] T-10 App-wide `X-Test-Clock` dependency, off when the variable is unset (`bind_clock`)
- [x] T-11 `GET /tickets` filters, no pagination; `GET /tickets/{id}`; `GET /health` with extra fields

## Phase 4 - delivery
- [x] T-12 Dockerfile from `python:3.13-slim`, non-root, healthcheck without curl
- [x] T-13 `docker-compose.yml` per the compose contract, `tests` profile service, no bind mounts
- [x] T-14 `tests/run_tests.py` printing `ITSMLAB-TESTS: passed=<n> failed=<m>` last
- [x] T-15 `make_decisions.py` and the shipped `DECISIONS.md`; drift test
- [x] T-16 Stretch artifacts: `specs/converge.md`, `CLAUDE.md`, `.claude/agents/reviewer.md`, `AGENT-POLICY.md`
- [x] T-17 `scripts/run_all_combinations.sh`: eight compose runs, one summary line each
- [ ] T-18 Cross-check against the Tier A checker image once it is published (`itsmlab verify 1` for all eight combinations); owned by the integration step, not by this repository
