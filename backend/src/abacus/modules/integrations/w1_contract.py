"""C20 v2.1 W1 stub (C-02-T06; SPEC-700 AC-3, AC-23, AC-24; ADR-344;
`docs/contracts/c20-integrations.md` v2.1). Screen families CLS-11 (Ledger sync console), POR-16
(the client owner's write grant) and ADM-08b (the firm switch and GL-posting settings).

Firm routes answer, in order: a client principal 404; the `closes.gl_console` flag off 404; a
human-only route refuses an agent, the platform or a support session 403 (INV-1); then 501 until
its build task (C-02-T20 console, T25 switches, T27 grants). Portal routes answer 404 to a firm
principal, then the same flag and 501. The connection itself stays read-only (CONN-001): a grant
is a consent record, and W1 stays `enabled: false`, so the firm switch will answer 409
`write_capability_not_released` once built.

Classification (ADR-031): client and user names are `confidential`; ids, states, counts and
dates are `internal`. Seed examples are Copperleaf's console at 9:24 AM, Sep 14, 2026.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from abacus.kernel._flags import CLOSES_GL_CONSOLE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
Internal = classified("internal")
Confidential = classified("confidential")

HealthWord = Literal["connected", "needs_attention", "needs_reauth", "disconnected"]
BatchStatus = Literal["proposed", "posting", "posted", "failed_post"]
ActivityKind = Literal["sync", "sync_failed", "post", "closing_date", "write_grant", "reauth"]
GrantEvent = Literal["granted", "revoked"]
ConsentCopy = Literal["por16.qbo.post_entries.v2"]


def _cfg(example: dict[str, object] | None = None) -> ConfigDict:
    if example is None:
        return ConfigDict(frozen=True, extra="forbid")
    extra = cast(JsonDict, {"examples": [example]})
    return ConfigDict(frozen=True, extra="forbid", json_schema_extra=extra)


# --- CLS-11 console ----------------------------------------------------------------------------


class W1ConsoleTilesOut(BaseModel):
    """CLS-11a tiles: 7 Posted (1 resolved Aug 11 under Failed post 0), 1 Proposed, Jul 31."""

    model_config = _cfg(
        {"posted": 7, "proposed": 1, "failed_post": 0, "resolved_failures": 1,
         "closing_date": "2026-07-31"}
    )  # fmt: skip

    posted: Annotated[int, Field(ge=0), Internal]
    proposed: Annotated[int, Field(ge=0), Internal]
    failed_post: Annotated[int, Field(ge=0), Internal]
    resolved_failures: Annotated[int, Field(ge=0), Internal]
    closing_date: Annotated[date | None, Internal] = None


class W1ConnectionPaneOut(BaseModel):
    """Authorized by Tess Moreno (client portal) · Mode "Client-authorized: read ledger, post
    approved entries" · Last sync 9:02 AM · 1,214 transactions read (Aug 1-31) · 0 errors."""

    model_config = _cfg()

    connection_id: Annotated[UUID, Internal]
    health: Annotated[HealthWord, Internal]
    authorized_by: Annotated[str | None, Field(max_length=200), Confidential] = None
    write_granted: Annotated[bool, Internal]
    last_sync_at: Annotated[datetime | None, Internal] = None
    last_sync_transactions: Annotated[int | None, Field(ge=0), Internal] = None
    last_sync_errors: Annotated[int | None, Field(ge=0), Internal] = None
    next_sync_at: Annotated[datetime | None, Internal] = None
    closing_date: Annotated[date | None, Internal] = None
    closing_date_set_by: Annotated[str | None, Field(max_length=200), Confidential] = None
    closing_date_set_at: Annotated[datetime | None, Internal] = None
    retry_at: Annotated[datetime | None, Internal] = None
    dependents: Annotated[list[str], Internal] = []


class W1LedgerConsoleOut(BaseModel):
    model_config = _cfg()

    client_entity_id: Annotated[UUID, Internal]
    client_entity_name: Annotated[str, Field(max_length=200), Confidential]
    ledger_label: Annotated[str, Field(max_length=60), Internal]
    tiles: Annotated[W1ConsoleTilesOut, Internal]
    connection: Annotated[W1ConnectionPaneOut | None, Internal] = None
    posting_paused_by: Annotated[str | None, Field(max_length=200), Confidential] = None


