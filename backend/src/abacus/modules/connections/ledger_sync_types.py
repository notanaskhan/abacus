"""Payloads of `LedgerSyncWorkflow` and its activities (C-01-T17). Identifiers and enums only:
plain dataclasses of strings and integers, so histories replay stably (ADR-090)."""

from __future__ import annotations

from dataclasses import dataclass, field

PLAN_TICK = "ledger_sync.plan_tick"
SYNC_ENTITY = "ledger_sync.sync_entity"
SYNC_NOW = "sync_now"
# Continue as new after this many hourly ticks (C-01 §4.5).
TICKS_PER_RUN = 24


@dataclass(frozen=True)
class SyncNowSignal:
    connection_id: str
    request_id: str
    started_by: str


@dataclass(frozen=True)
class LedgerSyncInput:
    tenant_id: str
    # Sync now requests carried across continue-as-new.
    pending: list[SyncNowSignal] = field(default_factory=list[SyncNowSignal])


@dataclass(frozen=True)
class PlanTickInput:
    tenant_id: str


@dataclass(frozen=True)
class PlanTickResult:
    wait_seconds: int
    connection_ids: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class SyncEntityInput:
    tenant_id: str
    connection_id: str
    trigger: str  # schedule | on_demand
    started_by: str
    request_id: str | None = None


@dataclass(frozen=True)
class SyncEntityResult:
    state: str
    snapshots: int = 0
    calls: int = 0
    failure_code: str | None = None
