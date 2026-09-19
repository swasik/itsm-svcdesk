# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md sections 1.1 and 1.6; the lecturer ran the tests
"""Request body validation for POST /tickets (R-03, R-20).

Server-owned fields (`id`, `priority`, `state`, timestamps, `sla`) and unknown fields are not declared here,
so pydantic ignores them silently, as LAB1.md section 1.1 requires. `impact` and `urgency` are strict
integers: `"1"`, `1.0`, `true` and `"high"` are all validation errors.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Level = Annotated[int, Field(strict=True, ge=1, le=3)]


class ReporterIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Annotated[str, Field(min_length=1, max_length=100)]
    email: Annotated[str | None, Field(max_length=320)] = None
    vip: bool = False


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str | None, Field(max_length=4000)] = ""
    reporter: ReporterIn
    impact: Level
    urgency: Level
    related_to: str | None = None

    @field_validator("description", mode="after")
    @classmethod
    def _none_is_empty(cls, value: str | None) -> str:
        return "" if value is None else value
