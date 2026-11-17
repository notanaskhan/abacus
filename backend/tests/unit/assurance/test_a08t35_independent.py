"""A-08-T35 (TASK-8532; ADR-078): independent acceptance tests for A-08's amber services.

Written from SPEC-657 and A-08 §4 to §6, not from the services' own tests: the I-AGENT-NEVER rows,
segregation of expansion approval and reconciliation acceptance, the threshold rule (both the
percent and the amount), the clearly-trivial line, the UDL, the follow-up timers, the coverage line
and the preparation legend. Each fails on a build that weakens the property.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from abacus.modules.assurance.analytics import SourceLine, compute_lines, line_status
from abacus.modules.assurance.confirmations_lifecycle import follow_up_step
from abacus.modules.assurance.confirmations_service import coverage_of
from abacus.modules.assurance.ssars import DEFAULT_AMOUNT, DEFAULT_PCT, LEGEND
from abacus.modules.workpapers.compute.attribute_stats import (
    StatsInvalid,
    below_clearly_trivial,
    upper_deviation_limit,
)
from abacus.modules.workpapers.compute.flux import Thresholds

MATRIX = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "permission-matrix"


def _actions(module: str) -> dict[str, dict[str, object]]:
    doc = yaml.safe_load((MATRIX / f"{module}.yaml").read_text(encoding="utf-8"))
    return dict(doc["actions"])


# ---- I-AGENT-NEVER: every accept, approve, decide and send is a person's ----------------------

HUMAN_ONLY = {
    "assurance": [
        "analytics.accept",
        "client_question.send",
        "confirmation.accept_reconciliation",
    ],
    "sampling": ["sample_expansion.request", "sample_expansion.decide"],
}


@pytest.mark.parametrize(
    ("module", "action"), [(m, a) for m, acts in HUMAN_ONLY.items() for a in acts]
)
def test_agent_and_system_are_denied_every_reserved_action(module: str, action: str) -> None:
    row = _actions(module)[action]
    assert row.get("agent") == "deny", action
    assert row.get("system") == "deny", action
    for client in ("client_admin", "client_contributor", "link_principal"):
        assert row.get(client) == "deny", (action, client)


def test_the_approver_and_the_acceptor_are_never_the_preparer() -> None:
    sampling = _actions("sampling")["sample_expansion.decide"]
    assert sampling.get("is_named_approver") == "required"
    assert sampling.get("not_preparer_of_target") == "required"
    for action in ("confirmation.accept_reconciliation", "analytics.accept"):
        assert _actions("assurance")[action].get("not_preparer_of_target") == "required", action


def test_staff_cannot_accept_a_reconciliation_or_an_explanation() -> None:
    for action in ("confirmation.accept_reconciliation", "analytics.accept"):
        row = _actions("assurance")[action]
        assert row.get("staff") in (None, "deny"), action
        assert row.get("manager") == "allow", action


# ---- threshold rule: over needs both the percent and the amount (AUD-13 a) --------------------


def _line(key: str, cy: str, py: str) -> SourceLine:
    return SourceLine(
        key, key, "income_statement", "Income statement", Decimal(cy), Decimal(py), ()
    )


def test_over_requires_both_the_percent_and_the_amount() -> None:
    granite = Thresholds(pct=Decimal("10"), amount=Decimal("116250"))
    lines, _ = compute_lines(
        [
            _line("interest", "520000", "410000"),  # 26.8% but 110,000: within
            _line("cogs", "29160000", "26490000"),  # 10.1% and 2,670,000: over
            _line("revenue", "48600000", "44900000"),  # 8.2%: within
        ],
        granite,
    )
    by = {x.key: x for x in lines if not x.derived}
    assert by["interest"].change_pct == Decimal("26.8")
    assert (by["interest"].over, by["cogs"].over, by["revenue"].over) == (False, True, False)


def test_a_subtotal_is_derived_and_never_evaluated() -> None:
    lines, _ = compute_lines(
        [_line("a", "200", "100"), _line("b", "300", "100")],
        Thresholds(pct=Decimal("1"), amount=Decimal("1")),
    )
    total = next(x for x in lines if x.derived)
    assert (total.cy, total.evaluated, line_status(total, None)) == (Decimal("500"), False, None)


def test_an_over_line_without_an_explanation_is_unexplained() -> None:
    lines, _ = compute_lines(
        [_line("inv", "11420000", "9180000")],
        Thresholds(pct=Decimal("10"), amount=Decimal("116250")),
    )
    inv = next(x for x in lines if not x.derived)
    assert line_status(inv, None) == "unexplained"


def test_the_review_default_threshold_is_ten_percent_and_fifty_thousand() -> None:
    assert (Decimal("10"), Decimal("50000")) == (DEFAULT_PCT, DEFAULT_AMOUNT)


# ---- confirmations: clearly trivial, coverage, follow-up timers --------------------------------


def test_a_difference_below_clearly_trivial_is_logged_not_an_exception() -> None:
    assert below_clearly_trivial(Decimal("4300.00"), Decimal("7750")) is True
    assert below_clearly_trivial(Decimal("-4300.00"), Decimal("7750")) is True
    assert below_clearly_trivial(Decimal("7750"), Decimal("7750")) is False  # strictly below


def test_coverage_is_sent_over_population_to_one_place() -> None:
    line = coverage_of(
        Decimal("5860000.00"),
        Decimal("897950.00"),
        Decimal("695200.00"),
        Decimal("4300.00"),
        Decimal("7750"),
    )
    assert line.sent_pct == Decimal("15.3")
    assert coverage_of(Decimal(0), Decimal(0), Decimal(0), Decimal(0), Decimal(0)).sent_pct == 0


def test_follow_up_sends_a_second_request_then_alternative_procedures() -> None:
    sent = datetime(2026, 9, 18, 14, tzinfo=UTC)
    assert follow_up_step([("sent", sent)], "sent", sent + timedelta(days=6)) is None
    assert follow_up_step([("sent", sent)], "sent", sent + timedelta(days=7)) == "second_request"
    second = sent + timedelta(days=10)
    events = [("sent", sent), ("second_request", second)]
    assert follow_up_step(events, "sent", second + timedelta(days=6)) is None
    assert follow_up_step(events, "sent", second + timedelta(days=7)) == "alternative_procedures"


def test_a_response_or_another_status_stops_the_follow_up() -> None:
    sent = datetime(2026, 9, 18, tzinfo=UTC)
    later = sent + timedelta(days=30)
    assert follow_up_step([("sent", sent), ("responded", later)], "sent", later) is None
    assert follow_up_step([("sent", sent)], "closed", later) is None


# ---- attribute testing: the UDL (AUD-12 c) ----------------------------------------------------


def test_zero_deviations_in_twenty_five_at_ninety_percent_is_8_8() -> None:
    assert upper_deviation_limit(0, 25, Decimal("0.90")) == Decimal("8.8")


def test_more_deviations_never_lower_the_udl() -> None:
    limits = [upper_deviation_limit(d, 40, Decimal("0.90")) for d in range(5)]
    assert limits == sorted(limits)
    assert upper_deviation_limit(40, 40, Decimal("0.90")) == Decimal("100.0")


@pytest.mark.parametrize(("dev", "n", "conf"), [(-1, 10, "0.9"), (11, 10, "0.9"), (0, 10, "1")])
def test_invalid_inputs_are_refused(dev: int, n: int, conf: str) -> None:
    with pytest.raises(StatsInvalid):
        upper_deviation_limit(dev, n, Decimal(conf))


# ---- preparation: the legend on every page (AUD-26 d) -----------------------------------------


def test_the_preparation_legend_is_the_standard_wording() -> None:
    assert LEGEND == "No assurance is provided."
