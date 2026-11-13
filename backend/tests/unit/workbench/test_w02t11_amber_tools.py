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

import abacus.api.app  # noqa: F401  # registers every module's tools
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
    monkeypatch.setattr(board, "_due", lambda r: r.due)
    monkeypatch.setattr(orgs, "firm_offices", offices)
    from abacus.kernel import clock

    monkeypatch.setattr(clock, "today", today)
    agent: Any = type("A", (), {"tenant": object()})()
    out = asyncio.run(tools.season_counts(agent, tools.SeasonIn()))
    assert (out.returns, out.open, out.done) == (3, 2, 1)
    assert sum(o.open + o.done for o in out.by_office) == out.returns
    assert [o.office for o in out.by_office] == ["Chicago", "Denver"]
    assert (out.engagements, out.engagements_with_two_returns, out.stalled) == (2, 1, 1)
    assert "client" not in str(out.model_dump()).lower()
