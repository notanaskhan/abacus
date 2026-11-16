"""T-07-T27 (TASK-8326; ADR-078, written in N's session; implementer AY): the Thornbury estate's
goldens against the estate engine (T-07-T22), each citing its TXT-04 artboard, plus the TXT-03 and
TXT-04 rules that are a person's only.

ac-test-author: notanaskhan
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import fiduciary_beneficiaries as fb
from abacus.modules.tax.compute import estate as e

D = Decimal
ASSETS = (
    e.Asset("A", "A", D("3850000"), D("3790000"), "stepped_up"),
    e.Asset("B", "B", D("8240000"), D("7965000"), "stepped_up"),
    e.Asset("C", "C", D("412000"), D("412000"), "stepped_up"),
    e.Asset("D", "D", D("1000000"), D("1000000"), "non_probate_excluded"),
    e.Asset("F", "F", D("186000"), D("186000"), "stepped_up"),
    e.Asset("I", "I", D("2712000"), D("2640000"), "ird_no_step_up"),
)
DEDUCTIONS = (
    e.Deduction("funeral", "J_funeral", D("28500")),
    e.Deduction("admin", "J_administration", D("240000")),
    e.Deduction("debts", "K", D("131500")),
    e.Deduction("charity", "O", D("500000")),
)
GIFTS = (
    e.Gift("2023", 2023, D("1217000")),
    e.Gift("2024", 2024, D("18000")),
    e.Gift("2025", 2025, D("19000")),
    e.Gift("2026", 2026, D("19000")),
)
THORNBURY = e.EstateInputs(
    2026, ASSETS, DEDUCTIONS, GIFTS, dsue=D("3000000"), residence_state="IL"
)


def test_golden_txt04_c_tentative_tax_is_345_800_plus_40_percent_of_15_700_000() -> None:
    """TXT-04 c: tentative tax base 16,700,000 → 6,625,800 (345,800 + 40% x 15,700,000)."""
    r = e.compute(THORNBURY)
    assert r.tentative_tax_base == D("16700000.00")
    assert r.tentative_tax == D("345800") + D("0.40") * D("15700000")


def test_golden_txt04_c_credit_on_18_000_000_leaves_no_tax() -> None:
    """TXT-04 c: applicable exclusion 18,000,000 (BEA 15,000,000 + DSUE 3,000,000) → credit
    7,145,800, net estate tax 0."""
    r = e.compute(THORNBURY)
    assert r.applicable_exclusion == D("18000000.00")
    assert r.credit == D("7145800.00")
    assert r.net_tax == D("0.00")


def test_golden_txt04_c_without_dsue_the_tax_is_680_000() -> None:
    """TXT-04 c side card "Without DSUE": credit 5,945,800 → tax 680,000."""
    r = e.compute(THORNBURY)
    assert (r.credit_without_dsue, r.tax_without_dsue) == (D("5945800.00"), D("680000.00"))


def test_golden_txt04_a_alternate_valuation_is_unavailable() -> None:
    """TXT-04 a note: AVD is available only if it reduces both the gross estate and the tax; with
    DSUE no tax is due, so it is not."""
    assert e.compute(THORNBURY).avd_available is False


def test_golden_txt04_filing_is_required_17_600_000_over_15_000_000() -> None:
    """Gross estate 16,400,000 + adjusted taxable gifts 1,200,000 = 17,600,000 > 15,000,000."""
    r = e.compute(THORNBURY)
    assert r.filing_threshold_amount == D("17600000.00")
    assert r.filing_required and r.bea == D("15000000.00")
    assert r.state_required is True  # Illinois: above its exclusion; no figure shown (TXT-04 c)


def _agent() -> AuthContext:
    who = uuid.uuid4()
    return AuthContext(TenantContext(uuid.uuid4(), "agent", str(who), who), who, uuid.uuid4(),
                       None, datetime.now(UTC))  # fmt: skip


async def test_ac_txt03_the_election_is_a_persons_only() -> None:
    with pytest.raises(Forbidden):
        await fb.record_election(_agent(), uuid.uuid4(), 2026, status="not_made", amount=None,
                                 paid_on=None, decision_owner_contact_id=uuid.uuid4())  # fmt: skip
