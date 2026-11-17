"""G-04-T11: plan & usage figures and plan-request rules (SPEC-680 AC-28, AC-32, AC-33, AC-41;
DEC-5418)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from abacus.modules.platform import plan_usage
from abacus.modules.platform.g04_fixtures import RATE_BANDS


def test_ac33_a_rules_minutes_are_codes_percent_of_the_included_minutes() -> None:
    assert plan_usage.rule_minutes(20_000, 90) == 18_000
    assert plan_usage.rule_minutes(20_000, 75) == 15_000
    assert plan_usage.rule_minutes(1_500, 83) == 1_245  # rounded down


def test_ac32_granite_peak_at_1240_of_1500_is_82_7_percent() -> None:
    assert plan_usage.used_pct(1_240, 1_500) == Decimal("82.7")
    assert plan_usage.used_pct(10, 0) == Decimal(0)


def test_ac28_the_fake_card_is_the_figure_books_46_people() -> None:
    card = plan_usage._fake_rates()  # pyright: ignore[reportPrivateUsage] -- the fake under test
    assert sum(b.people for b in card.bands) == 46 == sum(p for _, p, _ in RATE_BANDS)
    assert [b.hourly_rate for b in card.bands][-1] is None  # "Non-chargeable"


class _Ctx:
    def __init__(self, user: uuid.UUID) -> None:
        self.user_id = user


def test_ac41_the_requester_withdraws_and_never_approves() -> None:
    asker, partner = uuid.uuid4(), uuid.uuid4()
    row = {"status": "awaiting_partner", "requested_by": asker}
    assert plan_usage.allowed(row, _Ctx(asker), may_approve=True) == ["withdraw"]  # type: ignore[arg-type] -- the field it reads
    assert plan_usage.allowed(row, _Ctx(partner), may_approve=True) == ["approve", "decline"]  # type: ignore[arg-type] -- the field it reads
    assert plan_usage.allowed(row, _Ctx(partner), may_approve=False) == []  # type: ignore[arg-type] -- the field it reads
    sent = {"status": "sent_to_accrued", "requested_by": asker}
    assert plan_usage.allowed(sent, _Ctx(asker), may_approve=True) == []  # type: ignore[arg-type] -- the field it reads
