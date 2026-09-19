<!-- ai-generated: 100% - drafted by Claude Code from docs/lab1/API.md, with C1=wallclock, C2=immutable, C3=vip resolved -->
# HTTP contract - svcdesk

The contract of [`docs/lab1/API.md`](../../../docs/lab1/API.md) with the three decisions resolved to the values
this service implements (C1 = `wallclock`, C2 = `immutable`, C3 = `vip`). Where this file and `API.md` disagree,
`API.md` wins and this file is wrong and must be fixed.

All requests and responses are `application/json`. Every endpoint accepts the `X-Test-Clock` header
(section 8 below).

## 1. Endpoints

| method and path | success | failures |
|---|---|---|
| `GET /health` | 200 `{"status":"ok","service":"svcdesk"}` | - |
| `POST /tickets` | 201 Ticket | 400/422 validation |
| `GET /tickets` | 200 `[Ticket]` | - |
| `GET /tickets/{id}` | 200 Ticket | 404 unknown id |
| `GET /tickets/{id}/sla` | 200 SlaReport | 404 unknown id |
| `POST /tickets/{id}/ack` | 200 Ticket | 409 not `new`; 404 unknown id |
| `POST /tickets/{id}/start` | 200 Ticket | 409 not `acknowledged`; 404 unknown id |
| `POST /tickets/{id}/resolve` | 200 Ticket | 409 not `in_progress`; 404 unknown id |
| `POST /tickets/{id}/close` | 200 Ticket | 409 not `resolved`; 404 unknown id |
| `POST /tickets/{id}/reopen` | 200 Ticket | 409 not `resolved`, or more than 7 days after `resolved_at`, or `closed`; 404 unknown id |
| anything else | - | 404 with a JSON body (405 is acceptable for a wrong method on a known path) |

Action endpoints take no request body; a body, if sent, is ignored.

## 2. `GET /health`

```http
GET /health
```
```json
{"status": "ok", "service": "svcdesk"}
```

200 always, with no dependency on storage or on the clock. Extra fields are allowed.

## 3. `POST /tickets`

Request:

```json
{"title": "Printer on floor 2 is down",
 "description": "Nobody on the floor can print.",
 "reporter": {"name": "Anna Nowak", "email": "anna.nowak@example.com", "vip": false},
 "impact": 2, "urgency": 1, "related_to": null}
```

With `X-Test-Clock: 2026-10-14T10:00:00Z` (vector T1) the answer is 201:

```json
{"id": "6f1c2c1e-3f0a-4b7e-9a51-2a1c6d8e0f11",
 "title": "Printer on floor 2 is down",
 "description": "Nobody on the floor can print.",
 "reporter": {"name": "Anna Nowak", "email": "anna.nowak@example.com", "vip": false},
 "impact": 2, "urgency": 1, "priority": "P2", "state": "new",
 "created_at": "2026-10-14T10:00:00Z",
 "acknowledged_at": null, "resolved_at": null, "closed_at": null,
 "related_to": null,
 "sla": {"ack_due_at": "2026-10-14T11:00:00Z", "resolve_due_at": "2026-10-15T10:00:00Z"}}
```

Accepted and ignored in the request body: `id`, `priority`, `state`, `created_at`, `acknowledged_at`,
`resolved_at`, `closed_at`, `sla`, and any field the service does not know. They never cause a refusal.

Refused with 400 or 422 and `{"error": {...}}`:

| input | reason |
|---|---|
| no `title`, `title` not a string, `""`, or 201+ characters | R-03 |
| `description` longer than 4000 characters | R-03 |
| no `reporter`, `reporter` not an object, no `reporter.name`, name `""` or 101+ characters | R-03 |
| `reporter.email` present and neither a string nor `null`; `reporter.vip` present and not boolean | R-03 |
| `impact` or `urgency` absent, not an integer, boolean, or outside 1..3 (`5`, `"high"`, `2.5`) | R-03 |
| the body is not a JSON object | R-01 |

## 4. `GET /tickets`

```http
GET /tickets?state=new&priority=P1
```

200 with a JSON array of every matching ticket, in any order, no pagination. Both parameters are optional, match
exactly, and combine as a conjunction. Repeated parameters take the last value. A value that matches nothing
yields `[]`.

## 5. `GET /tickets/{id}`

200 with the full ticket, or 404 with `{"error": {"code": "not_found", "message": "..."}}`.

## 6. `GET /tickets/{id}/sla`

```json
{"priority": "P3",
 "ack_due_at": "2026-10-19T09:30:00Z",
 "resolve_due_at": "2026-10-21T13:30:00Z",
 "ack_breached": true,
 "resolve_breached": false,
 "paused": false}
```

Evaluated at the `now` of this request. `ack_due_at` and `resolve_due_at` are the same instants the ticket
carries in its `sla` block and never change. The three booleans follow
[data-model.md](../data-model.md) section 3.

## 7. Transitions

Each action returns 200 with the full ticket in its new state.

| endpoint | allowed from | sets | otherwise |
|---|---|---|---|
| `POST /tickets/{id}/ack` | `new` | `acknowledged_at = now`, state `acknowledged` | 409 |
| `POST /tickets/{id}/start` | `acknowledged` | state `in_progress` | 409 |
| `POST /tickets/{id}/resolve` | `in_progress` | `resolved_at = now`, state `resolved` | 409 |
| `POST /tickets/{id}/close` | `resolved` | `closed_at = now`, state `closed` | 409 |
| `POST /tickets/{id}/reopen` | `resolved` and `now <= resolved_at + 7 days` | clears `resolved_at` and `closed_at`, state `in_progress` | 409 |

409 bodies:

```json
{"error": {"code": "invalid_transition", "message": "cannot resolve a ticket in state acknowledged"}}
{"error": {"code": "reopen_window_expired", "message": "reopen is allowed within 7 days of resolution"}}
{"error": {"code": "ticket_closed", "message": "a closed ticket is immutable; raise a new ticket with related_to"}}
```

The `code` strings are not checked in Lab 1; the 409 and the presence of a top-level `error` object are.

Under C2 = `immutable`, `reopen` on a `closed` ticket is 409 however recently it was closed. The caller's route
back is `POST /tickets` with `related_to` set to the closed ticket's id.

## 8. `X-Test-Clock`

Active when the environment variable `SVCDESK_TEST_CLOCK` is `1` or `true`.

- `X-Test-Clock: 2026-10-16T13:30:00Z` makes that instant the `now` of this request and of nothing else.
- An offset is required: `2026-10-16T15:30:00+02:00` is fine, `2026-10-16 15:30:00` and `yesterday` are not and
  answer 400 or 422 with `{"error": {...}}`.
- Absent header: `now` is real UTC time. Variable unset or `0`: the header is ignored.
- The service never compares one request's clock with another's, never enforces monotonic time, and never refuses
  an action because its clock precedes a stored timestamp. Acknowledging at a clock earlier than `created_at` is
  a 200.

## 9. Error body

Every 400, 404, 409 and 422 the service produces carries:

```json
{"error": {"code": "<string>", "message": "<human-readable, no personal data>"}}
```

`code` is one of `validation`, `not_found`, `invalid_transition`, `reopen_window_expired`, `ticket_closed`.
An unknown path returns 404 with a JSON body; it uses the same shape, with `code` `not_found`.
