"""W1 enablement on live paths (C-02-T25; SPEC-700 F3; ADR-344 §3–§5; DEC-5817). PROTECTED (red).

ADR-344's four switches a posting needs, each a person's act with its own record, and read back by
`writes.w1_refusal` on every entry (so turning any one off stops the next entry of an in-flight
batch):

1. **The firm switch** (`write_capability.enable`, security_admin, fresh MFA): an insert-only
   `firm_write_capabilities` row. Enabling while the registry entry is `enabled: false` answers
   409 `write_capability_not_released`; disabling always succeeds.
2. **The engagement's `posting_enabled`** (`engagement_ledger_settings.update`, partner or
   manager): never for an attest client (I-POLICY-NOT-ATTEST, 409 `attest_client_posting_refused`).
3. **The client owner's write grant** (POR-16, `connection.grant_write`, fresh MFA, consent copy
   v2): an insert-only `connection_write_grants` row; the database refuses a grant for an attest
   client (0951's trigger) and the service refuses it first; a revocation always goes in.
4. **The kill switch** (C-02-T19) stays the last check.

ADM-08b's memo prefix and "Post as" label are `gl_posting_settings` (0992), versioned; its two
locked rows are code. The connection's read log gains the write rows (`access_log_writes`),
registered into `connections` so the client sees every write to its books (ADR-040).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.integrations.capabilities import write_capability
from abacus.modules.integrations.writes import W1_CAPABILITY

MFA_WINDOW: Final = timedelta(minutes=10)
CONSENT_COPY: Final = "por16.qbo.post_entries.v2"
DEFAULT_MEMO_PREFIX: Final = "Accrued"


class NotReleased(DomainConflict):
    code = "write_capability_not_released"
    message = "QuickBooks Online posting is not released for any firm yet."


class AttestRefused(DomainConflict):
    code = "attest_client_posting_refused"
    message = "Posting is never enabled for an attest client."


class MfaRequired(DomainConflict):
    code = "mfa_required"
    message = "Confirm it's you to change posting."


class VersionMoved(DomainConflict):
    code = "version_conflict"
    message = "Someone changed these settings; reload."


async def _fresh_mfa(ctx: AuthContext) -> datetime:
    at = ctx.mfa_at
    if at is None or await clock.now(ctx.tenant) - at > MFA_WINDOW:
        raise MfaRequired
    return at


# --- 1. the firm switch --------------------------------------------------------------------------


@dataclass(frozen=True)
class Switch:
    enabled: bool
    released: bool
    changed_by: UUID | None
    changed_at: datetime | None


_LATEST = text(
    "SELECT enabled, changed_by, changed_at FROM firm_write_capabilities WHERE capability_id = "
    ":cap ORDER BY changed_at DESC, id DESC LIMIT 1"
)


def released() -> bool:
    entry = write_capability(W1_CAPABILITY)
    return entry is not None and entry.shape == "W1" and entry.enabled


async def firm_switch(tenant: TenantContext) -> Switch:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_LATEST, {"cap": W1_CAPABILITY})).first()
    if row is None:
        return Switch(False, released(), None, None)
    return Switch(bool(row.enabled), released(), row.changed_by, row.changed_at)


async def set_firm_switch(ctx: AuthContext, *, enabled: bool, reason: str | None) -> Switch:
    await authorise(ctx, "write_capability.enable", Resource.firm(ctx.tenant_id))
    mfa_at = await _fresh_mfa(ctx)
    if enabled and not released():
        raise NotReleased
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO firm_write_capabilities (tenant_id, capability_id, enabled, "
                "changed_by, mfa_at, reason) VALUES (:t, :cap, :on, :u, :mfa, :r)"
            ),
            {"t": ctx.tenant_id, "cap": W1_CAPABILITY, "on": enabled, "u": ctx.user_id,
             "mfa": mfa_at, "r": reason},
        )  # fmt: skip
        tx.record(
            "write_capability.enabled" if enabled else "write_capability.disabled",
            target=Target("write_capability", ctx.tenant_id),
            after=Ref(enabled=int(enabled)),
        )
    return await firm_switch(ctx.tenant)


# --- ADM-08b settings ----------------------------------------------------------------------------


@dataclass(frozen=True)
class GlSettings:
    memo_prefix: str
    post_as: str
    version: int


async def gl_settings(ctx: AuthContext) -> GlSettings:
    from abacus.modules.identity.api import firm_name

    await authorise(ctx, "gl_posting_settings.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT memo_prefix, post_as, version FROM gl_posting_settings "
                    "WHERE provider = 'quickbooks_online'"
                )
            )
        ).first()
    if row is None:
        return GlSettings(DEFAULT_MEMO_PREFIX, await firm_name(ctx.tenant_id), 1)
    return GlSettings(str(row.memo_prefix), str(row.post_as), int(row.version))


async def update_gl_settings(
    ctx: AuthContext, *, memo_prefix: str, post_as: str, expected_version: int
) -> GlSettings:
    await authorise(ctx, "gl_posting_settings.update", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        current = await tx.session.scalar(
            text(
                "SELECT version FROM gl_posting_settings WHERE provider = 'quickbooks_online' "
                "FOR UPDATE"
            )
        )
        if current is None:
            if expected_version != 1:
                raise VersionMoved(facts={"version": 1})
            await tx.session.execute(
                text(
                    "INSERT INTO gl_posting_settings (tenant_id, memo_prefix, post_as, "
                    "updated_by) VALUES (:t, :m, :p, :u)"
                ),
                {"t": ctx.tenant_id, "m": memo_prefix.strip(), "p": post_as.strip(),
                 "u": ctx.user_id},
            )  # fmt: skip
        else:
            if int(current) != expected_version:
                raise VersionMoved(facts={"version": int(current)})
            await tx.session.execute(
                text(
                    "UPDATE gl_posting_settings SET memo_prefix = :m, post_as = :p, version = "
                    "version + 1, updated_by = :u, updated_at = clock_timestamp() WHERE provider "
                    "= 'quickbooks_online'"
                ),
                {"m": memo_prefix.strip(), "p": post_as.strip(), "u": ctx.user_id},
            )
        tx.record("gl_posting_settings.updated", target=Target("firm", ctx.tenant_id))
    return await gl_settings(ctx)


async def memo_prefix_of(tenant: TenantContext) -> str:
    """The memo prefix W1 writes carry (C-02-T13's writer reads it through `integrations.api`)."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT memo_prefix FROM gl_posting_settings WHERE provider = 'quickbooks_online'")
        )
    return DEFAULT_MEMO_PREFIX if found is None else str(found)


