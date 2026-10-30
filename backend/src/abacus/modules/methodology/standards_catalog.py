"""Firm standards on KNW-01 and in search (K-02-T08; K-01 §4.3; C15).

- KNW-01's `firm_standards` category: one card per standard with a published version ("Published",
  "v3 · from Oct 1, 2026", its owner), no review queue (a standard has no review step: its owner
  publishes), and a change-log entry per published version.
- The C15 search projection `firm_standard`: the name and kind only, never a value (metadata).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.methodology.catalog import (
    CatalogItem,
    CatalogProvider,
    ChangeEntry,
    ReviewItem,
    Viewer,
    register_catalog_provider,
)
from abacus.modules.methodology.standards import search_metadata, standard_cards, standard_changes
from abacus.modules.platform.api import SearchDocument, register_search_projection

CATEGORY: Final = "firm_standards"
SEARCH_TYPE: Final = "firm_standard"


def _route(standard_id: UUID) -> str:
    return f"/knowledge/standards?standard={standard_id}"


async def standards_items(viewer: Viewer) -> list[CatalogItem]:
    return [
        CatalogItem(
            id=card.id,
            category=CATEGORY,
            title=card.title,
            subtitle=None,
            status=card.status,
            version_label=None if card.version is None else f"v{card.version}",
            effective_from=card.effective_from,
            owner_user_id=card.owner_user_id,
            updated_at=card.updated_at,
            route=_route(card.id),
        )
        for card in await standard_cards(viewer.ctx)
    ]


async def standards_queue(_viewer: Viewer) -> list[ReviewItem]:
    return []


async def standards_changes(viewer: Viewer) -> list[ChangeEntry]:
    return [
        ChangeEntry(
            id=change.version_id,
            at=change.at,
            seq=change.version,
            category=CATEGORY,
            object_id=change.standard_id,
            title=f"{change.title} · v{change.version}",
            kind="published",
            actor_kind="human",
            actor_user_id=change.by_user,
            on_behalf_of_user_id=None,
        )
        for change in await standard_changes(viewer.ctx)
    ]


async def standard_search_document(
    tenant: TenantContext, standard_id: UUID
) -> SearchDocument | None:
    found = await search_metadata(tenant, standard_id)
    if found is None:
        return None
    name, kind = found
    return SearchDocument(
        object_type=SEARCH_TYPE,
        object_id=standard_id,
        engagement_id=None,
        title=name,
        body=kind.replace("_", " "),
    )


_registered = False


def register_standards_providers() -> None:
    """Once, from `methodology.api` (the search slot refuses a second registration)."""
    global _registered
    register_catalog_provider(
        CATEGORY, CatalogProvider(standards_items, standards_queue, standards_changes)
    )
    if not _registered:
        register_search_projection(SEARCH_TYPE, standard_search_document)
        _registered = True


__all__ = ["CATEGORY", "SEARCH_TYPE", "register_standards_providers"]
