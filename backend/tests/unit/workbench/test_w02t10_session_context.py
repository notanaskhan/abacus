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


def test_workpapers_card_carries_materiality_only_when_the_viewer_may_read_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S41 gaps (AC-C4, DEC-4734): the decided overall and its version, by code."""
    from decimal import Decimal

    from abacus.modules.assurance import api as assurance_api
    from abacus.modules.identity import api as identity_api
    from abacus.modules.workpapers import api as workpapers_api

    @dataclass(frozen=True)
    class _V:
        overall: Decimal
        version_no: int

    @dataclass(frozen=True)
    class _Record:
        versions: list[_V]

    async def work_items(tenant: object, engagement: object) -> list[uuid.UUID]:
        return [uuid.uuid4()]

    async def papers(tenant: object, wi: object) -> list[object]:
        return []

    async def resource(tenant: object, engagement: object) -> object:
        return object()

    async def allowed(ctx: object, action: str, resource: object) -> None:
        assert action in ("materiality.read", "control.read")

    async def denied(ctx: object, action: str, resource: object) -> None:
        raise identity_api.Forbidden(action, "role")

    async def record(ctx: object, engagement: object) -> _Record:
        return _Record([_V(Decimal(168100), 1), _V(Decimal(168100), 2)])

    monkeypatch.setattr(sc, "work_item_ids_of", work_items)
    monkeypatch.setattr(workpapers_api, "work_item_papers", papers)
    monkeypatch.setattr(identity_api, "engagement_resource", resource)
    monkeypatch.setattr(assurance_api, "materiality_record", record)
    _no_tb_or_exceptions(monkeypatch)
    option = next(o for o in asyncio.run(sc.all_options(CTX)) if o.kind == "workpaper_set")
    monkeypatch.setattr(identity_api, "authorise", allowed)
    _chip, lines = asyncio.run(sc.summary(CTX, option))
    assert lines == ("0 workpapers", "Materiality v2 · $168,100")  # AC-C4's words (DEC-4738)
    monkeypatch.setattr(identity_api, "authorise", denied)
    _chip, lines = asyncio.run(sc.summary(CTX, option))
    assert lines == ("0 workpapers",)


def _no_tb_or_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.assurance import api as assurance_api
    from abacus.modules.review import api as review_api

    async def none(*_a: object) -> list[object]:
        return []

    monkeypatch.setattr(review_api, "reviewables_of", none)
    monkeypatch.setattr(assurance_api, "control_exceptions", none)


def test_ac_c4_workpaper_line_and_client_record_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """S41 leftovers (AC-C4, DEC-4738): "Trial Balance · Prepared · MD · Materiality v2 · $252,200
    · Internal Control · 7 exceptions" and "… · PN 001 · plan year Jan 1-Dec 31 · 286
    participants with balances at BOY", each part only where the viewer may read it."""
    from decimal import Decimal

    from abacus.modules.assurance import api as assurance_api
    from abacus.modules.identity import api as identity_api
    from abacus.modules.organisations import api as organisations_api
    from abacus.modules.review import api as review_api
    from abacus.modules.workpapers import api as workpapers_api

    tb_id = uuid.uuid4()

    @dataclass(frozen=True)
    class _V:
        overall: Decimal
        version_no: int

    @dataclass(frozen=True)
    class _Record:
        versions: list[_V]

    @dataclass(frozen=True)
    class _Reviewable:
        target_type: str
        target_id: uuid.UUID

    @dataclass(frozen=True)
    class _Signed:
        initials: str
        stale: bool

    @dataclass(frozen=True)
    class _Level:
        level: int
        latest: _Signed | None

    @dataclass(frozen=True)
    class _Ladder:
        levels: list[_Level]

    @dataclass(frozen=True)
    class _Plan:
        plan_year_start: date
        plan_year_end: date
        participants_boy_with_balances: int | None

    seen: list[str] = []

    async def work_items(tenant: object, engagement: object) -> list[uuid.UUID]:
        return [uuid.uuid4()]

    async def papers(tenant: object, wi: object) -> list[object]:
        return []

    async def resource(tenant: object, engagement: object) -> object:
        return object()

    async def allowed(ctx: object, action: str, resource: object) -> None:
        seen.append(action)

    async def record(ctx: object, engagement: object) -> _Record:
        return _Record([_V(Decimal(252200), 2)])

    async def reviewables(tenant: object, engagement: object) -> list[_Reviewable]:
        return [_Reviewable("workpaper", uuid.uuid4()), _Reviewable("trial_balance", tb_id)]

    async def ladder(ctx: object, target_type: str, target_id: uuid.UUID) -> _Ladder:
        assert (target_type, target_id) == ("trial_balance", tb_id)
        return _Ladder([_Level(1, _Signed("MD", False)), _Level(2, None)])

    async def exceptions(ctx: object, engagement: object) -> list[object]:
        return [object()] * 7

    async def plan(tenant: object, engagement: object) -> _Plan:
        return _Plan(date(2025, 1, 1), date(2025, 12, 31), 286)

    async def plan_number(tenant: object, entity: object) -> str:
        return "001"

    monkeypatch.setattr(sc, "work_item_ids_of", work_items)
    monkeypatch.setattr(workpapers_api, "work_item_papers", papers)
    monkeypatch.setattr(identity_api, "engagement_resource", resource)
    monkeypatch.setattr(identity_api, "authorise", allowed)
    monkeypatch.setattr(assurance_api, "materiality_record", record)
    monkeypatch.setattr(review_api, "reviewables_of", reviewables)
    monkeypatch.setattr(review_api, "sign_off_ladder", ladder)
    monkeypatch.setattr(assurance_api, "control_exceptions", exceptions)
    monkeypatch.setattr(assurance_api, "ebp_plan_facts", plan)
    monkeypatch.setattr(organisations_api, "entity_plan_number", plan_number)
    options = asyncio.run(sc.all_options(CTX))
    papers_opt = next(o for o in options if o.kind == "workpaper_set")
    _chip, lines = asyncio.run(sc.summary(CTX, papers_opt))
    assert lines[-1] == (
        "Trial Balance · Prepared · MD · Materiality v2 · $252,200 · "
        "Internal Control · 7 exceptions"
    )
    client_opt = next(o for o in options if o.kind == "client_entity")
    _chip, lines = asyncio.run(sc.summary(CTX, client_opt))
    assert lines[0] == (
        "Northwind Robotics 401(k) Plan · PN 001 · plan year Jan 1\u2013Dec 31 · 286 participants "
        "with balances at BOY"
    )
    assert {"materiality.read", "control.read", "ebp.read"} <= set(seen)


def test_ac_c4_lines_say_nothing_when_the_viewer_may_not_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.identity import api as identity_api

    async def resource(tenant: object, engagement: object) -> object:
        return object()

    async def denied(ctx: object, action: str, resource: object) -> None:
        raise identity_api.Forbidden(action, "role")

    monkeypatch.setattr(identity_api, "engagement_resource", resource)
    monkeypatch.setattr(identity_api, "authorise", denied)
    client_opt = next(o for o in asyncio.run(sc.all_options(CTX)) if o.kind == "client_entity")
    _chip, lines = asyncio.run(sc.summary(CTX, client_opt))
    assert lines == (client_opt.title, client_opt.detail)
