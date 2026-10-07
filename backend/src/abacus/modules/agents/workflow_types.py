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
# Waited for a work slot longer than the class allows (SPEC-003 AC-14).
CAPACITY_TIMEOUT = "capacity_timeout"
# The model call wasn't admitted (SPEC-003 AC-11): ApplicationError type, with details
# (reason, retry_after seconds, the class's maximum wait in seconds).
NOT_ADMITTED = "NotAdmitted"
FAIL_CODES = frozenset({PROVIDER_UNAVAILABLE, INTERNAL_ERROR, CANCELLED, CAPACITY_TIMEOUT})


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


@dataclass(frozen=True)
class SlotGrant:
    """An `acquire_slot` activity's answer (SPEC-003): granted, and the class's maximum wait in
    seconds before the run fails `capacity_timeout`."""

    granted: bool
    max_wait_seconds: int
