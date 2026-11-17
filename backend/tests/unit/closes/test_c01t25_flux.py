"""C-01-T25: the close flux's pure parts (SPEC-655 AC-48; CLS-10; DEC-5411)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest

from abacus.modules.closes import flux
from abacus.modules.workpapers.compute.flux import Thresholds

D = Decimal
T = Thresholds(D("10"), D("2500"))


def _august() -> list[flux.Source]:
    return [
        flux.Source("4000", "Revenue", D("309000"), D("300000")),  # +3.0%: the % leg fails
        flux.Source("6100", "Payroll", D("69030"), D("61360")),  # +7,670, 12.5%
        flux.Source("6200", "Rent", D("4000"), D("4000")),
        flux.Source("6300", "Software", D("3600"), D("2400")),  # +50%: the $ leg fails
        flux.Source("6400", "Repairs & maintenance", D("3200"), D("640")),  # +2,560, 400.0%
    ]


def test_ac48_august_against_july_flags_only_payroll_and_repairs() -> None:
    lines = flux.lines_of(_august(), T)
    over = [(x.caption, x.change, x.pct) for x in lines if x.test == "over_both"]
    assert over == [
        ("Payroll", D("7670"), D("12.5")),
        ("Repairs & maintenance", D("2560"), D("400.0")),
    ]
    assert {x.status for x in lines if x.test == "within"} == {"within_threshold"}
    assert {x.status for x in lines if x.test == "over_both"} == {"unexplained"}


def test_ac48_year_over_year_without_the_prior_year_shows_dashes() -> None:
    source = [flux.Source(s.key, s.caption, s.current, None) for s in _august()]
    lines = flux.lines_of(source, T)
    assert {x.test for x in lines} == {"not_comparable"}
    assert all(x.prior is None and x.change is None and x.pct is None for x in lines)
    assert {x.status for x in lines} == {"within_threshold"}  # nothing to explain


@pytest.mark.parametrize(
    ("period", "basis", "before"),
    [("2026-08", "mom", "2026-07"), ("2026-01", "mom", "2025-12"), ("2026-08", "yoy", "2025-08")],
)
def test_prior_period(period: str, basis: flux.Basis, before: str) -> None:
    assert flux.prior_period(period, basis) == before


def test_threshold_label_reads_as_knw04() -> None:
    assert flux.threshold_label(T) == "10% and $2,500"
    assert flux.threshold_label(Thresholds(D("7.5"), D("10000"))) == "7.5% and $10,000"


def test_line_id_is_stable_per_set_and_key() -> None:
    s = UUID(int=1)
    assert flux.line_id(s, "6100") == flux.line_id(s, "6100")
    assert flux.line_id(s, "6100") != flux.line_id(UUID(int=2), "6100")
    assert flux.line_id(s, "6100") != flux.line_id(s, "6200")


@pytest.mark.parametrize(("raw", "key"), [("6100", "6100"), ("a b/c", "a_b_c"), ("_x", "a_x")])
def test_line_key_fits_the_table_pattern(raw: str, key: str) -> None:
    assert flux.line_key(raw) == key


def test_inputs_hash_separates_a_missing_prior_from_a_zero_prior() -> None:
    zero = [flux.Source("6100", "Payroll", D("1"), D("0"))]
    missing = [flux.Source("6100", "Payroll", D("1"), None)]
    assert flux.inputs_hash("mom", zero, T) != flux.inputs_hash("mom", missing, T)
    assert flux.inputs_hash("mom", zero, T) != flux.inputs_hash("yoy", zero, T)


def test_adjusted_figures_add_the_closes_entries_in_natural_sign() -> None:
    entries = [("6100", D("500"), D("0")), ("4000", D("0"), D("1000")), ("4000", D("200"), D("0"))]
    assert flux.adjusted(D("69030"), entries, "6100", income=False) == D("69530")
    assert flux.adjusted(D("309000"), entries, "4000", income=True) == D("309800")
    assert flux.adjusted(D("4000"), entries, "6200", income=False) == D("4000")
