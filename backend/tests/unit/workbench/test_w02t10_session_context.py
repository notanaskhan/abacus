"""W-02-T10 (TASK-7712; W-02 §3.3; SPEC-653 AC-C3 to AC-C5; DEC-4715): context options and items.

Row acceptance: "No Copperleaf; summaries foot to the seed." Options come only from engagements
the viewer can open; a record outside them is 404 on attach; summary lines are code's counts.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.workbench import session_context as sc


@dataclass(frozen=True)
class _Engagement:
    id: uuid.UUID
    name: str
    client_entity_id: uuid.UUID
    client_entity_name: str
    client_id: uuid.UUID
    fiscal_period_start: date = date(2025, 1, 1)
    fiscal_period_end: date = date(2025, 12, 31)


NORTHWIND = _Engagement(uuid.uuid4(), "PY2025 EBP Audit", uuid.uuid4(),
                        "Northwind Robotics 401(k) Plan", uuid.uuid4())  # fmt: skip
GRANITE = _Engagement(uuid.uuid4(), "FY2025 Audit", uuid.uuid4(),
                      "Granite Peak Outdoor Supply, Inc.", uuid.uuid4())  # fmt: skip


@pytest.fixture(autouse=True)
def visible(monkeypatch: pytest.MonkeyPatch) -> None:
    async def engagements(ctx: object) -> list[_Engagement]:
        return [NORTHWIND, GRANITE]  # Copperleaf is not one the viewer can open

    monkeypatch.setattr(sc, "engagements_for", engagements)


CTX: Any = type(  # Any: a test double
    "C", (), {"tenant": object(), "user_id": uuid.uuid4(), "tenant_id": uuid.uuid4()}
)()


def test_each_tab_lists_only_visible_records() -> None:
    rows = asyncio.run(sc.options(CTX, "client_record", None, set()))
    assert [o.title for o, _ in rows] == [
        "Northwind Robotics 401(k) Plan",
        "Granite Peak Outdoor Supply, Inc.",
    ]
    assert all("Copperleaf" not in o.title for o, _ in rows)
    docs = asyncio.run(sc.options(CTX, "documents", "northwind", set()))
    assert [o.title for o, _ in docs] == ["PBC · Northwind Robotics 401(k) Plan"]
    marked = asyncio.run(sc.options(CTX, "workpapers", None, {("workpaper_set", NORTHWIND.id)}))
    assert [on for _o, on in marked] == [True, False]


def test_the_client_record_detail_is_the_engagement_and_its_period() -> None:
    (row, _), *_ = asyncio.run(sc.options(CTX, "client_record", "northwind", set()))
    assert row.detail == "PY2025 EBP Audit · Jan 1, 2025\u2013Dec 31, 2025"


def test_pbc_summary_lines_are_codes_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.requests import api as requests_api

    async def work_items(tenant: object, engagement: object) -> list[uuid.UUID]:
        return [uuid.uuid4(), uuid.uuid4()]

    async def counts(ctx: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        return {ids[0]: (12, 24)}

    monkeypatch.setattr(sc, "work_item_ids_of", work_items)
    monkeypatch.setattr(requests_api, "pbc_counts", counts)
    option = next(o for o in asyncio.run(sc.all_options(CTX)) if o.kind == "request_set")
    chip, lines = asyncio.run(sc.summary(CTX, option))
    assert chip == "PBC · 12 of 24"
    assert lines[0] == "24 requests · 12 received"


def test_attaching_a_record_the_viewer_cannot_open_is_404() -> None:
    with pytest.raises(NotFound):
        asyncio.run(sc.attach(CTX, uuid.uuid4(), [("client_entity", uuid.uuid4())]))
