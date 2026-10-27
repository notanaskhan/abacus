"""K-01-T03 (TASK-1426): the catalog slots fail closed and search ranges are code.

- an unknown category, or a second provider for a taken one, is refused at registration;
- a provider that raises leaves its category out (no cards, no facet count), never a wrong one;
- a usage counter that raises leaves `usage_count` null;
- match ranges are every case-folded occurrence in the title, not overlapping.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.methodology import catalog
from abacus.modules.methodology.catalog import (
    CatalogItem,
    CatalogProvider,
    ChangeEntry,
    ReviewItem,
    Viewer,
    match_ranges,
    register_catalog_provider,
)

pytestmark = pytest.mark.asyncio


async def _no_queue(_viewer: Viewer) -> Sequence[ReviewItem]:
    return []


async def _no_changes(_viewer: Viewer) -> Sequence[ChangeEntry]:
    return []


async def _raises(_viewer: Viewer) -> Sequence[CatalogItem]:
    raise RuntimeError("provider down")


def _item(category: str, title: str, *, usage: bool = True) -> CatalogItem:
    item_id = uuid.uuid4()
    return CatalogItem(
        id=item_id,
        category=category,
        title=title,
        subtitle=None,
        status="published",
        version_label="v1",
        effective_from=None,
        owner_user_id=None,
        updated_at=datetime(2026, 9, 14, tzinfo=UTC),
        route="/knowledge",
        usage=("thing", item_id) if usage else None,
    )


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )


@pytest.fixture
def isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog, "_PROVIDERS", {})
    monkeypatch.setattr(catalog, "_COUNTERS", {})

    async def viewer(ctx: AuthContext) -> Viewer:
        return Viewer(ctx, sees_drafts=False, approves=False)

    monkeypatch.setattr(catalog, "_viewer", viewer)


def test_an_unknown_category_or_a_second_provider_is_refused(isolated: None) -> None:
    provider = CatalogProvider(_raises, _no_queue, _no_changes)
    with pytest.raises(ValueError, match="not a knowledge category"):
        register_catalog_provider("gossip", provider)
    register_catalog_provider("skills", provider)
    register_catalog_provider("skills", provider)  # the same provider again: a no-op

    async def other(_viewer: Viewer) -> Sequence[CatalogItem]:
        return []

    with pytest.raises(ValueError, match="already has a provider"):
        register_catalog_provider("skills", CatalogProvider(other, _no_queue, _no_changes))


async def test_a_failing_provider_and_counter_show_nothing_rather_than_wrong(
    isolated: None,
) -> None:
    async def notes(_viewer: Viewer) -> Sequence[CatalogItem]:
        return [_item("notes", "Subsequent events"), _item("skills", "Smuggled in")]

    async def counter(_ctx: AuthContext, _ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        raise RuntimeError("counter down")

    register_catalog_provider("skills", CatalogProvider(_raises, _no_queue, _no_changes))
    register_catalog_provider("notes", CatalogProvider(notes, _no_queue, _no_changes))
    catalog.register_usage_counter("thing", counter)
    page = await catalog.catalog_items(
        _ctx(), category=None, status=None, q=None, cursor=None, limit=None
    )
    assert [c.item.title for c in page.items] == ["Subsequent events"]
    assert page.items[0].usage_count is None
    assert {f.value: f.n for f in page.facets["category"]} == {"notes": 1}


def test_match_ranges_are_every_case_folded_occurrence() -> None:
    assert match_ranges("Materiality and materiality", "MATERIAL") == [(0, 8), (16, 24)]
    assert match_ranges("BH Audit Methodology", "") == []
    assert match_ranges("aaaa", "aa") == [(0, 2), (2, 4)]
