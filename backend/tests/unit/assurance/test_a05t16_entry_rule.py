"""A-05-T16's EBP-03 clause (TASK-5018; DEC-2482): "EBP-03 reads the entry rule from the verified
provision, never from the draft." Here: the wording code reads, what a draft or an unreadable
wording gives, and that the engine computes from the rule it is given.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from abacus.modules.assurance import ebp_attribute, ebp_eligibility_sample, ebp_provisions
from abacus.modules.assurance.compute.ebp import eligibility
from abacus.modules.assurance.compute.ebp.eligibility import EntryRule, entry_rule_from
from abacus.modules.assurance.compute.ebp.provisions import provisions_for
from abacus.modules.review.api import FieldState

ROWS = provisions_for(amendment_in_force=True)
NORTHWIND = {
    "minimum_age": "21",
    "service_requirement": "3 months (elapsed time)",
    "entry_dates": "First of month following",
}


def _state(value: str | None, levels: frozenset[int] = frozenset()) -> FieldState:
    return FieldState(None if value is None else {"t": "text", "v": value}, (), levels, ())


def _states(ticked: dict[str, str], drafted: dict[str, str]) -> dict[str, FieldState]:
    states: dict[str, FieldState] = {}
    for p in ROWS:
        if p.key in ticked:
            states[p.value_cell] = _state(ticked[p.key], frozenset({1}))
        else:
            states[p.value_cell] = _state(drafted.get(p.key))
        states[p.reference_cell] = _state(None)
    return states


def test_ac_the_handoffs_wording_reads_as_northwinds_rule() -> None:
    assert entry_rule_from(NORTHWIND) == EntryRule(minimum_age=21, service_months=3)


@pytest.mark.parametrize(
    ("age", "service", "dates", "expected"),
    [
        ("Age 21", "3 months", "First day of the month following", EntryRule(21, 3)),
        ("18 years old", "6 months of service", "first of the month following", EntryRule(18, 6)),
        ("21", "12 months", "First of the month following eligibility", EntryRule(21, 12)),
    ],
)
def test_the_rules_spelled_forms_read_the_same(
    age: str, service: str, dates: str, expected: EntryRule
) -> None:
    found = entry_rule_from(
        {"minimum_age": age, "service_requirement": service, "entry_dates": dates}
    )
    assert found == expected


@pytest.mark.parametrize(
    "change",
    [
        {"entry_dates": "First day of each calendar quarter"},
        {"service_requirement": "1 year and 1,000 hours"},
        {"service_requirement": "Three months"},
        {"minimum_age": "None"},
        {"minimum_age": "21 or 18 for union employees"},
        {"minimum_age": "<21"},
        {"minimum_age": "≠21"},
        {"service_requirement": "-3 months"},
        {"service_requirement": "> 3 months"},
        {"entry_dates": "First of month following!"},
    ],
)
def test_a_wording_code_cannot_read_is_never_guessed_at(change: dict[str, str]) -> None:
    assert entry_rule_from(NORTHWIND | change) is None


def test_ac_a_drafted_provision_never_reaches_the_rule() -> None:
    drafted = dict(NORTHWIND)
    ticked = {"minimum_age": drafted.pop("minimum_age"), "entry_dates": drafted.pop("entry_dates")}
    verified = ebp_provisions.verified_of(ROWS, _states(ticked, drafted))
    read = ebp_provisions.entry_rule_of(verified)
    assert (read.state, read.rule) == ("unverified", None)


def test_ac_three_ticks_give_the_rule() -> None:
    verified = ebp_provisions.verified_of(ROWS, _states(NORTHWIND, {}))
    read = ebp_provisions.entry_rule_of(verified)
    assert (read.state, read.rule) == ("verified", EntryRule(21, 3))


def test_a_verified_wording_code_cannot_read_is_unreadable_with_no_rule() -> None:
    ticked = NORTHWIND | {"entry_dates": "First day of each calendar quarter"}
    read = ebp_provisions.entry_rule_of(ebp_provisions.verified_of(ROWS, _states(ticked, {})))
    assert (read.state, read.rule) == ("unreadable", None)


async def test_no_ebp_02_paper_reads_as_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_paper(*_: object) -> None:
        return None

    monkeypatch.setattr(ebp_provisions, "paper_id_of_kind", no_paper)
    read = await ebp_provisions.entry_rule_read(object(), uuid.uuid4(), uuid.uuid4())  # pyright: ignore[reportArgumentType] -- never reached
    assert (read.state, read.rule) == ("unverified", None)


def test_the_engine_computes_from_the_rule_it_is_given() -> None:
    dob, hire = date(1990, 5, 15), date(2025, 3, 10)
    assert eligibility.entry(dob, hire).entry_on == date(2025, 7, 1)
    found = eligibility.entry(dob, hire, EntryRule(21, 6))
    assert (found.eligible_on, found.entry_on) == (date(2025, 9, 10), date(2025, 10, 1))
    assert found.inputs_hash != eligibility.entry(dob, hire).inputs_hash
    young = eligibility.entry(date(2007, 3, 1), date(2025, 1, 6), EntryRule(18, 3))
    assert young.eligible_on == date(2025, 4, 6)


def test_a_birthday_governs_under_any_minimum_age() -> None:
    found = eligibility.entry(date(2008, 9, 1), date(2025, 1, 6), EntryRule(18, 3))
    assert found.eligible_on == date(2026, 9, 1)
    assert found.eligible_on != found.service_on  # so EBP-03 withholds it (DEC-2225)


def test_ac_the_no_effect_note_uses_the_verified_rule() -> None:
    dob, census, hr = date(1990, 6, 14), date(2021, 3, 3), date(2021, 3, 17)
    both = ebp_attribute.hire_check("NW-1", dob, census, hr, EntryRule(21, 3))
    assert both.note == "No effect on entry: both dates give the same entry date"
    moved = ebp_attribute.hire_check(
        "NW-1", dob, date(2021, 2, 27), date(2021, 3, 2), EntryRule(21, 3)
    )
    assert moved.note is None
    none = ebp_attribute.hire_check("NW-1", dob, census, hr, None)
    assert (none.result, none.note) == ("needs_human", None)


async def test_with_no_rule_the_attribute_guard_still_gets_the_birth_date_to_scan_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`assert_masked` refuses an input carrying a date of birth; an empty list would disarm it."""
    born = date(1990, 6, 14)

    def person(hire: date) -> SimpleNamespace:
        return SimpleNamespace(name="Alicia Brennan", hire_on=hire, ssn_fp="s", dob_fp="d")

    async def rows(_tenant: object, _work_item: object, kind: str) -> dict[str, SimpleNamespace]:
        hire = date(2021, 3, 3) if kind == "census" else date(2021, 3, 17)
        return {"NW-1": person(hire)}

    async def item(*_: object) -> object:
        return SimpleNamespace(engagement_id=uuid.uuid4())

    async def no_rule(*_: object) -> ebp_provisions.EntryRuleRead:
        return ebp_provisions.EntryRuleRead("unverified")

    async def dob(*_: object) -> date:
        return born

    monkeypatch.setattr(ebp_attribute, "_rows", rows)
    monkeypatch.setattr(ebp_attribute, "assurance_item", item)
    monkeypatch.setattr(ebp_attribute, "entry_rule_read", no_rule)
    monkeypatch.setattr(ebp_attribute, "_dob", dob)
    checks, opened = await ebp_attribute._compare(object(), uuid.uuid4())  # pyright: ignore[reportPrivateUsage, reportArgumentType] -- the guard's input, with a stand-in tenant
    assert opened == [born]
    hire = next(c for c in checks if c.attribute == "hire_date")
    assert (hire.result, hire.note) == ("needs_human", None)


async def test_a_census_row_with_no_hire_date_opens_no_birth_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def never(*_: object) -> date:
        raise AssertionError("a date of birth was opened with nothing to compute")

    monkeypatch.setattr(ebp_eligibility_sample, "_dob", never)
    census = ebp_eligibility_sample._Person(  # pyright: ignore[reportPrivateUsage] -- the row's own input
        uuid.uuid4(), "NW-1", "Alicia Brennan", None, b"sealed", uuid.uuid4(), None, Decimal(8)
    )
    row = await ebp_eligibility_sample._row(  # pyright: ignore[reportPrivateUsage] -- the path under test
        object(),  # pyright: ignore[reportArgumentType] -- never reached
        1, uuid.uuid4(), "NW-1", "pass", {}, census, None, 2025, EntryRule(),
    )  # fmt: skip
    assert (row.entry_on, row.eligible_on) == (None, None)
