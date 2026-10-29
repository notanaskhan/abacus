"""C20 v1: the contract stub for POR-16 and the firm's connection actions (A-02-T06; SPEC-333
AC-35 to AC-44; ADR-136, ADR-040, ADR-108). Contract: `docs/contracts/c20-integrations.md`.

The client, not the firm, authorises access to the entity's ledger, bank and card feeds and
sales platforms. These routes fix POR-16's shapes so A-02-T18's fixture mode and A-02-T08's
consumer tests run against them; A-02-T16 implements them over `connections` (entity-scoped
connections, A-02-T13) and the catalogue (A-02-T12):

- `GET /v1/portal/entities/{entity_id}/connections` (`connection.read`, `scope_only`): one card
  per catalogue row whose adapter is registered here (AC-35, AC-49), with C2 `integration`
  status words, the consent copy for the sheet and *Export instead* beside every ledger card.
- `POST …/connections/{catalog_key}/start` (`connection.create`, fresh MFA, `Idempotency-Key`):
  `{consent_version, authorized: true}` writes one consent row and answers the provider's sign-in
  URL; without the authorization 422 `authorization_required` (AC-36), an old copy 409
  `consent_version_stale`, a second live ledger 409 `ledger_already_connected`, an adapter not
  registered 409 `connector_not_available`.
- `GET /v1/portal/connections/{connection_id}` (`connection.read`): the details drawer.
- `POST …/{connection_id}/retry` (`connection.retry`, `Idempotency-Key`): one run; a second
  click while it runs returns the same run (AC-40).
- `POST …/{connection_id}/disconnect` (`connection.disconnect`: the client Owner, on an entity
  their grant covers, fresh MFA; `Idempotency-Key`): crypto-erases the secret, keeps what was
  received (AC-39).
- `POST /v1/connections/{connection_id}/reconnect-requests` (`connection.reconnect_request`): the
  firm asks the client to reconnect (AC-44); live since A-02-T23 (`routes.py`).
- `POST /v1/engagements/{engagement_id}/connection/pulls` (`ledger.pull`): an on-demand pull
  through a live ledger (AC-46), behind `connections.live_ledger`.

Every other route is behind `connections.portal_v2`. Off: 404. On: 501 `not_implemented`. No
scope or copy ever offers a write (DF-19, AC-38): scopes are read scopes only.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Path
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import CONNECTIONS_LIVE_LEDGER
from abacus.kernel._statuses import IntegrationStatus, TrialBalanceLabelStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.connections.api import check_ledger_pull, pull_ledger
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.integrations.ports import IntegrationCategory

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
CatalogKey = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{1,49}$")]

# The tile's tone, by category (POR-16 spec: olive ledger, espresso bank and HR, clay card, ochre
# sales); the screen maps it to tokens.
Tone = Literal["olive", "espresso", "clay", "ochre"]
# Why a connection needs the client (A-02 §3.11): reauth on token_expired / invalid_grant; any
# other failure is `needs_attention` with `sync_failed`.
StatusReason = Literal["token_expired", "invalid_grant", "sync_failed", "provider_unavailable"]
ConnectionActor = Literal["client", "firm"]
SyncTrigger = Literal["request_item", "on_demand", "schedule", "export"]
SyncStatus = Literal["queued", "running", "succeeded", "failed_validation", "failed"]
# What the person may do on the card; the screen shows only these controls.
CardAction = Literal["connect", "reconnect", "details", "disconnect", "retry", "export_instead"]


class ConnectionScopeOut(BaseModel):
    """A read scope as the catalogue words it ("Read ledger", "Read transactions and
    statements"). Writes are never listed (DF-19)."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    label: Annotated[str, classified("public")]


class ConsentCopyOut(BaseModel):
    """The consent sheet's copy (POR-16 b, e, i), from the catalogue (content, not code)."""

    model_config = ConfigDict(frozen=True)

    version: Annotated[int, Field(ge=1), classified("internal")]
    title: Annotated[str, classified("public")]  # "Reconnect American Express"
    will: Annotated[list[str], classified("public")]
    wont: Annotated[list[str], classified("public")]
    authorization: Annotated[str, classified("public")]  # the toggle's sentence
    continue_label: Annotated[str, classified("public")]  # "Continue to American Express"
    helper: Annotated[str | None, classified("public")] = None


class ConnectionPersonOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    kind: Annotated[ConnectionActor, classified("internal")]  # "(client)" in ADM-07 (INV-5)


class ExportInsteadOut(BaseModel):
    """*Export instead* (ADR-108): the open trial-balance request, or none ("the team will ask
    when they need one")."""

    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID | None, classified("internal")] = None
    binder_id: Annotated[UUID | None, classified("internal")] = None


class PortalConnectionCardOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    catalog_key: Annotated[str, classified("internal")]
    name: Annotated[str, classified("public")]  # "American Express"
    category: Annotated[IntegrationCategory, classified("internal")]
    icon: Annotated[str, classified("public")]  # a Lucide glyph name; never a vendor logo
    tone: Annotated[Tone, classified("internal")]
    status: Annotated[IntegrationStatus, classified("internal")]
    status_reason: Annotated[StatusReason | None, classified("internal")] = None
    connection_id: Annotated[UUID | None, classified("internal")] = None
    # Masked, e.g. "American Express ••1009": client content, rendered as text.
    display_label: Annotated[str | None, classified("confidential")] = None
    connected_by: Annotated[ConnectionPersonOut | None, classified("internal")] = None
    connected_at: Annotated[datetime | None, classified("internal")] = None
    reconnected: Annotated[bool, classified("internal")] = False  # "reconnected by …" (d)
    last_sync_at: Annotated[datetime | None, classified("internal")] = None
    last_failed_at: Annotated[datetime | None, classified("internal")] = None
    reauth_requested_at: Annotated[datetime | None, classified("internal")] = None
    # The card's detail line from the catalogue ("Bank feed · daily", "You upload payout
    # reports each month instead."); the screen adds connected-by and sync facts.
    helper: Annotated[str | None, classified("public")] = None
    scopes: Annotated[list[ConnectionScopeOut], classified("public")] = []
    consent: Annotated[ConsentCopyOut | None, classified("public")] = None
    export_instead: Annotated[ExportInsteadOut | None, classified("internal")] = None
    version: Annotated[int, Field(ge=0), classified("internal")] = 0
    allowed_actions: Annotated[list[CardAction], classified("internal")] = []


class PortalEntityOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_entity_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


class PortalConnectionsOut(BaseModel):
    """POR-16 a: the entity's cards in catalogue order."""

    model_config = ConfigDict(frozen=True)

    entity: Annotated[PortalEntityOut, classified("confidential")]
    firm_display_name: Annotated[str, classified("public")]  # "Brightwater Hale"
    items: Annotated[list[PortalConnectionCardOut], Field(max_length=50), classified("internal")]


class ConnectionStartIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consent_version: Annotated[int, Field(ge=1), classified("internal")]
    authorized: Annotated[bool, classified("internal")]
    # A-02-T16: the card being reconnected, when the entity has more than one of this system.
    connection_id: Annotated[UUID | None, classified("internal")] = None


class ConnectionStartOut(BaseModel):
    """Sign-in happens on the provider's site, never in the portal. The URL carries a
    single-use state, so it is never logged."""

    model_config = ConfigDict(frozen=True)

    consent_id: Annotated[UUID, classified("internal")]
    authorise_url: Annotated[str, classified("restricted")]
    expires_at: Annotated[datetime, classified("internal")]


class SyncRunSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    sync_run_id: Annotated[UUID, classified("internal")]
    trigger: Annotated[SyncTrigger, classified("internal")]
    status: Annotated[SyncStatus, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    finished_at: Annotated[datetime | None, classified("internal")] = None
    failure_code: Annotated[str | None, classified("internal")] = None


class ConnectionActivityOut(BaseModel):
    """One line of the connection's activity in the ADM-07 grammar (A-02-T16; INV-5):
    "Connected by Tess Moreno (client)", "Reconnected by …", "Disconnected by …"."""

    model_config = ConfigDict(frozen=True)

    action: Annotated[str, classified("internal")]
    text: Annotated[str, classified("confidential")]
    at: Annotated[datetime, classified("internal")]


class PortalConnectionDetailOut(BaseModel):
    """The details drawer: scopes, who connected it and when, the last 5 sync runs."""

    model_config = ConfigDict(frozen=True)

    card: Annotated[PortalConnectionCardOut, classified("confidential")]
    recent_syncs: Annotated[
        list[SyncRunSummaryOut], Field(max_length=5), classified("internal")
    ] = []
    activity: Annotated[
        list[ConnectionActivityOut], Field(max_length=50), classified("confidential")
    ] = []


class ConnectionDisconnectIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=0), classified("internal")]


class SyncRunRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    sync_run_id: Annotated[UUID, classified("internal")]
    status: Annotated[SyncStatus, classified("internal")]


class ReconnectRequestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    connection_id: Annotated[UUID, classified("internal")]
    requested_by: Annotated[ConnectionPersonOut, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]


class LedgerPullIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    period_end: Annotated[date, classified("confidential")]
    label: Annotated[TrialBalanceLabelStatus, classified("internal")] = (
        TrialBalanceLabelStatus.STANDARD
    )


portal_router = AbacusRouter(prefix="/v1/portal", tags=["connections"])
firm_router = AbacusRouter(prefix="/v1", tags=["connections"])


@firm_router.post(
    "/engagements/{engagement_id}/connection/pulls",
    action="ledger.pull",
    response_model=SyncRunRefOut,
    status_code=202,
    errors=(409,),
)
async def ledger_pull_route(
    engagement_id: UUID, body: LedgerPullIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SyncRunRefOut:
    """*Pull latest* (A-02-T30): a `sync_runs` row with trigger `on_demand`; 409
    `connection_needs_reauth` or `connector_not_available`. Audited `ledger.pull_requested`."""
    if not await flag_enabled(ctx.tenant, CONNECTIONS_LIVE_LEDGER):
        raise NotFound(CONNECTIONS_LIVE_LEDGER.name)
    await check_ledger_pull(ctx, engagement_id)

    async def run() -> tuple[int, dict[str, object]]:
        made = await pull_ledger(ctx, engagement_id, body.period_end, body.label.value)
        return 202, SyncRunRefOut(
            sync_run_id=made.run_id, status=cast(SyncStatus, made.status)
        ).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="ledger.pull",
        key=idempotency_key,
        body={"engagement_id": str(engagement_id), **body.model_dump(mode="json")},
        run=run,
    )
    return SyncRunRefOut.model_validate(stored.body)
