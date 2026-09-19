# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md sections 1.2 and 2 (C3); the lecturer ran the tests
"""Priority: the impact x urgency matrix (R-04) and the VIP resolution of contradiction C3."""

from __future__ import annotations

MATRIX: dict[tuple[int, int], str] = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}

PRIORITIES = ("P1", "P2", "P3", "P4")


def priority_for(impact: int, urgency: int, vip: bool, c3: str) -> str:
    """Matrix first; under C3 = vip a VIP ticket at P3 or P4 is raised to P2, P1 and P2 are unchanged."""
    priority = MATRIX[(impact, urgency)]
    if c3 == "vip" and vip and priority in ("P3", "P4"):
        return "P2"
    return priority
