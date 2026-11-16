"""A-08-T14: the deviation log's statistics by code (AU-C 530; ADR-050)."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from abacus.modules.workpapers.compute.attribute_stats import (
    StatsInvalid,
    below_clearly_trivial,
    upper_deviation_limit,
)
from abacus.modules.workpapers.fieldwork_tests import VARIANT_OF


def test_ac_udl_reads_8_8_for_0_of_25() -> None:
    assert upper_deviation_limit(0, 25, D("0.90")) == D("8.8")


@pytest.mark.parametrize(
    ("deviations", "size", "confidence", "udl"),
    [
        (1, 60, "0.95", "7.7"),
        (0, 25, "0.95", "11.3"),
        (2, 100, "0.90", "5.2"),
        (5, 5, "0.9", "100.0"),
    ],
)
def test_udl_matches_the_exact_binomial_tables(
    deviations: int, size: int, confidence: str, udl: str
) -> None:
    assert upper_deviation_limit(deviations, size, D(confidence)) == D(udl)


def test_udl_refuses_impossible_counts() -> None:
    with pytest.raises(StatsInvalid):
        upper_deviation_limit(3, 2, D("0.9"))
    with pytest.raises(StatsInvalid):
        upper_deviation_limit(0, 25, D("1"))


def test_ac_a_1246_85_difference_below_ct_is_not_an_exception() -> None:
    assert below_clearly_trivial(D("1246.85"), D("2500.00"))
    assert below_clearly_trivial(D("-1246.85"), D("2500.00"))
    assert not below_clearly_trivial(D("2500.00"), D("2500.00"))


def test_the_three_variants_sit_on_the_shared_grid() -> None:
    assert VARIANT_OF == {
        "je_testing": "aud12_je",
        "test_of_details": "aud12_tod",
        "test_of_controls": "aud12_toc",
    }
