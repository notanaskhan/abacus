"""A-05-T30 (TASK-3257; SPEC-640; DEC-2237): the late-remittance service.

Row acceptance: "Recording the Sep 30 correction changes EBP-04f, the 4a preview and the AUD-27
PT card together, from one row." The three readers share `ebp_remittances.late_remittances`; the
correction moves the row's state by a person's event with evidence only.
"""

from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from abacus.modules.assurance import api, ebp_contract, ebp_remittances
from abacus.modules.assurance.ebp_remittances import LateRemittance


def _late(principal: str, status: str = "found") -> LateRemittance:
    return LateRemittance(
        id=uuid4(),
        payroll_date=date(2025, 12, 26),
        deposited_on=date(2026, 1, 9),
        principal=Decimal(principal),
        business_days=9,
        business_days_late=7,
        calendar_days=14,
        lost_earnings=Decimal("64.38"),
        excise_exposure=Decimal("9.66"),
        status=status,
        form_5330="exposure",
        finding_id=None,
        version=1,
    )


def test_line_4a_is_the_late_deferrals_by_code() -> None:
    assert ebp_remittances.schedule_h_4a([_late("33540.00")]) == Decimal("33540.00")
    assert ebp_remittances.schedule_h_4a([]) == Decimal(0)


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_one_reader_serves_ebp_04f_the_4a_preview_aud_27_and_ebp_07() -> None:
    assert api.late_remittances is ebp_remittances.late_remittances
    for route in (ebp_contract.ebp_late_remittances_route, ebp_contract.ebp_schedule_4a_route):
        assert "ebp_remittances.late_remittances" in inspect.getsource(route)


def test_the_api_word_for_pte_2002_51_is_not_required() -> None:
    assert ebp_remittances._api_form_5330("not_required_pte_2002_51") == "not_required"  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    assert ebp_remittances.FORM_5330["not_required"] == "not_required_pte_2002_51"


def test_the_established_practice_is_the_due_dates_lag() -> None:
    out = ebp_contract._late_out(_late("33540.00"))  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    assert (out.business_days, out.established_practice_days) == (9, 2)


@pytest.mark.asyncio
async def test_a_correction_without_evidence_is_refused_before_any_write() -> None:
    with pytest.raises(ebp_remittances.CorrectionEvidenceRequired):
        await ebp_remittances.record_correction(
            object(),  # type: ignore[arg-type] -- boto3 ships no stubs
            uuid4(),
            uuid4(),
            lost_earnings_deposited_on=date(2026, 9, 30),
            scc_notice_on=None,
            form_5330_status="not_required",
            evidence_version_ids=[],
        )
