# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md section 7.4; the lecturer ran the tests
"""Runtime settings: the three contradiction resolutions, the test clock switch, the database path and the
kb-index URL (Lab 3).

Every value comes from an environment variable so that the same image exhibits any of the eight
resolution combinations (LAB1.md section 2 and 7.4) without a rebuild.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from collections.abc import Mapping

ADMISSIBLE: dict[str, tuple[str, str]] = {
    "C1": ("wallclock", "business"),
    "C2": ("reopen", "immutable"),
    "C3": ("matrix", "vip"),
}

DEFAULTS: dict[str, str] = {"C1": "wallclock", "C2": "immutable", "C3": "vip"}

TRUE_VALUES = {"1", "true"}


@dataclass(frozen=True)
class Settings:
    c1: str = DEFAULTS["C1"]
    c2: str = DEFAULTS["C2"]
    c3: str = DEFAULTS["C3"]
    test_clock: bool = False
    db_path: str = "/data/svcdesk.db"
    kb_index_url: str = "http://kb-index:8080"

    def __post_init__(self) -> None:
        for key, value in (("C1", self.c1), ("C2", self.c2), ("C3", self.c3)):
            if value not in ADMISSIBLE[key]:
                raise ValueError(
                    f"SVCDESK_{key}={value!r} is not admissible; use one of {' | '.join(ADMISSIBLE[key])}"
                )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        return cls(
            c1=env.get("SVCDESK_C1", DEFAULTS["C1"]).strip().lower(),
            c2=env.get("SVCDESK_C2", DEFAULTS["C2"]).strip().lower(),
            c3=env.get("SVCDESK_C3", DEFAULTS["C3"]).strip().lower(),
            test_clock=env.get("SVCDESK_TEST_CLOCK", "0").strip().lower() in TRUE_VALUES,
            db_path=env.get("SVCDESK_DB", "/data/svcdesk.db"),
            kb_index_url=env.get("KB_INDEX_URL", "http://kb-index:8080"),
        )

    @property
    def resolutions(self) -> dict[str, str]:
        return {"C1": self.c1, "C2": self.c2, "C3": self.c3}
