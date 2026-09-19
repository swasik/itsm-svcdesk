# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md section 1.7; the lecturer ran the tests
"""Instants and the per-request test clock (LAB1.md section 1.7).

`now` is decided once per request: the `X-Test-Clock` header when the test clock is enabled and the header
is present, real UTC time otherwise. The service never compares one request's clock with another's.
"""

from __future__ import annotations

from datetime import UTC, datetime


def parse_instant(text: str) -> datetime:
    """Parse an RFC 3339 instant that carries an offset; return it as an aware UTC datetime.

    A naive timestamp (no offset) is malformed, as is anything `datetime.fromisoformat` rejects.
    """
    try:
        parsed = datetime.fromisoformat(text.strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"not an RFC 3339 instant: {text!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"naive timestamp without a UTC offset: {text!r}")
    return parsed.astimezone(UTC)


def format_instant(instant: datetime) -> str:
    """Render an aware datetime as a UTC RFC 3339 string with a Z suffix."""
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


def real_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)