class W1PostingLogRowOut(BaseModel):
    """2026-07-A · Posted · QBO 47901-47906 · 1 failure resolved."""

    model_config = _cfg(
        {"batch_id": "00000000-0000-4000-8000-0000000007a0", "batch_code": "2026-07-A",
         "period": "2026-07", "status": "posted", "entry_count": 6, "approved_count": 6,
         "first_external_ref": "47901", "last_external_ref": "47906", "resolved_failures": 1}
    )  # fmt: skip

    batch_id: Annotated[UUID, Internal]
    batch_code: Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[A-Z]$"), Internal]
    period: Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"), Internal]
    status: Annotated[BatchStatus, Internal]
    entry_count: Annotated[int, Field(ge=0), Internal]
    approved_count: Annotated[int, Field(ge=0), Internal]
    first_external_ref: Annotated[str | None, Internal] = None
    last_external_ref: Annotated[str | None, Internal] = None
    resolved_failures: Annotated[int, Field(ge=0), Internal] = 0


class W1PostingLogOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[W1PostingLogRowOut], Internal]
    total: Annotated[int, Field(ge=0), Internal]


class W1ActivityOut(BaseModel):
    """A Sync events row (CLS-11a2), its label resolved at read time."""

    model_config = _cfg()

    at: Annotated[datetime, Internal]
    kind: Annotated[ActivityKind, Internal]
    batch_code: Annotated[str | None, Internal] = None
    count: Annotated[int | None, Field(ge=0), Internal] = None
    actor_name: Annotated[str | None, Field(max_length=200), Confidential] = None
    provider_code: Annotated[str | None, Field(max_length=64), Internal] = None


class W1ActivityListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[W1ActivityOut], Internal]
    total: Annotated[int, Field(ge=0), Internal]


# --- switches and settings (ADM-08b, the engagement) -------------------------------------------


class W1CapabilitySwitchIn(BaseModel):
    model_config = _cfg()

    reason: Annotated[str | None, Field(max_length=500), Confidential] = None


class W1CapabilitySwitchOut(BaseModel):
    """ "Enabled QuickBooks Online posting · Felix Andersen" (ADM-07)."""

    model_config = _cfg()

    capability_id: Annotated[Literal["ledger_post_journal_entries"], Internal]
    enabled: Annotated[bool, Internal]
    released: Annotated[bool, Internal]
    changed_by: Annotated[str | None, Field(max_length=200), Confidential] = None
    changed_at: Annotated[datetime | None, Internal] = None


class W1GlPostingSettingsOut(BaseModel):
    """ADM-08b: two locked rows ("Post only human-approved batches", "Attest posting disabled"),
    the memo prefix and the "Post as" label."""

    model_config = _cfg({"memo_prefix": "Accrued", "post_as": "Brightwater Hale LLP",
                         "human_approved_only": True, "attest_posting_disabled": True,
                         "version": 1})  # fmt: skip

    memo_prefix: Annotated[str, Field(max_length=40), Confidential]
    post_as: Annotated[str, Field(max_length=120), Confidential]
    human_approved_only: Annotated[Literal[True], Internal] = True
    attest_posting_disabled: Annotated[Literal[True], Internal] = True
    version: Annotated[int, Field(ge=1), Internal]


class W1GlPostingSettingsIn(BaseModel):
    model_config = _cfg()

    memo_prefix: Annotated[str, Field(min_length=1, max_length=40), Confidential]
    post_as: Annotated[str, Field(min_length=1, max_length=120), Confidential]
    expected_version: Annotated[int, Field(ge=1), Internal]


class W1EngagementLedgerSettingsIn(BaseModel):
    model_config = _cfg()

    connection_id: Annotated[UUID, Internal]
    posting_enabled: Annotated[bool, Internal]
    expected_version: Annotated[int | None, Field(ge=1), Internal] = None


class W1EngagementLedgerSettingsOut(BaseModel):
    model_config = _cfg()

    engagement_id: Annotated[UUID, Internal]
    connection_id: Annotated[UUID, Internal]
    posting_enabled: Annotated[bool, Internal]
    version: Annotated[int, Field(ge=1), Internal]


# --- POR-16 write grant (portal) ---------------------------------------------------------------


