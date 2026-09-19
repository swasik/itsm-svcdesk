# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md sections 1 and 2; the lecturer ran the suite natively and in compose
"""Fixtures: one HTTP client per resolution combination.

Two modes, chosen by the environment:

- `SVCDESK_URL` set: talk to that running service and expect the combination declared by SVCDESK_C1/C2/C3
  (defaults wallclock / immutable / vip, the same defaults the compose file uses). This is what the compose
  `tests` service does.
- `SVCDESK_URL` unset: start the reference in-process (a real uvicorn server on an ephemeral port, its own
  SQLite file) once per combination and run the whole API suite under all eight combinations
  (`SVCDESK_COMBOS=env` restricts that to the combination named by the environment).

Only HTTP is used, so the same tests would run against any implementation of the API.
"""

from __future__ import annotations

import itertools
import os
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest

C1_VALUES = ("wallclock", "business")
C2_VALUES = ("reopen", "immutable")
C3_VALUES = ("matrix", "vip")
ALL_COMBOS = list(itertools.product(C1_VALUES, C2_VALUES, C3_VALUES))
DEFAULT_COMBO = ("wallclock", "immutable", "vip")

REMOTE_URL = os.environ.get("SVCDESK_URL", "").strip() or None

requires_local = pytest.mark.skipif(
    REMOTE_URL is not None, reason="needs an in-process server; SVCDESK_URL points at a running service"
)


def env_combo() -> tuple[str, str, str]:
    return (
        os.environ.get("SVCDESK_C1", DEFAULT_COMBO[0]).strip().lower(),
        os.environ.get("SVCDESK_C2", DEFAULT_COMBO[1]).strip().lower(),
        os.environ.get("SVCDESK_C3", DEFAULT_COMBO[2]).strip().lower(),
    )


def combos_under_test() -> list[tuple[str, str, str]]:
    if REMOTE_URL is not None or os.environ.get("SVCDESK_COMBOS", "all").lower() == "env":
        return [env_combo()]
    return ALL_COMBOS


# A parametrised session fixture (not metafunc.parametrize) so that pytest groups the tests by combination
# and starts each in-process server exactly once.
@pytest.fixture(scope="session", params=combos_under_test(), ids=["-".join(p) for p in combos_under_test()])
def combo(request: pytest.FixtureRequest) -> tuple[str, str, str]:
    return request.param


@dataclass
class ServerHandle:
    url: str
    combo: tuple[str, str, str]


class LocalServer(ServerHandle):
    """The reference app served by uvicorn in a background thread on an ephemeral port."""

    def __init__(self, combo: tuple[str, str, str], db_path: str, test_clock: bool = True) -> None:
        import uvicorn

        from svcdesk.app import create_app
        from svcdesk.config import Settings

        super().__init__(url="", combo=combo)
        settings = Settings(c1=combo[0], c2=combo[1], c3=combo[2], test_clock=test_clock, db_path=db_path)
        config = uvicorn.Config(create_app(settings), host="127.0.0.1", port=0, log_level="warning", lifespan="on")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self) -> "LocalServer":
        self.thread.start()
        deadline = time.monotonic() + 15
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("uvicorn did not start")
            time.sleep(0.02)
        port = self.server.servers[0].sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        return self

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=15)


@pytest.fixture(scope="session")
def server(combo: tuple[str, str, str], tmp_path_factory: pytest.TempPathFactory) -> Iterator[ServerHandle]:
    if REMOTE_URL is not None:
        yield ServerHandle(url=REMOTE_URL, combo=combo)
        return
    db_path = tmp_path_factory.mktemp("svcdesk-" + "-".join(combo)) / "svcdesk.db"
    local = LocalServer(combo, str(db_path)).start()
    try:
        yield local
    finally:
        local.stop()


@pytest.fixture(scope="session")
def client(server: ServerHandle) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=server.url, timeout=10.0) as http:
        yield http


@pytest.fixture(scope="session")
def c1(combo: tuple[str, str, str]) -> str:
    return combo[0]


@pytest.fixture(scope="session")
def c2(combo: tuple[str, str, str]) -> str:
    return combo[1]


@pytest.fixture(scope="session")
def c3(combo: tuple[str, str, str]) -> str:
    return combo[2]