# --- 2. the engagement's posting switch ----------------------------------------------------------


@dataclass(frozen=True)
class EngagementLedger:
    engagement_id: UUID
    connection_id: UUID
    posting_enabled: bool
    version: int


async def set_posting_enabled(
    ctx: AuthContext,
    engagement_id: UUID,
    connection_id: UUID,
    *,
    posting_enabled: bool,
    expected_version: int | None,
) -> EngagementLedger:
    from abacus.modules.engagements.api import attest_of, engagement_resource_of

    await authorise(
        ctx, "engagement_ledger_settings.update",
        await engagement_resource_of(ctx.tenant, engagement_id),
    )  # fmt: skip
    if posting_enabled and await attest_of(ctx.tenant, engagement_id) is not False:
        raise AttestRefused  # unknown reads attest (fail closed)
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "SELECT id, version FROM connection_engagement_settings WHERE engagement_id = "
                    ":e AND connection_id = :c FOR UPDATE"
                ),
                {"e": engagement_id, "c": connection_id},
            )
        ).first()
        by = ctx.user_id if posting_enabled else None
        if row is None:
            await tx.session.execute(
                text(
                    "INSERT INTO connection_engagement_settings (tenant_id, engagement_id, "
                    "connection_id, posting_enabled, posting_enabled_by, posting_enabled_at) "
                    "VALUES (:t, :e, :c, :on, :u, CASE WHEN :on THEN clock_timestamp() END)"
                ),
                {"t": ctx.tenant_id, "e": engagement_id, "c": connection_id,
                 "on": posting_enabled, "u": by},
            )  # fmt: skip
            version = 1
        else:
            if expected_version is not None and int(row.version) != expected_version:
                raise VersionMoved(facts={"version": int(row.version)})
            await tx.session.execute(
                text(
                    "UPDATE connection_engagement_settings SET posting_enabled = :on, "
                    "posting_enabled_by = :u, posting_enabled_at = CASE WHEN :on THEN "
                    "clock_timestamp() END, version = version + 1 WHERE id = :id"
                ),
                {"on": posting_enabled, "u": by, "id": row.id},
            )
            version = int(row.version) + 1
        tx.record(
            "engagement_ledger_settings.updated",
            target=Target("engagement", engagement_id),
            after=Ref(posting_enabled=int(posting_enabled)),
            scope=Scope(engagement_id=engagement_id),
        )
    return EngagementLedger(engagement_id, connection_id, posting_enabled, version)


# --- 3. the client owner's write grant (POR-16) --------------------------------------------------


@dataclass(frozen=True)
class Grant:
    connection_id: UUID
    event: str
    at: datetime
    consent_copy_version: str


