"""The `sampling` slice (A-03-T16 part two, TASK-2716; A-03 §5.4; DEC-1767): A-03's firm content
and Northwind's Participants sample, through the services as the people the design names.

- **Firm content** (Margaret Okonkwo, Sep 1): BH-EBP-210 Table 2 through the standards import
  (published), and BH FS groupings v1 through the taxonomy import (published).
- **Northwind Participants** (AUD-11 a, b): Dana Kowalski uploads the census, v1 (409 rows) on
  Sep 15 and v2 (412) on Sep 16; Marcus Delaney builds each population, records its ties (v1's
  register is off by $182,300.00; v2 ties to the register and to the W-3), creates the sample set
  and draws Version 1 (seed 0x3C77D0) and Version 2 (seed 0x5E2A91) with the scenario seeds;
  on Sep 15 Ana Cruz and Kira Ross confirm their independence (CLI-08 left them pending),
  Margaret names Dana Kowalski the SKE designee and concludes independence (G2, DEC-1767), so
  Marcus prepares Version 2 (L1) and Hannah Leclerc approves it (L2) at 4:05 PM.

- **Granite Peak FY2026** (AUD-31 f, AUD-11 f; TASK-2717, DEC-1768): on Sep 10 Margaret adds
  Caleb Dunn to the team, its five members confirm their independence, she names Luis Ferrante
  the SKE designee and concludes (G2). On Sep 11 Simone Baptiste records the NetSuite trial
  balance (128 accounts) and adopts it, which starts the rules on BH FS groupings v1, and Caleb
  confirms the mapping (L1). On Sep 24 at 10:18 AM Simone records the subsequent-period GL, builds
  the disbursements population (1,912 payments, $38,640,200.00), creates "Disbursements" and
  draws Version 1 with seed 0x7C31B4 (24 + 16 = 40).

The FY2025 prior mapping (no FY2025 engagement exists), the Distributions set, `make fixtures
export` and the fixture equivalence test are TASK-2717's remaining list. Opt-in (`--slice
sampling`, which brings `people`, `standards` and `acceptance`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT
from abacus_tools.synthetic.scenarios.brightwater_hale.sampling_content import SEEDS
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.standards import TABLE_2
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "sampling"
NEEDS: Final = ("people", "standards", "acceptance")  # acceptance: MD and HL confirm (Sep 2)
NORTHWIND: Final = "Northwind Robotics, Inc."
GRANITE: Final = "Granite Peak Outdoor Supply, Inc."
GRANITE_TEAM: Final = ("MO", "OH", "SB", "CH", "CD")  # team_of(A2) and Caleb Dunn
SET_TITLE: Final = "Participants"
SET_PURPOSE: Final = "Eligibility, contribution and pay-rate tests on the same 25 participants"
FLAGS: Final = ("sampling.sample_sets", "ledger.tb_mapping")


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=CT)


def _event(key: str, at: datetime, kind: str, actor: str, **data: object) -> Event:
    return Event(f"sampling:{key}", at, kind, actor, SLICE, dict(data), client=NORTHWIND)


def _granite(key: str, at: datetime, kind: str, actor: str, **data: object) -> Event:
    return Event(f"sampling:granite:{key}", at, kind, actor, SLICE, dict(data), client=GRANITE)


def granite_events() -> list[Event]:
    """DEC-1768: Granite's G2 before the mapping is confirmed, as Northwind's (DEC-1767)."""
    events = [
        _granite(
            "team-added:CD",
            _at(10, 9, 0),
            "engagements.member_proposed",
            "MO",
            audit="A2",
            member="CD",
            role="senior",
            hours="40.0",
        ),
        _granite(
            "contact:luis-ferrante",
            _at(10, 9, 10),
            "organisations.granite_contact_created",
            "MO",
            contact="Luis Ferrante",
        ),
    ]
    events += [
        Event(
            f"independence:A2:{initials}",
            _at(10, 9, 30 + n),
            "engagements.member_independence_confirmed",
            initials,
            SLICE,
            {"audit": "A2"},
            client=GRANITE,
        )
        for n, initials in enumerate(GRANITE_TEAM)
    ]
    events += [
        _granite(
            "ske-designee",
            _at(10, 10, 0),
            "engagements.contact_designated",
            "MO",
            audit="A2",
            contact="Luis Ferrante",
            designation="ske_designee",
        ),
        _granite(
            "independence-concluded",
            _at(10, 10, 30),
            "engagements.independence_concluded",
            "MO",
            audit="A2",
            option="independent",
        ),
        _granite("tb", _at(11, 8, 30), "ledger.granite_tb_recorded", "SB"),
        _granite("tb-adopted", _at(11, 8, 40), "assurance.granite_tb_adopted", "SB"),
        _granite("mapping-run", _at(11, 8, 41), "assurance.granite_mapping_started", "SB"),
        _granite("mapping-confirmed", _at(11, 15, 0), "assurance.granite_mapping_confirmed", "CD"),
        _granite("gl", _at(24, 10, 18), "ledger.granite_gl_recorded", "SB"),
        _granite(
            "population",
            _at(24, 10, 18) + timedelta(seconds=20),
            "sampling.gl_population_built",
            "SB",
        ),
        _granite("set", _at(24, 10, 19), "sampling.gl_sample_set_created", "SB"),
        _granite(
            "draw",
            _at(24, 10, 19) + timedelta(seconds=30),
            "sampling.gl_version_drawn",
            "SB",
            seed=SEEDS["granite-peak-disbursements-v1"],
        ),
    ]
    return events


@register_slice(SLICE)
def sampling_events() -> list[Event]:
    firm = SETUP_AT + timedelta(hours=3)
    table = {"key": TABLE_2.key}
    events = [
        Event(f"flag:{name}", SETUP_AT, "platform.flag_set", "system", SLICE, {"flag": name})
        for name in FLAGS
    ]
    events += [
        Event(
            f"standard-create:{TABLE_2.key}",
            firm,
            "standards.created",
            "MO",
            SLICE,
            {**table, "kind": TABLE_2.kind, "name": TABLE_2.name, "owner": TABLE_2.owner},
        ),
        Event(
            f"standard-import:{TABLE_2.key}:v1",
            firm + timedelta(minutes=5),
            "standards.version_imported",
            "MO",
            SLICE,
            {**table, "version": 1},
        ),
        Event(
            f"standard-publish:{TABLE_2.key}:v1",
            firm + timedelta(minutes=10),
            "standards.version_published",
            "MO",
            SLICE,
            {**table, "version": 1},
        ),
        _event(
            "groupings-import", firm + timedelta(minutes=15), "ledger.grouping_set_imported", "MO"
        ),
        _event(
            "groupings-publish",
            firm + timedelta(minutes=20),
            "ledger.grouping_set_published",
            "MO",
        ),
    ]
    for census, day, upload, build, draw in ((1, 15, (15, 30), (16, 30), (16, 40)),
                                              (2, 16, (9, 0), (15, 0), (15, 10))):  # fmt: skip
        seed = SEEDS[f"northwind-participants-v{census}"]
        events += [
            _event(
                f"census-v{census}",
                _at(day, *upload),
                "evidence.sampling_census_uploaded",
                "system",
                census=census,
            ),
            _event(
                f"population-v{census}",
                _at(day, *build),
                "sampling.population_built",
                "MD",
                census=census,
            ),
            _event(
                f"tie-v{census}:register",
                _at(day, build[0], build[1] + 2),
                "sampling.tie_recorded",
                "MD",
                census=census,
                tie="register",
            ),
        ]
        if census == 2:
            events.append(
                _event(
                    "tie-v2:w3",
                    _at(day, build[0], build[1] + 4),
                    "sampling.tie_recorded",
                    "MD",
                    census=2,
                    tie="w3",
                )
            )
        else:
            events.append(
                _event("sample-set", _at(day, 16, 35), "sampling.sample_set_created", "MD")
            )
        events.append(
            _event(
                f"draw-v{census}",
                _at(day, *draw),
                "sampling.version_drawn",
                "MD",
                census=census,
                seed=seed,
            )
        )
    # DEC-1767: on Sep 15 Ana Cruz and Kira Ross confirm their independence on Northwind (CLI-08
    # left them pending), Margaret names Dana Kowalski the SKE designee (CLI-02) and concludes
    # independence (G2), so Version 2 is prepared and approved as AUD-11 a shows.
    events += [
        *[
            Event(
                f"independence:A1:{initials}",
                _at(15, 9, minute),
                "engagements.member_independence_confirmed",
                initials,
                SLICE,
                {"audit": "A1", "canon_on": "2026-09-15"},
                client=NORTHWIND,
            )
            for initials, minute in (("AC", 0), ("KR", 5))
        ],
        _event(
            "ske-designee",
            _at(15, 9, 30),
            "engagements.contact_designated",
            "MO",
            audit="A1",
            contact="Dana Kowalski",
            designation="ske_designee",
        ),
        _event(
            "independence-concluded",
            _at(15, 10, 0),
            "engagements.independence_concluded",
            "MO",
            audit="A1",
            option="independent",
        ),
        _event("prepare-v2", _at(16, 15, 12), "sampling.version_prepared", "MD", version=2),
        _event("approve-v2", _at(16, 16, 5), "sampling.version_approved", "HL", version=2),
    ]
    return events + granite_events()


__all__ = [
    "FLAGS",
    "GRANITE",
    "GRANITE_TEAM",
    "NEEDS",
    "SET_PURPOSE",
    "SET_TITLE",
    "SLICE",
    "granite_events",
    "sampling_events",
]
