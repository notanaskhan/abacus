"""T-05-T53 (TASK-7904; T-05 F12; TXP-10, TXP-07, TAX-05, SHL-12 h; DEC-4907): the entity
return's final-approval guards (red).

Row acceptance: "Daniel's final approval lists each blocker in words until all clear, and an agent
principal is refused."
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.tax import approval
from abacus.modules.tax import entity_guards as eg

_RIDGELINE_OFF: dict[str, dict[str, object]] = {
    "05!A2": {"t": "text", "v": "Meera Shah"},
    "05!B2": {"t": "decimal", "v": "2000000"},
    "05!C2": {"t": "decimal", "v": "0"},
    "05!D2": {"t": "decimal", "v": "0"},
    "05!E2": {"t": "decimal", "v": "4866200"},
    "05!F2": {"t": "decimal", "v": "6866200"},
    "07!B9": {"t": "decimal", "v": "6860000"},
}


class _Session:
    def __init__(self, form: str) -> None:
        self.form = form

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, stmt: object, params: object) -> object:
        if "form" in str(stmt):
            return _Result([SimpleNamespace(form=self.form, engagement_id=uuid.uuid4())])
        return _Result([])


class _Result:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows

    def first(self) -> SimpleNamespace | None:
        return self.rows[0] if self.rows else None

    def __iter__(self):  # noqa: ANN204 -- a result's rows
        return iter(self.rows)


def _patch(monkeypatch: pytest.MonkeyPatch, *, unmapped: int | None, approved: bool,
           active: bool, form: str = "1065") -> None:  # fmt: skip
    from abacus.modules.agents import api as agents_api
    from abacus.modules.review import api as review_api
    from abacus.modules.tax import entity_gates

    async def unmapped_accounts(*_a: object) -> int | None:
        return unmapped

    async def allocation(*_a: object) -> bool:
        return approved

    async def values(*_a: object) -> dict[str, dict[str, object]]:
        return dict(_RIDGELINE_OFF)

    async def runs(*_a: object) -> list[SimpleNamespace]:
        return [SimpleNamespace(active=active, run_id=uuid.uuid4())]

    def session(_t: object) -> _Session:
        return _Session(form)

    monkeypatch.setattr(eg, "tenant_session", session)
    monkeypatch.setattr(entity_gates, "unmapped_accounts", unmapped_accounts)
    monkeypatch.setattr(entity_gates, "allocation_approved", allocation)
    monkeypatch.setattr(review_api, "current_values", values)
    monkeypatch.setattr(agents_api, "work_item_runs", runs)


def _kinds(monkeypatch: pytest.MonkeyPatch, **kw: object) -> list[str]:
    _patch(monkeypatch, **kw)  # type: ignore[arg-type] -- the test's keyword set
    tenant = TenantContext(uuid.uuid4(), "human", "t")
    return [b.kind for b in asyncio.run(eg.entity_blockers(tenant, uuid.uuid4()))]


def test_ac_each_blocker_until_all_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    kinds = _kinds(monkeypatch, unmapped=3, approved=False, active=True)
    assert kinds == [
        "unmapped_accounts",
        "allocation_structure_not_approved",
        "tie_out_off_unacknowledged",
        "workbook_run_in_progress",
    ]
    for kind in kinds:
        assert approval.blocker_words(kind) != "A check blocks final approval."


def test_ac_no_trial_balance_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "trial_balance_missing" in _kinds(
        monkeypatch, unmapped=None, approved=True, active=False
    )


def test_ac_not_an_entity_return_adds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _kinds(monkeypatch, unmapped=3, approved=False, active=True, form="1040") == []


def test_ac_agent_principal_is_refused() -> None:
    from abacus.modules.identity.api import Forbidden

    agent_like = SimpleNamespace(
        client=False, is_support=False, tenant=TenantContext(uuid.uuid4(), "agent", "run:1")
    )
    with pytest.raises(Forbidden):
        approval._human(agent_like)  # type: ignore[arg-type] -- layer 3 is the thing tested


def test_ac_provider_registered() -> None:

    assert eg.KIND in approval._PROVIDERS  # pyright: ignore[reportPrivateUsage] -- the registry is the thing tested
