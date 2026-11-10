"""T-04-T25 (TASK-6723; T-04 §6; SPEC-649 AC-9.x): the return drafter's code rules, pure: the
box-to-field mapper, the worksheet set, the judgment guard and the checkpoint hash."""

from __future__ import annotations

import uuid
from decimal import Decimal

from abacus.modules.tax.drafter import (
    Box,
    ReturnDraftJudgment,
    TargetField,
    WorksheetJudgment,
    box_map,
    draft_hash,
    judged_set,
    map_boxes,
    worksheet_set,
)

W2 = uuid.uuid4()
K1 = uuid.uuid4()


def _box(form: str, key: str, value: str | None, version: uuid.UUID, low: bool = False) -> Box:
    return Box(uuid.uuid4(), version, form, key, value, 1, (10.0, 20.0, 30.0, 40.0), low)


def _field(
    sheet: str, key: str, current: str | None = None, derivation: str = "input"
) -> TargetField:
    return TargetField(
        sheet, uuid.uuid4(), uuid.uuid4(), key, Decimal(current) if current else None, derivation
    )


FELD = [
    _box("w2", "w2.box1", "268,400", W2),
    _box("w2", "w2.box2", "52,860", W2),
    _box("w2", "w2.box17", "17,400", W2),
    _box("k1_1065", "k1_1065.box2", "307,900", K1),
    _box("k1_1065", "k1_1065.box5", "4,600", K1),
    _box("k1_1065", "k1_1065.box18a", "1,550", K1),
    _box("k1_1065", "k1_1065.state_ny_ptet", "4,746", K1),
]
FIELDS = {
    (f.worksheet_key, f.field_key): f
    for f in (
        _field("w2", "w2.box1"),
        _field("w2", "w2.box2"),
        _field("w2", "w2.box17"),
        _field("sch_e_p2", "sch_e_p2.k1_box2"),
        _field("sch_e_p2", "sch_e_p2.k1_box5", "4600"),
        _field("it201", "it201.tax", derivation="engine"),
    )
}


def test_ac_the_feld_set_is_w2_sch_e_p2_it201_and_it653() -> None:
    assert worksheet_set(FELD) == ("w2", "sch_e_p2", "it201", "it653")
    assert worksheet_set([_box("w2", "w2.box1", "1", W2)]) == ("w2", "it201")


def test_ac_boxes_land_on_their_fields_and_box_18a_is_a_self_check_issue() -> None:
    mapped = map_boxes(2025, FELD, FIELDS)
    proposed = {(c.target.field_key, c.value) for c in mapped.changes}
    assert proposed == {
        ("w2.box1", Decimal("268400")),
        ("w2.box2", Decimal("52860")),
        ("w2.box17", Decimal("17400")),
        ("sch_e_p2.k1_box2", Decimal("307900")),
    }  # box 5 already holds 4,600: not proposed
    codes = {(g.code, g.field_key) for g in mapped.gaps}
    assert ("box_18a_state", "k1_1065.box18a") in codes
    assert ("box_unmapped", "k1_1065.state_ny_ptet") in codes


def test_an_engine_field_a_low_confidence_box_and_a_later_year_follow_the_rules() -> None:
    engine = {("w2", "w2.box1"): _field("w2", "w2.box1", derivation="engine")}
    assert map_boxes(2025, [_box("w2", "w2.box1", "268,400", W2)], engine).changes == ()
    low = map_boxes(2025, [_box("w2", "w2.box1", "268,400", W2, low=True)], FIELDS)
    assert [g.code for g in low.gaps] == ["box_low_confidence"]
    assert box_map(2027) is box_map(2025)  # a year inherits where unchanged


def _judged(worksheet: str, tsj: str, note: str) -> WorksheetJudgment:
    return WorksheetJudgment.model_validate(
        dict(zip(("key", "tsj", "new_this_year_note"), (worksheet, tsj, note), strict=True))
    )


def test_the_model_judges_only_tsj_and_notes_within_codes_offer() -> None:
    judgment = ReturnDraftJudgment(
        worksheets=[
            WorksheetJudgment(key="w2", tsj="S"),
            WorksheetJudgment(
                key="it653", tsj="T", new_this_year_note="New this year: PTET elected"
            ),
            _judged("sch_e_p2", "T", "Up 1,550 from last year"),
            WorksheetJudgment(key="it999", tsj="T"),
        ]
    )
    plans = {p.key: p for p in judged_set(("w2", "sch_e_p2", "it201", "it653"), "J", judgment)}
    assert set(plans) == {"w2", "sch_e_p2", "it201", "it653"}  # it999 was never offered
    assert (plans["w2"].tsj, plans["it201"].tsj, plans["it201"].judged) == ("S", "J", False)
    assert plans["it653"].new_this_year_note == "New this year: PTET elected"
    assert plans["sch_e_p2"].new_this_year_note is None  # a number in a note is dropped
    assert all(p.tsj == "J" for p in judged_set(("it201",), "J", None))


def test_the_checkpoint_hash_is_the_changes_in_any_order() -> None:
    changes = map_boxes(2025, FELD, FIELDS).changes
    assert draft_hash(changes) == draft_hash(tuple(reversed(changes)))
    assert len(draft_hash(changes)) == 64
