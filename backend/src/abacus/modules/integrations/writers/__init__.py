"""The `Writer` port (A-02-T15; ADR-150, P-17). A port only: no writer exists, and none may be
called except through `integrations.writes.execute_write`, which v1 refuses every time.

A future writer (W1 posting under P-16, W2 the tax engine bridge, W7 e-signature) implements
this for one declared capability: a dry run first, then one idempotent write whose request and
response are kept write-once as evidence, from a human-approved action (ADR-150).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class WriteRequest:
    capability: str
    client_id: UUID
    approval_ref: UUID  # the human-approved action the write carries out (ADR-150)
    idempotency_key: str


@dataclass(frozen=True)
class WritePreview:
    """What a dry run would change, as identifiers and counts only."""

    capability: str
    changes: int


@dataclass(frozen=True)
class WriteReceipt:
    capability: str
    evidence_version_id: UUID  # the write-once request and response


@runtime_checkable
class Writer(Protocol):
    @property
    def capability(self) -> str: ...

    async def dry_run(self, request: WriteRequest) -> WritePreview: ...

    async def write(self, request: WriteRequest) -> WriteReceipt: ...
