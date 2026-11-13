"""W-02-T11 (TASK-7713; W-02 §6; C17; DEC-4716): the Workbench's four amber tools.

Row acceptance: "Totals foot; out-of-scope refused; tool_selection passes." Each tool is on C17
with its description prompt and kind; `tax.season_counts` returns counts only and foots (open +
done = returns; offices foot to the returns); `binders.read` counts by code.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest

import abacus.api.app  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every module's tools
from abacus.modules.agents.tools.registry import tool

NAMES = {
    "tax.season_counts": "compute",
    "binders.read": "read",
    "workpapers.read_section": "read",
    "assurance.read_materiality": "read",
}


@pytest.mark.parametrize(("name", "kind"), sorted(NAMES.items()))
def test_each_tool_is_on_c17_with_its_description_prompt(name: str, kind: str) -> None:
    found = tool(name)
    assert found.kind == kind
    assert found.description == f"tool.{name}@v1"
    assert found.data_class == "confidential"  # never tri (§7216 design for J11)


@dataclass(frozen=True)
class _R:
    status: str
    due: date | None


@dataclass(frozen=True)
class _F:
    office_id: uuid.UUID | None
    engagement_id: uuid.UUID


def test_season_counts_foot_and_carry_no_return_content(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.organisations import api as orgs
    from abacus.modules.tax import board, tools

    chicago, denver = uuid.uuid4(), uuid.uuid4()
    e1, e2 = uuid.uuid4(), uuid.uuid4()
    rows = [
        (_R("filed", None), _F(chicago, e1)),
        (_R("in_prep", date(2026, 9, 1)), _F(chicago, e1)),
        (_R("in_review", date(2026, 10, 15)), _F(denver, e2)),
    ]

    async def fake_board(ctx: object, year: object) -> Any:  # noqa: ANN401 -- Any: the board
        return type("B", (), {"tax_year": 2025, "rows": rows})()

    async def offices(tenant: object) -> list[tuple[uuid.UUID, str]]:
        return [(chicago, "Chicago"), (denver, "Denver")]

    async def today(tenant: object) -> date:
        return date(2026, 9, 14)

    monkeypatch.setattr(board, "_board", fake_board)

    def due_of(r: _R) -> date | None:
        return r.due

    monkeypatch.setattr(board, "_due", due_of)
    monkeypatch.setattr(orgs, "firm_offices", offices)
    from abacus.kernel import clock

    monkeypatch.setattr(clock, "today", today)
    agent: Any = type("A", (), {"tenant": object()})()  # Any: a test double
    out = asyncio.run(tools.season_counts(agent, tools.SeasonIn(tax_year=2025)))
    assert (out.returns, out.open, out.done) == (3, 2, 1)
    assert sum(o.open + o.done for o in out.by_office) == out.returns
    assert [o.office for o in out.by_office] == ["Chicago", "Denver"]
    assert (out.engagements, out.engagements_with_two_returns, out.stalled) == (2, 1, 1)
    assert "client" not in str(out.model_dump()).lower()
    # S41 end pass (DEC-4733): the frozen suite's arguments filter and group by code.
    only = asyncio.run(
        tools.season_counts(
            agent, tools.SeasonIn(tax_year=2025, group_by=["office"], status_in=["in_review"])
        )
    )
    assert (only.returns, only.by_status) == (1, [])
    assert [o.office for o in only.by_office] == ["Denver"]


def test_tool_inputs_match_the_frozen_workbench_suite() -> None:
    """S41 end pass (DEC-4733): each W-02-T11 tool takes exactly the arguments the frozen
    `evals/workbench_assistant/suite.yaml` records (required and accepted)."""
    from pathlib import Path

    import yaml

    from abacus.modules.assurance.agent_tools import MaterialityIn
    from abacus.modules.requests.agent_tools import BindersIn
    from abacus.modules.tax import tools
    from abacus.modules.workpapers.agent_tools import SectionIn

    suite = yaml.safe_load(
        (Path(__file__).resolve().parents[4] / "evals/workbench_assistant/suite.yaml").read_text()
    )
    models = {
        "tax.season_counts": tools.SeasonIn,
        "binders.read": BindersIn,
        "workpapers.read_section": SectionIn,
        "assurance.read_materiality": MaterialityIn,
    }
    for name, model in models.items():
        spec = suite["defaults"]["tool_args"][name]
        fields = model.model_fields
        assert set(fields) == set(spec["accepted"]), name
        assert {k for k, f in fields.items() if f.is_required()} == set(spec["required"]), name


def test_binders_read_answers_the_seasons_visible_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """S41 gaps (AC-A6, DEC-4734): `season_total` is BND-01's visible count for the season (the
    index applies walls), the page narrows to `binder_ids`, and the tiles come with it."""
    from abacus.kernel.listing import ListPage
    from abacus.modules.requests import agent_tools as req
    from abacus.modules.requests import binder_index

    @dataclass(frozen=True)
    class _Row:
        id: uuid.UUID
        name: str
        client_name: str
        kind: str
        status: str
        total_count: int
        done_count: int
        last_client_activity_at: None = None

    a, b = uuid.uuid4(), uuid.uuid4()
    seen: list[binder_index.IndexFilters] = []

    async def list_binders(
        ctx: object, filters: binder_index.IndexFilters, cursor: object, limit: object
    ) -> object:
        seen.append(filters)
        return ListPage[Any](  # Any: a test double row
            items=[_Row(a, "2025 Binder", "Feld", "tax", "published", 13, 11),
                   _Row(b, "2025 Binder", "Iyer", "tax", "published", 9, 2)],
            total=241, counts={"published": 180, "complete": 61},
        )  # fmt: skip

    monkeypatch.setattr(binder_index, "list_binders", list_binders)
    out = asyncio.run(req.read_binders(object(), req.BindersIn(tax_year=2025, binder_ids=[b])))  # type: ignore[arg-type] -- a test double stands in for the run's context
    assert (out.season_total, out.total, [r.id for r in out.binders]) == (241, 1, [b])
    assert out.by_status == {"published": 180, "complete": 61}
    assert seen[0].season == "TY2025"
