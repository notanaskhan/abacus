"""Workflow and activity payloads for retrieval (TASK-010 design §6). Identifiers only.

Plain dataclasses of strings, so they serialise stably (replay, ADR-090). The workflow input is
never proof of anything: every activity re-derives its context from the run row
(`load_system_context`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalInput:
    tenant_id: str
    run_id: str


@dataclass(frozen=True)
class FailInput:
    tenant_id: str
    run_id: str
    status: str
    code: str


@dataclass(frozen=True)
class RetrievalOutcome:
    status: str
    code: str | None = None
    evidence_version_id: str | None = None
