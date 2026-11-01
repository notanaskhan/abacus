"""A-05-T13 (TASK-2910; A-05 §3 F2; DEC-1957): the provisions registry and comparison by code.

Row acceptance (code half): "the mode proposes 20 provisions (18 for Version 1), flags the SPD
quarterly-entry conflict and the Jan 1, 2025 catch-up amendment". The run half (every quote
verifies) is the section-draft workflow's C4 check on the mode's document citations.
"""

from __future__ import annotations

from datetime import date

from abacus.modules.assurance.compute.ebp import provisions as pv

PY_END = date(2025, 12, 31)


def test_twenty_provisions_on_rows_2_to_21_and_eighteen_before_the_amendment() -> None:
    assert len(pv.PROVISIONS) == 20
    assert [p.row for p in pv.PROVISIONS] == list(range(2, 22))
    assert pv.BY_KEY["entry_dates"].value_cell == "B5"
    assert len(pv.provisions_for(amendment_in_force=False)) == 18
    assert {p.key for p in pv.PROVISIONS if p.amendment_governed} == {
        "long_term_part_time",
        "catch_up",
    }


def test_the_jan_1_2025_amendment_governs_catch_up() -> None:
    values: dict[pv.Source, str | None] = {
        "adoption_agreement": "Yes",
        "amendment": "Yes, incl. ages 60\N{EN DASH}63",
    }
    assert (
        pv.governing(
            "catch_up", values, amendment_effective_on=date(2025, 1, 1), plan_year_end=PY_END
        )
        == "amendment"
    )
    assert (
        pv.governing(
            "catch_up", values, amendment_effective_on=date(2026, 1, 1), plan_year_end=PY_END
        )
        == "adoption_agreement"
    )


def test_the_spd_quarterly_entry_is_a_conflict_and_spelling_is_not() -> None:
    found = pv.conflicts(
        {
            "entry_dates": {
                "adoption_agreement": "First of month following",
                "spd": "First day of the calendar quarter following",
            },
            "minimum_age": {"adoption_agreement": "21", "spd": " 21 "},
            "service_requirement": {
                "adoption_agreement": "3 months (elapsed time)",
                "spd": "3 Months (Elapsed time)",
            },
        },
        amendment_effective_on=date(2025, 1, 1),
        plan_year_end=PY_END,
    )
    assert [c.key for c in found] == ["entry_dates"]
    assert found[0].governing == "adoption_agreement"
