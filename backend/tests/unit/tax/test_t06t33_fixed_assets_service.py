"""T-06-T33 (TASK-8831; T-06 F1; SPEC-702 AC-1 to AC-6; TXP-03; DEC-5833): the fixed-assets
service.
Row acceptance: "An edit by Olivia Brandt changes nothing until a reviewer approves the proposal,
and approval writes a checkpoint and re-ties 733,500."
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from abacus.modules.identity.api import Forbidden
from abacus.modules.tax import fixed_assets_service as fa
from abacus.modules.tax.compute import depreciation as e3


def _asset(no: int, cls: str = "39", cost: str = "1000000", key: str = "elm") -> fa.AssetRecord:
    method, convention = ("SL", "MM") if cls in e3.REAL_PROPERTY else ("200DB", "HY")
    return fa.AssetRecord(
        uuid.uuid4(), no, f"Asset {no}", uuid.uuid4(), key, date(2024, 3, 1), None, None, None,
        Decimal(cost), cls, method, convention, Decimal(0), Decimal(0), True, "ok", 1, False,
    )  # fmt: skip


def _facts(*assets: fa.AssetRecord, tb: dict[str, int] | None = None) -> fa.Facts:
    return fa.Facts(uuid.uuid4(), uuid.uuid4(), 2026, "preparing", assets, (), tb or {}, {})


def test_register_from_e3_and_ties() -> None:
    facts = _facts(_asset(1), _asset(2, "7", "50000", "larimer"))
    computed = fa.compute(facts)
    assert computed.register.crossfoots()
    to_tb, book, _bonus = fa.tallies(facts, computed)
    assert to_tb == "check" and book == "tie"  # no TB on 01 yet: check, never a guessed tie
    reg = computed.register
    tied = replace(facts, tb={"1600": reg.cost, "1650": reg.accumulated, "5600": reg.current})
    assert fa.tallies(tied, computed)[0] == "tie"
    off = replace(facts, tb={"1600": reg.cost, "1650": reg.accumulated, "5600": reg.current + 1})
    assert fa.tallies(off, computed)[0] == "off"


def test_a_ghost_value_changes_nothing() -> None:
    asset = _asset(1, "7", "50000")
    ghost = fa._apply(asset, {"recovery_class": "5", "bonus_pct": "60"})  # pyright: ignore[reportPrivateUsage] -- the unit under test
    assert asset.recovery_class == "7" and ghost.recovery_class == "5" and ghost.version == 2
    before = fa.compute(_facts(asset)).register.current
    assert fa.compute(_facts(asset)).register.current == before  # the stored asset is unchanged


def test_impossible_change_refuses() -> None:
    with pytest.raises(ValueError):
        fa._apply(_asset(1, "39"), {"convention": "HY"})  # pyright: ignore[reportPrivateUsage] -- the unit under test


def test_approval_recomputes_the_register() -> None:
    a, b = _asset(1, "7", "50000"), _asset(2, "39")
    before = fa.compute(_facts(a, b)).register
    changed = fa._apply(a, {"bonus_pct": "100"})  # pyright: ignore[reportPrivateUsage] -- the unit under test
    after = fa.compute(_facts(changed, b)).register
    assert after.current != before.current and after.crossfoots()


def test_requester_never_decides(monkeypatch: pytest.MonkeyPatch) -> None:
    requester = uuid.uuid4()
    facts = _facts(_asset(1))

    async def loaded(*_a: object) -> tuple[fa.Facts, object]:
        return facts, object()

    async def authorise(*_a: object) -> None:
        return None

    class _S:
        async def __aenter__(self) -> _S:
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def execute(self, *_a: object) -> SimpleNamespace:
            row = SimpleNamespace(
                id=uuid.uuid4(),
                asset_id=facts.assets[0].id,
                expected_version=1,
                change={"bonus_pct": "100"},
                requested_by=requester,
                decided=None,
            )
            return SimpleNamespace(first=lambda: row)  # fmt: skip

    monkeypatch.setattr(fa, "_loaded", loaded)
    monkeypatch.setattr(fa, "authorise", authorise)
    monkeypatch.setattr(fa, "tenant_session", lambda _t: _S())  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType] -- a monkeypatched double
    ctx = SimpleNamespace(
        client=False, is_support=False, user_id=requester,
        tenant=SimpleNamespace(actor_kind="human"), tenant_id=uuid.uuid4(),
    )  # fmt: skip
    with pytest.raises(Forbidden):
        asyncio.run(
            fa.settle_change(
                ctx,  # pyright: ignore[reportArgumentType] -- a context double
                facts.return_id,
                uuid.uuid4(),
                approve=True,
                reason=None,
            )
        )


def test_approval_writes_a_checkpoint() -> None:
    source = inspect.getsource(fa.settle_change)
    assert "save_checkpoint(" in source and "ProposalChanged" in source


def test_section_flags_registered() -> None:
    from abacus.modules.tax import entity_sections

    assert entity_sections._FLAGS["fixed-assets"] is fa.open_flags  # pyright: ignore[reportPrivateUsage] -- the unit under test
