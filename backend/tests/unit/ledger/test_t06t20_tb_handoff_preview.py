"""T-06-T20 (SPEC-702 F6; DEC-5631): the hand-off preview is code's and pins what the person saw;
an unregistered source kind refuses (fail closed). The DB paths run in the end-pass suite."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.ledger import tb_handoff as h

SRC = Path(h.__file__).resolve().parents[1]

D = Decimal
S = UUID("00000000-0000-4000-8000-00000000a001")


def _preview(**kw: object) -> h.Preview:
    accounts = [h.AccountIn(f"{1000 + i}", f"Account {i}", D("100")) for i in range(128)]
    prior = {a.account_no: "L1" for a in accounts[:121]}
    suggestions = {a.account_no: ("L2", S) for a in accounts[121:126]}
    return h.preview(
        accounts,
        prior_codes=prior,
        suggestions=suggestions,
        book_income_before_tax=D("3100000"),
        income_tax_expense=D("750000"),
        schedules=["fixed_assets", "accrued_liabilities", "passed_adjustments"],
        tax_items=[h.TaxItem("passed_adjustment", {"entry": "AJE-3"}, D("68400"), True)],
    )


def test_granite_peak_travels_121_5_2_and_book_income_2_350_000() -> None:
    p = _preview()
    assert dict(p.counts) == {"total": 128, "prior_year": 121, "suggested": 5, "blank": 2}
    assert p.book_income["net_income_per_books"] == "2350000"
    assert all(a.needs_review for a in p.accounts if a.travel != "prior_year")


def test_the_hash_is_stable_and_moves_with_any_change() -> None:
    assert _preview().preview_hash == _preview().preview_hash
    changed = h.preview(
        [h.AccountIn("1000", "Cash", D("1"))], prior_codes={}, suggestions={},
        book_income_before_tax=D("0"), income_tax_expense=D("0"), schedules=[], tax_items=[],
    )  # fmt: skip
    assert changed.preview_hash != _preview().preview_hash


async def test_an_unregistered_source_kind_is_not_released() -> None:
    tenant = TenantContext(tenant_id=S, actor_kind="human", actor_id=str(S))
    assert not await h.source_released(tenant, "nobody_registered_this", S)


def test_the_three_source_kinds_have_their_owners_gates() -> None:
    # The owners' gate modules only (importing assurance.api would also swap G5's provider for
    # the rest of the worker); each api.py calls `register()` at import (source checked below).
    from abacus.modules.assurance import handoff_gate as assurance_gate
    from abacus.modules.closes import handoff_gate as closes_gate

    assurance_gate.register()
    closes_gate.register()
    gates = h._GATES  # pyright: ignore[reportPrivateUsage] -- the registry under test
    assert gates["audit_release"] is assurance_gate.report_released
    assert gates["review_release"] is assurance_gate.report_released
    assert gates["close_lock"] is closes_gate.close_locked
    for module in ("assurance", "closes"):
        source = (SRC / module / "api.py").read_text(encoding="utf-8")
        assert "_handoff_gate.register()" in source
