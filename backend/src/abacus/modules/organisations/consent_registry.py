"""C19 consents, the read half and the lifecycle (T-01-T16; T-01 §3.1, §4.4; ADM-05, CLI-05;
SPEC-501 AC-39 to AC-44).

- **Registry** (`GET /v1/consents`): the P-36 list envelope over the consents the reader may see
  (`visible_clients` on the consent's client: walled clients are absent and never counted), with
  the ADM-05 tiles as `counts` (Signed, Expiring, Requested, Expired, Declined, Revoked; Signed
  excludes Expiring, so the tiles add to the total), filters by status (`expiring` is derived:
  signed and within 30 days of expiry), purpose, tax year, client and offshore, and the
  needs-attention order: requested, expiring, expired, declined, revoked, signed, superseded,
  then client name. An offshore member sees only clients whose every taxpayer entity holds an
  `offshore_disclosure` consent in force (I-OFFSHORE).
- **Summary** for ADM-04 D, CLI-02 and the BND-01 tag: counts only, no client names.
- **Detail**: the consent, its signers (method, time), its one document (the signed text's
  SHA-256) and the agent reads since signature (`tri.tool_read` access events naming it).
- **Export** (`consent.export`, fresh MFA by the matrix): ConsentExportWorkflow builds the CSV
  (formula-neutralised cells) into a sealed transient bundle in the exports store and audits
  `consent.exported`; the 202 answers the export id, `queued`.
- **Sweep** (ConsentLifecycleSweep, daily 6:00 AM CT, business time): a signed consent within 30
  days of expiry raises `consent.expiring` once (its `expiring` event marks it); one past its
  expiry becomes `expired` with `consent.expired` and `access.changed`; one signed under
  material terms the register no longer holds is flagged once (`reconsent_required` event).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import (
    ColumnElement,
    and_,
    case,
    column,
    func,
    select,
    table,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from abacus.kernel import provider_terms
from abacus.kernel.access import run_reads
from abacus.kernel.clock import now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.export_bundles import put_bundle
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AccessChanged,
    AuthContext,
    Resource,
    authorise,
    is_offshore,
    visible_clients,
)
from abacus.modules.organisations.events import ConsentExpired, ConsentExpiring

READ: Final = "consent.read"
EXPORT: Final = "consent.export"
EXPIRING_WITHIN: Final = timedelta(days=30)
_ROUTE: Final = "bedrock"
# Needs attention first (ADM-05a).
_ORDER: Final = ("requested", "expiring", "expired", "declined", "revoked", "signed", "superseded")
TILES: Final = ("signed", "expiring", "requested", "expired", "declined", "revoked")

_consents = table(
    "consents",
    column("id", PG_UUID(as_uuid=True)),
    column("tenant_id", PG_UUID(as_uuid=True)),
    column("client_id", PG_UUID(as_uuid=True)),
    column("client_entity_id", PG_UUID(as_uuid=True)),
    column("purpose"),
    column("tax_years"),
    column("status"),
    column("expires_at"),
    column("signed_at"),
    column("provider_terms_version"),
    column("created_by", PG_UUID(as_uuid=True)),
)
_clients = table("clients", column("id", PG_UUID(as_uuid=True)), column("name"))


def display_status(at: datetime) -> ColumnElement[str]:
    """`expiring` is derived, never stored: signed and within 30 days of expiry."""
    return case(
        (
            and_(
                _consents.c.status == "signed",
                _consents.c.expires_at.is_not(None),
                _consents.c.expires_at <= at + EXPIRING_WITHIN,
            ),
            "expiring",
        ),
        else_=_consents.c.status,
    )


async def _scope(ctx: AuthContext) -> ColumnElement[bool]:
    """Walls (no hidden count) and, for an offshore member, I-OFFSHORE."""
    if ctx.client:
        raise NotFound("consent")
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    clause = await visible_clients(ctx, READ, _consents.c.client_id)
    if await is_offshore(ctx.tenant, ctx.user_id):
        # consent_gate imports the C19 contract, which imports this module: read it late.
        from abacus.modules.organisations.consent_gate import offshore_column

        clause = and_(clause, offshore_column(_consents.c.client_id, "offshore_disclosure"))
    return clause


@dataclass(frozen=True)
class RegistryPage:
    ids: list[UUID]
    total: int
    counts: dict[str, int]
    next_cursor: str | None


def _filters(
    at: datetime,
    status: str | None,
    purpose: str | None,
    tax_year: int | None,
    client_id: UUID | None,
    offshore: bool | None,
) -> ColumnElement[bool]:
    parts: list[ColumnElement[bool]] = [true()]
    if status is not None:
        parts.append(display_status(at) == status)
    if purpose is not None:
        parts.append(_consents.c.purpose == purpose)
    if tax_year is not None:
        parts.append(_consents.c.tax_years.any(tax_year))  # ARRAY column
    if client_id is not None:
        parts.append(_consents.c.client_id == client_id)
    if offshore is not None:
        parts.append(
            (_consents.c.purpose == "offshore_disclosure")
            if offshore
            else (_consents.c.purpose != "offshore_disclosure")
        )
    return and_(*parts)


async def registry(
    ctx: AuthContext,
    *,
    status: str | None = None,
    purpose: str | None = None,
    tax_year: int | None = None,
    client_id: UUID | None = None,
    offshore: bool | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> RegistryPage:
    """ADM-05: the visible consents, needs attention first, with the tiles."""
    scope = await _scope(ctx)
    at = await now(ctx.tenant)
    shown = display_status(at)
    rank = case(*((shown == s, i) for i, s in enumerate(_ORDER)), else_=len(_ORDER))
    where = and_(scope, _filters(at, status, purpose, tax_year, client_id, offshore))
    offset = int(cursor) if cursor and cursor.isdigit() else 0
    async with tenant_session(ctx.tenant) as session:
        ids = list(
            (
                await session.execute(
                    select(_consents.c.id)
                    .select_from(_consents.join(_clients, _clients.c.id == _consents.c.client_id))
                    .where(where)
                    .order_by(rank, _clients.c.name, _consents.c.purpose, _consents.c.id)
                    .offset(offset)
                    .limit(limit + 1)
                )
            ).scalars()
        )
        tile_rows = (
            await session.execute(
                select(shown.label("s"), func.count())
                .where(and_(scope, _filters(at, None, purpose, tax_year, client_id, offshore)))
                .group_by(shown)
            )
        ).all()
    counts = {t: 0 for t in TILES}
    for s, n in tile_rows:
        if s in counts:
            counts[s] = int(n)
    total = sum(int(n) for _, n in tile_rows if status is None or _ == status)
    more = len(ids) > limit
    return RegistryPage(ids[:limit], total, counts, str(offset + limit) if more else None)


async def summary(ctx: AuthContext) -> dict[str, int]:
    """ADM-04 D (with the clients the agents are blocked for), CLI-02 b, the BND-01 tag: counts
    only (no names)."""
    scope = await _scope(ctx)
    at = await now(ctx.tenant)
    shown = display_status(at)
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                select(shown, _consents.c.purpose, func.count())
                .where(scope)
                .group_by(shown, _consents.c.purpose)
            )
        ).all()
        # T-01-T51 (ADM-04 D): clients in scope whose §7216 consent to use is not in force, so
        # the agents cannot read their return information (a count, no names).
        in_force = func.bool_or(
            and_(_consents.c.purpose == "use", shown.in_(("signed", "expiring")))
        )
        per_client = (
            select(_consents.c.client_id)
            .where(scope)
            .group_by(_consents.c.client_id)
            .having(func.coalesce(in_force, False).is_(False))
            .subquery()
        )
        blocked = int(
            (await session.execute(select(func.count()).select_from(per_client))).scalar_one()
        )
    out = {t: 0 for t in (*TILES, "total", "ai_use_signed", "offshore")}
    out["blocked_clients"] = blocked
    for s, purpose, n in rows:
        n = int(n)
        out["total"] += n
        if s in out:
            out[s] += n
        if purpose in ("use", "ai_disclosure") and s in ("signed", "expiring"):
            out["ai_use_signed"] += n
        if purpose == "offshore_disclosure":
            out["offshore"] += n
    return out


async def visible_ids(ctx: AuthContext, ids: Sequence[UUID]) -> list[UUID]:
    """The ids among `ids` the reader may see (a walled consent is 404, no count)."""
    scope = await _scope(ctx)
    async with tenant_session(ctx.tenant) as session:
        return list(
            (
                await session.execute(
                    select(_consents.c.id).where(scope, _consents.c.id.in_(list(ids)))
                )
            ).scalars()
        )


async def entity_ids(ctx: AuthContext, entity_id: UUID) -> list[UUID]:
    """CLI-05: one taxpayer's consents, newest first, under the same scope."""
    scope = await _scope(ctx)
    async with tenant_session(ctx.tenant) as session:
        return list(
            (
                await session.execute(
                    select(_consents.c.id)
                    .where(scope, _consents.c.client_entity_id == entity_id)
                    .order_by(_consents.c.signed_at.desc().nulls_first(), _consents.c.id)
                )
            ).scalars()
        )


