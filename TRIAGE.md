---
lab5_triage:
  image: ghcr.io/swasik/itsm-svcdesk@sha256:f81832ce5b5110a8ee3bc2b85d27863a851feecde5c2c13089a2e6b44383e934
  sarif_receipt: 264
---
<!-- ai-generated: 100% - Claude Code (hosted test run) triaged the pipeline's runs and wrote this file -->
# Triage

What the gates and the reporting scanners found on my service, and what I did about each (CI-SPEC.md P-11, P-12).
One row per rule of one tool. The rows come from the pipeline's runs on GitHub (the image job's Trivy gate, and the
reporting scanners' SARIF of the canary run, results outside `lab5-canary/`). The six Trivy rows were found before
the first push, by the same Trivy image gate run locally on the untriaged image; the first run on GitHub (with the
triaged Dockerfile) was green, and its image is the digest above.

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | CVE-2026-103111 | fix | libpcre2-8-0 10.46-1~deb13u2 in the base image; fixed by pinning python:3.13-slim to the 2026-10-11 digest and `apt-get upgrade` in the Dockerfile (10.46-1~deb13u3) |
| trivy | CVE-2026-84782 | fix | openssl, libssl3t64 and openssl-provider-legacy 3.5.7-1~deb13u2 in the base image; fixed by the same `apt-get upgrade` line of the Dockerfile (3.5.7-1~deb13u3) |
| trivy | GHSA-6v7p-g79w-8964 | fix | msgpack 1.1.2 vendored inside pip 26.2.1 (no pip release has the fix); fixed by `pip uninstall -y pip` after installing svcdesk: the runtime image has no pip, nothing calls it at run time |
| trivy | CVE-2025-47273 | fix | setuptools 70.3.0 (pkg_resources) vendored inside pip; gone with pip from the runtime image, same Dockerfile line |
| trivy | CVE-2026-97687 | fix | urllib3 2.7.0 vendored inside pip (proxy TLS override); gone with pip from the runtime image, same Dockerfile line; svcdesk itself uses httpx, not urllib3 |
| trivy | CVE-2026-97689 | fix | urllib3 2.7.0 vendored inside pip (chunk parser DoS); gone with pip from the runtime image, same Dockerfile line |
| semgrep | python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query | false-positive | src/svcdesk/db.py lines 122, 131, 148: sqlite3, not SQLAlchemy; the f-strings interpolate only the constant COLUMNS tuple and fixed `state = ?` / `priority = ?` fragments, every value is a bound `?` parameter. Also semgrep/rules.py lines 12 and 18: the `# ruleid:` test cases of my own Stretch 3 rule, written to match on purpose and never imported or run by svcdesk |
| semgrep | python.lang.security.audit.formatted-sql-query.formatted-sql-query | false-positive | semgrep/rules.py line 18: a test case of my own Semgrep rule (Stretch 3), an f-string SQL statement kept there so that `semgrep --test` proves the rule fires; the file is test data, not part of svcdesk, and is never imported |
| semgrep | python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected | false-positive | src/svcdesk/healthcheck.py line 14: the URL is always `http://127.0.0.1:<port>/health`; only the port comes from the container's own environment, so no file:// or foreign host can reach urlopen |
| semgrep | package_managers.uv.uv-missing-dependency-cooldown.uv-missing-dependency-cooldown | accept | pyproject.toml line 35: `[tool.uv]` has no dependency cooldown; every dependency is pinned exactly (==) and only uv venv/pip install is used, so a fresh release cannot slip in; revisit by 2027-01-31 when we adopt a lock file |
| semgrep | semgrep.svcdesk-sql-text-from-fstring | accept | my own guard rule (semgrep/rules.yml) reports db.py lines 122, 131, 148: reviewed, the interpolated text is constant column lists; the rule keeps every new f-string SQL statement visible in review |
| semgrep | semgrep.svcdesk-env-read-outside-settings | accept | my own rule reports src/svcdesk/healthcheck.py line 12: the healthcheck runs as a separate process and only reads its port; accepted until the healthcheck moves into Settings (by 2027-01-31) |

## Bake-off

Practice set first (9 labelled defects; my bakeoff.py reproduces expected.json): Trivy 3 TP / 0 FP, Grype and
OSV-Scanner 2 / 0 each, gitleaks 2 / 0, Semgrep 5 / 2, the course's example AI reviewer 6 / 3.

My canary set (SARIF receipt #264, canary run 38121870505 of C 1be96eb, 8 labelled defects: A03 path traversal,
A08 weak randomness, A10 pickle, C01-C03 three credentials, D05 PyYAML and D08 urllib3 pins):

| tool | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|
| trivy | 4 | 1 | 4 | 0.8 | 0.5 | 0.6154 |
| gitleaks | 3 | 1 | 5 | 0.75 | 0.375 | 0.5 |
| grype | 2 | 0 | 6 | 1.0 | 0.25 | 0.4 |
| osv-scanner | 2 | 0 | 6 | 1.0 | 0.25 | 0.4 |
| ai-reviewer (qwen3:4b-instruct, local) | 3 | 2 | 5 | 0.6 | 0.375 | 0.4615 |
| semgrep | 2 | 4 | 6 | 0.3333 | 0.25 | 0.2857 |

Cells that surprised me, checked result by result. Trivy is the best single detector here only because it runs two
scanners: its 14 advisories on the two pins collapse onto D05 and D08, and its secret scanner adds C02 and C03.
The one FP that gitleaks, Trivy and Semgrep share is the same decoy: jwt.io's public example token in
`app/token_fixtures.py`, a test fixture. gitleaks is the only tool that finds C01 (a `curl -u user:password` with
no token shape). Semgrep pays for its breadth: of its 4 FPs, 3 are SQL rules firing on the two decoys that are safe
by construction (`columns.py` interpolates an allow-listed column name, `ticket_counts.py` an `int()`), and its one
code TP is the pickle in `session_store.py`. The local 4B model found two of the three credentials and the PyYAML pin,
reported the `int()`-cast decoy as SQL injection, and put the curl credential on line 1 instead of 3 - a positioning
error that P-20 counts as an FP plus an FN. Nobody found A03 (path traversal) or A08 (`random.choice` for reset
tokens), and none of the five scanners can see A12-style access control at all.

What I would gate on: Trivy (dependency files and the image) and gitleaks, as the skeleton does - precision 0.75 to
0.8 here, a fixed class, a cheap and obvious fix, and their single FP is a fixture that an ignore with a reason
handles. Grype and OSV-Scanner add nothing Trivy did not already find on this set (precision 1.0 but the same two
defects), so they stay reporting. Semgrep with `p/default` (precision 0.33) and the AI reviewer (0.6) would fail
builds on safe code; they belong in review, not in a gate. Every recall above is an upper bound: seeded defects are
written to be found, and on real code these numbers would be lower.
