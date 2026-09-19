<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote this file in the spec-kit constitution format from design/LAB1.md; the lecturer reviewed it -->
# svcdesk constitution

The non-negotiable principles behind every spec, plan and task in this repository. A task that conflicts with a
principle is wrong; the principle is not.

## I. The API contract is the product

`svcdesk` is an HTTP/JSON service-desk API. Its observable behaviour (endpoints, status codes, the ticket model,
the priority matrix, the SLA arithmetic, breach and pause semantics, the state machine, validation, the test
clock, the compose contract) is defined by the course's `API.md` and restated in `specs/spec.md`. Any language,
framework or storage engine that exhibits that behaviour is acceptable; nothing that deviates from it is.

## II. Contradictions are resolved explicitly, never silently

The requirements document contains three pairs of requirements that cannot both hold. Each is resolved by
rejecting the minimal conflicting part of one requirement and keeping everything else, and every resolution is
recorded in `DECISIONS.md` with the rejected alternative, the reason, the service owner who signs it off and the
customer outcome it favours. The running service must exhibit exactly the declared combination; the declaration
is generated, not hand-edited, so that it cannot drift from the code.

## III. Tests prove the contract, and they speak HTTP only

Every requirement has a test; the SLA vectors T1 to T8 are reproduced exactly under both clocks; every
resolution combination is exercised. The suite talks to the service over HTTP so that it would run unchanged
against any other implementation, and it prints a machine-readable summary line so the checker can read it.

## IV. Time is per request

`now` is decided once per request, from the `X-Test-Clock` header when the test clock is enabled and from real
UTC otherwise. The service never compares one request's clock with another's, never enforces monotonic time,
and never rejects an action because its clock precedes a stored timestamp. All instants are stored and returned
as UTC with a `Z` suffix and compared as points in time.

## V. Runs anywhere, needs nothing at run time

The image builds from `python:3.13-slim` with every dependency installed at build time; the running container
needs no network, no bind mounts and no privileges. Tickets persist in a named volume. The service starts and
answers `/health` within seconds, well inside the checker's 120-second window.

## VI. Disclosure and plain text

Every source, spec and markdown file carries an `ai-generated: NN% - ...` header in its first ten lines that
says how much of it a model wrote and how it was verified. Files use ASCII hyphens only.
