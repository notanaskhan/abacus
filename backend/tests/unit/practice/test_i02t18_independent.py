"""I-02-T18 (ADR-078; TASK-7916): independent acceptance tests for I-02-T10 (`practice.today`, the
Today read model), written from SPEC-654 and the row's acceptance, not from the implementation.

Row acceptance: "The suite is committed before T10 is approved and passes on main without edits
by the implementing session." It checks count equality with the gates HOME-01 and HOME-02 count
(over random gate sets), group footing, Needs-you-first and card order, the next business day,
and that no count carries model text.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.practice.today import assembly as a

TODAY = date(2026, 9, 14)  # Monday
KINDS = ("decision", "sign_off", "approval_send", "signature", "needs_attention")


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        cast(Any, "partner"),  # Any: a firm role name stand-in
        None,
    )


def _item(cell: str, due: int | None, blocked: bool, engagement: uuid.UUID) -> a.Item:
    return a.Item(
        gate_id=uuid.uuid4(), kind=cell, cell=cell, engagement_id=engagement,
        work_item_id=uuid.uuid4(), due_on=None if due is None else TODAY + timedelta(days=due),
        blocked=blocked, state="blocked" if blocked else "open", title=f"{cell} gate",
        context="code context", route="/home/approvals",
    )  # fmt: skip


def _wire(monkeypatch: pytest.MonkeyPatch, items: list[a.Item]) -> None:
    from abacus.kernel import clock
    from abacus.modules.practice import due_dates

    async def today(*_a: object) -> date:
        return TODAY

    async def items_of(*_a: object) -> list[a.Item]:
        return items

    async def labels(*_a: object) -> dict[uuid.UUID, str]:
        return {}

    async def briefings(*_a: object) -> dict[uuid.UUID, object]:
        return {}

    async def names(*_a: object) -> dict[uuid.UUID, str]:
        return {}

    async def next_day(on: date, n: int) -> date:
        return on + timedelta(days=n)

    monkeypatch.setattr(clock, "today", today)
    monkeypatch.setattr(a, "_items", items_of)
    monkeypatch.setattr(a, "_labels", labels)
    monkeypatch.setattr(a, "_briefings", briefings)
    monkeypatch.setattr(a, "names_of", names)
    monkeypatch.setattr(due_dates, "add_business_days", next_day)


item_strategy = st.tuples(
    st.sampled_from(KINDS), st.one_of(st.none(), st.integers(-3, 10)), st.booleans()
)


@settings(max_examples=40, deadline=None)
@given(st.lists(item_strategy, max_size=25))
def test_counts_equal_the_gates_for_any_gate_set(spec: list[tuple[str, int | None, bool]]) -> None:
    """I-COUNT: each cell equals the number of gates in its band; overdue equals the gates due
    before today; the items total equals the gates (HOME-01's number)."""
    mp = pytest.MonkeyPatch()
    try:
        e = uuid.uuid4()
        items = [_item(c, d, b, e) for c, d, b in spec]
        _wire(mp, items)
        vm = asyncio.run(a.assemble(_ctx()))
    finally:
        mp.undo()
    by_cell = {c.kind: c.count for c in vm.cells}
    for kind in KINDS:
        assert by_cell[kind] == sum(1 for i in items if i.cell == kind)
    assert by_cell["overdue"] == sum(1 for i in items if i.due_on and i.due_on < TODAY)
    assert vm.items == len(items)
    assert all(isinstance(c.count, int) for c in vm.cells)


def test_groups_foot(monkeypatch: pytest.MonkeyPatch) -> None:
    e = uuid.uuid4()
    items = [
        _item("sign_off", 1, False, e), _item("sign_off", 1, True, e),
        _item("decision", -1, False, e), _item("approval_send", None, True, e),
    ]  # fmt: skip
    _wire(monkeypatch, items)
    vm = asyncio.run(a.assemble(_ctx()))
    groups = {g.key: g.count for g in vm.groups}
    assert groups["late"] == 1
    assert groups["due_tomorrow"] == 2
    assert groups["ready_for_signoff"] == 1
    assert groups["needs_attention"] == 2


def test_needs_you_first_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Overdue first, then blocked, then nearest due date; three rows."""
    e = uuid.uuid4()
    late = _item("decision", -2, False, e)
    blocked = _item("sign_off", 5, True, e)
    soon = _item("approval_send", 1, False, e)
    later = _item("approval_send", 4, False, e)
    _wire(monkeypatch, [later, soon, blocked, late])
    vm = asyncio.run(a.assemble(_ctx()))
    assert [r.gate_id for r in vm.needs_you_first] == [late.gate_id, blocked.gate_id, soon.gate_id]


def test_cards_ordered_by_most_urgent_row(monkeypatch: pytest.MonkeyPatch) -> None:
    calm, urgent = uuid.uuid4(), uuid.uuid4()
    _wire(monkeypatch, [_item("sign_off", 6, False, calm), _item("decision", -1, False, urgent)])
    vm = asyncio.run(a.assemble(_ctx()))
    assert [c.engagement_id for c in vm.cards] == [urgent, calm]


def test_next_business_day_skips_a_holiday() -> None:
    # The holiday roll is the platform's table (an integration read); the arithmetic is the
    # kernel's, given that roll.
    from abacus.kernel.calendar import add_business_days

    friday_before_labor_day = date(2026, 9, 4)
    labor_day = frozenset({date(2026, 9, 7)})
    assert add_business_days(friday_before_labor_day, 1, labor_day) == date(2026, 9, 8)
    assert add_business_days(friday_before_labor_day, 1, frozenset()) == date(2026, 9, 7)


def test_no_model_text_in_any_count_or_lead_fact(monkeypatch: pytest.MonkeyPatch) -> None:
    e = uuid.uuid4()
    _wire(monkeypatch, [_item("decision", 1, True, e)])
    vm = asyncio.run(a.assemble(_ctx()))
    for fact in vm.lead_facts:
        assert all(isinstance(v, int | str) for v in fact.values.values())
        assert all(isinstance(r, uuid.UUID) for r in fact.refs)
    assert vm.status in ("ready", "building")


def test_forced_build_limit() -> None:
    from abacus.modules.agents.briefing import dispatch

    assert dispatch.MAX_FORCED == 3
    import inspect

    assert "RebuildLimit" in inspect.getsource(dispatch.ensure_briefings)
