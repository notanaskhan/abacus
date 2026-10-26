"""Domain events the ledger announces (A-02-T07; C9 §7). Identifiers only (ADR-031)."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class TrialBalanceVersionCreated(DomainEvent):
    """A version of a trial balance of record was adopted (v1 or a re-version): P-04 marks
    sign-offs on an earlier version stale (SPEC-333 AC-4)."""

    event_type: ClassVar[str] = "trial_balance.version_created"

    trial_balance_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    snapshot_id: Annotated[UUID, classified("internal")]
    prior_snapshot_id: Annotated[UUID | None, classified("internal")] = None
