<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote this feature specification from design/LAB1.md section 1 and section 2; the lecturer reviewed it -->
# Feature specification: svcdesk, the service-desk API

## User stories

1. As a reporter I raise a ticket with a title, a description, my name, and the impact and urgency of the
   incident, and I get back a ticket with an id, a computed priority and two SLA deadlines.
2. As a desk agent I move a ticket through acknowledged, in progress, resolved and closed, and the service
   records when each step happened.
3. As a reporter whose fix did not work I reopen a resolved ticket within seven days (and a closed one, if the
   desk's policy allows it) and the ticket goes back to in progress.
4. As a service level manager I ask at any instant whether a ticket's acknowledgement or resolution target is
   breached and whether its clock is currently paused.
5. As the checker I drive the service with a per-request test clock so that every scenario is reproducible.

## Functional requirements

- FR-1 `POST /tickets` validates the body (R-03): `title` 1..200 characters, `description` at most 4000
  (default empty), `reporter.name` 1..100, `reporter.email` optional, `reporter.vip` optional boolean,
  `impact` and `urgency` required integers 1..3, `related_to` optional and unvalidated. Server-owned fields
  (`id`, `priority`, `state`, timestamps, `sla`) and unknown fields are ignored silently. Errors are 422 with a
  top-level `error` object (R-20).
- FR-2 Priority is computed from the impact x urgency matrix (R-04) and, under resolution C3 = vip, a VIP
  ticket at P3 or P4 is raised to P2 (R-05 versus R-06).
- FR-3 SLA targets (R-12): P1 15 min / 4 h, P2 1 h / 8 h, P3 4 h / 24 h, P4 8 h / 72 h. Business hours are
  Monday to Friday [08:00, 16:00) Europe/Warsaw; a target that ends exactly at closing is due at closing.
  Under C1 = wallclock the P1 targets run on the wall clock and P2 to P4 on business hours; under
  C1 = business every priority runs on business hours (R-13 versus R-14). Vectors T1 to T8 are reproduced.
- FR-4 `GET /tickets/{id}/sla` returns priority, both due instants, `ack_breached`, `resolve_breached` and
  `paused` evaluated at the request's `now`; equality is not a breach; a reopened ticket is unresolved again
  and keeps its resolution target (R-15, R-16).
- FR-5 State machine (R-07, R-08): ack from new, start from acknowledged, resolve from in_progress, close from
  resolved, reopen from resolved within 7 days of `resolved_at` and, under C2 = reopen only, from closed within
  7 days of `closed_at` (R-09, R-10, R-11). Everything else is 409 with an `error` object; unknown ids are 404.
- FR-6 `GET /tickets` returns every matching ticket in one array, optionally filtered by `state` and
  `priority`, without pagination (R-19); `GET /tickets/{id}` returns one ticket or 404 (R-18).
- FR-7 `GET /health` returns `{"status": "ok", "service": "svcdesk", ...}`; unknown paths are 404 with a JSON
  body (R-02, R-25).
- FR-8 Test clock (R-21): with `SVCDESK_TEST_CLOCK=1` every request may carry `X-Test-Clock`; a header that
  does not parse or has no offset is a 400; without the header `now` is real UTC; with the variable off the
  header is ignored.
- FR-9 Compose contract (R-22, R-24): service `svcdesk` on 8080 with the test clock on, no bind mounts, no
  network at run time, healthy within 120 s; a `tests` service under the `tests` profile. Tickets persist
  across a container restart (R-23).

## Acceptance

The reference passes its own suite under all eight resolution combinations and `itsmlab verify 1` with every
Core spec passing and Stretch 3 of 3, for every combination with a matching `DECISIONS.md`.
