"""The `sampling` slice (A-03-T16 part two, TASK-2716; A-03 §5.4; DEC-1767): A-03's firm content
and Northwind's Participants sample, through the services as the people the design names.

- **Firm content** (Margaret Okonkwo, Sep 1): BH-EBP-210 Table 2 through the standards import
  (published), and BH FS groupings v1 through the taxonomy import (published).
- **Northwind Participants** (AUD-11 a, b): Dana Kowalski uploads the census, v1 (409 rows) on
  Sep 15 and v2 (412) on Sep 16; Marcus Delaney builds each population, records its ties (v1's
  register is off by $182,300.00; v2 ties to the register and to the W-3), creates the sample set
  and draws Version 1 (seed 0x3C77D0) and Version 2 (seed 0x5E2A91) with the scenario seeds.
  Both are drafts: Version 2's L1 and approval (AUD-11 a) need Northwind's G2, which CLI-08 leaves
  unmet at E0 (DEC-1767).

Granite Peak (the 128-account trial balance, its mapping and the 1,912 disbursements), the
Distributions set, `make fixtures export` and the fixture equivalence test are TASK-2716's
remaining list. Opt-in (`--slice sampling`, which brings `people` and `standards`).
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
SET_TITLE: Final = "Participants"
SET_PURPOSE: Final = "Eligibility, contribution and pay-rate tests on the same 25 participants"
FLAGS: Final = ("sampling.sample_sets", "ledger.tb_mapping")


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=CT)


def _event(key: str, at: datetime, kind: str, actor: str, **data: object) -> Event:
    return Event(f"sampling:{key}", at, kind, actor, SLICE, dict(data), client=NORTHWIND)


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
    # AUD-11 a's "Prepared · MD" and "✓ HL" wait: R-SO-5 needs Northwind's G2, which CLI-08
    # leaves unmet at E0 (Ana Cruz has not confirmed). DEC-1767 records the conflict.
    return events


__all__ = ["FLAGS", "NEEDS", "SET_PURPOSE", "SET_TITLE", "SLICE", "sampling_events"]
