# ai-generated: 100% - Claude Code (Fable 5.1) wrote this runner from design/LAB1.md section 5 (Stretch S3); the lecturer ran it natively and in compose
"""Run the suite and print `ITSMLAB-TESTS: passed=<n> failed=<m>` as the last stdout line (Stretch S3).

`failed` counts every failed or errored test phase and any collection error, so a broken suite never reports
failed=0. Exit status is 0 only when nothing failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


class Counter:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "call" and report.passed:
            self.passed += 1
        elif report.failed:
            self.failed += 1

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            self.failed += 1


def main(argv: list[str]) -> int:
    counter = Counter()
    tests_dir = str(Path(__file__).resolve().parent)
    code = pytest.main(["-q", "-p", "no:cacheprovider", tests_dir, *argv], plugins=[counter])
    if code != 0 and counter.failed == 0:
        counter.failed = 1  # no tests collected, usage error or internal error: never report a clean run
    sys.stdout.flush()
    print(f"ITSMLAB-TESTS: passed={counter.passed} failed={counter.failed}", flush=True)
    return 0 if counter.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