_DOC = text("SELECT purpose, text_sha256, signed_at FROM consents WHERE id = :id")


@dataclass(frozen=True)
class Detail:
    document: tuple[str, str]  # purpose, SHA-256 hex
    agent_reads: list[tuple[UUID, datetime, UUID | None]]


async def detail(ctx: AuthContext, consent_id: UUID) -> Detail:
    """CLI-05d, the ADM-05 drawer: the document's hash and agent reads since signature."""
    if not await visible_ids(ctx, [consent_id]):
        raise NotFound("consent")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_DOC, {"id": consent_id})).one()
        reads: list[tuple[UUID, datetime, UUID | None]] = []
        if row.signed_at is not None:
            reads = [
                (r.run_id, r.occurred_at, r.on_behalf_of_user_id)
                for r in await run_reads(
                    session, "tri.tool_read", "consent", consent_id, row.signed_at
                )
            ]
    return Detail((row.purpose, bytes(row.text_sha256).hex()), reads)


# --- export --------------------------------------------------------------------------------------

_CSV_ROWS = text(
    "SELECT cl.name AS client, e.name AS taxpayer, c.purpose, c.tax_years, c.status, "
    "c.requested_at, c.signed_at, c.expires_at, c.declined_at, c.revoked_at, c.source "
    "FROM consents c JOIN clients cl ON cl.id = c.client_id "
    "JOIN client_entities e ON e.id = c.client_entity_id WHERE c.id = ANY(:ids) "
    "ORDER BY cl.name, e.name, c.purpose"
)
_HEADER: Final = (
    "Client",
    "Taxpayer",
    "Purpose",
    "Tax years",
    "Status",
    "Requested",
    "Signed",
    "Expires",
    "Declined",
    "Revoked",
    "Source",
)


