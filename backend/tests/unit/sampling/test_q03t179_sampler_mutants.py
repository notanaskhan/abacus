"""Q-03-T179 (TASK-7826): the sampler packages' surviving mutants, closed from their sources.

The weekly run of 2026-11-13 (43330118713) left `sampling/compute` stats at 70.1%, canonical at
77%, draw at 83.3% and versions at 66.7% killed, under the row's 85%. The survivors were the
refusal messages, the open and closed bounds, the canonical population hash's exact bytes, the
rejection sampler's limit and the projections' two decimals. Expected values are rebuilt here from
each function's own definition (ADR-340 §5 for the stream; the population hash's line rule), never
read back from the code under test.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from decimal import Decimal

import pytest

from abacus.modules.sampling.compute import draw, stats, versions
from abacus.modules.sampling.compute.canonical import Record, canonical, normalise_key

D = Decimal


# --- canonical population --------------------------------------------------------------------


def _expected_hash(lines: list[list[object]]) -> str:
    digest = hashlib.sha256()
    for line in lines:
        digest.update(json.dumps(line, ensure_ascii=False).encode("utf-8") + b"\n")
    return digest.hexdigest()


def test_population_hash_is_the_sorted_key_and_amount_lines() -> None:
    found = canonical([Record("Café-2", D("1.005")), Record(" café-1", D(2))])
    assert [r.key for r in found.records] == [" café-1", "Café-2"]
    assert found.total == D("3.005")
    assert found.population_hash == _expected_hash([["café-1", "2.00"], ["café-2", "1.01"]])


def test_a_population_without_amounts_has_no_total() -> None:
    found = canonical([Record("b"), Record("A")])
    assert found.total is None
    assert found.population_hash == _expected_hash([["a", None], ["b", None]])


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([], "a population must hold at least one record"),
        ([Record("NW-1"), Record("nw-1 ")], "two records share a normalised key"),
        ([Record("a", D(1)), Record("b")], "either every record has an amount or none does"),
    ],
)
def test_population_refusals(records: list[Record], message: str) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        canonical(records)


def test_key_normalising() -> None:
    assert normalise_key(" NW-1184 ") == "nw-1184"
    assert normalise_key("\uff4e\uff57") == "nw"  # NFKC: fullwidth "nw"
    with pytest.raises(ValueError, match=r"^a record key must not be blank$"):
        normalise_key("   ")
    with pytest.raises(ValueError, match=r"^a record key must not hold control characters$"):
        normalise_key("nw\x07-1")
    assert normalise_key("nw­1") == "nw­1"  # a format character (Cf) is not a control


# --- the draw stream (ADR-340 §5) ---------------------------------------------------------------


def _reference_below(rng: random.Random, bound: int) -> int:
    limit = (2**32 // bound) * bound
    word = rng.getrandbits(32)
    while word >= limit:
        word = rng.getrandbits(32)
    return word % bound


def test_stream_rejects_words_past_the_largest_multiple() -> None:
    bound = 2**31 + 1  # one multiple fits: about half the words are redrawn
    stream = draw.Stream(4118)
    reference = random.Random(4118)  # the stream's own PRNG (ADR-340 §5)
    assert [stream.below(bound) for _ in range(20)] == [
        _reference_below(reference, bound) for _ in range(20)
    ]
    assert draw.Stream(7).below(1) == 0


def test_stream_seed_and_bound_refusals() -> None:
    draw.Stream(0)
    draw.Stream(draw.SEED_MAX)
    for seed in (-1, draw.SEED_MAX + 1):
        with pytest.raises(ValueError, match=r"^a seed is a 24-bit value$"):
            draw.Stream(seed)
    stream = draw.Stream(1)
    for bound in (0, -3):
        with pytest.raises(ValueError, match=r"^bound must be positive$"):
            stream.below(bound)


def test_partial_fisher_yates_bounds() -> None:
    assert draw.partial_fisher_yates(draw.Stream(1), 5, 0) == []
    whole = draw.partial_fisher_yates(draw.Stream(1), 5, 5)
    assert sorted(whole) == [0, 1, 2, 3, 4]
    for count in (-1, 6):
        with pytest.raises(ValueError, match=r"^count must lie between 0 and the population$"):
            draw.partial_fisher_yates(draw.Stream(1), 5, count)


def test_an_unknown_sampler_version() -> None:
    assert versions.sampler(versions.CURRENT).identifier == versions.CURRENT
    with pytest.raises(KeyError) as raised:
        versions.sampler("v9.9")
    assert raised.value.args == ("unknown_sampler_version",)


# --- statistics ---------------------------------------------------------------------------------


def test_rate_bounds_and_their_messages() -> None:
    with pytest.raises(ValueError, match=r"^confidence must lie in \(0, 1\)$"):
        stats.attribute_size(1, D("0.05"))
    with pytest.raises(ValueError, match=r"^confidence must lie in \(0, 1\)$"):
        stats.attribute_size(0, D("0.05"))
    with pytest.raises(ValueError, match=r"^tolerable_rate must lie in \(0, 1\)$"):
        stats.attribute_size(D("0.95"), 1)
    with pytest.raises(ValueError, match=r"^expected_rate must lie in \[0, 1\)$"):
        stats.attribute_size(D("0.95"), D("0.05"), 1)
    with pytest.raises(ValueError, match=r"^confidence must lie in \(0, 1\)$"):
        stats.udl(0, 10, 1)


def test_attribute_size_with_no_expected_deviation() -> None:
    # The smallest n with (1 - 0.05)^n <= 0.05.
    expected = math.ceil(math.log(0.05) / math.log(0.95))
    assert stats.attribute_size(D("0.95"), D("0.05")) == expected == 59
    assert stats.attribute_size(0.95, 0.05) == 59  # floats are read through their text
    with pytest.raises(ValueError, match=r"^the expected rate must be below the tolerable rate$"):
        stats.attribute_size(D("0.95"), D("0.05"), D("0.05"))


def test_binomial_cdf_is_exactly_one_at_and_past_n() -> None:
    assert str(stats.binomial_cdf(3, 3, D("0.3"))) == "1"
    assert str(stats.binomial_cdf(4, 3, D("0.3"))) == "1"
    assert stats.binomial_cdf(0, 2, D("0.5")) == D("0.25")
    assert stats.binomial_cdf(1, 2, D("0.5")) == D("0.75")


def test_udl_edges() -> None:
    assert stats.udl(5, 5, D("0.95")) == D(1)
    for deviations, size in ((0, 0), (-1, 5), (6, 5)):
        with pytest.raises(
            ValueError, match=r"^deviations must lie between 0 and a positive size$"
        ):
            stats.udl(deviations, size, D("0.95"))
    # Clopper-Pearson with no deviation has a closed form: 1 - (1 - confidence)^(1/size).
    limit = stats.udl(0, 59, D("0.95"))
    assert abs(float(limit) - (1 - 0.05 ** (1 / 59))) < 1e-9
    assert D(0) < limit < D(1)
    assert stats.udl_percent(0, 59, D("0.95")) == D("5.0")


def test_projections_are_two_decimals_and_refuse_an_empty_sample() -> None:
    assert str(stats.projected_misstatement(2140, 25, 412)) == "35267.20"
    assert stats.projected_misstatement(D(10), 1, 1) == D("10.00")
    for sample, population in ((0, 10), (11, 10)):
        with pytest.raises(
            ValueError, match=r"^the sample must be a non-empty part of the population$"
        ):
            stats.projected_misstatement(1, sample, population)
    assert str(stats.projected_misstatement_ratio(D(10), D(3), D(100))) == "333.33"
    assert stats.projected_misstatement_ratio(D(1), D(1), D(5)) == D("5.00")
    for sample in (0, -1):
        with pytest.raises(ValueError, match=r"^the sample amount must be positive$"):
            stats.projected_misstatement_ratio(D(1), sample, D(5))
