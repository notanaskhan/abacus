"""WB-11's detail reads (W-01-T15; W-01 §3 F6; WB-11; DEC-5321; red).

- **The timeline** (`events`): the firm's install events for one integration, newest first, 50 a
  page (cursor `<at>|<id>`); each row's label is written at read time from its kind and code
  (never stored text), and `ok` is false for a failure (token expired, health failed, a failed
  run).
- **Dependents** (`dependents`): the capabilities that require the integration, from the agents
  module's provider; `paused` is computed from the install's status (needs reauth, needs
  attention, paused or disconnected), never stored (AC-15).
- **The drawer** (`drawer`; S47, TASK-8338): WB-11's projection for one viewer, built on WB-10's
  tile (status, kind, blocked reason, allowed actions) and the install the tile reads (the firm's,
  or the viewer's own for a personal app). The connection card, the read rows (a scope a recorded
  grant leaves out reads off for the firm), the recent events and the dependents are live.
  The write, never and who-can-use words are the catalogue's (0933's `detail_copy`); a personal
  app's never rows are its consent `wont` lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import select, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.api import AuthContext, names_of
from abacus.modules.integrations.connect_catalog import (
    Tile,
    WorkbenchRow,
    catalogue,
    connections_manager,
)
from abacus.modules.integrations.dependents import dependents_of
from abacus.modules.integrations.models import FirmIntegration, UserIntegration

PAGE: Final = 50
_FAILED: Final = frozenset({"token_expired", "health_failed", "run_failed"})
_LABELS: Final = {
    "connect_started": "Connection started",
    "connected": "Connected",
    "reconnected": "Reconnected",
    "disconnected": "Disconnected",
    "synced": "Synced",
    "token_expired": "Token expired",
    "health_failed": "Health check failed",
    "health_recovered": "Health check recovered",
    "run_failed": "1 scheduled run failed",
    "paused": "Paused",
    "resumed": "Resumed",
}
_PAUSING: Final = frozenset({"needs_reauth", "needs_attention", "paused", "disconnected"})
_EVENTS: Final = text(
    "SELECT id, kind, at, code FROM integration_events WHERE catalog_key = :k "
    "AND install_kind = 'firm' AND (CAST(:at AS timestamptz) IS NULL OR (at, id) < "
    "(CAST(:at AS timestamptz), CAST(:id AS uuid))) ORDER BY at DESC, id DESC LIMIT :n"
)
_STATUS: Final = text("SELECT status FROM firm_integrations WHERE catalog_key = :k")


@dataclass(frozen=True)
class Event:
    id: UUID
    kind: str
    at: datetime
    label: str
    ok: bool


@dataclass(frozen=True)
class Dependents:
    count: int
    paused: bool
    keys: tuple[str, ...]


def label_of(kind: str) -> str:
    return _LABELS.get(kind, kind.replace("_", " ").capitalize())


def _cursor(value: str | None) -> tuple[datetime | None, UUID | None]:
    """The page's `<at>|<id>` cursor, parsed here: a malformed one starts from the newest (as
    before), never a database error."""
    if not value or "|" not in value:
        return None, None
    at, _, ident = value.partition("|")
    try:
        return datetime.fromisoformat(at), UUID(ident)
    except ValueError:
        return None, None


async def events(
    tenant: TenantContext, catalog_key: str, cursor: str | None = None
) -> tuple[list[Event], str | None]:
    at, ident = _cursor(cursor)
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                _EVENTS, {"k": catalog_key, "at": at, "id": ident, "n": PAGE + 1}
            )
        ).all()
    page = [
        Event(r[0], str(r[1]), r[2], label_of(str(r[1])), str(r[1]) not in _FAILED)
        for r in rows[:PAGE]
    ]
    following = f"{page[-1].at.isoformat()}|{page[-1].id}" if len(rows) > PAGE and page else None
    return page, following


async def dependents(tenant: TenantContext, catalog_key: str) -> Dependents:
    keys = tuple(await dependents_of(catalog_key))
    async with tenant_session(tenant) as session:
        status = await session.scalar(_STATUS, {"k": catalog_key})
    return Dependents(len(keys), status in _PAUSING if status else bool(keys), keys)


RECENT: Final = 5


@dataclass(frozen=True)
class Card:
    mode: str
    auth_mode_label: str
    connected_by: str | None
    connected_at: datetime | None
    token_renews_at: datetime | None
    last_sync_at: datetime | None


@dataclass(frozen=True)
class MayDo:
    label: str
    state: str  # allowed · off_for_firm · never


@dataclass(frozen=True)
class WriteRow:
    label: str
    gate_label: str | None
    state: str  # allowed · off_for_firm


@dataclass(frozen=True)
class Drawer:
    tile: Tile
    card: Card
    reads: tuple[MayDo, ...]
    never: tuple[MayDo, ...]
    writes: tuple[WriteRow, ...]
    who_can_use: str
    who_can_use_note: str | None
    events: tuple[Event, ...]
    dependents: Dependents
    managed_by: str | None
    version: int


def _mode(row: WorkbenchRow, install_mode: str | None) -> str:
    if row.ownership_mode == "personal":
        return "personal"
    if row.ownership_mode == "client_authorised":
        return "firm_app"
    return install_mode if install_mode in ("token", "file_bridge", "firm_app") else "token"


async def drawer(ctx: AuthContext, catalog_key: str) -> Drawer:
    """WB-11 for the viewer (the route authorised `integration_catalog.read`); 404 for a key
    WB-10 does not list."""
    from abacus.kernel.errors import NotFound

    tile = next((t for t in (await catalogue(ctx)).tiles if t.row.key == catalog_key), None)
    if tile is None:
        raise NotFound("integration")
    row = tile.row
    personal = row.ownership_mode == "personal"
    async with tenant_session(ctx.tenant) as session:
        if personal:
            mine = await session.scalar(
                select(UserIntegration).where(
                    UserIntegration.catalog_key == catalog_key,
                    UserIntegration.user_id == ctx.user_id,
                    UserIntegration.status != "disconnected",
                )
            )
            granted = tuple(mine.granted_scopes) if mine else None
            by, at, renews, synced = (
                (mine.user_id, mine.connected_at, mine.token_renews_at, mine.last_sync_at)
                if mine
                else (None, None, None, None)
            )
            install_mode, version = None, mine.version if mine else 1
        else:
            firm = await session.scalar(
                select(FirmIntegration).where(
                    FirmIntegration.catalog_key == catalog_key,
                    FirmIntegration.status != "disconnected",
                )
            )
            granted = tuple(firm.granted_scopes or ()) if firm else None
            by, at, renews, synced = (
                (firm.connected_by, firm.connected_at, firm.token_renews_at, firm.last_sync_at)
                if firm
                else (None, None, None, None)
            )
            install_mode, version = (firm.mode, firm.version) if firm else (None, 1)
    mode = _mode(row, install_mode)
    named = (await names_of([by])).get(by) if by is not None else None
    reads = tuple(
        # A read is off for the firm only against a recorded grant (an install that has recorded
        # no scopes is not tracked for them).
        MayDo(label, "allowed" if not granted or code in granted else "off_for_firm")
        for code, label in row.read_scopes
    )
    copy = row.consent_copy or {}
    detail = row.detail_copy or {}
    wont = cast("list[object]", copy.get("wont", []) if personal else detail.get("never", []))
    never = tuple(MayDo(str(line), "never") for line in wont)
    # 0933 (DEC-5337): the catalogue's words for each declared write, on only when the
    # write-capability registry enables it.
    from abacus.modules.integrations.capabilities import write_capability

    writes = tuple(
        WriteRow(
            str(w.get("label", "")),
            None if w.get("gate_label") is None else str(w["gate_label"]),
            "allowed"
            if (found := write_capability(str(w.get("key", "")))) is not None and found.enabled
            else "off_for_firm",
        )
        for w in cast("list[dict[str, object]]", detail.get("writes", []))
    )
    page, _ = await events(ctx.tenant, catalog_key) if not personal else ([], None)
    return Drawer(
        tile=tile,
        card=Card(
            mode=mode,
            auth_mode_label=row.auth_line,
            connected_by=named,
            connected_at=at,
            token_renews_at=None if mode == "file_bridge" else renews,  # AC-23
            last_sync_at=synced,
        ),
        reads=reads,
        never=never,
        writes=writes,
        who_can_use=str(detail.get("who_can_use") or ""),
        who_can_use_note=None
        if detail.get("who_can_use_note") is None
        else str(detail["who_can_use_note"]),
        events=tuple(page[:RECENT]),
        dependents=await dependents(ctx.tenant, catalog_key),
        managed_by=None if personal else await connections_manager(ctx.tenant_id),
        version=version,
    )
