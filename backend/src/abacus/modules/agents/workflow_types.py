"""Screening workflow and activity payloads (TASK-011 design §7). Identifiers only.

Plain dataclasses of strings, so they serialise stably (replay, ADR-090). The workflow input is
never proof of anything: activities re-derive the agent's context from its run row.
"""

from __future__ import annotations

from dataclasses import dataclass

# What the workflow may record when it ends a run (anything else becomes INTERNAL_ERROR).
PROVIDER_UNAVAILABLE = "provider_unavailable"
INTERNAL_ERROR = "internal_error"
CANCELLED = "cancelled"
FAIL_CODES = frozenset({PROVIDER_UNAVAILABLE, INTERNAL_ERROR, CANCELLED})


@dataclass(frozen=True)
class ScreeningInput:
    """From the relayed `evidence_version.created` event: the only source of `requested_by`."""

    tenant_id: str
    evidence_version_id: str
    event_id: str
    requested_by: str | None


@dataclass(frozen=True)
class RunInput:
    tenant_id: str
    run_id: str


@dataclass(frozen=True)
class FailInput:
    tenant_id: str
    run_id: str
    code: str


@dataclass(frozen=True)
class ScreeningOutcome:
    """`skipped` (no run: nobody to act for, or not a screenable version), or the run's final
    status (`completed`, `escalated`, `failed`)."""

    status: str
    run_id: str | None = None
    code: str | None = None
    screening_result_id: str | None = None