def _cell(value: object) -> str:
    """Client content is hostile (ADR-052): a cell never starts a formula."""
    text_value = "" if value is None else str(value)
    return f"'{text_value}" if text_value[:1] in ("=", "+", "-", "@", "\t", "\r") else text_value


def consent_csv(rows: Sequence[Sequence[object]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(_HEADER)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return out.getvalue().encode()


async def start_export(ctx: AuthContext) -> UUID:
    """`consent.export` (fresh MFA by the matrix): audit now, build in the workflow."""
    if ctx.client:
        raise NotFound("consent")
    await authorise(ctx, EXPORT, Resource.firm(ctx.tenant_id))
    ids = (await registry(ctx, limit=100_000)).ids
    export_id = uuid4()
    async with uow(ctx.tenant) as tx:
        tx.record(
            "consent.exported",
            target=Target("consent_export", export_id),
            after=Ref(rows=len(ids)),
        )
    from abacus.modules.organisations.activities import start_consent_export
    from abacus.modules.organisations.workflows import ConsentExportInput

    await start_consent_export(
        ConsentExportInput(str(ctx.tenant_id), str(export_id), [str(i) for i in ids])
    )
    return export_id


async def build_export(tenant_id: UUID, export_id: UUID, ids: Sequence[UUID]) -> int:
    """The workflow's activity: the CSV into a sealed transient bundle; its segment count."""
    tenant = TenantContext(tenant_id, "system", f"consents:export:{export_id}")
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_CSV_ROWS, {"ids": list(ids)})).all()
    body = consent_csv(
        [
            (
                r.client,
                r.taxpayer,
                r.purpose,
                " ".join(str(y) for y in r.tax_years),
                r.status,
                r.requested_at,
                r.signed_at,
                r.expires_at,
                r.declined_at,
                r.revoked_at,
                r.source,
            )
            for r in rows
        ]
    )
    return await put_bundle("consent-register", tenant_id, export_id, io.BytesIO(body))


