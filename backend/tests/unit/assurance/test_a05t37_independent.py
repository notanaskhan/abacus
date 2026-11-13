"""Independent AC tests and goldens for the contributions engines and the late-remittance service
(A-05-T37; ADR-078; A-05 §3 F6, SPEC-640).

Written apart from A-05-T24 and T30: business days (Dec 26 → Jan 9 is 9 with Jan 1 out), the small-
plan safe harbor never applied to a large plan, VFCP lost earnings (33,540.00 for 10 days at 7%
compounded daily = 64.38) and its 15% excise (9.66), line 4a from deferrals only, the correction
state machine (evidence required, pending until the SCC notice, corrected once, never by time), and
the single-object read EBP-07 and AUD-27 share.
"""

from __future__ import annotations

import inspect
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.assurance import ebp_remittances
from abacus.modules.assurance.compute.ebp import remittance as r

HOLIDAYS = frozenset({date(2025, 12, 25), date(2026, 1, 1)})
RATES = {"2025-Q4": Decimal("7"), "2026-Q1": Decimal("7")}


def test_dec_26_to_jan_9_is_nine_business_days_and_late_on_a_two_day_practice() -> None:
    t = r.timing(
        date(2025, 12, 26),
        date(2026, 1, 9),
        established_practice_days=2,
        participants=301,
        holidays=HOLIDAYS,
    )
    assert (t.business_days, t.calendar_days, t.due_on, t.late) == (
        9,
        14,
        date(2025, 12, 30),
        True,
    )


def test_the_seven_day_safe_harbor_never_applies_to_a_large_plan() -> None:
    large = r.timing(
        date(2025, 12, 26),
        date(2026, 1, 6),
        established_practice_days=2,
        participants=301,
        holidays=HOLIDAYS,
    )
    small = r.timing(
        date(2025, 12, 26),
        date(2026, 1, 6),
        established_practice_days=2,
        participants=80,
        holidays=HOLIDAYS,
    )
    assert large.late is True
    assert small.late is False


def test_vfcp_lost_earnings_golden_and_excise() -> None:
    le = r.lost_earnings(
        Decimal("33540.00"), date(2025, 12, 30), date(2026, 1, 9), rate_table=RATES
    )
    assert (le.interest_days, le.lost_earnings, le.excise_exposure) == (
        10,
        Decimal("64.38"),
        Decimal("9.66"),
    )
    assert le.rate_refs == ("2025-Q4", "2026-Q1")


def test_a_missing_quarter_rate_refuses_rather_than_guessing() -> None:
    with pytest.raises(r.RateMissing):
        r.lost_earnings(Decimal("100.00"), date(2025, 12, 30), date(2026, 1, 9), rate_table={})


@given(
    principal=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000000"), places=2),
    days=st.integers(min_value=0, max_value=60),
)
def test_lost_earnings_are_idempotent_non_negative_and_monotone_in_days(
    principal: Decimal, days: int
) -> None:
    due = date(2025, 10, 1)
    table = {"2025-Q4": Decimal("7")}
    a = r.lost_earnings(principal, due, due + timedelta(days=days), rate_table=table)
    b = r.lost_earnings(principal, due, due + timedelta(days=days), rate_table=table)
    assert a == b
    assert a.lost_earnings >= 0
    later = r.lost_earnings(principal, due, due + timedelta(days=days + 1), rate_table=table)
    assert later.lost_earnings >= a.lost_earnings


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_line_4a_sums_late_deferrals_only() -> None:
    assert r.schedule_h_4a([Decimal("33540.00")]) == Decimal("33540.00")
    assert r.schedule_h_4a([]) == Decimal("0")
    # The service sums the late remittances' principal, which is participant deferrals only.
    source = inspect.getsource(ebp_remittances.schedule_h_4a)
    assert "principal" in source
    assert "match" not in source


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_a_correction_needs_evidence_and_is_one_human_event() -> None:
    source = inspect.getsource(ebp_remittances.record_correction)
    assert "if not evidence_version_ids:" in source
    assert "raise CorrectionEvidenceRequired" in source
    assert 'actor_kind="human"' in source
    assert "AlreadyCorrected" in source
    # Pending until the SCC notice is recorded; never set from a clock.
    assert '"corrected" if scc_notice_on else "pending_vfcp_scc"' in source
    assert "today(" not in source and "date.today" not in source


def test_a_correction_records_form_5330_only_as_not_required_or_filed() -> None:
    """Exposure is the finding's state, never something a person records as a correction."""
    assert set(ebp_remittances.FORM_5330) == {"not_required", "filed"}


def test_the_late_remittance_is_one_object_read_by_every_consumer() -> None:
    """EBP-07 and AUD-27 read the same `late_remittances` through `assurance.api`."""
    from abacus.modules.assurance import api

    assert api.late_remittances is ebp_remittances.late_remittances
    assert "late_remittances" in api.__all__
