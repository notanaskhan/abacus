"""The ledger sync routes, C9 v2.1 sync-status facts (C-01-T07; C-01 §4.3, §4.5; SPEC-655 F5;
`docs/contracts/c09-ledger.md` "C9 v2.1"). Provider: connections (red).

- `GET /v1/client-entities/{eid}/ledger-sync`: the entity's sync facts (last sync, next sync,
  failure code, meter state) in `ledger_sync` words (`ledger.read`).
- `POST /v1/client-entities/{eid}/ledger-sync`: Sync now, one pull at once, logged
  `ledger.sync_now` (Senior and above; a live person's, INV-1).

Every route answers, in order: a client principal 404; `connections.ledger_sync` off 404; the
human-only POST refuses non-persons 403; then 501 until C-01-T17 (`LedgerSyncWorkflow`). Read
only: nothing here writes to QuickBooks (CONN-001, ADR-040).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import CONNECTIONS_LEDGER_SYNC
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")

SyncState = Literal["synced", "syncing", "rate_limited", "needs_reauth", "paused", "not_connected"]


class LedgerNotConnected(DomainConflict):
    """Sync now on an entity without a live ledger connection."""

    code = "ledger_not_connected"


class MeterBudgetExhausted(DomainConflict):
    """Scheduled syncs paused: the firm's monthly Intuit call budget is reached (QC-5)."""

    code = "meter_budget_exhausted"


class MeterOut(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    month: Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"), Internal]
    calls: Annotated[int, Field(ge=0), Internal]
    budget: Annotated[int | None, Field(ge=0), Internal] = None
    state: Annotated[Literal["ok", "warning", "exhausted"], Internal]  # 80% and 100% (QC-5)


class LedgerSyncStatusOut(BaseModel):
    """ "Synced 10:02 AM · next 11:02 AM" (CLS-02 rail, CLS-04 header)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    client_entity_id: Annotated[UUID, Internal]
    connection_id: Annotated[UUID | None, Internal] = None
    provider: Annotated[Literal["quickbooks_online"] | None, Internal] = None
    state: Annotated[SyncState, Internal]
    last_synced_at: Annotated[datetime | None, Internal] = None
    next_sync_at: Annotated[datetime | None, Internal] = None
    retry_at: Annotated[datetime | None, Internal] = None  # "rate limit · retrying 10:07 AM"
    failure_code: Annotated[str | None, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$"), Internal] = None
    meter: MeterOut | None = None


class SyncNowOut(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sync_run_id: Annotated[UUID, Internal]
    state: Annotated[SyncState, Internal]


ledger_sync_router = AbacusRouter(prefix="/v1/client-entities", tags=["ledger sync"])


async def _sync_on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, CONNECTIONS_LEDGER_SYNC):
        raise NotFound(CONNECTIONS_LEDGER_SYNC.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@ledger_sync_router.get(
    "/{client_entity_id}/ledger-sync",
    action="ledger.read",
    response_model=LedgerSyncStatusOut,
    errors=(501,),
)
async def ledger_sync_status_route(client_entity_id: UUID, ctx: Ctx) -> LedgerSyncStatusOut:
    """The entity's sync facts (C-01-T17)."""
    await _sync_on(ctx)
    _not_yet()


@ledger_sync_router.post(
    "/{client_entity_id}/ledger-sync",
    action="ledger.sync_now",
    response_model=SyncNowOut,
    status_code=202,
    errors=(409, 501),
)
async def ledger_sync_now_route(
    client_entity_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SyncNowOut:
    """Sync now: one pull at once (409 `ledger_not_connected`; C-01-T17)."""
    await _sync_on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden("ledger.sync_now", "role")
    _not_yet()
