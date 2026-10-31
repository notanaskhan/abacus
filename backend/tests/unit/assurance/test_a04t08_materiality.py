"""A-04-T08: the materiality engine (A-04 §3.3 AC3.1, AC3.2, AC3.3, AC3.6, AC3.8; DEC-1850).

Figures from the AUD-07 handoff and its R2 revision (Northwind Robotics 401(k) Plan, PY2025) and
J04 (Granite Peak Outdoor Supply).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.assurance.compute import materiality as m

D = Decimal
EBP = m.Policy(D("1.0"), D("2.0"), D("50"), D("75"), D("5"))
FS = m.Policy(D("3"), D("7"), D("50"), D("75"), D("5"))


def _northwind(
    rate: str = "1.5", pm: str = "75", ct: str = "5", amount: str = "16812400"
) -> m.Thresholds:
    return m.thresholds(
        basis="unadjusted",
        benchmark_key="net_assets",
        benchmark_amount=D(amount),
        rate_pct=D(rate),
        pm_pct=D(pm),
        ct_pct=D(ct),
        policy=EBP,
    )


def test_ac3_1_northwind_overall_pm_ct_from_the_rounded_overall() -> None:
    t = _northwind()
    # 16,812,400 x 1.5% = 252,186 -> 252,200 (nearest 100, half up); PM and CT of 252,200.
    assert (t.overall, t.pm, t.ct) == (D("252200.00"), D("189150.00"), D("12610.00"))
    assert (t.policy_low_pct, t.policy_high_pct) == (D("1.0"), D("2.0"))
    assert t.stamp.engine_name == "materiality"
    assert t.stamp.engine_version == m.ENGINE_VERSION
    assert len(t.stamp.inputs_hash) == 64


def test_ac3_1_bottom_option_and_the_option_set() -> None:
    low = _northwind(rate="1.0")
    assert (low.overall, low.pm, low.ct) == (D("168100.00"), D("126075.00"), D("8405.00"))
    opts = m.options(
        basis="unadjusted",
        benchmark_key="net_assets",
        benchmark_amount=D("16812400"),
        pm_pct=D("75"),
        ct_pct=D("5"),
        policy=EBP,
    )
    assert [o.key for o in opts] == ["rate_1_0", "rate_1_5", "custom"]
    assert opts[1].thresholds is not None and opts[1].thresholds.overall == D("252200.00")
    assert opts[2].thresholds is None
    assert m.option_keys(EBP) == {"rate_1_0", "rate_1_5", "custom"}


def test_ac3_1_benchmark_ranges() -> None:
    rows = m.benchmarks(
        [
            m.BenchmarkInput(
                "net_assets",
                "Net assets available for benefits",
                D("16812400"),
                D("1.0"),
                D("2.0"),
                "overall",
            ),
            m.BenchmarkInput(
                "contributions",
                "Contributions (participant, employer, rollovers)",
                D("1318300"),
                D("3.0"),
                D("5.0"),
                "considered_for_specific",
            ),
            m.BenchmarkInput(
                "benefit_payments",
                "Benefit payments to participants",
                D("812650"),
                D("3.0"),
                D("5.0"),
                "considered_for_specific",
            ),
        ],
        rate_pct=D("1.5"),
    )
    assert [(r.low, r.high) for r in rows] == [
        (D("168100.00"), D("336200.00")),
        (D("39500.00"), D("65900.00")),
        (D("24400.00"), D("40600.00")),  # 24,379.5 and 40,632.5, half up
    ]


def test_ac3_2_prior_years_and_growth_leave_thresholds_unchanged() -> None:
    row = m.benchmark(
        m.BenchmarkInput(
            "net_assets",
            "Net assets available for benefits",
            D("16812400"),
            D("1.0"),
            D("2.0"),
            "overall",
            (
                m.PriorYear("PY2024", D("14228500"), D("213400")),
                m.PriorYear("PY2023", D("11902700"), D("178500")),
            ),
        ),
        rate_pct=D("1.5"),
    )
    assert [p.at_rate for p in row.prior_years] == [D("213400.00"), D("178500.00")]
    assert [p.overall_used for p in row.prior_years] == [D("213400.00"), D("178500.00")]
    assert row.growth_pct == D("18.2")  # 16,812,400 / 14,228,500 - 1
    assert _northwind().overall == D("252200.00")


@pytest.mark.parametrize(
    ("rate", "pm", "ct", "field"),
    [
        ("0.9", "75", "5", "rate_pct"),
        ("2.1", "75", "5", "rate_pct"),
        ("1.5", "49", "5", "pm_pct"),
        ("1.5", "76", "5", "pm_pct"),
        ("1.5", "75", "4", "ct_pct"),
    ],
)
def test_ac3_3_preview_refuses_outside_policy(rate: str, pm: str, ct: str, field: str) -> None:
    with pytest.raises(m.OutsidePolicy) as raised:
        m.preview(
            basis="unadjusted",
            benchmark_key="net_assets",
            benchmark_amount=D("16812400"),
            rate_pct=D(rate),
            pm_pct=D(pm),
            ct_pct=D(ct),
            policy=EBP,
        )
    assert raised.value.field == field
    assert raised.value.code == "outside_policy"


def test_ac3_3_preview_bounds_are_inclusive_and_match_thresholds() -> None:
    for rate, pm in (("1.0", "50"), ("2.0", "75"), ("1.37", "60")):
        args = dict(
            basis="unadjusted",
            benchmark_key="net_assets",
            benchmark_amount=D("16812400"),
            rate_pct=D(rate),
            pm_pct=D(pm),
            ct_pct=D("5"),
            policy=EBP,
        )
        assert m.preview(**args) == m.thresholds(**args)  # type: ignore[arg-type] -- the kwargs dict is homogeneous by construction


def test_ac3_6_final_basis_difference() -> None:
    r = m.reassess(_northwind(), final_amount=D("16861000"))
    assert (r.final_amount, r.at_rate, r.difference, r.difference_pct) == (
        D("16861000.00"),
        D("252900.00"),
        D("700.00"),
        D("0.3"),
    )


def test_ac3_8_granite_peak_five_percent_of_pre_tax_income() -> None:
    t = m.thresholds(
        basis="unadjusted",
        benchmark_key="pre_tax_income",
        benchmark_amount=D("3100000"),
        rate_pct=D("5"),
        pm_pct=D("75"),
        ct_pct=D("5"),
        policy=FS,
    )
    assert (t.overall, t.pm, t.ct) == (D("155000.00"), D("116250.00"), D("7750.00"))
    assert [
        o.key
        for o in m.options(
            basis="unadjusted",
            benchmark_key="pre_tax_income",
            benchmark_amount=D("3100000"),
            pm_pct=D("75"),
            ct_pct=D("5"),
            policy=FS,
        )
    ] == ["rate_3_0", "rate_5_0", "custom"]


def test_inputs_hash_is_by_value_and_changes_with_inputs() -> None:
    assert _northwind(rate="1.5").stamp == _northwind(rate="1.50").stamp
    assert _northwind(rate="1.5").stamp != _northwind(rate="1.6").stamp
    assert _northwind(amount="16812400").stamp != _northwind(amount="16812401").stamp


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity"])
def test_refuses_a_benchmark_that_is_not_positive(amount: str) -> None:
    with pytest.raises(m.MaterialityInvalid):
        _northwind(amount=amount)


def test_refuses_two_overall_benchmarks_and_duplicate_keys() -> None:
    row = m.BenchmarkInput("net_assets", "N", D("1"), D("1"), D("2"), "overall")
    with pytest.raises(m.MaterialityInvalid):
        m.benchmarks(
            [row, m.BenchmarkInput("x", "X", D("1"), D("1"), D("2"), "overall")], rate_pct=D("1.5")
        )
    with pytest.raises(m.MaterialityInvalid):
        m.benchmarks([row, row], rate_pct=D("1.5"))


def test_round_to_increment_half_up() -> None:
    assert m.round_to_increment(D("252186")) == D("252200.00")
    assert m.round_to_increment(D("252150")) == D("252200.00")
    assert m.round_to_increment(D("252149.99")) == D("252100.00")
    assert m.round_to_increment(D("1234"), D("1")) == D("1234.00")
