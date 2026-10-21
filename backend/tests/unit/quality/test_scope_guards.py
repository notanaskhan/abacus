"""F-02-T08, T10 (DEC-19): excluded identifiers match whole words only, single audit stays in the
catalogue, banned terms are found in product text, and the generated web data is current."""

from __future__ import annotations

import pytest

from abacus_tools.quality import scope_guards as sg

GUARDS = sg.load()


@pytest.mark.parametrize(
    "text",
    [
        "yellow_book",
        "framework = 'esg'",
        "PCAOB audit",
        "fund-accounting",
        "peer_benchmark_opt_in",
    ],
)
def test_t08_excluded_identifiers_are_found(text: str) -> None:
    assert list(sg.excluded_in(text, GUARDS, "x.py"))  # the matcher under test


@pytest.mark.parametrize(
    "text",
    [
        "agricultural",  # not gri
        "security review",  # not cui
        "CMMC Level 2 readiness",  # X-04's allowed neighbour
        "GAAS nonissuer",  # X-07's allowed neighbour
        "Hannah Leclerc via Agent",
        "reviewer",
        "Brightwater Hale",
    ],
)
def test_t10_the_false_positive_corpus_raises_nothing(text: str) -> None:
    assert not list(sg.excluded_in(text, GUARDS, "x.py"))
    assert not list(sg.terms_in(text, GUARDS))


def test_t08_single_audit_is_refused_outside_the_catalogue() -> None:
    assert any("single_audit" in m for m in sg.excluded_in("single_audit", GUARDS, "x.py"))


def test_t08_banned_terms_name_the_replacement() -> None:
    [message] = list(sg.terms_in("Approved by Accrued Agent", GUARDS))
    assert "via Agent" in message


def test_t08_the_repository_is_clean_and_the_web_data_current() -> None:
    assert sg.scan() == []
    assert sg.GENERATED.read_text() == sg.generated()
    assert len(GUARDS.nav) == 13
