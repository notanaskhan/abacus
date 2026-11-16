"""A-09-T13 (TASK-8094; SPEC-658 AC-1.1 to AC-1.3; DEC-5070): the consolidation's pure rules.

The structure: one root, each entity one level under its parent, three tiers at most (X-06).
The slots: every entity's current slot (interim through the interim date, or the year end) and,
with a prior period, its prior slot; missing is what is required and not stored. ETags and the
missing-slot ids are stable.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from abacus.modules.assurance import group_consolidation as svc
from abacus.modules.ledger import consolidation as c

H, OP, M, D, R = (uuid.uuid4() for _ in range(5))


def _e(cid: uuid.UUID, parent: uuid.UUID | None, level: int) -> c.StructureEntity:
    return c.StructureEntity(cid, parent, level, None, None)


HARLOW = [_e(H, None, 1), _e(OP, H, 2), _e(M, OP, 3), _e(D, OP, 3), _e(R, H, 2)]


def test_harlow_and_pike_three_tiers_are_valid() -> None:
    c.check_structure(HARLOW)


@pytest.mark.parametrize(
    ("entities", "reason"),
    [
        ([*HARLOW, _e(uuid.uuid4(), M, 4)], "fourth_tier"),
        ([_e(H, None, 1), _e(OP, None, 1)], "one_root"),
        ([_e(H, None, 1), _e(M, H, 3)], "parent_level"),
        ([_e(H, None, 1), _e(H, None, 1)], "duplicate_entity"),
    ],
)
def test_an_invalid_structure_is_refused(entities: list[c.StructureEntity], reason: str) -> None:
    with pytest.raises(c.StructureInvalid) as refused:
        c.check_structure(entities)
    assert refused.value.facts == {"reason": reason}


def _rows() -> list[c.EntityRow]:
    return [
        c.EntityRow(uuid.uuid4(), e.client_entity_id, None, e.level, None, None, n)
        for n, e in enumerate(HARLOW)
    ]


def test_ac1_3_each_entity_needs_its_interim_and_prior_slots() -> None:
    rows = _rows()
    keys = c.required_slots(rows, date(2026, 12, 31), date(2026, 8, 31), date(2025, 12, 31))
    assert len(keys) == 10
    interim = [k for k in keys if k.period_kind == "current"]
    assert {(k.label, k.period_start, k.period_end) for k in interim} == {
        ("interim", date(2026, 1, 1), date(2026, 8, 31))
    }
    prior = [k for k in keys if k.period_kind == "prior"]
    assert {(k.label, k.period_start, k.period_end) for k in prior} == {
        ("prior", date(2025, 1, 1), date(2025, 12, 31))
    }


def test_without_interim_or_prior_the_slot_is_the_year() -> None:
    keys = c.required_slots(_rows()[:1], date(2026, 12, 31), None, None)
    assert [(k.label, k.period_kind, k.period_start, k.period_end) for k in keys] == [
        ("standard", "current", date(2026, 1, 1), date(2026, 12, 31))
    ]


def test_missing_is_required_minus_stored() -> None:
    rows = _rows()
    keys = c.required_slots(rows, date(2026, 12, 31), date(2026, 8, 31), date(2025, 12, 31))
    stored = tuple(
        c.SlotRow(uuid.uuid4(), k, "attached", uuid.uuid4(), "upload", None, None, None)
        for k in keys
        if not (k.consolidation_entity_id == rows[4].id and k.period_kind == "prior")
    )
    facts = c.ConsolidationFacts(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        "Harlow & Pike FY2026",
        date(2026, 12, 31),
        date(2026, 8, 31),
        date(2025, 12, 31),
        None,
        "draft",
        "open",
        None,
        None,
        1,
        tuple(rows),
        stored,
        keys,
    )
    (missing,) = facts.missing()
    assert (missing.consolidation_entity_id, missing.label) == (rows[4].id, "prior")


def test_etags_and_missing_slot_ids_are_stable() -> None:
    assert svc.seen_version('W/"3"') == 3 == svc.seen_version("3") == svc.seen_version('"3"')
    with pytest.raises(svc.IfMatchInvalid):
        svc.seen_version("abc")
    key = c.SlotKey(uuid.uuid4(), "prior", "prior", date(2025, 1, 1), date(2025, 12, 31))
    assert svc.slot_id(key) == svc.slot_id(key)


def test_a_leap_day_year_end_starts_the_day_after() -> None:
    assert c.year_start(date(2028, 2, 29)) == date(2027, 3, 1)
