<!-- ai-generated: 100% - drafted by Claude Code from docs/lab1 (REQUIREMENTS.md R-01..R-25, API.md, CHECKS.md) -->
# Feature 001 - svcdesk: the service-desk HTTP API

| | |
|---|---|
| **Feature id** | `001-svcdesk-api` |
| **Lab** | 1 |
| **Status** | specified, not yet implemented |
| **Input** | `docs/lab1/REQUIREMENTS.md` (R-01..R-25), `docs/lab1/API.md` (the enforced contract), `docs/lab1/CHECKS.md` (the published checks) |
| **Owner of the requirement** | Service Desk product owner, internal IT |

## 1. Summary

A small ticketing service for a service desk of about four hundred people in three offices. Tickets live in a
spreadsheet and in inboxes today, and nobody can say on Monday morning which tickets are late. `svcdesk` accepts
tickets over HTTP, derives their priority from impact and urgency, drives them through a fixed state machine,
keeps the two SLA clocks (acknowledge, resolve) and answers, per ticket, whether either target has been breached
and whether the clock is currently paused.

The service is the only interface: JSON over HTTP on port 8080, no UI, no CLI, no message bus.

## 2. Scope

### In scope

- Ticket creation with validation, server-derived priority, and server-owned identifiers and timestamps.
- Retrieval of one ticket, and a list of all tickets with exact-match filters on `state` and `priority`.
- The five transitions `ack`, `start`, `resolve`, `close`, `reopen`, each its own endpoint, each refusing every
  other source state with 409.
- The reopen window of 7 days.
- Two SLA due instants per ticket, on a wall-clock or a business-hours clock depending on priority, plus the
  breach and pause report at `GET /tickets/{id}/sla`.
- A per-request test clock for deterministic verification.
- Persistence across a restart of the container, and the Compose packaging.

### Out of scope for Lab 1

- Authentication, authorisation, roles, rate limiting, audit trail, notifications.
- Pagination, sorting, free-text search, partial updates (`PATCH`), deletion.
- Validating that `related_to` names an existing ticket (API.md section 2: not validated in Lab 1).
- Polish public holidays: they are business days for the whole course (API.md section 4).
- Assignment of a ticket to an agent, comments, attachments, categories.

## 3. Glossary

| term | meaning |
|---|---|
| **instant** | an RFC 3339 timestamp compared as a point in time, never as a string; emitted in UTC with a `Z` suffix |
| **now** | the instant of the current request: the `X-Test-Clock` header when the test clock is enabled and the header is present, otherwise real UTC time |
| **business window** | the half-open local interval `[08:00:00, 16:00:00)` on Monday to Friday in `Europe/Warsaw`, DST-aware |
| **wall-clock target** | `created_at + target duration` |
| **business-hours target** | the due instant reached by consuming the target duration out of consecutive business windows from `created_at` |
| **breach** | the event happened after its due instant, or has not happened and the due instant has passed |

## 4. The three contradictions and how they are resolved

`REQUIREMENTS.md` contains three pairs of requirements that cannot both hold. Each is resolved by rejecting the
smallest conflicting part of one requirement and keeping everything else in the pair, so both sides stay in force
everywhere they do not collide. The resolutions below are the ones this service implements and the ones
`DECISIONS.md` declares; the reasoning for each belongs in `DECISIONS.md`, not here.

### C1 - SLA clock for P1: `wallclock`

| | |
|---|---|
| **Pair** | R-13 (SLA clocks pause outside business hours; time outside them counts against *no* target) versus R-14 (a P1 is acknowledged within 15 min and resolved within 4 h of creation, *around the clock*) |
| **Collision** | For a P1 raised at 17:00 on a Friday, R-13 makes the acknowledgement due on Monday morning and R-14 makes it due at 17:15 the same evening. |
| **Kept** | R-14 in full. R-13 for every priority other than P1. |
| **Rejected** | The words "any SLA target" in R-13, narrowed to "any SLA target of a P2, P3 or P4 ticket". |
| **Behaviour** | Both P1 targets are wall-clock; P2, P3 and P4 targets are business-hours. A P1 never reports `paused: true`. A mixed pair for P1 (one target on each clock) is not admissible and is not produced. |

### C2 - Closed tickets and reopening: `immutable`

