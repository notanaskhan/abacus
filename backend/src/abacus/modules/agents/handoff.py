"""The human handoff contract and typed citations (ADR-054, ADR-066). TASK-011 design §5.

Every agent output extends `Handoff`: a proposed action, a confidence, a short rationale,
citations to exact sources, and what couldn't be verified. Citations are verified by code before
anyone sees them (`citations.verify`); a failing citation is marked unverified, never shown as
fact. Agent text is untrusted: the board renders it as sanitised plain text (ADR-065).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified

CellRef = Annotated[str, Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]{0,6}$")]


class Citation(BaseModel):
    """A spreadsheet cell, and optionally the exact text or number the agent says it holds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cell: Annotated[CellRef, classified("internal")]
    quote: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    value: Annotated[Decimal | None, classified("confidential")] = None


class Handoff(BaseModel):
    """Subclasses declare `action` as a Literal of the actions their agent may propose."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    confidence: Annotated[float, Field(ge=0, le=1), classified("internal")]
    rationale: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
    citations: Annotated[list[Citation], Field(max_length=50), classified("confidential")]
    unverified: Annotated[
        list[Annotated[str, Field(max_length=300)]],
        Field(max_length=50),
        classified("confidential"),
    ]


class ScreeningOutput(Handoff):
    """The screener's proposal (SPEC-000 §10)."""

    action: Annotated[Literal["ready_for_review", "needs_revision"], classified("internal")]


class VerifiedCitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    cell: Annotated[str, classified("internal")]
    quote: Annotated[str | None, classified("confidential")]
    value: Annotated[str | None, classified("confidential")]
    verified: Annotated[bool, classified("internal")]
    reason: Annotated[str | None, classified("internal")]
