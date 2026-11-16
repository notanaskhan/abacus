"""The Connect catalogue service (W-01-T07; C20 v2; SPEC-659 AC-1 to AC-6, AC-31; red).

WB-10's read, for one firm and one viewer at the business clock:

- **Published rows only.** A workbench row lists once the clock has passed its `published_at`
  and while it is not `hidden` (0901's `integration_catalog_workbench()`; 55 = 9 + 40 + 6 at E2
  because Drata and Vanta publish Oct 1).
- **Effective status.** An install decides it: the firm's for firm and client-authorised tiles,
  the viewer's own for personal ones (`connecting`, `connected`, `needs_attention`,
  `needs_reauth`, `paused`). Without one, the listing does, honestly (AC-4): `available` only
  when an adapter for the key is registered in this process for this firm
  (`adapters.adapter_for`: a real one, or a fake on a synthetic firm outside production, W-01-T09);
  otherwise `coming_soon`, with Notify me.
- **Counts.** `all` is the tiles; `connected` every tile with a live install; `available` and
  `coming_soon` the rest by status. Category counts are catalogue totals by tag at the clock and
  never change with the filters (AC-2): one tile can count in two categories.
- **Filters.** `category` (a tag), `status` (connected · available · coming_soon) and `q` (case-
  insensitive, on the name and the description).
- **Blocked reasons.** A firm tile the viewer may not enable names who manages firm connections
  (AC-6, WB-10 d: "Felix Andersen manages firm connections."); a tile whose catalogue row names a
  prerequisite scope the firm's install of that integration has not granted shows the row's
  reason (WB-10 a, Workstream). Both are read-time; nothing is stored.
- **Allowed actions** are the viewer's matrix actions for that tile (the agent holds none, AC-8).

Notify me (`interest`, AC-31) is idempotent: the first call records, every later one answers the
same. Nothing here starts a connection (R1).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import now as business_now
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    firm_admins,
    firm_role_allows,
    is_synthetic_firm,
    names_of,
    own_role_allows,
    security_admins,
)
from abacus.modules.integrations.adapters import adapter_for
from abacus.modules.integrations.models import (
    FirmIntegration,
    IntegrationInterest,
    UserIntegration,
)

Status = Literal[
    "available",
    "coming_soon",
    "connecting",
    "connected",
    "needs_attention",
    "needs_reauth",
    "paused",
    "disconnected",
]
Kind = Literal["firm", "personal", "client_authorised", "file_bridge"]
Bucket = Literal["connected", "available", "coming_soon"]

# WB-10's category list, in the canvas order (the codes are 0890's CHECK).
CATEGORIES: Final[tuple[tuple[str, str, str], ...]] = (
    ("tax", "Tax Software", "Tax preparation, compliance and e-file"),
    ("practice", "Practice Management", "Workflow, time, billing and client CRM"),
    ("erp", "ERP & Accounting", "Client general ledgers and ERP systems"),
    ("grc", "GRC & Compliance", "Controls, evidence and compliance automation"),
    ("docs", "Document Management", "File storage, portals and e-signature"),
    ("comms", "Communications", "Email, chat and meetings"),
    ("prod", "Productivity", "Calendars, notes and project tools"),
    ("crm", "CRM", "Client relationships and pipeline"),
    ("hris", "HRIS & Payroll", "People, payroll and benefits"),
    ("spend", "Spend & Payments", "Bills, cards and expense management"),
)
LIVE: Final = frozenset({"connecting", "connected", "needs_attention", "needs_reauth", "paused"})
FIRM_ACTIONS: Final = ("integration.connect_firm", "integration.disconnect_firm")
PERSONAL_ACTIONS: Final = ("integration.connect_personal", "integration.disconnect_personal")
_ROWS = text("SELECT * FROM integration_catalog_workbench()")


@dataclass(frozen=True)
class WorkbenchRow:
    key: str
    name: str
    categories: tuple[str, ...]
    ownership_mode: str
    connector_provider: str | None
    adapter_key: str | None
    listing_status: str
    consent_copy: dict[str, Any] | None  # Any: catalogue JSON content
    consent_version: int | None
    read_scopes: tuple[tuple[str, str], ...]
    icon: str
    tone: str
    sort_order: int
    description: str
    auth_line: str
    published_at: datetime | None
    prerequisite: dict[str, str] | None
    revision: int
    detail_copy: dict[str, Any] | None = None  # Any: catalogue JSON content (0933)


@dataclass(frozen=True)
class Install:
    id: UUID
    status: str
    mode: str | None  # firm installs: token · file_bridge · firm_app
    connected_by: UUID | None
    granted_scopes: tuple[str, ...]
    version: int


@dataclass(frozen=True)
class Tile:
    row: WorkbenchRow
    kind: Kind
    status: Status
    viewer_status: Status
    connected_by_label: str | None
    blocked_reason: str | None
    allowed_actions: tuple[str, ...]

    @property
    def bucket(self) -> Bucket:
        if self.status in LIVE:
            return "connected"
        return "available" if self.status == "available" else "coming_soon"


@dataclass(frozen=True)
class Catalogue:
    tiles: tuple[Tile, ...]  # filtered
    counts: dict[str, int]  # over every published tile
    categories: tuple[tuple[str, str, str, int], ...]  # code, label, description, count
    total: int


def _scopes(raw: object) -> tuple[tuple[str, str], ...]:
    reads = cast(dict[str, list[dict[str, str]]], raw or {}).get("read", [])
    return tuple((str(s["code"]), str(s["label"])) for s in reads)


async def workbench_rows(session: AsyncSession) -> list[WorkbenchRow]:
    rows = (await session.execute(_ROWS)).mappings()
    return [
        WorkbenchRow(
            key=r["key"],
            name=r["name"],
            categories=tuple(r["categories"] or ()),
            ownership_mode=r["ownership_mode"],
            connector_provider=r["connector_provider"],
            adapter_key=r["adapter_key"],
            listing_status=r["listing_status"],
            consent_copy=r["consent_copy"],
            consent_version=r["consent_version"],
            read_scopes=_scopes(r["scopes"]),
            icon=r["icon"],
            tone=r["tone"],
            sort_order=r["sort_order"],
            description=r["description"] or "",
            auth_line=r["auth_line"] or "",
            published_at=r["published_at"],
            prerequisite=r["prerequisite"],
            revision=r["revision"],
            detail_copy=r.get("detail_copy"),
        )
        for r in rows
    ]


def published(rows: Sequence[WorkbenchRow], at: datetime) -> list[WorkbenchRow]:
    """The tiles listed at `at`: not hidden, and published by then."""
    return [
        r
        for r in rows
        if r.listing_status != "hidden" and r.published_at is not None and r.published_at <= at
    ]


async def firm_installs(session: AsyncSession) -> dict[str, Install]:
    found = await session.execute(
        select(FirmIntegration).where(FirmIntegration.status != "disconnected")
    )
    return {
        f.catalog_key: Install(
            f.id, f.status, f.mode, f.connected_by, tuple(f.granted_scopes or ()), f.version
        )
        for f in found.scalars()
    }


async def own_installs(session: AsyncSession, user_id: UUID) -> dict[str, Install]:
    found = await session.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == user_id, UserIntegration.status != "disconnected"
        )
    )
    return {
        u.catalog_key: Install(u.id, u.status, None, u.user_id, tuple(u.granted_scopes), u.version)
        for u in found.scalars()
    }


def honest_listing(row: WorkbenchRow, *, synthetic: bool) -> Status:
    """`available` only with an adapter for this firm (AC-4, fail-closed); else coming soon."""
    if row.listing_status != "available":
        return "coming_soon"
    return "available" if adapter_for(row.adapter_key, synthetic=synthetic) else "coming_soon"


def kind_of(row: WorkbenchRow, install: Install | None) -> Kind:
    if row.ownership_mode == "personal":
        return "personal"
    if row.ownership_mode == "client_authorised":
        return "client_authorised"
    return "file_bridge" if install is not None and install.mode == "file_bridge" else "firm"


def tile_of(
    row: WorkbenchRow,
    *,
    ctx: AuthContext,
    synthetic: bool,
    firm: dict[str, Install],
    mine: dict[str, Install],
    names: dict[UUID, str],
    manager: str | None,
) -> Tile:
    personal = row.ownership_mode == "personal"
    install = (mine if personal else firm).get(row.key)
    kind = kind_of(row, install)
    status = cast(Status, install.status) if install else honest_listing(row, synthetic=synthetic)
    label = None
    if install is not None and not personal and install.connected_by is not None:
        label = names.get(install.connected_by)
    actions = PERSONAL_ACTIONS if personal else FIRM_ACTIONS
    allows = own_role_allows if personal else firm_role_allows
    allowed = tuple(a for a in actions if allows(ctx, a))
    blocked = None
    if not personal and not allowed and manager is not None:
        blocked = f"{manager} manages firm connections."
    prerequisite = row.prerequisite
    if blocked is None and prerequisite is not None and install is None:
        needed = firm.get(prerequisite["key"])
        if needed is None or prerequisite["scope"] not in needed.granted_scopes:
            blocked = prerequisite["reason"]
    if status == "coming_soon" and own_role_allows(ctx, "integration.interest"):
        allowed = (*allowed, "integration.interest")  # Notify me
    return Tile(row, kind, status, status, label, blocked, allowed)


async def _manager(tenant_id: UUID) -> str | None:
    """Who manages firm connections, named on a disabled Enable: a security admin, else a
    firm admin; the first by name."""
    for holders in (await security_admins(tenant_id), await firm_admins(tenant_id)):
        if holders:
            named = await names_of(list(holders))
            return sorted(named.values())[0] if named else None
    return None


async def connections_manager(tenant_id: UUID) -> str | None:
    """Who manages firm connections (WB-10 d, WB-11 f): read-time, never stored."""
    return await _manager(tenant_id)


def _matches(tile: Tile, category: str | None, status: Bucket | None, q: str | None) -> bool:
    if category is not None and category not in tile.row.categories:
        return False
    if status is not None and tile.bucket != status:
        return False
    if q:
        needle = q.strip().casefold()
        hay = f"{tile.row.name} {tile.row.description}".casefold()
        if needle and needle not in hay:
            return False
    return True


async def catalogue(
    ctx: AuthContext,
    *,
    category: str | None = None,
    status: Bucket | None = None,
    q: str | None = None,
) -> Catalogue:
    """WB-10's catalogue for the viewer (the route authorised `integration_catalog.read`)."""
    at = await business_now(ctx.tenant)
    synthetic = await is_synthetic_firm(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        rows = published(await workbench_rows(session), at)
        firm = await firm_installs(session)
        mine = await own_installs(session, ctx.user_id)
    people = sorted({i.connected_by for i in firm.values() if i.connected_by}, key=str)
    names = await names_of(people) if people else {}
    manager = await _manager(ctx.tenant_id)
    tiles = [
        tile_of(
            r, ctx=ctx, synthetic=synthetic, firm=firm, mine=mine, names=names, manager=manager
        )
        for r in rows
    ]
    buckets = Counter(t.bucket for t in tiles)
    tags = Counter(c for r in rows for c in r.categories)
    return Catalogue(
        tiles=tuple(t for t in tiles if _matches(t, category, status, q)),
        counts={
            "all": len(tiles),
            "connected": buckets["connected"],
            "available": buckets["available"],
            "coming_soon": buckets["coming_soon"],
        },
        categories=tuple((c, label, d, tags[c]) for c, label, d in CATEGORIES if tags[c]),
        total=len(tiles),
    )


async def published_row(ctx: AuthContext, key: str) -> WorkbenchRow:
    """One listed tile's row, or 404 (unpublished, hidden or unknown are alike)."""
    at = await business_now(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        rows = published(await workbench_rows(session), at)
    found = next((r for r in rows if r.key == key), None)
    if found is None:
        raise NotFound("integration")
    return found


async def interest(ctx: AuthContext, key: str) -> bool:
    """Notify me (AC-31): idempotent; True when this call recorded it."""
    await published_row(ctx, key)
    async with uow(ctx.tenant) as tx:
        created = await tx.session.scalar(
            pg_insert(IntegrationInterest)
            .values(tenant_id=ctx.tenant_id, user_id=ctx.user_id, catalog_key=key)
            .on_conflict_do_nothing()
            .returning(IntegrationInterest.catalog_key)
        )
        tx.record(
            "integration.interest_recorded" if created else "integration.interest_repeated",
            target=Target("firm", ctx.tenant_id),
            after=Ref(recorded=1 if created else 0),
        )
    return created is not None