# --- the lifecycle sweep -------------------------------------------------------------------------

_DUE = text(
    "SELECT c.id, c.client_id, c.created_by, c.expires_at, c.provider_terms_version, "
    "EXISTS (SELECT 1 FROM consent_events v WHERE v.consent_id = c.id "
    "        AND v.kind = 'expiring') AS warned, "
    "EXISTS (SELECT 1 FROM consent_events v WHERE v.consent_id = c.id "
    "        AND v.kind = 'reconsent_required') AS flagged "
    "FROM consents c WHERE c.status = 'signed' AND c.revoked_at IS NULL"
)
_EXPIRE = text(
    "UPDATE consents SET status = 'expired', row_version = row_version + 1 "
    "WHERE id = :id AND status = 'signed'"
)
_EVENT = text(
    "INSERT INTO consent_events (tenant_id, consent_id, kind, actor_kind, actor_id, facts) "
    "VALUES (:tenant, :consent, :kind, 'system', 'consent_sweep', CAST(:facts AS jsonb))"
)
_PORTAL_SIGNERS = text(
    "SELECT DISTINCT ct.user_id FROM consent_signers s JOIN contacts ct ON ct.id = s.contact_id "
    "WHERE s.consent_id = :id AND ct.user_id IS NOT NULL"
)


@dataclass(frozen=True)
class SweepResult:
    expiring: int
    expired: int
    reconsent: int


async def sweep(tenant_id: UUID) -> SweepResult:
    """One firm's pass (idempotent on business time): warn, expire, flag register drift."""
    tenant = TenantContext(tenant_id, "system", "consent_sweep")
    at = await now(tenant)
    entry = provider_terms.covering(_ROUTE, at.date())
    material = entry.material if entry is not None else None
    expiring = expired = reconsent = 0
    async with uow(tenant) as tx:
        rows = (await tx.session.execute(_DUE)).all()
        for row in rows:
            if row.expires_at is not None and row.expires_at <= at:
                await tx.session.execute(_EXPIRE, {"id": row.id})
                await tx.session.execute(
                    _EVENT,
                    {"tenant": tenant_id, "consent": row.id, "kind": "expired", "facts": "{}"},
                )
                tx.record("consent.expired", target=Target("consent", row.id))
                tx.emit(ConsentExpired(consent_id=row.id, client_id=row.client_id))
                for user_id in (
                    await tx.session.execute(_PORTAL_SIGNERS, {"id": row.id})
                ).scalars():
                    tx.emit(AccessChanged(user_id=user_id))
                expired += 1
                continue
            if (
                row.expires_at is not None
                and row.expires_at <= at + EXPIRING_WITHIN
                and not row.warned
            ):
                await tx.session.execute(
                    _EVENT,
                    {
                        "tenant": tenant_id,
                        "consent": row.id,
                        "kind": "expiring",
                        "facts": json.dumps({"sweep": "expiring"}),
                    },
                )
                tx.emit(
                    ConsentExpiring(
                        consent_id=row.id, client_id=row.client_id, requested_by=row.created_by
                    )
                )
                expiring += 1
            if (
                material is not None
                and row.provider_terms_version not in (material, "recorded")
                and not row.flagged
            ):
                await tx.session.execute(
                    _EVENT,
                    {
                        "tenant": tenant_id,
                        "consent": row.id,
                        "kind": "reconsent_required",
                        "facts": json.dumps({"sweep": "reconsent_required"}),
                    },
                )
                tx.record("consent.reconsent_required", target=Target("consent", row.id))
                reconsent += 1
    return SweepResult(expiring, expired, reconsent)
