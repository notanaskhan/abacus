"""T-06-T42 (TASK-8911; SPEC-702 F5, AC-22 to AC-26; TXP-13; amber): other-entity workpapers.

Row acceptance: "Bluestem answers 409 return_locked on any write, and Lakeshore's allocation lands
only as a proposal a person adopts." Here: every write on a Filed or Accepted return is
`return_locked` before anything is read or written; the allocation creates a proposal and writes no
Part IX line (the adapter does, on adoption only); E10's M-2 arithmetic and the distribution rule;
E12's time-study split foots; the routes call the service.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.modules.tax import other_entities_service as oe
from abacus.modules.tax.entity_depth_errors import ReturnLocked

SRC = Path(oe.__file__).parent


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(
        tenant=SimpleNamespace(tenant_id=uuid4(), actor_kind="human"), tenant_id=uuid4(),
        user_id=uuid4(), client=None, is_support=False,
    )  # fmt: skip


@pytest.fixture
def accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    async def loaded(_ctx: object, return_id: object, _action: str) -> oe._Return:  # pyright: ignore[reportPrivateUsage]
        return oe._Return(return_id, uuid4(), "accepted", object())  # type: ignore[arg-type]  # pyright: ignore[reportPrivateUsage]

    def unreachable(*_: object, **__: object) -> object:
        raise AssertionError("nothing is read or written on a locked return")

    monkeypatch.setattr(oe, "_loaded", loaded)
    monkeypatch.setattr(oe, "tenant_session", unreachable)
    monkeypatch.setattr(oe, "uow", unreachable)


async def test_bluestem_answers_return_locked_on_explain(accepted: None) -> None:
    with pytest.raises(ReturnLocked):
        await oe.explain_item(_ctx(), uuid4(), uuid4())  # type: ignore[arg-type]


async def test_bluestem_answers_return_locked_on_the_allocation(accepted: None) -> None:
    with pytest.raises(ReturnLocked):
        await oe.start_allocation(_ctx(), uuid4())  # type: ignore[arg-type]


def test_the_m2_columns_roll_by_line() -> None:
    lines = {1: Decimal("1200000"), 2: Decimal("788200"), 3: Decimal("0"), 4: Decimal("0"),
             5: Decimal("0"), 7: Decimal("500000")}  # fmt: skip
    assert oe.column_ending(lines) == Decimal("1488200")
    assert oe.aaa_ending(lines) == Decimal("1488200")


def test_aaa_never_goes_below_zero_on_a_distribution() -> None:
    lines = {1: Decimal("100"), 2: Decimal("50"), 7: Decimal("400")}
    assert oe.aaa_ending(lines) == Decimal("0")  # the rest comes from the next column
    assert oe.column_ending(lines) == Decimal("-250")


def _line(**over: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": uuid4(), "part_ix_line": "5", "label": "Salaries", "total": Decimal("2000000"),
        "program": Decimal("0"), "management_general": Decimal("0"), "fundraising": Decimal("0"),
        "allocation_basis": "time_study",
        "time_study": {"pct": {"program": "80", "management_general": "12", "fundraising": "8"}},
    }  # fmt: skip
    base.update(over)
    return SimpleNamespace(**base)


def test_the_time_study_split_foots_and_skips_direct_lines() -> None:
    rows = [_line(), _line(allocation_basis="direct", time_study=None)]
    found = oe.allocate(rows)
    assert len(found) == 1
    _, line = found[0]
    assert (line.program, line.management_general, line.fundraising) == (
        Decimal("1600000"), Decimal("240000"), Decimal("160000"),
    )  # fmt: skip
    assert line.crossfoots


def test_percentages_that_do_not_sum_refuse() -> None:
    bad = _line(time_study={"pct": {"program": "80", "management_general": "10"}})
    with pytest.raises(ValueError):
        oe.allocate([bad])


async def test_lakeshores_allocation_lands_only_as_a_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.agents import api as agents

    line = _line()
    executed: list[str] = []
    proposals: list[dict[str, object]] = []

    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def execute(self, sql: object, *_: object) -> object:
            executed.append(str(sql))
            return SimpleNamespace(all=lambda: [line])

    class _Tx(_Session):
        session = None

        def record(self, *_: object, **__: object) -> None:
            return None

    tx = _Tx()
    tx.session = tx  # type: ignore[assignment]

    async def loaded(_ctx: object, return_id: object, _action: str) -> oe._Return:  # pyright: ignore[reportPrivateUsage]
        return oe._Return(return_id, uuid4(), "in_review", object())  # type: ignore[arg-type]  # pyright: ignore[reportPrivateUsage]

    async def start(*_: object) -> object:
        return SimpleNamespace(agent_run_id=uuid4())

    async def propose(_agent: object, **kw: object) -> object:
        proposals.append(kw)
        return uuid4()

    async def end(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(oe, "_loaded", loaded)
    monkeypatch.setattr(oe, "tenant_session", lambda _t: _Session())  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(oe, "uow", lambda _t: tx)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(agents, "start_capability_run", start)
    monkeypatch.setattr(agents, "create_proposal", propose)
    monkeypatch.setattr(agents, "end_capability_run", end)
    run = await oe.start_allocation(_ctx(), uuid4())  # type: ignore[arg-type]
    assert run.proposal_id is not None
    assert [p["kind"] for p in proposals] == ["time_study_allocation"]
    rows = proposals[0]["rows"]
    assert [r.target_type for r in rows] == ["functional_expense_line"]  # type: ignore[attr-defined]
    assert not any("UPDATE functional_expense_lines" in sql for sql in executed)


def test_the_adapter_and_target_are_registered() -> None:
    api = (SRC / "api.py").read_text(encoding="utf-8")
    assert "_other_entities.register()" in api
    service = (SRC / "other_entities_service.py").read_text(encoding="utf-8")
    assert "register_proposal_adapter(PROPOSAL_KIND, adopt_allocation)" in service


def test_the_routes_call_the_service() -> None:
    contract = (SRC / "entity_depth_contract.py").read_text(encoding="utf-8")
    for call in ("oe.aaa(", "oe.provision(", "oe.explain_item(", "oe.functional_expenses(",
                 "oe.start_allocation("):  # fmt: skip
        assert call in contract, call
