"""A-05-T20 (TASK-3019; A-05 §3 F4; DEC-2066): the eligibility engine.

Row acceptance: "Kwame's missed amounts are 2,472 and 1,442, Yuki's are 3,168 and 1,848, and the
population query returns exactly 4 participants." The four are the seed's never-enrolled
participants (EBP-03's flag "4 participants", NW-1388 and NW-1401 among them); here they stand
beside an enrolled one, an opt-out and a late hire who has not entered by year end.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.assurance.compute.ebp import eligibility as e


def test_ac_kwame_and_yuki_missed_amounts() -> None:
    kwame, yuki = e.missed(D("41200")), e.missed(D("52800"))
    assert (kwame.deferral, kwame.match) == (D("2472.00"), D("1442.00"))
    assert (yuki.deferral, yuki.match) == (D("3168.00"), D("1848.00"))


def test_ac_the_population_query_returns_exactly_four() -> None:
    def p(ref: str, hire: date, deferred: bool = False, opt_out: bool = False) -> e.Participant:
        return e.Participant(ref, date(1990, 1, 1), hire, deferred, opt_out)

    people = [
        p("NW-1388", date(2024, 3, 4)),
        p("NW-1401", date(2024, 6, 17)),
        p("NW-1422", date(2024, 9, 9)),
        p("NW-1435", date(2025, 2, 3)),
        p("NW-1450", date(2024, 1, 8), deferred=True),
        p("NW-1461", date(2024, 2, 5), opt_out=True),
        p("NW-1499", date(2025, 11, 3)),  # enters Mar 1, 2026: after the plan year
    ]
    assert e.eligible_not_enrolled_no_optout(people, date(2025, 12, 31)) == (
        "NW-1388",
        "NW-1401",
        "NW-1422",
        "NW-1435",
    )


@pytest.mark.parametrize(
    ("dob", "hire", "entry"),
    [
        (date(1990, 5, 10), date(2024, 11, 15), date(2025, 3, 1)),  # hire + 3 months governs
        (date(2004, 8, 20), date(2025, 1, 6), date(2025, 9, 1)),  # age 21 governs
        (date(1990, 1, 1), date(2024, 11, 30), date(2025, 3, 1)),  # Feb 28 clamp, then Mar 1
        (date(2004, 2, 29), date(2024, 1, 2), date(2025, 3, 1)),  # leap birthday counts Feb 28
    ],
)
def test_ac_entry_is_the_first_after_the_later_of_21_and_hire_plus_3(
    dob: date, hire: date, entry: date
) -> None:
    assert e.entry(dob, hire).entry_on == entry


def test_ac_escalation_6_plus_1_to_15() -> None:
    assert e.escalation_rate(date(2023, 4, 1), 2025) == D(8)  # Ethan Caldwell
    assert e.escalation_rate(date(2024, 7, 1), 2025) == D(7)  # Darnell Hughes, Felipe Navarro
    assert e.escalation_rate(date(2025, 2, 1), 2025) == D(6)  # 2025 entrants
    assert e.escalation_rate(date(2010, 1, 1), 2025) == D(15)
    assert e.escalation_rate(date(2026, 1, 1), 2025) == D(0)


def test_ac_row_22_needs_a_person_with_a_computed_no_effect_note() -> None:
    found = e.review(date(1990, 5, 10), date(2024, 11, 15), date(2024, 11, 20))
    assert found.requires_review and found.no_effect and found.note is not None
    assert not e.review(date(1990, 5, 10), date(2024, 11, 15), date(2024, 11, 15)).requires_review


@given(
    st.dates(min_value=date(1940, 1, 1), max_value=date(2006, 12, 31)),
    st.dates(min_value=date(2000, 1, 1), max_value=date(2030, 12, 31)),
)
def test_property_entry_is_a_first_after_both_conditions(dob: date, hire: date) -> None:
    found = e.entry(dob, hire)
    assert found.entry_on.day == 1
    assert found.entry_on > e.birthday(dob, 21) and found.entry_on > e.add_months(hire, 3)
    assert found == e.entry(dob, hire)
