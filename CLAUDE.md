<!-- ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md section 5; the lecturer reviewed it -->
# svcdesk - instructions for coding agents

This repository is the reference implementation of `svcdesk`, the service-desk API of the ITSM course
(Lab 1). Read this file before touching anything.

## What is a contract and what is a choice

- The HTTP contract (endpoints, ticket model, priority matrix, SLA vectors, breach and pause semantics, state
  machine, validation, test clock, compose contract) is fixed by the course's `API.md`; `specs/spec.md` restates
  it. Do not change observable behaviour without a matching change to the specs and the tests.
- The three contradiction resolutions are runtime switches (`SVCDESK_C1`, `SVCDESK_C2`, `SVCDESK_C3`), and
  `DECISIONS.md` must always declare the combination the running service exhibits. Never edit `DECISIONS.md` by
  hand: change the prose in `make_decisions.py` and regenerate (`python make_decisions.py C1 C2 C3`).
- Everything else (module layout, storage, error message wording) is an implementation choice.

## Layout

- `src/svcdesk/` - the package (`sla.py` is the SLA arithmetic, `service.py` the state machine, `app.py` HTTP).
- `tests/` - pytest suite; `tests/run_tests.py` prints the `ITSMLAB-TESTS:` line used by the compose `tests` service.
- `specs/` - spec-kit style constitution, spec, plan, tasks and the converge report.
- `DECISIONS.md`, `make_decisions.py` - the decision record and its generator.
- `docker-compose.yml`, `Dockerfile` - the compose contract; no bind mounts, no network at run time.

## Commands

```
uv venv --python 3.13 && uv pip install -e ".[tests]"
uv run pytest -q                                  # all eight combinations in-process
uv run python tests/run_tests.py                  # same, with the ITSMLAB-TESTS summary line
docker compose up --build --wait svcdesk && docker compose --profile tests run --rm tests
```

## Rules

- Run the tests before and after every change; a change that breaks a vector of `tests/vectors.py` is wrong,
  the vectors are not.
- Keep the AI-disclosure header (`ai-generated: NN% - ...`) in the first ten lines of every source, spec and
  markdown file you create; update the percentage when you rewrite a file.
- ASCII hyphens only, never em-dashes or en-dashes; `tests/test_repo.py` fails otherwise.
- Do not add dependencies that need a network at run time; the grading sandbox has no egress.
- Do not push, delete files or run containers from a sub-agent; see `AGENT-POLICY.md` for why each of those is
  a blast-radius decision, and `.claude/agents/reviewer.md` for the read-only reviewer.
