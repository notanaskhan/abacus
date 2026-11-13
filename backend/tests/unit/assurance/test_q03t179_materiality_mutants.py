"""Q-03-T179 (TASK-7826): the materiality engine's surviving mutants, closed from its sources.

The weekly run of 2026-11-13 (43330118713) left `assurance/compute/materiality` at 69.3% killed,
under the row's 85%. The survivors were the stamp's inputs (what the SHA-256 is taken over), the
names the refusals carry, and the rounding edges. These tests pin each one from the engine's
own definitions and AUD-07's figures (16,812,400 x 1.5% = 252,186 -> 252,200; PM 75% = 189,150;
CT 5% = 12,610; range 3.0%-5.0% of 1,318,300 = 39,500 and 65,900; 14,228,500 at 1.5% = 213,400;
growth 18.2%; final 16,861,000 -> 252,900, +700, 0.3%). Expected hashes are rebuilt here from the
canonical-input rule (sorted keys, compact separators, Decimals by value), never read back from
the engine.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest

from abacus.modules.assurance.compute import materiality as m

D = Decimal
canonical_text = m._text  # pyright: ignore[reportPrivateUsage] -- the canonical-input rule under test
POLICY = m.Policy(
    low_pct=D("1.0"), high_pct=D("2.0"), pm_low_pct=D(50), pm_high_pct=D(75), ct_pct=D(5)
)


def _hash(**parts: object) -> str:
    body = {"engine": "materiality", "version": "1", **parts}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _thresholds(**over: object) -> m.Thresholds:
    args: dict[str, object] = {
        "basis": "unadjusted",
        "benchmark_key": "revenue",
        "benchmark_amount": D("16812400"),
        "rate_pct": D("1.5"),
        "pm_pct": D(75),
        "ct_pct": D(5),
        "policy": POLICY,
    }
    args.update(over)
    return m.thresholds(**args)  # type: ignore[arg-type]  # keyword overrides of known types


# --- the figures and the stamp -------------------------------------------------------------------


def test_thresholds_figures_and_their_stamp() -> None:
    t = _thresholds()
    assert (t.overall, t.pm, t.ct) == (D("252200.00"), D("189150.00"), D("12610.00"))
    assert t.benchmark_amount == D("16812400.00")
    assert (t.policy_low_pct, t.policy_high_pct) == (D("1.0"), D("2.0"))
    assert t.stamp == m.Stamp(
        "materiality",
        "1",
        _hash(
            kind="thresholds",
            basis="unadjusted",
            benchmark_key="revenue",
            benchmark_amount="16812400",
            rate_pct="1.5",
            pm_pct="75",
            ct_pct="5",
            policy=["1", "2", "50", "75"],
            policy_ct="5",
            increment="100",
        ),
    )


def test_every_stamped_input_moves_the_hash() -> None:
    base = _thresholds().stamp.inputs_hash
    assert _thresholds(basis="final").stamp.inputs_hash != base
    assert _thresholds(benchmark_key="assets").stamp.inputs_hash != base
    assert _thresholds(benchmark_amount=D("16812401")).stamp.inputs_hash != base
    assert _thresholds(rate_pct=D("1.6")).stamp.inputs_hash != base
    assert _thresholds(pm_pct=D(70)).stamp.inputs_hash != base
    wider = m.Policy(D("1.0"), D("2.5"), D(50), D(75), D(5))
    assert _thresholds(policy=wider).stamp.inputs_hash != base
    other_ct = m.Policy(D("1.0"), D("2.0"), D(50), D(75), D(4))
    assert _thresholds(policy=other_ct, ct_pct=D(4)).stamp.inputs_hash != base
    coarse = m.Policy(D("1.0"), D("2.0"), D(50), D(75), D(5), increment=D(1000))
    assert _thresholds(policy=coarse).stamp.inputs_hash != base
    # Decimals hash by value: 1.5, 1.50 and 1.500 are one input.
    assert _thresholds(rate_pct=D("1.500")).stamp.inputs_hash == base


def test_text_is_the_plain_value_by_value() -> None:
    assert canonical_text(D("1.500")) == "1.5"
    assert canonical_text(D("1E+3")) == "1000"
    assert canonical_text(D("100.00")) == "100"
    assert canonical_text([D("1.0"), (D("2.50"), "x")]) == ["1", ["2.5", "x"]]
    assert canonical_text("revenue") == "revenue"
    assert canonical_text(None) is None


def test_a_benchmark_row_and_its_stamp() -> None:
    item = m.BenchmarkInput(
        key="revenue",
        label="Total revenue",
        amount=D("1318300"),
        low_pct=D("3.0"),
        high_pct=D("5.0"),
        use="overall",
        prior_years=(m.PriorYear("FY2025", D("14228500"), D("213000.555")),),
    )
    row = m.benchmark(item, rate_pct=D("1.5"))
    assert (row.low, row.high) == (D("39500.00"), D("65900.00"))
    assert row.amount == D("1318300.00")
    assert row.prior_years == (
        m.PriorYearAtRate("FY2025", D("14228500.00"), D("213400.00"), D("213000.56")),
    )
    assert row.growth_pct == D("-90.7")
    assert row.stamp.inputs_hash == _hash(
        kind="benchmark",
        key="revenue",
        amount="1318300",
        range=["3", "5"],
        rate_pct="1.5",
        increment="100",
        prior_years=[["FY2025", "14228500", "213000.555"]],
    )
    bare = m.benchmark(
        m.BenchmarkInput("assets", "Total assets", D("500"), D(1), D(2), "not_used"), rate_pct=D(1)
    )
    assert bare.prior_years == () and bare.growth_pct is None


def test_reassessment_and_its_stamp() -> None:
    decided = _thresholds()
    found = m.reassess(decided, final_amount=D("16861000"))
    assert (found.final_amount, found.at_rate, found.difference, found.difference_pct) == (
        D("16861000.00"),
        D("252900.00"),
        D("700.00"),
        D("0.3"),
    )
    assert found.stamp.inputs_hash == _hash(
        kind="reassessment",
        decided=decided.stamp.inputs_hash,
        final_amount="16861000",
        rate_pct="1.5",
        increment="100",
    )
    coarse = m.reassess(decided, final_amount=D("16861000"), increment=D(1000))
    assert coarse.at_rate == D("253000.00")
    assert coarse.stamp.inputs_hash != found.stamp.inputs_hash
    lower = m.reassess(decided, final_amount=D("16000000"))
    assert (lower.at_rate, lower.difference, lower.difference_pct) == (
        D("240000.00"),
        D("-12200.00"),
        D("-4.8"),
    )


# --- rounding edges ------------------------------------------------------------------------------


def test_round_to_increment_is_half_up_to_the_step() -> None:
    assert m.round_to_increment(D("252186")) == D("252200.00")
    assert m.round_to_increment(D("24350")) == D("24400.00")  # a tie rounds up, never to even
    assert m.round_to_increment(D("24250")) == D("24300.00")
    assert m.round_to_increment(D("24349.99")) == D("24300.00")
    assert m.round_to_increment(D("1249"), D(500)) == D("1000.00")
    assert m.round_to_increment(D("1250"), D(500)) == D("1500.00")
    assert str(m.round_to_increment(D("252186"))) == "252200.00"


def test_at_rate_uses_the_given_increment() -> None:
    assert m.at_rate(D("16812400"), D("1.5")) == D("252200.00")
    assert m.at_rate(D("16812400"), D("1.5"), D(1000)) == D("252000.00")
    assert m.at_rate(D("1000"), D("2.5"), D(1)) == D("25.00")


def test_pm_and_ct_round_to_the_whole_dollar_half_up() -> None:
    # A step of 1 shows the shares' own rounding.
    fine = m.Policy(D("1.0"), D("2.0"), D(50), D(75), D(5), increment=D(1))
    t = _thresholds(benchmark_amount=D("10100"), rate_pct=D("1.0"), pm_pct=D(75), policy=fine)
    assert t.overall == D("101.00")
    assert t.pm == D("76.00")  # 75.75 -> 76
    assert t.ct == D("5.00")  # 5.05 -> 5
    assert str(t.pm) == "76.00"


def test_growth_one_decimal_and_no_growth_on_nothing() -> None:
    assert m.growth_pct(D("16812400"), D("14228500")) == D("18.2")
    assert m.growth_pct(D(100), D(0)) is None
    assert m.growth_pct(D(100), D(-5)) is None
    assert m.growth_pct(D("100.5"), D(100)) == D("0.5")


def test_options_are_the_bottom_and_the_midpoint() -> None:
    assert m.option_rates(POLICY) == (D("1.0"), D("1.5"))
    flat = m.Policy(D(2), D(2), D(50), D(75), D(5))
    assert m.option_rates(flat) == (D(2),)
    assert m.option_key(D("1.5")) == "rate_1_5"
    assert m.option_key(D(5)) == "rate_5_0"
    assert m.option_key(D("1.25")) == "rate_1_3"
    assert m.option_key(D("10")) == "rate_10_0"
    found = m.options(
        basis="final",
        benchmark_key="revenue",
        benchmark_amount=D("16812400"),
        pm_pct=D(75),
        ct_pct=D(5),
        policy=POLICY,
    )
    assert [o.key for o in found] == ["rate_1_0", "rate_1_5", "custom"]
    assert found[2].thresholds is None
    first = found[0].thresholds
    assert first is not None and first.basis == "final" and first.overall == D("168100.00")
    assert m.option_keys(POLICY) == frozenset({"rate_1_0", "rate_1_5", "custom"})


# --- refusals and the names they carry ---------------------------------------------------------


@pytest.mark.parametrize(
    ("call", "name"),
    [
        (lambda: _thresholds(benchmark_amount=D(0)), "benchmark_amount"),
        (lambda: _thresholds(rate_pct=D(0)), "rate_pct"),
        (lambda: _thresholds(pm_pct=D(0)), "pm_pct"),
        (lambda: _thresholds(ct_pct=D("NaN")), "ct_pct"),
        (lambda: m.round_to_increment(D(1), D(0)), "increment"),
        (lambda: m.reassess(_thresholds(), final_amount=D(-1)), "final_amount"),
        (
            lambda: m.benchmark(
                m.BenchmarkInput("k", "l", D(0), D(1), D(2), "overall"), rate_pct=D(1)
            ),
            "benchmark_amount",
        ),
        (
            lambda: m.benchmark(
                m.BenchmarkInput("k", "l", D(1), D(0), D(2), "overall"), rate_pct=D(1)
            ),
            "low_pct",
        ),
        (
            lambda: m.benchmark(
                m.BenchmarkInput("k", "l", D(1), D(1), D(101), "overall"), rate_pct=D(1)
            ),
            "high_pct",
        ),
        (
            lambda: m.benchmark(
                m.BenchmarkInput("k", "l", D(1), D(1), D(2), "overall"), rate_pct=D(0)
            ),
            "rate_pct",
        ),
        (
            lambda: m.benchmark(
                m.BenchmarkInput("k", "l", D(1), D(3), D(2), "overall"), rate_pct=D(1)
            ),
            "range",
        ),
    ],
)
def test_each_refusal_names_its_input(call: object, name: str) -> None:
    with pytest.raises(m.MaterialityInvalid) as raised:
        call()  # type: ignore[operator]  # a parametrised zero-argument call
    assert raised.value.args == (name,)
    assert raised.value.code == "materiality_invalid"


def test_percent_bounds_are_open_at_zero_and_closed_at_a_hundred() -> None:
    m.benchmark(m.BenchmarkInput("k", "l", D(1), D(1), D(100), "overall"), rate_pct=D(100))
    with pytest.raises(m.MaterialityInvalid):
        m.benchmark(m.BenchmarkInput("k", "l", D(1), D(1), D("100.01"), "overall"), rate_pct=D(1))
    with pytest.raises(m.MaterialityInvalid):
        m.benchmark(
            m.BenchmarkInput("k", "l", D(1), D("Infinity"), D(2), "overall"), rate_pct=D(1)
        )
    with pytest.raises(m.MaterialityInvalid):
        m.round_to_increment(D(1), D("Infinity"))


@pytest.mark.parametrize(
    ("over", "field"),
    [
        ({"rate_pct": D("0.9")}, "rate_pct"),
        ({"rate_pct": D("2.1")}, "rate_pct"),
        ({"pm_pct": D(49)}, "pm_pct"),
        ({"pm_pct": D(76)}, "pm_pct"),
        ({"ct_pct": D(4)}, "ct_pct"),
    ],
)
def test_outside_policy_names_the_field(over: dict[str, object], field: str) -> None:
    with pytest.raises(m.OutsidePolicy) as raised:
        _thresholds(**over)
    assert raised.value.field == field
    assert str(raised.value) == f"{field} is outside the firm's materiality policy"
    assert raised.value.code == "outside_policy"


def test_policy_bounds_are_inclusive() -> None:
    assert _thresholds(rate_pct=D("1.0"), pm_pct=D(50)).overall == D("168100.00")
    assert _thresholds(rate_pct=D("2.0"), pm_pct=D(75)).overall == D("336200.00")


def test_benchmarks_refuse_two_overall_rows_and_repeated_keys() -> None:
    a = m.BenchmarkInput("a", "A", D(100), D(1), D(2), "overall")
    b = m.BenchmarkInput("b", "B", D(100), D(1), D(2), "overall")
    with pytest.raises(m.MaterialityInvalid) as two:
        m.benchmarks([a, b], rate_pct=D(1))
    assert two.value.args == ("overall_benchmark",)
    with pytest.raises(m.MaterialityInvalid) as same:
        m.benchmarks([a, m.BenchmarkInput("a", "A2", D(5), D(1), D(2), "specific")], rate_pct=D(1))
    assert same.value.args == ("benchmark_key",)
    rows = m.benchmarks(
        [a, m.BenchmarkInput("c", "C", D(300), D(1), D(2), "specific")],
        rate_pct=D(1),
        increment=D(1),
    )
    assert [(r.key, r.low, r.high) for r in rows] == [
        ("a", D("1.00"), D("2.00")),
        ("c", D("3.00"), D("6.00")),
    ]
