"""TASK-5012 (DEC-2264): the compute branches the stage 2 floor found untested (ADR-079: 100% line
and branch on `*/compute/`). Each test pins what the branch does: a refusal names its reason, and a
result comes from the arithmetic, never from the implementation's own constants."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
import yaml

from abacus.modules.assurance.compute import materiality, soc_gap
from abacus.modules.assurance.compute import sum as sum_engine
from abacus.modules.assurance.compute.ebp import provisions, remittance
from abacus.modules.ledger.compute.mapping import subtotals
from abacus.modules.notices.compute import bracket, risk
from abacus.modules.notices.compute.stamp import stamp as notices_stamp
from abacus.modules.practice.compute.calendar import Area, Place, Postponement, covers
from abacus.modules.sampling.compute import draw, stats
from abacus.modules.sampling.compute.canonical import Record, canonical, normalise_key
from abacus.modules.sampling.compute.draw import Stream
from abacus.modules.sampling.compute.v2_3 import Method, StratumRule, select
from abacus.modules.tax.compute import likely_to_extend, payments
from abacus.modules.tax.compute.transcripts import (
    ParsedTranscript,
    Transaction,
    transactions_with_code,
)

DAY = date(2027, 4, 15)
PARAMS = payments.parameters(2027)


def _raises(error: type[Exception], match: str, call: Callable[[], object]) -> None:
    with pytest.raises(error, match=match):
        call()


# --- assurance -----------------------------------------------------------------------------------


def test_a_provision_with_no_governing_document_is_not_a_conflict() -> None:
    found = provisions.conflicts(
        {"loans": {"spd": "Allowed", "adoption_agreement": None}},
        amendment_effective_on=None,
        plan_year_end=DAY,
    )
    assert found == []


def test_remittance_refuses_a_negative_practice_and_a_nil_principal() -> None:
    _raises(
        ValueError,
        "established practice",
        lambda: remittance.timing(
            DAY, DAY, established_practice_days=-1, participants=10, holidays=frozenset()
        ),
    )
    _raises(ValueError, "principal", lambda: remittance.lost_earnings(Decimal(0), DAY, DAY))


def _benchmark(key: str = "assets", low: int = 1, high: int = 2) -> materiality.BenchmarkInput:
    return materiality.BenchmarkInput(
        key, key.title(), Decimal(1000), Decimal(low), Decimal(high), "not_used"
    )


def test_materiality_refuses_a_bad_percent_a_reversed_range_and_a_repeated_key() -> None:
    _raises(
        materiality.MaterialityInvalid,
        "rate_pct",
        lambda: materiality.benchmark(_benchmark(), rate_pct=Decimal(0)),
    )
    _raises(
        materiality.MaterialityInvalid,
        "range",
        lambda: materiality.benchmark(_benchmark(low=2, high=1), rate_pct=Decimal(1)),
    )
    _raises(
        materiality.MaterialityInvalid,
        "benchmark_key",
        lambda: materiality.benchmarks([_benchmark(), _benchmark()], rate_pct=Decimal(1)),
    )


def test_growth_has_no_figure_on_a_prior_of_zero() -> None:
    assert materiality.growth_pct(Decimal(10), Decimal(0)) is None
    assert materiality.growth_pct(Decimal(10), Decimal(-1)) is None


def test_soc_gap_refuses_a_period_that_ends_before_it_starts() -> None:
    _raises(
        ValueError,
        "ends before it starts",
        lambda: soc_gap.gap(
            plan_year_start=DAY,
            plan_year_end=DAY,
            period_start=DAY,
            period_end=DAY - timedelta(days=1),
            bridge_received=False,
        ),
    )


def test_the_sum_refuses_thresholds_out_of_order_and_a_nil_approaching_percent() -> None:
    ordered = sum_engine.Thresholds(overall=Decimal(10), pm=Decimal(5), ct=Decimal(1))
    _raises(
        sum_engine.SumInvalid,
        "thresholds",
        lambda: sum_engine.evaluate(
            [],
            sum_engine.Thresholds(overall=Decimal(10), pm=Decimal(5), ct=Decimal(6)),
            column_set="commercial",
        ),
    )
    _raises(
        sum_engine.SumInvalid,
        "approaching_pm_pct",
        lambda: sum_engine.evaluate(
            [], ordered, column_set="commercial", approaching_pm_pct=Decimal(0)
        ),
    )


# --- ledger --------------------------------------------------------------------------------------


def test_a_balance_mapped_outside_the_groupings_adds_to_no_subtotal() -> None:
    [only] = subtotals(["cash"], [("cash", Decimal(5)), ("retired", Decimal(7))])
    assert (only.grouping_key, only.subtotal) == ("cash", Decimal(5))


# --- notices -------------------------------------------------------------------------------------


def _table() -> bracket.Schedule:
    table = bracket.schedule(2024, "mfj")
    assert table is not None
    return table


@pytest.mark.parametrize(
    ("income", "expected"),
    [
        # Inside the first bracket, the higher brackets add nothing: 10% of 10,000.
        ("10000", "1000.00"),
        # IRS 2024 MFJ schedule: 196,669.50 at 731,200, then 37% of the 68,800 above it.
        ("800000", "222125.50"),
        ("-5", "0.00"),
    ],
)
def test_tax_follows_the_schedule_at_both_ends(income: str, expected: str) -> None:
    assert bracket.tax(Decimal(income), _table()) == Decimal(expected)


def test_a_change_above_the_last_bound_is_checked_at_the_top_rate() -> None:
    result = bracket.check("mfj", 2024, Decimal(800_000), Decimal(810_000), Decimal(3700))
    assert (result.checked, result.rate, result.expected, result.agrees) == (
        True,
        Decimal("0.37"),
        Decimal("3700.00"),
        True,
    )


def test_a_year_without_a_schedule_is_not_checked() -> None:
    assert bracket.schedule(1999, "single") is None
    result = bracket.check("single", 1999, Decimal(1), Decimal(2), Decimal(3))
    assert (result.checked, result.reason) == (False, bracket.NO_SCHEDULE)


def test_a_respond_by_past_the_amber_window_has_no_band() -> None:
    days = risk.AMBER_DAYS + 1
    assert risk.band(DAY + timedelta(days=days), DAY) == risk.Risk("none", days)


def test_the_notices_stamp_hashes_a_date_by_its_iso_form() -> None:
    assert notices_stamp("k", {"on": DAY}) == notices_stamp("k", {"on": "2027-04-15"})


# --- practice ------------------------------------------------------------------------------------


def test_a_postponement_covers_only_days_inside_its_window() -> None:
    relief = Postponement(
        "IR-2027-1", (Area("CA", frozenset()),), DAY, DAY + timedelta(days=9), date(2027, 10, 15)
    )
    assert covers(relief, DAY, Place("CA")) is True
    assert covers(relief, DAY - timedelta(days=1), Place("CA")) is False
    assert covers(relief, DAY + timedelta(days=10), Place("CA")) is False


# --- sampling ------------------------------------------------------------------------------------


def test_a_record_key_must_not_be_blank_or_hold_control_characters() -> None:
    _raises(ValueError, "blank", lambda: normalise_key("   "))
    _raises(ValueError, "control characters", lambda: normalise_key("NW\x011184"))


def test_below_refuses_a_nil_bound() -> None:
    _raises(ValueError, "bound must be positive", lambda: Stream(1).below(0))


def test_below_redraws_words_past_the_largest_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    # Above 2**31 the bound itself is the only multiple: a word at or past it is redrawn.
    bound = 2**31 + 1
    words = iter([bound, 2**32 - 1, 5])

    class Scripted:
        def __init__(self, _seed: int) -> None:
            pass

        def getrandbits(self, _bits: int) -> int:
            return next(words)

    monkeypatch.setattr(draw, "random", SimpleNamespace(Random=Scripted))
    assert Stream(7).below(bound) == 5


def test_the_binomial_cdf_of_every_outcome_is_one() -> None:
    assert stats.binomial_cdf(5, 5, Decimal("0.1")) == Decimal(1)


def test_attribute_size_refuses_when_no_size_up_to_the_cap_is_enough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(stats, "_MAX_SIZE", 3)
    _raises(ValueError, "no sample size", lambda: stats.attribute_size("0.90", "0.10"))


def test_the_ratio_projection_refuses_a_nil_sample_amount() -> None:
    _raises(
        ValueError,
        "sample amount must be positive",
        lambda: stats.projected_misstatement_ratio(1, 0, 100),
    )


@pytest.mark.parametrize(
    ("strata", "reason"),
    [
        ((), "needs strata"),
        (
            (StratumRule(Decimal(5), Decimal(5), "all"),),
            "minimum must be below its maximum",
        ),
        ((StratumRule(None, None, "random", -1),), "must not be negative"),
    ],
)
def test_select_refuses_bad_strata(strata: tuple[StratumRule, ...], reason: str) -> None:
    population = canonical([Record("A", Decimal(1))])
    _raises(
        ValueError,
        reason,
        lambda: select(population, "threshold_random_stratified", seed=1, strata=strata),
    )


def test_select_refuses_what_a_method_does_not_take() -> None:
    money = canonical([Record("A", Decimal(1))])
    bare = canonical([Record("A")])
    every = (StratumRule(None, None, "all"),)
    _raises(
        ValueError,
        "unknown method",
        lambda: select(money, cast(Method, "made_up"), seed=1, size=1),
    )
    _raises(
        ValueError,
        "takes its size from its strata",
        lambda: select(money, "threshold_random_stratified", seed=1, size=1, strata=every),
    )
    _raises(
        ValueError,
        "needs an amount on every record",
        lambda: select(bare, "threshold_random_stratified", seed=1, strata=every),
    )
    for size in (None, 0, 2):
        _raises(
            ValueError,
            "needs a size between 1 and the population",
            lambda size=size: select(bare, "attribute_statistical", seed=1, size=size),
        )


# --- tax -----------------------------------------------------------------------------------------


QUIET = likely_to_extend.ReturnFacts(
    original_due_on=DAY,
    filed=False,
    extension_filed=False,
    k1s_outstanding=0,
    binder_open_items=0,
    engagement_accepted=True,
    preparer_flagged=False,
)


def test_likely_to_extend_lists_each_signal_in_display_order() -> None:
    every = replace(
        QUIET,
        k1s_outstanding=1,
        binder_open_items=1,
        engagement_accepted=False,
        preparer_flagged=True,
    )
    assert likely_to_extend.signals(every, DAY, PARAMS) == likely_to_extend.ORDER


def test_a_return_with_nothing_open_shows_no_signal() -> None:
    assert likely_to_extend.signals(QUIET, DAY, PARAMS) == ()


def _raw_parameters() -> dict[str, dict[str, object]]:
    path = Path(payments.__file__).with_name("parameters") / "ty2027.yaml"
    return cast(dict[str, dict[str, object]], yaml.safe_load(path.read_text(encoding="utf-8")))


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
def test_the_parameter_file_refuses_an_unknown_rounding_and_a_boolean_figure() -> None:
    rounding = deepcopy(_raw_parameters())
    rounding["estimates"]["rounding"] = "bankers"
    _raises(ValueError, "unknown rounding", lambda: payments.parse_parameters(rounding))
    figure = deepcopy(_raw_parameters())
    figure["estimates"]["current_year_pct"] = True
    _raises(ValueError, "string or an integer", lambda: payments.parse_parameters(figure))


def test_a_year_without_a_parameter_file_raises_lookup_error() -> None:
    _raises(LookupError, "ty1999", lambda: payments.parameters(1999))


def test_the_payments_stamp_hashes_a_date_by_its_iso_form() -> None:
    by_date = payments.stamp("k", {"on": DAY}, PARAMS)
    assert by_date == payments.stamp("k", {"on": "2027-04-15"}, PARAMS)


def test_payments_refuse_negative_figures() -> None:
    form = next(name for name, pct in PARAMS.extension_safe_harbor_pct.items() if pct is not None)
    _raises(
        ValueError,
        "projected liability",
        lambda: payments.safe_harbor(form, Decimal(-1), PARAMS),
    )
    _raises(
        ValueError,
        "payments must not be negative",
        lambda: payments.paid_by_original_due(Decimal(-1), [], None, PARAMS),
    )
    _raises(
        ValueError,
        "payments must not be negative",
        lambda: payments.paid_by_original_due(Decimal(1), [Decimal(-1)], None, PARAMS),
    )
    _raises(
        ValueError,
        "annual payment must not be negative",
        lambda: payments.installment_amounts(Decimal(-1), PARAMS),
    )


def test_an_estates_first_tax_year_is_one() -> None:
    _raises(ValueError, "first tax year is 1", lambda: payments.estate_exempt(0, PARAMS))


def test_the_current_year_method_takes_its_percent_of_the_current_tax() -> None:
    result = payments.required_annual_payment(
        "current_year_90",
        prior_year_tax=None,
        current_year_tax=Decimal(1000),
        projected_withholding=Decimal(100),
        params=PARAMS,
    )
    assert (result.pct, result.base, result.annual) == (
        PARAMS.estimates.current_year_pct,
        Decimal(900),
        Decimal(800),
    )


def test_the_annual_payment_needs_its_tax_figure_and_refuses_negatives() -> None:
    _raises(
        ValueError,
        "prior_year_100 needs its tax figure",
        lambda: payments.required_annual_payment(
            "prior_year_100", prior_year_tax=None, projected_withholding=None, params=PARAMS
        ),
    )
    _raises(
        ValueError,
        "tax and withholding must not be negative",
        lambda: payments.required_annual_payment(
            "prior_year_100", prior_year_tax=Decimal(-1), projected_withholding=None, params=PARAMS
        ),
    )
    _raises(
        ValueError,
        "tax and withholding must not be negative",
        lambda: payments.required_annual_payment(
            "prior_year_100",
            prior_year_tax=Decimal(1),
            projected_withholding=Decimal(-1),
            params=PARAMS,
        ),
    )


def test_transactions_with_code_keeps_only_that_code_in_posting_order() -> None:
    def row(line_no: int, code: str) -> Transaction:
        return Transaction(line_no, code, "x", None, DAY, Decimal(0))

    parsed = ParsedTranscript(
        kind="account", tax_year=2024, transactions=(row(1, "150"), row(2, "922"), row(3, "150"))
    )
    assert [t.line_no for t in transactions_with_code(parsed, "150")] == [1, 3]
    assert transactions_with_code(parsed, "806") == ()
