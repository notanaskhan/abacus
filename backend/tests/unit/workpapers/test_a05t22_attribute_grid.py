"""A-05-T22 (TASK-3212; DEC-2212): the shared attribute grid's rules.

Row acceptance: "The seed yields exactly two exceptions (rows 8 and 15) and one Needs human (row
22), and an agent can never set pass, exception or no effect." The grid's row states and counts
and the SHL-15 prefill are pinned here on EBP-03's 25 rows; the database refuses an agent's
conclusion (0642's `test_attribute_results_human_concludes`, tested with T15); the service refuses
it before the database (`mark` takes only a person's results).
"""

from __future__ import annotations

import inspect
import uuid

import pytest

from abacus.modules.workpapers import attribute_grid as g

ATTRS = (g.Attribute("entry_date", "Entry date per the plan's terms"),)


def _cell(result: str, by: str = "human") -> g.Cell:
    return g.Cell("entry_date", result, 1, None, (uuid.uuid4(),), None, by)


def _ebp03() -> g.Grid:
    rows: list[g.Row] = []
    for position in range(1, 26):
        result = {8: "exception", 15: "exception", 22: "needs_human"}.get(position, "pass")
        by = "agent" if result == "needs_human" else "human"
        rows.append(g.Row(position, uuid.uuid4(), f"NW-{1100 + position}", (_cell(result, by),)))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.state] = counts.get(r.state, 0) + 1
    return g.Grid(
        uuid.uuid4(), "ebp_eligibility", uuid.uuid4(), ATTRS, tuple(rows), 3, "0" * 64, counts
    )


def test_ac_two_exceptions_and_one_needs_human() -> None:
    found = _ebp03()
    assert found.counts == {"pass": 22, "exception": 2, "needs_human": 1}
    assert [r.position for r in found.rows if r.state == "exception"] == [8, 15]
    assert [r.position for r in found.rows if r.state == "needs_human"] == [22]


def test_ac_a_row_with_any_exception_is_an_exception() -> None:
    row = g.Row(1, uuid.uuid4(), "NW-1", (_cell("pass"), _cell("exception")))
    assert row.state == "exception"
    assert g.Row(2, uuid.uuid4(), "NW-2", ()).state == "not_started"


def test_ac_an_exception_row_prefills_shl15_with_its_anchor() -> None:
    found = _ebp03()
    row8 = next(r for r in found.rows if r.position == 8)
    prefill = g.exception_prefill(found, row8.item_id)
    assert prefill.anchor == "EBP-03!row 8"
    assert prefill.title == "Entry date per the plan's terms"
    assert len(prefill.citation_ids) == 1
    with pytest.raises(g.NotFound):
        g.exception_prefill(found, found.rows[0].item_id)  # a passing row has no draft


def test_ac_the_agent_writes_only_tested_or_needs_human() -> None:
    hints = inspect.signature(g.record_agent_result).parameters["result"].annotation
    assert "AgentResult" in str(hints)
    assert set(g.AgentResult.__args__) == {"agent_tested", "needs_human"}
    assert set(g.HumanResult.__args__) == {"pass", "exception", "no_effect"}


async def test_ac_mark_refuses_anything_but_a_persons_result() -> None:
    with pytest.raises(g.DomainInvalid):
        await g.mark(
            object(),  # pyright: ignore[reportArgumentType] -- refused before any read
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            "entry_date",
            "agent_tested",  # pyright: ignore[reportArgumentType] -- a deliberately wrong argument
            None,
        )