async def _grant(ctx: AuthContext, connection_id: UUID, *, event: str, consent: str) -> Grant:
    from abacus.modules.connections.api import authorised_engagement, entity_of_connection
    from abacus.modules.organisations.api import attest_client_of, client_of_entity

    action = "connection.grant_write" if event == "granted" else "connection.revoke_write"
    entity_id = await entity_of_connection(ctx, connection_id)
    await authorised_engagement(ctx, entity_id, action)
    mfa_at = await _fresh_mfa(ctx)
    if event == "granted":
        if consent != CONSENT_COPY:
            raise DomainConflict(facts={"reason": "consent_copy_outdated"})
        client = await client_of_entity(ctx.tenant, entity_id)
        if client is None or await attest_client_of(ctx.tenant, client) is not False:
            raise AttestRefused
    async with uow(ctx.tenant) as tx:
        at = cast(
            datetime,
            await tx.session.scalar(
                text(
                    "INSERT INTO connection_write_grants (tenant_id, connection_id, "
                    "client_entity_id, capability_id, consent_copy_version, "
                    "granted_by_client_user_id, mfa_at, event, actor_id) VALUES (:t, :c, :ce, "
                    ":cap, :v, :u, :mfa, :ev, :a) RETURNING at"
                ),
                {"t": ctx.tenant_id, "c": connection_id, "ce": entity_id, "cap": W1_CAPABILITY,
                 "v": consent, "u": ctx.user_id, "mfa": mfa_at, "ev": event,
                 "a": str(ctx.user_id)},
            ),
        )  # fmt: skip
        tx.record(
            f"connection.write_{event}",
            target=Target("connection", connection_id),
            after=Ref(capability=0 if event == "revoked" else 1),
        )
    return Grant(connection_id, event, at, consent)


async def grant_write(ctx: AuthContext, connection_id: UUID, consent: str) -> Grant:
    return await _grant(ctx, connection_id, event="granted", consent=consent)


async def revoke_write(ctx: AuthContext, connection_id: UUID) -> Grant:
    """Always goes in; the next entry of any in-flight batch is `write_grant_missing`."""
    async with tenant_session(ctx.tenant) as session:
        consent = await session.scalar(
            text(
                "SELECT consent_copy_version FROM connection_write_grants WHERE connection_id = "
                ":c ORDER BY at DESC, id DESC LIMIT 1"
            ),
            {"c": connection_id},
        )
    if consent is None:
        raise NotFound("connection_write_grant")
    return await _grant(ctx, connection_id, event="revoked", consent=str(consent))


# --- the client-visible read log, with the writes ------------------------------------------------


@dataclass(frozen=True)
class WriteLogRow:
    id: UUID
    operation: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    actor_user_id: UUID


async def access_log_writes(tenant: TenantContext, client_entity_id: UUID) -> list[WriteLogRow]:
    """Every W1 write to the entity's books, newest first (ADR-040's client-visible log)."""
    async with tenant_session(tenant) as session:
        rows = list(
            (
                await session.execute(
                    text(
                        "SELECT id, operation, status, coalesce(started_at, created_at) AS s, "
                        "finished_at, actor_user_id FROM ledger_write_operations WHERE "
                        "client_entity_id = :ce ORDER BY created_at DESC, id LIMIT 200"
                    ),
                    {"ce": client_entity_id},
                )
            ).all()
        )
    return [
        WriteLogRow(r.id, str(r.operation), str(r.status), r.s, r.finished_at, r.actor_user_id)
        for r in rows
    ]


async def _write_log_entries(tenant: TenantContext, client_entity_id: UUID) -> list[object]:
    from abacus.modules.connections.api import LogEntry

    return [
        LogEntry(
            r.id, f"write:{r.operation}", "", "", r.status, r.started_at, r.finished_at,
            str(r.actor_user_id),
        )
        for r in await access_log_writes(tenant, client_entity_id)
    ]


def register() -> None:
    """Hand the connection log its writes reader (called from `integrations.api`)."""
    from abacus.modules.connections.api import register_access_log_writes

    register_access_log_writes(_write_log_entries)  # type: ignore[arg-type] -- LogEntry rows


__all__ = [
    "CONSENT_COPY",
    "AttestRefused",
    "EngagementLedger",
    "GlSettings",
    "Grant",
    "MfaRequired",
    "NotReleased",
    "Switch",
    "VersionMoved",
    "WriteLogRow",
    "access_log_writes",
    "firm_switch",
    "gl_settings",
    "grant_write",
    "memo_prefix_of",
    "released",
    "revoke_write",
    "set_firm_switch",
    "set_posting_enabled",
    "update_gl_settings",
]
