# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md section 1.8; the lecturer ran it under Docker Compose
"""Container healthcheck without curl: exit 0 when GET /health answers 200 on the local port."""

from __future__ import annotations

import os
import sys
import urllib.request


def main() -> int:
    port = os.environ.get("SVCDESK_PORT_INTERNAL", "8080")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as response:
            return 0 if response.status == 200 else 1
    except Exception:  # noqa: BLE001 - any failure means unhealthy
        return 1


if __name__ == "__main__":
    sys.exit(main())
