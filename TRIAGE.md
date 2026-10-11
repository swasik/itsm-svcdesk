---
lab5_triage:
  image: ghcr.io/fresh-student/itsm-svcdesk@sha256:1ddb8dbea9f0013547566b7dd8d6805186f6362116b38824dd88a6ab22b92c0e
  sarif_receipt: 0
---
<!-- ai-generated: 100% - Claude Code (hosted test run) triaged the pipeline's runs and wrote this file -->
# Triage

What the gates and the reporting scanners found on my service, and what I did about each (CI-SPEC.md P-11, P-12).
One row per rule of one tool. The rows come from the pipeline's runs on GitHub (the image job's Trivy gate, and the
reporting scanners' SARIF of the canary run, results outside `lab5-canary/`).

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | CVE-2026-103111 | fix | libpcre2-8-0 10.46-1~deb13u2 in the base image; fixed by pinning python:3.13-slim to the 2026-10-11 digest and `apt-get upgrade` in the Dockerfile (10.46-1~deb13u3) |
| trivy | CVE-2026-84782 | fix | openssl, libssl3t64 and openssl-provider-legacy 3.5.7-1~deb13u2 in the base image; fixed by the same `apt-get upgrade` line of the Dockerfile (3.5.7-1~deb13u3) |
| trivy | GHSA-6v7p-g79w-8964 | fix | msgpack 1.1.2 vendored inside pip 26.2.1 (no pip release has the fix); fixed by `pip uninstall -y pip` after installing svcdesk: the runtime image has no pip, nothing calls it at run time |
| trivy | CVE-2025-47273 | fix | setuptools 70.3.0 (pkg_resources) vendored inside pip; gone with pip from the runtime image, same Dockerfile line |
| trivy | CVE-2026-97687 | fix | urllib3 2.7.0 vendored inside pip (proxy TLS override); gone with pip from the runtime image, same Dockerfile line; svcdesk itself uses httpx, not urllib3 |
| trivy | CVE-2026-97689 | fix | urllib3 2.7.0 vendored inside pip (chunk parser DoS); gone with pip from the runtime image, same Dockerfile line |
| semgrep | python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query | false-positive | src/svcdesk/db.py lines 122, 131, 148: sqlite3, not SQLAlchemy; the f-strings interpolate only the constant COLUMNS tuple and fixed `state = ?` / `priority = ?` fragments, every value is a bound `?` parameter |
| semgrep | python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected | false-positive | src/svcdesk/healthcheck.py line 14: the URL is always `http://127.0.0.1:<port>/health`; only the port comes from the container's own environment, so no file:// or foreign host can reach urlopen |
| semgrep | package_managers.uv.uv-missing-dependency-cooldown.uv-missing-dependency-cooldown | accept | pyproject.toml line 35: `[tool.uv]` has no dependency cooldown; every dependency is pinned exactly (==) and only uv venv/pip install is used, so a fresh release cannot slip in; revisit by 2027-01-31 when we adopt a lock file |
| semgrep | semgrep.svcdesk-sql-text-from-fstring | accept | my own guard rule (semgrep/rules.yml) reports db.py lines 122, 131, 148: reviewed, the interpolated text is constant column lists; the rule keeps every new f-string SQL statement visible in review |
| semgrep | semgrep.svcdesk-env-read-outside-settings | accept | my own rule reports src/svcdesk/healthcheck.py line 12: the healthcheck runs as a separate process and only reads its port; accepted until the healthcheck moves into Settings (by 2027-01-31) |

## Bake-off

Practice set first (9 labelled defects, my bakeoff.py reproduces expected.json exactly): Trivy 3 TP / 0 FP
(precision 1.0, recall 0.3333), Grype and OSV-Scanner 2 / 0 each (1.0, 0.2222), gitleaks 2 / 0 (1.0, 0.2222),
Semgrep 5 / 2 (0.7143, 0.5556, F1 0.625), the course's example AI reviewer 6 / 3 (0.6667 on all three). The three
dependency scanners and gitleaks never raise a false alarm in the set because their class is fixed by the tool
(P-19 b) and a pin or a credential is either there or not; they are also blind to everything outside their class,
which caps their recall at 2/9 or 3/9. Semgrep is the only detector that sees code defects, and its two false
positives are the instructive cells: the same SHA-1 rule is a true positive on a password hash and a false positive
on a message fingerprint - only the key can tell the two apart.

On my canary set the labels were not revealed in this offline run (no SARIF receipt could be filed), so I have the
raw result counts but no matrix: inside lab5-canary/ Trivy reported 20 distinct results, Grype 18, OSV-Scanner 22
distinct (36 raw - it writes almost every result twice), gitleaks 3 (one per credential file), Semgrep 5 and the
local qwen3:4b-instruct reviewer 9. With 2 pins in the set, most of Trivy's and Grype's results are distinct
advisories on the same two packages and will collapse onto 2 TPs; whether the rest count as FPs depends on P-21's
(ruleId, file, lines) key, which makes per-advisory reporting look like low precision even when every advisory is real.

What I would gate on: Trivy for dependency files and the image, and gitleaks - high precision, a fixed class, a
cheap fix (raise a pin, move a credential) - which is what the skeleton does. Semgrep and an AI reviewer report;
with precision around 0.7 on seeded defects they would make developers click through red builds. Every recall
here is an upper bound: seeded defects are written to be found, and the set also holds defects none of the five
scanners can see by construction (access control, logic), so the real-world numbers would be lower.
