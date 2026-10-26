"""The integration catalogue, read (A-02-T12; C20 v1; SPEC-333 AC-49, AC-10.1).

Catalogue rows are content loaded by an operator from a reviewed document (`catalog_load.py`,
`abacus_tools.integration_catalog`); this module reads them through the definer function
`integration_catalog_rows()`, inside the caller's tenant session, and decides what each row may
be listed as here. **Catalogue honesty:** a row is `available` only when its listing says so
*and* its adapter is registered in this process with the row's category and connection provider;
any other listed row is `coming_soon` (POR-16 offers it only *Export instead*), and `hidden`
rows are never listed. Callers authorise before they read (the POR-16 route: `connection.read`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.integrations.adapters import registered_adapter

Listing = Literal["available", "coming_soon", "hidden"]
Surface = Literal["portal", "workbench"]


@dataclass(frozen=True)
class CatalogRow:
    key: str
    name: str
    category: str
    ownership_mode: str
    surfaces: tuple[str, ...]
    connector_provider: str | None
    adapter_key: str | None
    listing_status: str
    consent_copy: dict[str, Any] | None  # Any: JSON content (will, wont, authorization, helper)
    consent_version: int | None
    read_scopes: tuple[tuple[str, str], ...]  # (code, label)
    icon: str
    tone: str
    sort_order: int
    revision: int
    loaded_at: datetime


@dataclass(frozen=True)
class CatalogEntry:
    row: CatalogRow
    listing: Listing


def _scopes(raw: object) -> tuple[tuple[str, str], ...]:
    reads = cast(dict[str, list[dict[str, str]]], raw).get("read", [])
    return tuple((str(s["code"]), str(s["label"])) for s in reads)


def listing_of(row: CatalogRow) -> Listing:
    """What the row may be listed as in this environment (AC-49, fail-closed)."""
    if row.listing_status == "hidden":
        return "hidden"
    adapter = registered_adapter(row.adapter_key)
    honest = (
        adapter is not None
        and adapter.category == row.category
        and adapter.connector_provider == row.connector_provider
    )
    if row.listing_status == "available" and honest:
        return "available"
    return "coming_soon"


async def catalog_rows(tenant: TenantContext) -> list[CatalogRow]:
    """Every catalogue row, in catalogue order."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(text("SELECT * FROM integration_catalog_rows()"))).mappings()
        return [
            CatalogRow(
                key=r["key"],
                name=r["name"],
                category=r["category"],
                ownership_mode=r["ownership_mode"],
                surfaces=tuple(r["surfaces"]),
                connector_provider=r["connector_provider"],
                adapter_key=r["adapter_key"],
                listing_status=r["listing_status"],
                consent_copy=r["consent_copy"],
                consent_version=r["consent_version"],
                read_scopes=_scopes(r["scopes"]),
                icon=r["icon"],
                tone=r["tone"],
                sort_order=r["sort_order"],
                revision=r["revision"],
                loaded_at=r["loaded_at"],
            )
            for r in rows
        ]


def listed(rows: Sequence[CatalogRow], surface: Surface, ownership: str) -> list[CatalogEntry]:
    """The rows a surface lists for an ownership mode, with their honest listing."""
    out: list[CatalogEntry] = []
    for row in rows:
        if surface not in row.surfaces or row.ownership_mode != ownership:
            continue
        listing = listing_of(row)
        if listing != "hidden":
            out.append(CatalogEntry(row, listing))
    return out


async def client_catalog(tenant: TenantContext) -> list[CatalogEntry]:
    """POR-16's catalogue: client-authorised rows on the portal surface (A-02-T16 composes the
    cards with the entity's connections)."""
    return listed(await catalog_rows(tenant), "portal", "client_authorised")


def is_available(entry: CatalogEntry) -> bool:
    return entry.listing == "available"
