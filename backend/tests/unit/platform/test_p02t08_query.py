"""P-02-T08 (TASK-7617; DEC-4614): the query service's pure parts: match ranges over the title,
the related-party context, the per-person budget, and a projection's visibility failing closed."""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy.sql.elements import False_

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.platform.search import query, spec
from abacus.modules.platform.search.errors import SearchQueryInvalid, SearchRateLimited


def _ctx(role: str = "manager") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), cast(Any, role), None
    )


def test_match_ranges_light_each_query_word_once() -> None:
    assert query.match_ranges("2025 Form 1040 · Feld", "feld") == [(17, 21)]
    assert query.match_ranges("Granite Peak Outdoor Supply", "granite peak") == [(0, 7), (8, 12)]
    assert query.match_ranges("Ridgeline", "zzz") == []


def test_a_related_party_match_names_the_party() -> None:
    row = {
        "title": "2025 Form 1065",
        "context": "Ridgeline Property Partners, LP",
        "related": [{"name": "Jonah Feld", "label": "limited partner 25%"}],
    }
    assert query.context_of(row, "feld") == "Jonah Feld, limited partner 25%"
    assert query.context_of(row, "1065") == "Ridgeline Property Partners, LP"


def test_the_budget_is_ten_a_second_burst_twenty(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx()
    clock = {"t": 1000.0}
    monkeypatch.setattr(query.time, "monotonic", lambda: clock["t"])
    for _ in range(20):
        query.take_token(ctx)
    with pytest.raises(SearchRateLimited):
        query.take_token(ctx)
    clock["t"] += 0.1  # one token back
    query.take_token(ctx)


def test_an_unknown_scope_kind_admits_nothing() -> None:
    async def build(tenant: object, object_id: uuid.UUID) -> None:
        return None

    odd = spec.SearchProjection(
        object_type="p02_odd",
        group="clients",
        read_action="client.read",
        scope_kind=cast(Any, "portal_scope"),
        build=build,
        target="CLI-02",
    )
    assert isinstance(query.visible_for(_ctx(), odd), False_)


def test_empty_text_outside_agent_mode_is_invalid() -> None:
    import asyncio

    from abacus.modules.platform.search.contract import SearchQueryIn

    with pytest.raises(SearchQueryInvalid):
        asyncio.run(query.search(_ctx(), SearchQueryIn(q="   "), agent_mode=False))
