<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote this convergence report after running the suite; the lecturer reviewed the traceability -->
# Converge report: requirements to specification to tests

This report closes the spec-kit loop: for every requirement in the handout it names where the behaviour lives
and which test proves it, lists the divergences found while converging, and records what stays open.

## Traceability

| requirement | where implemented | proven by |
|---|---|---|
| R-01, R-02 HTTP JSON API on 8080, `/health` | `app.py`, `docker-compose.yml` | `test_health`, compose `--wait` |
| R-03 ticket fields and limits | `models.py` | `test_validation_errors`, `test_boundary_lengths_are_accepted` |
| R-04 priority matrix | `priority.py` | `test_priority_matrix` (nine cells), `test_matrix` |
| R-05, R-06 VIP (contradiction C3) | `priority.py`, `SVCDESK_C3` | `test_vip_low_ticket_follows_c3`, `test_priority_in_body_is_ignored` |
| R-07, R-08 states and 409 on invalid transitions | `service.py` | `test_start_then_resolve_then_close`, `test_invalid_transitions_are_409` |
| R-09, R-10, R-11 reopen and its window (contradiction C2) | `service.py`, `SVCDESK_C2` | `test_reopen_closed_one_day_later_follows_c2`, `test_reopen_resolved_after_seven_days_is_409` |
| R-12 SLA targets | `sla.TARGETS` | `test_sla_vectors` (T1 to T8) |
| R-13, R-14 the two clocks (contradiction C1) | `sla.clock_for`, `SVCDESK_C1` | `test_c1_probe_t3_matches_declared_resolution`, `test_due_instants_follow_c1` |
| R-15, R-16 `/sla`, breach and pause | `sla.evaluate`, `service.sla_view` | `test_ack_breached_after_due` and the other breach and pause tests |
| R-17 RFC 3339 instants | `clock.py` | `test_format_instant_is_utc_with_z`, `test_clock_with_offset_is_normalised_to_utc` |
| R-18 opaque unique ids | `service.create` (UUID4) | `test_two_creates_have_distinct_ids` |
| R-19 filters, no pagination | `db.list` | `test_list_returns_all_matching_tickets_without_pagination` |
| R-20 validation errors with an `error` object | `app.py` handlers | `test_validation_errors`, `test_malformed_json_body_is_400_or_422` |
| R-21 test clock | `app.bind_clock` | `test_clock_is_never_monotonic`, `test_malformed_clock_is_400_or_422`, `test_clock_header_is_ignored_when_test_clock_is_off` |
| R-22, R-24 compose contract, 120 s start | `docker-compose.yml`, `Dockerfile` | `test_compose_contract`, the compose run in README.md |
| R-23 persistence | `db.py`, named volume | `test_tickets_survive_a_restart` |
| R-25 unknown routes 404 JSON | `app.py` handlers | `test_unknown_path_is_404_json` |

## The three conflicts, as observed

The suite does what the checker does: it probes the running service (T3 for C1, a ticket closed one day
earlier for C2, a VIP ticket at impact 3 and urgency 3 for C3) and requires the observation to equal the
combination the environment declares. `DECISIONS.md` is regenerated from the same three values, so the
declaration, the environment and the behaviour cannot disagree without a test failing.

## Divergences found while converging

1. The first draft closed the database with FastAPI's `on_event("shutdown")`, which is deprecated; replaced
   with a lifespan context so the test servers shut down cleanly.
2. Starlette's `TestClient` now warns that `httpx` support is deprecated; instead of silencing the warning the
   suite starts real uvicorn servers on ephemeral ports and talks plain HTTP, which is also what the checker
   does, so the in-process and the container runs share one code path.
3. `python:3.13-slim` has no system time zone database; `tzdata` was added as a dependency so
   `zoneinfo` can resolve Europe/Warsaw inside the container.

## Open

- Integration with the published checker image (`itsmlab verify 1` under all eight combinations) belongs to
  the integration step of the course build; the suite here mirrors the published checks but is not the checker.
