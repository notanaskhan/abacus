"""CV-1 (TASK-9000, DEC-6005): total coverage never drops below the figure main last recorded.

The recorded total lives in `backend/coverage-baseline.toml`. Stage 1 refuses a change that lowers
it or removes it (against origin/main); stage 2 measures the combined unit and integration data and
refuses a total under it. Raising it is a normal change."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from abacus_tools.ci import coverage_ratchet as cr

BASELINE = """
decision = "DEC-6005"
measured_on = "df6b9c15f"
run = "45518852575"
total = 80.50
"""


def test_the_baseline_parses_to_its_exact_figure() -> None:
    got = cr.parse(BASELINE)
    assert got == cr.Baseline("DEC-6005", "df6b9c15f", "45518852575", D("80.50"))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            'measured_on = "x"\nrun = "1"\ntotal = 80.5',
            'the baseline names its decision (decision = "DEC-nn")',
        ),
        (
            'decision = "D-1"\nmeasured_on = "x"\nrun = "1"\ntotal = 80.5',
            'the baseline names its decision (decision = "DEC-nn")',
        ),
        (
            'decision = "DEC-1"\nrun = "1"\ntotal = 80.5',
            "the baseline names the commit it was measured on (measured_on)",
        ),
        (
            'decision = "DEC-1"\nmeasured_on = "x"\ntotal = 80.5',
            "the baseline names the CI run that measured it (run)",
        ),
        (
            'decision = "DEC-1"\nmeasured_on = "x"\nrun = "1"',
            "the baseline has a total between 0 and 100",
        ),
        (
            'decision = "DEC-1"\nmeasured_on = "x"\nrun = "1"\ntotal = 100.5',
            "the baseline has a total between 0 and 100",
        ),
        (
            'decision = "DEC-1"\nmeasured_on = "x"\nrun = "1"\ntotal = -1',
            "the baseline has a total between 0 and 100",
        ),
        (
            'decision = "DEC-1"\nmeasured_on = "x"\nrun = "1"\ntotal = "81"',
            "the baseline has a total between 0 and 100",
        ),
        (
            'decision = "DEC-1"\nmeasured_on = "x"\nrun = "1"\ntotal = 80.555',
            "the total has at most two decimals",
        ),
        ("not toml [", "the baseline is not TOML"),
    ],
)
def test_a_malformed_baseline_is_refused_with_its_reason(text: str, message: str) -> None:
    with pytest.raises(cr.BaselineInvalid) as refused:
        cr.parse(text)
    assert str(refused.value) == message


def test_an_integer_total_is_read_as_that_figure() -> None:
    got = cr.parse('decision = "DEC-1"\nmeasured_on = "x"\nrun = "1"\ntotal = 81')
    assert got.total == D("81")


def test_stage_one_refuses_a_lowered_or_removed_baseline() -> None:
    lowered = BASELINE.replace("80.50", "80.49")
    assert cr.check(lowered, BASELINE) == [
        "backend/coverage-baseline.toml: total 80.50 lowered to 80.49"
    ]
    assert cr.check(None, BASELINE) == [
        "backend/coverage-baseline.toml: the baseline was removed (it was 80.50)"
    ]


def test_stage_one_allows_an_equal_or_raised_baseline_and_a_new_file() -> None:
    assert cr.check(BASELINE, BASELINE) == []
    assert cr.check(BASELINE.replace("80.50", "82.10"), BASELINE) == []
    assert cr.check(BASELINE, None) == []  # the base predates the file


def test_stage_one_reports_a_malformed_head_and_ignores_a_malformed_base() -> None:
    assert cr.check("total = 1", BASELINE) == [
        'backend/coverage-baseline.toml: the baseline names its decision (decision = "DEC-nn")'
    ]
    assert cr.check(BASELINE, "total = 1") == []


@pytest.mark.parametrize(
    ("measured", "expected"),
    [
        (D("80.49"), ["total coverage 80.49% is under main's recorded 80.50% (DEC-6005)"]),
        (D("0.00"), ["total coverage 0.00% is under main's recorded 80.50% (DEC-6005)"]),
        (D("80.50"), []),
        (D("80.51"), []),
        (D("99.99"), []),
    ],
)
def test_stage_two_refuses_only_a_total_under_the_baseline(
    measured: D, expected: list[str]
) -> None:
    assert cr.judge(cr.parse(BASELINE), measured) == expected


def test_a_total_well_above_the_baseline_asks_for_it_to_be_raised() -> None:
    base = cr.parse(BASELINE)
    assert cr.advice(base, D("81.00")) is None  # within half a point: nothing to say
    assert cr.advice(base, D("81.01")) == (
        "total coverage 81.01% is above the recorded 80.50%: "
        "raise backend/coverage-baseline.toml to 81.01 with this change"
    )


@pytest.mark.parametrize(
    ("output", "expected"),
    [("81.37\n", D("81.37")), ("100.00", D("100.00")), ("  7.10 \n", D("7.10"))],
)
def test_the_total_is_read_from_coverage_reports_total_format(output: str, expected: D) -> None:
    assert cr.read_total(output) == expected


@pytest.mark.parametrize("output", ["", "TOTAL 81%", "81.3x", "No data to report."])
def test_an_unreadable_total_is_refused(output: str) -> None:
    with pytest.raises(cr.BaselineInvalid) as refused:
        cr.read_total(output)
    assert str(refused.value) == f"coverage report gave no total: {output.strip()!r}"


def test_the_committed_baseline_is_well_formed_and_under_the_floor() -> None:
    got = cr.parse(cr.FILE.read_text(encoding="utf-8"))
    assert got.decision == "DEC-6005"
    assert D("0") < got.total <= D("95")