class W1WriteGrantIn(BaseModel):
    """The QBO consent sheet's "will" list includes "post journal entries your accountant
    approves, and set the closing date after posting"; "won't" includes "change or delete
    existing transactions" (consent copy v2, a catalogue row)."""

    model_config = _cfg()

    capability_id: Annotated[Literal["ledger_post_journal_entries"], Internal]
    consent_copy_version: Annotated[ConsentCopy, Internal]


class W1WriteGrantOut(BaseModel):
    model_config = _cfg()

    connection_id: Annotated[UUID, Internal]
    event: Annotated[GrantEvent, Internal]
    at: Annotated[datetime, Internal]
    consent_copy_version: Annotated[ConsentCopy, Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

w1_router = AbacusRouter(prefix="/v1", tags=["connections"])
w1_portal_router = AbacusRouter(prefix="/v1/portal", tags=["connections"])
_E = "/client-entities/{client_entity_id}"


def _log_row(r: object) -> W1PostingLogRowOut:
    from abacus.modules.integrations.ledger_console import LogRow

    row = cast(LogRow, r)
    return W1PostingLogRowOut(
        batch_id=row.batch_id,
        batch_code=row.batch_code,
        period=row.period,
        status=cast(BatchStatus, row.status),
        entry_count=row.entry_count,
        approved_count=row.approved_count,
        first_external_ref=row.first_external_ref,
        last_external_ref=row.last_external_ref,
        resolved_failures=row.resolved_failures,
    )


async def _console_on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, CLOSES_GL_CONSOLE):
        raise NotFound(CLOSES_GL_CONSOLE.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _console_on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def _portal_on(ctx: AuthContext, action: str) -> None:
    """A firm principal never reaches a portal route; a client owner's own act only."""
    if not ctx.client or not await flag_enabled(ctx.tenant, CLOSES_GL_CONSOLE):
        raise NotFound(CLOSES_GL_CONSOLE.name)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


@w1_router.get(
    f"{_E}/ledger-console",
    action="ledger_connection.read",
    response_model=W1LedgerConsoleOut,
    errors=(501,),
)
async def ledger_console_route(client_entity_id: UUID, ctx: Ctx) -> W1LedgerConsoleOut:
    """CLS-11 subbar, tiles and connection pane; a walled entity answers 404 (C-02-T20)."""
    from abacus.modules.integrations import ledger_console as lc

    await _console_on(ctx)
    found = await lc.ledger_console(ctx, client_entity_id)
    return W1LedgerConsoleOut(
        client_entity_id=found.client_entity_id,
        client_entity_name=found.client_entity_name,
        ledger_label=lc.LEDGER_LABEL,
        tiles=W1ConsoleTilesOut.model_validate(found.tiles),
        connection=None
        if found.connection is None
        else W1ConnectionPaneOut.model_validate(found.connection),
    )


@w1_router.get(
    f"{_E}/posting-batches",
    action="ledger_connection.read",
    response_model=W1PostingLogOut,
    errors=(501,),
)
async def posting_log_route(
    client_entity_id: UUID,
    ctx: Ctx,
    period: str | None = None,
    status: BatchStatus | None = None,
) -> W1PostingLogOut:
    """The posting log, newest first (CLS-11a)."""
    from abacus.modules.integrations import ledger_console as lc

    await _console_on(ctx)
    rows = await lc.posting_log(ctx, client_entity_id, period=period, status=status)
    return W1PostingLogOut(items=[_log_row(r) for r in rows], total=len(rows))


@w1_router.get(
    f"{_E}/posting-batches.csv",
    action="ledger_connection.export",
    response_model=bytes,
    errors=(501,),
)
async def posting_log_csv_route(client_entity_id: UUID, ctx: Ctx) -> bytes:
    """A deterministic CSV of the posting log (audited)."""
    from abacus.kernel.uow import Target, uow
    from abacus.modules.integrations import ledger_console as lc

    await _human(ctx, "ledger_connection.export")
    rows = await lc.posting_log(ctx, client_entity_id, period=None, status=None)
    async with uow(ctx.tenant) as tx:
        tx.record("ledger_connection.exported", target=Target("client_entity", client_entity_id))
    return lc.posting_log_csv(rows)


@w1_router.get(
    f"{_E}/ledger-activity",
    action="ledger_connection.read",
    response_model=W1ActivityListOut,
    errors=(501,),
)
async def ledger_activity_route(
    client_entity_id: UUID, ctx: Ctx, kind: ActivityKind | None = None
) -> W1ActivityListOut:
    """Sync events (CLS-11a2), newest first."""
    from abacus.modules.integrations import ledger_console as lc

    await _console_on(ctx)
    found = await lc.ledger_activity(ctx, client_entity_id, kind=kind)
    return W1ActivityListOut(
        items=[
            W1ActivityOut(
                at=a.at,
                kind=cast(ActivityKind, a.kind),
                batch_code=a.batch_code,
                count=a.count,
                actor_name=name,
            )
            for a, name in found
        ],
        total=len(found),
    )


@w1_router.get(
    "/posting-batches/{batch_id}",
    action="ledger_connection.read",
    response_model=W1PostingLogRowOut,
    errors=(501,),
)
async def posting_batch_route(batch_id: UUID, ctx: Ctx) -> W1PostingLogRowOut:
    """The O2 batch drawer (CLS-11b2); entries with QBO ids come from C8's batch read."""
    await _console_on(ctx)
    raise NotImplementedYet


@w1_router.post(
    "/write-capabilities/ledger_post_journal_entries:enable",
    action="write_capability.enable",
    response_model=W1CapabilitySwitchOut,
    errors=(409, 501),
)
async def enable_capability_route(body: W1CapabilitySwitchIn, ctx: Ctx) -> W1CapabilitySwitchOut:
    """The firm switch; 409 `write_capability_not_released` while the registry is off."""
    await _human(ctx, "write_capability.enable")
    raise NotImplementedYet


@w1_router.post(
    "/write-capabilities/ledger_post_journal_entries:disable",
    action="write_capability.enable",
    response_model=W1CapabilitySwitchOut,
    errors=(409, 501),
)
async def disable_capability_route(body: W1CapabilitySwitchIn, ctx: Ctx) -> W1CapabilitySwitchOut:
    """Turning the switch off always succeeds and refuses every in-flight batch's next entry."""
    await _human(ctx, "write_capability.enable")
    raise NotImplementedYet


@w1_router.get(
    "/integrations/quickbooks_online/settings/gl-posting",
    action="gl_posting_settings.read",
    response_model=W1GlPostingSettingsOut,
    errors=(501,),
)
async def gl_posting_settings_route(ctx: Ctx) -> W1GlPostingSettingsOut:
    await _console_on(ctx)
    raise NotImplementedYet


@w1_router.put(
    "/integrations/quickbooks_online/settings/gl-posting",
    action="gl_posting_settings.update",
    response_model=W1GlPostingSettingsOut,
    errors=(409, 501),
)
async def gl_posting_settings_update_route(
    body: W1GlPostingSettingsIn, ctx: Ctx
) -> W1GlPostingSettingsOut:
    await _human(ctx, "gl_posting_settings.update")
    raise NotImplementedYet


@w1_router.put(
    "/engagements/{engagement_id}/ledger-settings",
    action="engagement_ledger_settings.update",
    response_model=W1EngagementLedgerSettingsOut,
    errors=(409, 501),
)
async def engagement_ledger_settings_route(
    engagement_id: UUID, body: W1EngagementLedgerSettingsIn, ctx: Ctx
) -> W1EngagementLedgerSettingsOut:
    """The engagement's `posting_enabled` (partner or manager)."""
    await _human(ctx, "engagement_ledger_settings.update")
    raise NotImplementedYet


@w1_portal_router.post(
    "/connections/{connection_id}/write-grants",
    action="connection.grant_write",
    response_model=W1WriteGrantOut,
    status_code=201,
    errors=(409, 501),
)
async def grant_write_route(
    connection_id: UUID, body: W1WriteGrantIn, ctx: Ctx
) -> W1WriteGrantOut:
    """The client owner grants posting with a fresh MFA; refused for an attest client."""
    await _portal_on(ctx, "connection.grant_write")
    raise NotImplementedYet


@w1_portal_router.delete(
    "/connections/{connection_id}/write-grants/current",
    action="connection.revoke_write",
    response_model=W1WriteGrantOut,
    errors=(501,),
)
async def revoke_write_route(connection_id: UUID, ctx: Ctx) -> W1WriteGrantOut:
    """The client owner revokes; the next entry of any in-flight batch is `write_grant_missing`."""
    await _portal_on(ctx, "connection.revoke_write")
    raise NotImplementedYet
