<!-- ai-generated: 100% - drafted by Claude Code from docs/lab1 (HANDOUT.md, REQUIREMENTS.md, API.md, CHECKS.md) -->
# svcdesk - project constitution

The standing rules for every change to this repository, for the whole semester. A specification, a plan or a
commit that breaks one of these is wrong even when the checker is green.

## P1 - Specification before code

No file appears under `src/` (other than `src/README.md`) before the specification under `specs/` is pushed and
the `specs` receipt exists. The receipt records the order; the history is the evidence (Core spec L1-CORE-5).
When the implementation has to diverge from the specification, the specification is amended in the same commit,
never silently outgrown.

## P2 - `API.md` is the contract, `REQUIREMENTS.md` is the intent

`docs/lab1/REQUIREMENTS.md` says what the service desk wants and why; `docs/lab1/API.md` says exactly what the
HTTP interface does. Where the two differ in precision, API.md wins and the specification records that it did.
Nothing in this repository re-interprets a published test vector: the eight vectors of API.md section 4 are
reproduced exactly, to the second.

## P3 - Contradictions are resolved in the open

The requirements contain three pairs that cannot both hold (C1, C2, C3). Each is resolved by rejecting the
smallest conflicting part of one requirement and keeping everything else in the pair. The resolution is written
down in `DECISIONS.md` with its owner and its cost, and the running service exhibits exactly the declared value
(Core spec L1-CORE-4). Changing the behaviour and changing `DECISIONS.md` is one change, never two.

## P4 - Determinism over wall time

Every clock-dependent behaviour is reachable through the per-request test clock (`X-Test-Clock`). The service
never compares one request's clock with another's, never enforces monotonic time and never rejects an action
because its clock precedes a stored timestamp. Timestamps are stored and compared as instants, never as strings.

## P5 - Everything at build time

The image installs its dependencies while it is built and needs no network afterwards. No host-path bind mounts
on any service, in any override file. The service listens on 8080 inside the container and answers `/health`
within 120 s of `docker compose up`.

## P6 - Errors are part of the interface

A refusal is a designed response: the right status (400/422 for validation, 404 for unknown ids and paths,
409 for an invalid transition or an expired reopen window) and a JSON body with a top-level `error` object.
Fields the service owns and fields it does not know are ignored on input, never rejected.

## P7 - Disclosure

Every `.md`, `.py` and other checked source file under `specs/` and `src/`, plus `DECISIONS.md`, carries the
`ai-generated: <0-100>% - <how>` comment in its first ten lines, and the number is the honest one. No personal
data enters the repository: no hostnames, no usernames, no `doctor` output.

## Amendment

This file changes by an ordinary commit that says what changed and why. The three decisions C1, C2 and C3 are
not amendments to this constitution; they live in `DECISIONS.md` and may be revised there as long as the service
and the document move together.
