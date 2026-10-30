"""K-02-T10 (TASK-2309; SPEC-500 AC-39 to AC-44; K-02 §4.3): the deterministic standards API.

The row's acceptance: Copperleaf's August entries classify as four within threshold totalling
20,020 and one review required at 14,900, and an attest client is always held whatever the
amount. The seeded thresholds arrive with K-02-T18; here a version shaped like them proves the
rules, and Hypothesis proves the properties every result keeps (it names its policy, the attest
hold never yields, both variance thresholds must be crossed).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.methodology.standards_contract import (
    AjeThresholdsPayload,
    DocumentConfidencePayload,
    MaterialityRangesPayload,
    PolicyRef,
    ReturnApprovalPolicyPayload,
    ReviewLevelsPayload,
    SsarsCasSettingsPayload,
    StandardRowMissing,
    VarianceThresholdsPayload,
    classify_entry,
    confidence_hold,
    materiality_range_for,
    required_review_levels,
    return_approval_policy,
    ssars_framework_for,
    validate_materiality,
    variance_exceeded,
)

POLICY = PolicyRef("bh-aje-thresholds", uuid.uuid4(), 2, "BH AJE thresholds")
AJE = AjeThresholdsPayload.model_validate(
    {
        "kind": "aje_thresholds",
        "rows": [
            {
                "account_class": "Prepaids",
                "rule": "limit",
                "limit_usd": 10_000,
                "approver_level": "senior_or_above",
                "batch": True,
            },
            {
                "account_class": "Accruals",
                "rule": "limit",
                "limit_usd": 10_000,
                "approver_level": "senior_or_above",
                "batch": True,
            },
            {
                "account_class": "All other classes",
                "rule": "review_required",
                "limit_usd": None,
                "approver_level": "manager_or_partner",
                "batch": False,
            },
            {
                "account_class": "Attest clients",
                "rule": "always_held",
                "limit_usd": None,
                "approver_level": "partner",
                "batch": False,
            },
        ],
    }
)


def test_ac39_entries_classify_by_class_limit_and_the_rest_need_review() -> None:
    august = [("Prepaids", 4_800), ("Accruals", 6_120), ("Prepaids", 3_700), ("Accruals", 5_400)]
    found = [
        classify_entry(AJE, POLICY, account_class=c, amount_usd=a, attest_client=False)
        for c, a in august
    ]
    assert all(r.outcome == "within_threshold" for r in found)
    assert sum(a for _, a in august) == 20_020
    over = classify_entry(
        AJE, POLICY, account_class="Accruals", amount_usd=14_900, attest_client=False
    )
    assert (over.outcome, over.reason, over.approver_level) == (
        "review_required",
        "over_limit",
        "manager_or_partner",
    )
    other = classify_entry(
        AJE, POLICY, account_class="Revenue", amount_usd=10, attest_client=False
    )
    assert other.reason == "unlisted_class"
    at_limit = classify_entry(
        AJE, POLICY, account_class="Prepaids", amount_usd=10_000, attest_client=False
    )
    assert at_limit.outcome == "within_threshold"  # the limit is inclusive


@given(
    amount=st.integers(min_value=-(10**9), max_value=10**9),
    cls=st.sampled_from(["Prepaids", "Accruals", "Revenue"]),
)
def test_ac39_an_attest_client_is_always_held_and_every_result_names_its_policy(
    amount: int, cls: str
) -> None:
    held = classify_entry(AJE, POLICY, account_class=cls, amount_usd=amount, attest_client=True)
    assert (held.outcome, held.reason, held.approver_level) == (
        "review_required",
        "attest_client",
        "partner",
    )
    assert held.policy == POLICY


VARIANCE = VarianceThresholdsPayload.model_validate(
    {
        "kind": "variance_thresholds",
        "rows": [{"context": "close_flux", "pct": "10", "amount_usd": 5000}],
    }
)


def test_ac40_a_variance_needs_both_percent_and_amount() -> None:
    both = variance_exceeded(
        VARIANCE, POLICY, context="close_flux", current_usd=60_000, prior_usd=50_000
    )
    assert (
        both.exceeded and both.pct_change == Decimal("20.000") and both.amount_change_usd == 10_000
    )
    pct_only = variance_exceeded(
        VARIANCE, POLICY, context="close_flux", current_usd=1_200, prior_usd=1_000
    )
    assert not pct_only.exceeded
    amount_only = variance_exceeded(
        VARIANCE, POLICY, context="close_flux", current_usd=1_006_000, prior_usd=1_000_000
    )
    assert not amount_only.exceeded
    from_zero = variance_exceeded(
        VARIANCE, POLICY, context="close_flux", current_usd=6_000, prior_usd=0
    )
    assert from_zero.exceeded and from_zero.pct_change is None
    with pytest.raises(StandardRowMissing):
        variance_exceeded(VARIANCE, POLICY, context="tax_two_year", current_usd=1, prior_usd=1)


@given(cur=st.integers(-(10**8), 10**8), prior=st.integers(-(10**8), 10**8))
def test_ac40_exceeded_implies_the_amount_threshold_was_crossed(cur: int, prior: int) -> None:
    found = variance_exceeded(
        VARIANCE, POLICY, context="close_flux", current_usd=cur, prior_usd=prior
    )
    if found.exceeded:
        assert found.amount_change_usd > 5000
        assert found.pct_change is None or found.pct_change > 10
    assert found.amount_change_usd == abs(cur - prior)


MATERIALITY = MaterialityRangesPayload.model_validate(
    {
        "kind": "materiality_ranges",
        "rows": [
            {
                "engagement_kind": "ebp_audit",
                "benchmark": "Net assets",
                "low_pct": "0.5",
                "high_pct": "1",
            }
        ],
        "performance_materiality": {"low_pct": "50", "high_pct": "75"},
        "clearly_trivial_pct": "5",
    }
)


def test_ac41_materiality_ranges_and_validation() -> None:
    found = materiality_range_for(MATERIALITY, POLICY, engagement_kind="ebp_audit")
    assert found.benchmark == "Net assets" and found.performance_materiality == (
        Decimal(50),
        Decimal(75),
    )
    ok = validate_materiality(
        MATERIALITY,
        POLICY,
        engagement_kind="ebp_audit",
        pct=Decimal("0.75"),
        performance_pct=Decimal(75),
        clearly_trivial_pct=Decimal(5),
    )
    assert ok.within_range and ok.performance_within_range and ok.clearly_trivial_matches
    off = validate_materiality(
        MATERIALITY,
        POLICY,
        engagement_kind="ebp_audit",
        pct=Decimal("1.5"),
        performance_pct=Decimal(80),
        clearly_trivial_pct=Decimal(3),
    )
    assert not (off.within_range or off.performance_within_range or off.clearly_trivial_matches)


def test_ac42_confidence_holds_below_the_floor_and_never_auto_accepts() -> None:
    payload = DocumentConfidencePayload.model_validate(
        {
            "kind": "document_confidence",
            "hold_below_pct": "85",
            "auto_accept_above_pct": "98",
            "auto_accept_enabled": False,
        }
    )
    assert confidence_hold(payload, POLICY, confidence_pct=Decimal("84.9")).hold
    high = confidence_hold(payload, POLICY, confidence_pct=Decimal(99))
    assert not high.hold and not high.auto_accept


def test_ac43_review_levels_and_return_approval() -> None:
    levels = ReviewLevelsPayload.model_validate(
        {
            "kind": "review_levels",
            "tiers": [
                {
                    "tier": 3,
                    "name": "Complex",
                    "required_levels": ["L1", "L2", "L4"],
                    "second_partner_review": True,
                    "criteria": "",
                }
            ],
        }
    )
    found = required_review_levels(levels, POLICY, tier=3)
    assert found.levels == ("L1", "L2", "L4") and found.second_partner_review
    with pytest.raises(StandardRowMissing):
        required_review_levels(levels, POLICY, tier=1)
    client, partner = uuid.uuid4(), uuid.uuid4()
    approval = ReturnApprovalPolicyPayload.model_validate(
        {
            "kind": "return_approval_policy",
            "code": "BH-TAX-02",
            "rule": "signing_partner_final_approval",
            "applies_to": [{"client_id": str(client), "approver_user_id": str(partner)}],
            "export_condition": "after_final_approval",
        }
    )
    named = return_approval_policy(approval, POLICY, client_id=client)
    assert (named.code, named.approver_user_id, named.export_after_final_approval) == (
        "BH-TAX-02",
        partner,
        True,
    )
    assert (
        return_approval_policy(approval, POLICY, client_id=uuid.uuid4()).approver_user_id is None
    )


def test_ac44_ssars_27_starts_with_periods_ending_dec_15_2026() -> None:
    off = SsarsCasSettingsPayload.model_validate(
        {"kind": "ssars_cas_settings", "early_adopt_ssars27": False}
    )
    early = SsarsCasSettingsPayload.model_validate(
        {"kind": "ssars_cas_settings", "early_adopt_ssars27": True}
    )
    assert (
        ssars_framework_for(off, POLICY, period_end=date(2026, 12, 14)).framework
        == "ar_c_70_preparation"
    )
    assert (
        ssars_framework_for(off, POLICY, period_end=date(2026, 12, 15)).framework
        == "cas_by_product"
    )
    assert (
        ssars_framework_for(early, POLICY, period_end=date(2026, 6, 30)).framework
        == "cas_by_product"
    )