| | |
|---|---|
| **Pair** | R-09 (a closed ticket is immutable; further work on the issue needs a new ticket referencing it via `related_to`) versus R-10 (a reporter may reopen a resolved *or closed* ticket within 7 days) |
| **Collision** | Reopening a closed ticket mutates a ticket R-09 declares frozen. |
| **Kept** | R-09 in full. R-10 for resolved tickets, with its 7-day window and its return to `in_progress`. R-11 in full. |
| **Rejected** | The words "or closed" in R-10. |
| **Behaviour** | `POST /tickets/{id}/reopen` succeeds from `resolved` while `now <= resolved_at + 7 days`. From `closed` it answers 409 regardless of age; the client raises a new ticket carrying `related_to`. |

### C3 - VIP reporters and the priority matrix: `vip`

| | |
|---|---|
| **Pair** | R-05 (priority is derived from impact and urgency *and from nothing else*) versus R-06 (a VIP reporter's ticket is never lower than P2) |
| **Collision** | `reporter.vip` is something else, and R-06 makes priority depend on it. |
| **Kept** | R-06 in full. The operative half of R-05: neither the reporter nor the agent can *request* a priority, and no input other than impact, urgency and `reporter.vip` touches it. |
| **Rejected** | The absolute "and from nothing else" in R-05, narrowed to "and from nothing the client asks for". |
| **Behaviour** | The matrix runs first; a VIP ticket that lands on P3 or P4 is raised to P2; P1 and P2 are unchanged. A `priority` field in the request body is still ignored, under this resolution as under the other. |

## 5. User scenarios

### S1 - An agent raises a ticket for a caller (primary flow)

A caller reports that the printer on floor 2 is down; a team cannot print. The agent posts the title, the
description, the reporter's name and e-mail, impact 2 and urgency 1. The service answers 201 with a ticket that
already carries its id, `priority: "P2"`, `state: "new"`, `created_at`, and an `sla` block with both due instants.
Nothing about priority or timing was negotiated with the caller.

**Accepted when:** the response is 201; `priority` is `P2`; `state` is `new`; `id` is a non-empty string distinct
from every other ticket's; `acknowledged_at`, `resolved_at`, `closed_at` are `null`; `sla.ack_due_at` and
`sla.resolve_due_at` are instants computed on the business-hours clock.

### S2 - A ticket runs through its life

The agent acknowledges the ticket, starts work, resolves it, and closes it once the caller confirms. Each step is
a separate call and each records its instant. A caller who confirms nothing leaves the ticket at `resolved`.

**Accepted when:** `ack` from `new`, `start` from `acknowledged`, `resolve` from `in_progress` and `close` from
`resolved` each answer 200 with the full ticket in the next state, and `acknowledged_at`, `resolved_at`,
`closed_at` equal the `now` of their own request.

### S3 - A shortcut is refused

A new agent tries to resolve a ticket that was never started, and to close one that is still in progress.

**Accepted when:** both answer 409 with a JSON body carrying a top-level `error` object, and the ticket's state
is unchanged. The same holds for acknowledging twice, starting a `new` ticket, closing a `new` ticket and
reopening a `new` ticket.

### S4 - The fix did not work

Six days after the ticket was resolved the caller says the printer is down again. The reporter reopens it and it
returns to `in_progress` against its original resolution target. Eight days after resolution the same request is
refused and the caller raises a new ticket.

**Accepted when:** reopen at `resolved_at + 6 days` answers 200 with `in_progress`, `resolved_at` cleared;
reopen at `resolved_at + 7 days + 1 s` answers 409; `resolve_due_at` is unchanged by the reopen (R-11).

### S5 - A closed ticket comes back (C2 = `immutable`)

A caller asks to reopen a ticket closed yesterday. The service refuses; the agent raises a new ticket whose
`related_to` names the closed one.

**Accepted when:** reopen on a ticket closed 1 day earlier answers 409, whatever its age; a create carrying
`related_to` is accepted and echoes the value.

### S6 - The Monday report

At 09:00 on Monday the desk lead asks, for each open ticket, whether either target is breached and whether its
clock is paused. One `GET /tickets/{id}/sla` per ticket answers it.

**Accepted when:** `GET /tickets/{id}/sla` returns `priority`, `ack_due_at`, `resolve_due_at`, `ack_breached`,
`resolve_breached`, `paused`, all evaluated at the `now` of that request.

### S7 - A bad request

A create arrives without a title, with `impact: 5`, with `urgency: "high"`, or with a 201-character title.

**Accepted when:** each answers 400 or 422 with a top-level `error` object, and no ticket is created. A create
that also carries `id`, `priority`, `state`, `created_at` or an unknown field is accepted and those fields are
ignored.

## 6. Functional requirements

Each FR cites the requirement it comes from and the checks that observe it. `either` in CHECKS.md means the
checker accepts both resolutions; the value this service produces is the one fixed in section 4.

### 6.1 Transport and health

- **FR-001** (R-01) The service listens on TCP 8080 inside the container and speaks only HTTP. Every request body
  and every response body is JSON with `Content-Type: application/json`.
- **FR-002** (R-02, 2.01) `GET /health` answers 200 with at least `{"status": "ok", "service": "svcdesk"}`.
  Extra fields are allowed.
- **FR-003** (R-25, 2.02) An unknown path answers 404 with a JSON body. A wrong method on a known path answers
  404 or 405.
- **FR-004** (R-25, 2.21) An unknown ticket id answers 404 with a JSON body carrying a top-level `error` object,
  on every endpoint that takes an id.

### 6.2 The ticket

- **FR-005** (R-03, R-18, 2.05, 2.06) A ticket carries: `id` (opaque, unique, non-empty, assigned by the service,
  never accepted or predicted by a client), `title`, `description`, `reporter` (`name`, `email`, `vip`), `impact`,
  `urgency`, `priority`, `state`, `created_at`, `acknowledged_at`, `resolved_at`, `closed_at`, `related_to` and
  `sla` (`ack_due_at`, `resolve_due_at`). The full ticket is the body of every successful create, get and action.
- **FR-006** (R-03) Defaults on create: `description` `""`, `reporter.email` `null`, `reporter.vip` `false`,
  `related_to` `null`, `state` `new`, and `acknowledged_at`, `resolved_at`, `closed_at` `null`.
- **FR-007** (R-17) Every instant the service emits is RFC 3339 in UTC with a `Z` suffix. Every instant it reads
  is parsed as a point in time and compared as one.

### 6.3 Validation

- **FR-008** (R-03, R-20, 2.16, 2.19) `title` is required, a string of 1 to 200 characters. Absent, not a string,
  empty or 201 characters or longer: 400 or 422.
- **FR-009** (R-03, R-20) `description` is optional, a string of at most 4000 characters.
- **FR-010** (R-03, R-20) `reporter` is required and is an object; `reporter.name` is required, a string of 1 to
  100 characters; `reporter.email` is optional, a string or `null`; `reporter.vip` is optional and boolean.
- **FR-011** (R-03, R-20, 2.17, 2.18) `impact` and `urgency` are required integers in 1..3. A value outside the
  range, a non-integer, a boolean, or a string such as `"high"`: 400 or 422.
- **FR-012** (R-20, API.md section 2) The server-owned fields `id`, `priority`, `state`, `created_at`,
  `acknowledged_at`, `resolved_at`, `closed_at` and `sla`, and any field the service does not know, are ignored
  when they arrive in a request body. They are never a reason to refuse it.
- **FR-013** (R-20) Every refusal carries 400 or 422 and a JSON body with a top-level `error` object. The `code`
  strings (`validation`, `invalid_transition`, `reopen_window_expired`, `ticket_closed`, `not_found`) are written
  because they help the caller, not because Lab 1 checks them.

### 6.4 Priority

- **FR-014** (R-04, 2.07..2.15) Priority comes from the matrix:

  | impact \ urgency | 1 | 2 | 3 |
  |---|---|---|---|
  | **1** | P1 | P2 | P3 |
  | **2** | P2 | P3 | P4 |
  | **3** | P3 | P4 | P4 |

- **FR-015** (R-06, C3 = `vip`, 2.46) After the matrix, a ticket whose `reporter.vip` is `true` and whose matrix
  priority is P3 or P4 becomes P2. P1 and P2 are left alone (2.47).
- **FR-016** (R-05, 2.48) A `priority` field in the request body is ignored; priority depends on `impact`,
  `urgency` and `reporter.vip` and on nothing else. Priority is fixed at creation and never changes afterwards -
  no transition, and no reopen, recomputes it.

### 6.5 State machine

- **FR-017** (R-07, 2.24, 2.27, 2.28, 2.30) The transitions, each with its own endpoint, each answering 200 with
  the full ticket:

  | action | endpoint | from | to | side effect |
  |---|---|---|---|---|
  | acknowledge | `POST /tickets/{id}/ack` | `new` | `acknowledged` | `acknowledged_at = now` |
  | start | `POST /tickets/{id}/start` | `acknowledged` | `in_progress` | - |
  | resolve | `POST /tickets/{id}/resolve` | `in_progress` | `resolved` | `resolved_at = now` |
  | close | `POST /tickets/{id}/close` | `resolved` | `closed` | `closed_at = now` |
  | reopen | `POST /tickets/{id}/reopen` | `resolved` only (C2 = `immutable`) | `in_progress` | clears `resolved_at` and `closed_at` |

- **FR-018** (R-08, 2.25, 2.26, 2.29, 2.31, 2.34, 2.49) Every other source state for every action answers 409
  with a top-level `error` object and leaves the ticket untouched. There are no shortcuts: resolve from
  `acknowledged` is 409, close from `in_progress` is 409, a second `ack` is 409.
- **FR-019** (R-10, 2.32, 2.33) Reopen from `resolved` succeeds while `now <= resolved_at + 7 days` and answers
  409 afterwards. Reaching the boundary exactly is still allowed; one second past it is not.
- **FR-020** (R-09, C2 = `immutable`, 2.35) Reopen from `closed` answers 409 regardless of how recently the
  ticket was closed. A closed ticket is never mutated by any endpoint.
- **FR-021** (R-11) A reopen does not restart, extend or recompute `resolve_due_at`, and does not change
  `priority` or `created_at`. It only returns the ticket to `in_progress` and clears the two event timestamps.

### 6.6 SLA due instants

- **FR-022** (R-12) Targets by priority:

  | priority | acknowledge within | resolve within |
  |---|---|---|
  | P1 | 15 min | 4 h |
  | P2 | 1 h | 8 h |
  | P3 | 4 h | 24 h |
  | P4 | 8 h | 72 h |

  Both targets are measured from `created_at`.
- **FR-023** (R-14, C1 = `wallclock`) A P1 ticket's two due instants are `created_at + 15 min` and
  `created_at + 4 h`, around the clock.
- **FR-024** (R-13) A P2, P3 or P4 ticket's two due instants are computed on the business-hours clock: Monday to
  Friday, `[08:00:00, 16:00:00)` local time in `Europe/Warsaw`, DST-aware, public holidays counted as business
  days.
- **FR-025** (R-13) The business-hours algorithm. Convert `created_at` to `Europe/Warsaw`. If that local time is
  outside a business window, move forward to the next opening: 08:00:00 of the same day when it is before opening
  on a business day, otherwise 08:00:00 of the next business day. Consume the target duration out of consecutive
  business windows. A target that ends exactly at closing is due at 16:00:00 of that day, not at 08:00:00 of the
  next (**the tie rule**). Convert the result back to UTC.
- **FR-026** (R-12, 2.36..2.41) The published test vectors are reproduced exactly. Under the resolutions of
  section 4 the service must return:

  | id | priority | `created_at` | local | `ack_due_at` | `resolve_due_at` |
  |---|---|---|---|---|---|
  | T1 | P1 | 2026-10-14T10:00:00Z | Wed 12:00 CEST | 2026-10-14T10:15:00Z | 2026-10-14T14:00:00Z |
  | T2 | P3 | 2026-10-16T13:30:00Z | Fri 15:30 CEST | 2026-10-19T09:30:00Z | 2026-10-21T13:30:00Z |
  | T3 | P1 | 2026-10-16T15:00:00Z | Fri 17:00 CEST | 2026-10-16T15:15:00Z | 2026-10-16T19:00:00Z |
  | T4 | P2 | 2026-10-17T10:00:00Z | Sat 12:00 CEST | 2026-10-19T07:00:00Z | 2026-10-19T14:00:00Z |
  | T5 | P4 | 2027-01-14T14:30:00Z | Thu 15:30 CET | 2027-01-15T14:30:00Z | 2027-01-27T14:30:00Z |
  | T6 | P1 | 2027-01-15T15:50:00Z | Fri 16:50 CET | 2027-01-15T16:05:00Z | 2027-01-15T19:50:00Z |
  | T7 | P2 | 2026-10-14T10:00:00Z | Wed 12:00 CEST | 2026-10-14T11:00:00Z | 2026-10-15T10:00:00Z |
  | T8 | P3 | 2026-10-23T13:00:00Z | Fri 15:00 CEST | 2026-10-26T10:00:00Z | 2026-10-28T14:00:00Z |

  T1 is the case where both clocks agree. T3 and T6 are the C1 discriminators: these are the wall-clock values.
  T4 is the tie rule: 8 business hours from Monday 08:00 end exactly at 16:00 local, so the ticket is due Monday
  16:00 CEST = 14:00Z, not Tuesday morning. T8 spans the weekend in which DST ends: 1 h Friday, 8 h Monday,
  8 h Tuesday, 7 h Wednesday, due Wednesday 15:00 CET = 14:00Z.

### 6.7 Breach and pause

- **FR-027** (R-15) `GET /tickets/{id}/sla` answers 200 with `priority`, `ack_due_at`, `resolve_due_at`,
  `ack_breached`, `resolve_breached`, `paused`, evaluated at the `now` of that request.
- **FR-028** (R-16, 2.42, 2.43, 2.44) `ack_breached` is true when the ticket has not been acknowledged and
  `now > ack_due_at`, or it was acknowledged and `acknowledged_at > ack_due_at`. Equality is not a breach; a
  ticket acknowledged in time stays unbreached however late the report is read.
- **FR-029** (R-16) `resolve_breached` is true when the ticket is not resolved and `now > resolve_due_at`, or it
  was resolved and `resolved_at > resolve_due_at`. A reopened ticket counts as not resolved again, against its
  original `resolve_due_at`.
- **FR-030** (R-16, 2.45) `paused` is true when the ticket is neither `resolved` nor `closed`, its resolution
  target runs on the business-hours clock, and `now` falls outside a business window. Under C1 = `wallclock` a P1
  ticket therefore always reports `paused: false`.

### 6.8 Listing

- **FR-031** (R-19, 2.20, 2.22, 2.23) `GET /tickets` answers 200 with a JSON array of every ticket, in any order,
  without pagination. `?state=` and `?priority=` filter by exact match and combine as a conjunction. A filter
  value that matches nothing yields an empty array, not an error. `GET /tickets/{id}` answers 200 with one ticket.

### 6.9 Test clock

- **FR-032** (R-21, 2.03) When `SVCDESK_TEST_CLOCK` is `1` or `true`, a request may carry `X-Test-Clock` with an
  RFC 3339 instant including an offset; for that request only, `now` is that instant. It sets `created_at`,
  `acknowledged_at`, `resolved_at` and `closed_at`, and is the reference for breach, pause and the reopen window.
- **FR-033** (R-21, 2.04) A header that does not parse - including a naive timestamp with no offset - answers 400
  or 422 with a top-level `error` object.
- **FR-034** (R-21) `now` is per request and nothing else. The service never compares one request's clock with
  another's, never enforces monotonic time, and never refuses an action because its clock precedes a stored
  timestamp. `GET /tickets` and `GET /tickets/{id}` carry no clock-dependent field; the header is accepted and
  irrelevant there. When the variable is unset or `0`, the header is ignored and `now` is real UTC time.

### 6.10 Packaging and persistence

- **FR-035** (R-22, 1.01) A Compose file at the repository root defines a service named exactly `svcdesk` that
  builds from a context inside the repository, listens on 8080 inside the container, and sets
  `SVCDESK_TEST_CLOCK: "1"`.
- **FR-036** (R-22, 1.02) No service has a host-path bind mount in the resolved configuration
  (`docker compose config`), in the base file or in any override. Named volumes and `tmpfs` are used instead.
- **FR-037** (R-22) The image needs no network at run time; every dependency is installed while the image builds.
- **FR-038** (R-24, 1.03, 1.04) From `docker compose up --wait svcdesk`, the service is running and `GET /health`
  answers 200 within 120 s.
- **FR-039** (R-23) Tickets survive a restart of the `svcdesk` container: state is written to durable storage in
  a named volume, not held only in memory.

## 7. Key entities

| entity | description |
|---|---|
| **Ticket** | The only aggregate. Identified by an opaque server-assigned id. Holds the reported facts (title, description, reporter, impact, urgency, `related_to`), the derived priority, the current state, four event instants and two due instants. |
| **Reporter** | A value embedded in the ticket: `name`, optional `email`, `vip` flag. Not an entity of its own in Lab 1; there is no reporter directory. |
| **SLA block** | A value derived once at creation from `priority` and `created_at`: `ack_due_at` and `resolve_due_at`. Immutable for the life of the ticket. |
| **SLA report** | Not stored. Computed per request from the ticket and `now`: the two due instants, two breach flags, one pause flag. |

The full field list, types and the storage schema are in [data-model.md](data-model.md); the endpoint-by-endpoint
contract is in [contracts/http-api.md](contracts/http-api.md).

## 8. Non-functional requirements

- **NFR-001** Determinism. Given the same `X-Test-Clock` and the same body, the response is identical except for
  the generated id. No behaviour depends on the host time zone or locale; the only time zone in the code is
  `Europe/Warsaw` for the business calendar, and the only output zone is UTC.
- **NFR-002** Time-zone data. The image ships the IANA database for `Europe/Warsaw`. Without it the first
  `POST /tickets` fails and every conformance check that creates a ticket errors out.
- **NFR-003** Budget. The checker allows 10 s per HTTP request, 120 s from `up` to a healthy `/health`, and the
  run peaks at about 0.4 GB of container memory. The service creates at most a few hundred tickets per run, so
  no index or cache is needed for correctness or for speed.
- **NFR-004** Isolation. No egress at run time, no host paths, no writes outside the container's own filesystem
  and its named volume.
- **NFR-005** Every file under `specs/` and `src/` with a checked extension carries the AI-disclosure comment in
  its first ten lines.

## 9. Traceability

| requirement | resolved by | observed by |
|---|---|---|
| R-01, R-02 | FR-001, FR-002 | 2.01 |
| R-03 | FR-005, FR-006, FR-008..FR-011 | 2.05, 2.16..2.19 |
| R-04 | FR-014 | 2.07..2.15 |
| R-05 | FR-016 | 2.48 |
| R-06 | FR-015 (C3 = `vip`) | 2.46, 2.47 |
| R-07 | FR-017 | 2.24, 2.27, 2.28, 2.30 |
| R-08 | FR-018 | 2.25, 2.26, 2.29, 2.31, 2.34, 2.49 |
| R-09 | FR-020 (C2 = `immutable`) | 2.35 |
| R-10 | FR-019 | 2.32 |
| R-11 | FR-019, FR-021 | 2.33 |
| R-12 | FR-022, FR-026 | 2.36..2.41 |
| R-13 | FR-024, FR-025 | 2.37..2.40 |
| R-14 | FR-023 (C1 = `wallclock`) | 2.41 |
| R-15 | FR-027 | 2.42..2.45 |
| R-16 | FR-028..FR-030 | 2.42..2.45 |
| R-17 | FR-007 | 2.03, 2.24, 2.28, 2.30 |
| R-18 | FR-005 | 2.05, 2.06 |
| R-19 | FR-031 | 2.20, 2.22, 2.23 |
| R-20 | FR-008..FR-013 | 2.16..2.19 |
| R-21 | FR-032..FR-034 | 2.03, 2.04 |
| R-22 | FR-035..FR-037 | 1.01, 1.02 |
| R-23 | FR-039 | not checked in Tier A for Lab 1 (API.md section 10) |
| R-24 | FR-038 | 1.03, 1.04 |
| R-25 | FR-003, FR-004 | 2.02, 2.21 |

## 10. Assumptions and decisions taken while specifying

- **A-01** Where `REQUIREMENTS.md` and `API.md` differ in precision, `API.md` is implemented. The requirements
  document supplies the intent that `DECISIONS.md` argues from.
- **A-02** "1 to 200 characters" is counted in Unicode code points, the unit a JSON string is made of.
- **A-03** `reporter` must be an object when present and is required; a create without it is a validation error,
  by R-03 ("a reporter with a name (required)").
- **A-04** A boolean is not an integer for `impact` and `urgency`, even in languages where it is a subtype of one.
- **A-05** `?state=` and `?priority=` with an unknown value (`state=banana`) return an empty array rather than a
  400: R-19 asks for exact-match filters, not for a validated enum, and no check probes it.
- **A-06** `related_to` is stored and echoed verbatim, including when it names no existing ticket (API.md
  section 2).
- **A-07** Priority is frozen at creation. Nothing in R-04..R-06 or in the state machine asks for recomputation,
  and recomputing would move a due instant that R-11 says must not move.
- **A-08** The service accepts `X-Test-Clock` on every endpoint, including the ones where it changes nothing.

## 11. Definition of done

- Every FR above is implemented and every published check in `docs/lab1/CHECKS.md` for L1-CORE-1 through
  L1-CORE-4 passes; `./itsmlab.sh verify 1` exits 0 with L1-CORE-5 reported as `skip`.
- The `observations` line of the run reads `C1=wallclock C2=immutable C3=vip` and `DECISIONS.md` declares the
  same three values with all five labels filled in each section.
- The eight test vectors of FR-026 are reproduced to the second.
- No file under `src/` was committed before the `specs` receipt.
