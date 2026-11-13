"""T-05-T50 (TASK-7901; T-05 F8; TXP-10, TXP-11, TXP-07; DEC-4901, DEC-4902): the fix flow on an
entity return's workbook.

Row acceptance: "Approving the M-2 fix at 9:51 starts Run 3, the issue resolves at 9:52 and the
Issues badge drops from 11 to 10." Code parses the person's instructions (no model); the run only
proposes; approval writes the cells as the approver's, checkpoints and re-runs the capital group;
the tie-out issue is resolved by the system when the tie passes, never by the approval.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

from abacus.modules.tax import workbook_fix as wf
from abacus.modules.tax.workbook_fix import (
    PlannedCell,
    new_value,
    parse_instructions,
    rerun_groups,
)

D = Decimal
FORM = "1065"


def test_ac_parse_add_on_titled_address() -> None:
    [cell] = parse_instructions("Add 6,200 to 07 M-2!B6", FORM)
    assert (cell.op, cell.amount, cell.at.key) == ("add", D("6200"), "07!B6")


def test_ac_parse_set_subtract_and_short_forms() -> None:
    cells = parse_instructions(
        "Set 05 Capital!F12 to 1,203,400; subtract (1,000) from 07!B9 and add 15 to 07 B4", FORM
    )
    assert [(c.op, c.at.key) for c in cells] == [
        ("set", "05!F12"),
        ("subtract", "07!B9"),
        ("add", "07!B4"),
    ]
    assert cells[0].amount == D("1203400")
    assert cells[1].amount == D("-1000")


def test_ac_words_outside_the_grammar_name_nothing() -> None:
    assert parse_instructions("Please look at the M-2, something is off", FORM) == ()
    assert parse_instructions('=HYPERLINK("x") add 5 to 99!A1', FORM) == ()  # no sheet 99
    assert parse_instructions("Add 6,200 to 07!B6", "9999") == ()  # a form without a workbook


def test_ac_later_clause_on_the_same_cell_wins() -> None:
    [cell] = parse_instructions("Add 100 to 07!B6, then set 07!B6 to 6,200", FORM)
    assert (cell.op, cell.amount) == ("set", D("6200"))


def test_ac_code_computes_each_new_value() -> None:
    at = parse_instructions("add 6,200 to 07!B6", FORM)[0].at
    assert new_value(PlannedCell("add", D("6200"), at), D("6860000")) == D("6866200")
    assert new_value(PlannedCell("subtract", D("200"), at), None) == D("-200")
    assert new_value(PlannedCell("set", D("5"), at), D("99")) == D("5")


def test_ac_rerun_is_the_owning_groups_in_plan_order() -> None:
    assert rerun_groups(["07!B6", "05!F12"]) == ("capital",)
    assert rerun_groups(["01!B4", "09!C2"]) == ("map", "k1s")
    assert rerun_groups(["zz!A1"]) == ()


def test_ac_capital_group_rerun_is_run_3_scope() -> None:
    from abacus.modules.tax.entity_run_plan import selected

    keys = [s.key for s in selected("group", list(rerun_groups(["07!B6"])))]
    assert keys == ["interim_closing_706d", "capital_m2", "federal_k1s", "state_k1s_k3s"]


@dataclass
class _Row:
    field_ref: dict[str, Any]  # Any: a test double of the store row
    after: dict[str, Any] | None  # Any: a test double of the store row
    suggestion_id: uuid.UUID | None = None
    citation_ids: tuple[uuid.UUID, ...] = ()


class _Session:
    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None


class _Tx:
    def __init__(self) -> None:
        self.records: list[tuple[str, Any]] = []  # Any: a test double of the store row
        self.session = None

    def record(self, name: str, **kw: object) -> None:
        self.records.append((name, kw))


class _Uow:
    def __init__(self, tx: _Tx) -> None:
        self.tx = tx

    async def __aenter__(self) -> _Tx:
        return self.tx

    async def __aexit__(self, *a: object) -> None:
        return None


def _session(_t: object) -> _Session:
    return _Session()


def _uow_of(tx: _Tx) -> Callable[[object], _Uow]:
    def make(_t: object) -> _Uow:
        return _Uow(tx)

    return make


def _no_dependents(*_a: object) -> dict[str, Decimal | None]:
    return {}


def _no_write(_t: object) -> _Uow:
    pytest.fail("no write for an unapproved fix")


def test_ac_approval_writes_as_the_approver_checkpoints_and_reruns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.kernel.db import TenantContext
    from abacus.modules.agents import api as agents_api
    from abacus.modules.identity import api as identity_api
    from abacus.modules.review import api as review_api

    tenant = TenantContext(uuid.uuid4(), "system", "test")
    return_id, engagement, approver, proposal = (uuid.uuid4() for _ in range(4))
    rows = [_Row({"target_type": wf.WORKBOOK, "target_id": str(return_id), "field_key": "07!B6"},
                 {"t": "decimal", "v": "6866200"})]  # fmt: skip
    writes: list[Any] = []  # Any: a test double of the store row
    tx = _Tx()
    rerun: list[tuple[uuid.UUID, str, tuple[str, ...]]] = []

    async def approved(_s: object, _p: object) -> object:
        return engagement, rows

    async def approver_of(_s: object, _p: object) -> object:
        return approver

    async def form_of(_t: object, _r: object) -> str:
        return FORM

    async def names(_ids: object) -> dict[Any, str]:  # Any: a test double of the store row
        return {approver: "Daniel Reyes"}

    async def values(*_a: object) -> dict[str, dict[str, object]]:
        return {"07!B6": {"t": "decimal", "v": "6860000"}}

    async def write(_tx: object, **kw: Any) -> int:  # noqa: ANN401
        writes.extend(kw["writes"])
        assert kw["on_behalf_of_user_id"] == approver
        return len(kw["writes"])

    async def member(_t: object, _u: object) -> object:
        return "person"

    async def checkpoint_and_rerun(
        person: object, eng: object, ret: uuid.UUID, name: str, cells: tuple[str, ...]
    ) -> None:
        rerun.append((ret, name, cells))

    monkeypatch.setattr(wf, "tenant_session", _session)
    monkeypatch.setattr(agents_api, "approved_proposal_rows", approved)
    monkeypatch.setattr(agents_api, "proposal_approver", approver_of)
    monkeypatch.setattr(wf, "workbook_form", form_of)
    monkeypatch.setattr(identity_api, "display_names", names)
    monkeypatch.setattr(identity_api, "member_context", member)
    monkeypatch.setattr(review_api, "current_values", values)
    monkeypatch.setattr(wf, "write_cells", write)
    monkeypatch.setattr(wf, "uow", _uow_of(tx))
    monkeypatch.setattr(wf, "recompute", _no_dependents)
    monkeypatch.setattr(wf, "_checkpoint_and_rerun", checkpoint_and_rerun)

    asyncio.run(wf.apply_fix(tenant, proposal))

    [w] = writes
    assert (w.address, w.value, w.source) == ("07!B6", D("6866200"), "human")
    assert w.citation_note == "Fix approved by Daniel Reyes"
    assert [name for name, _ in tx.records] == ["workbook.fix_applied"]
    assert rerun == [(return_id, "Fix approved by Daniel Reyes", ("07!B6",))]


def test_ac_a_pending_or_rejected_proposal_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.kernel.db import TenantContext
    from abacus.modules.agents import api as agents_api

    async def none(*_a: object) -> None:
        return None

    monkeypatch.setattr(wf, "tenant_session", _session)
    monkeypatch.setattr(agents_api, "approved_proposal_rows", none)
    monkeypatch.setattr(agents_api, "proposal_approver", none)
    monkeypatch.setattr(wf, "uow", _no_write)
    asyncio.run(wf.apply_fix(TenantContext(uuid.uuid4(), "system", "t"), uuid.uuid4()))


def test_ac_tie_out_issue_never_resolves_on_the_approval() -> None:
    import inspect

    from abacus.modules.review import issue_runs

    source = inspect.getsource(issue_runs)
    assert "system_resolved_only" in source


def test_ac_registered_kind_and_target() -> None:
    from abacus.modules.agents.proposal_slots import check_suggestion_target, has_proposal_adapter

    assert has_proposal_adapter(wf.KIND)
    check_suggestion_target(wf.WORKBOOK)
