"""A-04-T12 (TASK-2900; DEC-1950): the benchmark key and the policy row an audit reads."""

from __future__ import annotations

import pytest

from abacus.modules.assurance.materiality import (
    BenchmarkNotFound,
    _kind_matches,  # pyright: ignore[reportPrivateUsage] -- the policy row rule
    benchmark_key,
)


@pytest.mark.parametrize(
    ("label", "key"),
    [
        ("Net assets available for benefits", "net_assets"),
        ("Pre-tax income", "pre_tax_income"),
        ("Total expenses", "total_expenses"),
        ("Contributions (participant, employer, rollovers)", "contributions"),
        ("Benefit payments to participants", "benefit_payments"),
    ],
)
def test_the_key_is_the_label_to_its_first_connecting_word(label: str, key: str) -> None:
    assert benchmark_key(label) == key


def test_a_label_without_a_word_is_refused() -> None:
    with pytest.raises(BenchmarkNotFound):
        benchmark_key("--")


def test_an_ebp_audit_reads_the_defined_contribution_row_unless_the_plan_is_defined_benefit() -> (
    None
):
    assert _kind_matches("EBP (defined contribution)", "ebp", "dc")
    assert _kind_matches("EBP (defined contribution)", "ebp", None)
    assert not _kind_matches("EBP (defined contribution)", "ebp", "db")
    assert _kind_matches("EBP (defined benefit)", "ebp", "db")
    assert _kind_matches("For-profit FS audit", "fs", None)
    assert not _kind_matches("Not-for-profit", "fs", None)
