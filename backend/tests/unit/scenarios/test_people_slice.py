"""G-01-T06 (G-01 section 5.3; ADM-02a, ADM-02b, ADM-03a): the `people` slice before it is
loaded. Every footing figure is typed here from the ADM-02 spec and G-01 section 5.3, never read
back from the code under test: bands 7 + 7 + 11 + 14 + 5 + 2, templates 7 + 4 + 6 + 8 + 8 + 11 +
1 + 1, teams 16 + 21 + 7 + 2, offices 22 + 14 + 10, groups EQR 2, Monitoring 5, Seasonal 5, and no
47th name."""

from __future__ import annotations

from collections import Counter
from datetime import date

from abacus_tools.synthetic.scenarios.brightwater_hale import SCENARIO_HASH, build, loader
from abacus_tools.synthetic.scenarios.brightwater_hale.firm_people import (
    GROUPS,
    SEATS_TOTAL,
    TEMPLATE_OF_ROLE,
    access_ends_of,
    level_of,
    team_of,
    title_of,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.people import SEATS
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event


def _events() -> list[Event]:
    return [e for e in build(slices=("audit_core", "people")).events if e.slice == "people"]


def test_the_slice_is_registered_opt_in_and_leaves_the_default_hash() -> None:
    assert "people" in registered()
    assert all(e.slice != "people" for e in build().events)
    assert build().fingerprint() == SCENARIO_HASH
    assert loader.expand_slices(("people",)) == ("people",)


def test_bands_foot_to_46_in_the_screens_order() -> None:
    levels = [level_of(s) for s in SEATS]
    assert Counter(levels) == {
        "partner": 7,
        "manager": 7,
        "senior": 11,
        "staff": 14,
        "seasonal": 5,
        "admin": 2,
    }
    assert levels == sorted(
        levels, key=["partner", "manager", "senior", "staff", "seasonal", "admin"].index
    )


def test_templates_foot_to_46() -> None:
    counts = Counter(TEMPLATE_OF_ROLE[s.role] for s in SEATS)
    assert [counts[t] for t in (
        "partner", "manager", "tax_reviewer", "senior", "staff", "tax_preparer", "firm_admin",
        "it_security",
    )] == [7, 4, 6, 8, 8, 11, 1, 1]  # fmt: skip


def test_teams_and_offices_foot_to_46() -> None:
    teams = Counter(team_of(s) for s in SEATS)
    assert teams == {
        "Audit & assurance": 16,
        "Tax": 21,
        "Client accounting": 7,
        "Firm operations": 2,
    }
    assert Counter(s.office for s in SEATS) == {"Chicago": 22, "Denver": 14, "New York": 10}
    assert {k: len(v) for k, v in GROUPS.items()} == {
        "EQR pool": 2,
        "Monitoring reviewers": 5,
        "Seasonal": 5,
    }


def test_seasonal_access_ends_oct_31_and_only_for_the_five() -> None:
    seasonal = [s.initials for s in SEATS if access_ends_of(s) == date(2026, 10, 31)]
    assert seasonal == ["LP", "MA", "PS", "NK", "RV"]
    assert all(access_ends_of(s) is None for s in SEATS if s.initials not in seasonal)


def test_titles_are_one_per_person() -> None:
    by = {s.initials: title_of(s) for s in SEATS}
    assert by["GH"] == "Client Service Coordinator" and by["FA"] == "Qualified Individual"
    assert by["MO"] == "Managing Partner, QM owner"
    assert by["DR"] == "Tax Partner"  # SHL-03c's, the one `/v1/me` shows (TASK-397's gap)


def test_events_name_every_seat_once_and_no_47th_name() -> None:
    events = _events()
    profiles = [e for e in events if e.kind == "identity.member_profile_set"]
    assert len(profiles) == 46
    assert {e.data["initials"] for e in profiles} == {s.initials for s in SEATS}
    seats = [e for e in events if e.kind == "identity.seats_provisioned"]
    assert [e.data["seats"] for e in seats] == [SEATS_TOTAL] == [46]
    felix = next(e for e in profiles if e.data["initials"] == "FA")
    assert felix.data["template"] == "it_security"
