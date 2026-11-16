"""WB-11's detail reads (W-01-T15; W-01 §3 F6; WB-11; DEC-5321; red).

- **The timeline** (`events`): the firm's install events for one integration, newest first, 50 a
  page (cursor `<at>|<id>`); each row's label is written at read time from its kind and code
  (never stored text), and `ok` is false for a failure (token expired, health failed, a failed
  run).
- **Dependents** (`dependents`): the capabilities that require the integration, from the agents
  module's provider; `paused` is computed from the install's status (needs reauth, needs
  attention, paused or disconnected), never stored (AC-15).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.integrations.dependents import dependents_of

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


def _cursor(value: str | None) -> tuple[str | None, str | None]:
    if not value or "|" not in value:
        return None, None
    at, _, ident = value.partition("|")
    return at, ident


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
