"""`NoticeIntakeWorkflow`'s input (N-04-T07): identifiers only; no value reaches a payload."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NoticeIntakeInput:
    tenant_id: str
    intake_id: str


@dataclass(frozen=True)
class IntakeReadStep:
    tenant_id: str
    intake_id: str
    refusal: str | None = None  # the OCR gate's refusal, from the signal
