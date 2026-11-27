"""Q-03-T367 (TASK-8959): the compute engines' canonical input hashes, pinned.

`inputs_hash` is a contract: the same inputs always give the same digest (a recompute that changes
nothing is the same version), and every input the engine reads changes it. The quarterly mutation
sweep found the hashes' canonical bodies unguarded: a dropped field, a reordered sort or a changed
key survived, because the suites only compared two digests of the same inputs. Each engine below
pins one digest (recorded from the engine at this version; a change to the canonical body is a
new engine version, ADR-050) and shows that each field it hashes moves the digest.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal as D

import pytest

from abacus.modules.closes.compute import reconciliation as rec
from abacus.modules.closes.compute import schedules as sch
from abacus.modules.sampling.compute import je_scoring as js
from abacus.modules.sampling.compute import je_selection as jsel

# --- the bank reconciliation -------------------------------------------------------------------

_LINES = (
    rec.StatementLine(
        "s2", date(2026, 8, 12), "CHECK 2281", D("410.00"), None, confidence=D("0.95")
    ),
    rec.StatementLine("s1", date(2026, 8, 3), "Square deposit", None, D("1250.40")),
)
_REGISTER = (
    rec.RegisterLine("r2", date(2026, 8, 10), D("-410.00"), number="#2281"),
    rec.RegisterLine("r1", date(2026, 8, 3), D("1250.40")),
)
_PRIOR = (
    rec.PriorItem("p1", "bank", "outstanding_check", date(2026, 7, 28), D("95.00"), "#2270", "r0"),
)
_REC = rec.Inputs(
    period_end=date(2026, 8, 31),
    book_balance=D("10000"),
    balance_per_bank=D("10305.00"),
    statement_lines=_LINES,
    register_lines=_REGISTER,
    prior_items=_PRIOR,
)
REC_DIGEST = "7660dda295f18de72668dd541c3c29e38486e1ead2129d8e0fd4844f3b1f0f98"


def test_the_reconciliation_inputs_hash_is_pinned() -> None:
    assert rec.inputs_hash(_REC) == REC_DIGEST
    # Order-independent: the lines are sorted by id and ref before hashing.
    flipped = replace(
        _REC, statement_lines=_LINES[::-1], register_lines=_REGISTER[::-1], prior_items=_PRIOR
    )
    assert rec.inputs_hash(flipped) == REC_DIGEST
    # Amounts hash at the cent: 10000 and 10000.00 are the same input.
    assert rec.inputs_hash(replace(_REC, book_balance=D("10000.00"))) == REC_DIGEST


def _line(i: int, **kw: object) -> tuple[rec.StatementLine, ...]:
    lines = list(_LINES)
    lines[i] = replace(lines[i], **kw)
    return tuple(lines)


def _reg(i: int, **kw: object) -> tuple[rec.RegisterLine, ...]:
    regs = list(_REGISTER)
    regs[i] = replace(regs[i], **kw)
    return tuple(regs)


def _prior(**kw: object) -> tuple[rec.PriorItem, ...]:
    return (replace(_PRIOR[0], **kw),)


@pytest.mark.parametrize(
    "changed",
    [
        replace(_REC, period_end=date(2026, 9, 30)),
        replace(_REC, book_balance=D("10000.01")),
        replace(_REC, balance_per_bank=None),
        replace(_REC, balance_per_bank=D("10305.01")),
        replace(_REC, statement_lines=_line(0, id="s3")),
        replace(_REC, statement_lines=_line(0, txn_date=date(2026, 8, 13))),
        replace(_REC, statement_lines=_line(0, withdrawal=D("410.01"))),
        replace(_REC, statement_lines=_line(0, description="CHECK 2282")),
        replace(_REC, statement_lines=_line(0, confidence=D("0.96"))),
        replace(_REC, statement_lines=_LINES[:1]),
        replace(_REC, register_lines=_reg(0, ref="r3")),
        replace(_REC, register_lines=_reg(0, txn_date=date(2026, 8, 11))),
        replace(_REC, register_lines=_reg(0, amount=D("-410.01"))),
        replace(_REC, register_lines=_reg(0, number="#2282")),
        replace(_REC, register_lines=_reg(1, number="1001")),
        replace(_REC, prior_items=_prior(id="p2")),
        replace(_REC, prior_items=_prior(side="book")),
        replace(_REC, prior_items=_prior(kind="deposit_in_transit")),
        replace(_REC, prior_items=_prior(txn_date=date(2026, 7, 29))),
        replace(_REC, prior_items=_prior(amount=D("95.01"))),
        replace(_REC, prior_items=_prior(register_line_ref="r9")),
        replace(_REC, prior_items=_prior(register_line_ref=None)),
        replace(_REC, prior_items=()),
        replace(_REC, date_window_days=8),
        replace(_REC, stale_after_days=91),
        replace(_REC, confidence_floor=D("0.801")),
    ],
    ids=lambda x: "case",
)
def test_every_reconciliation_input_moves_the_hash(changed: rec.Inputs) -> None:
    assert rec.inputs_hash(changed) != REC_DIGEST


def test_the_reconciliation_result_hashes_are_pinned() -> None:
    result = rec.reconcile(_REC)
    assert result.engine_version == "closes.reconciliation/2"
    assert result.inputs_hash == REC_DIGEST
    assert (
        result.content_hash == "12fce7e9d401819f2e5c07e7cc0cb0d0cdabbfd4ea7be1e3e2279bb3772e7473"
    )


# --- the close schedules -----------------------------------------------------------------------

_ARR = sch.Arrangement(
    kind="prepaid",
    scheduled_total=D("1200"),
    start_on=date(2026, 1, 1),
    finish_on=date(2026, 12, 31),
    frequency="monthly",
    starting_balance=D("100"),
)
SCH_DIGEST = "069e6ed5cc24622a16c508d692018e2cde9217bbf8b19d41b370ad4178a702d2"


def test_the_schedule_inputs_hash_is_pinned() -> None:
    assert sch.inputs_hash(_ARR, "2026-08", D("700")) == SCH_DIGEST
    assert sch.inputs_hash(_ARR, "2026-08", D("700.00")) == SCH_DIGEST


@pytest.mark.parametrize(
    ("arrangement", "period", "gl"),
    [
        (replace(_ARR, kind="accrual"), "2026-08", D("700")),
        (replace(_ARR, scheduled_total=D("1200.01")), "2026-08", D("700")),
        (replace(_ARR, start_on=date(2026, 2, 1)), "2026-08", D("700")),
        (replace(_ARR, finish_on=date(2026, 11, 30)), "2026-08", D("700")),
        (replace(_ARR, frequency="quarterly"), "2026-08", D("700")),
        (replace(_ARR, starting_balance=D("100.01")), "2026-08", D("700")),
        (_ARR, "2026-09", D("700")),
        (_ARR, "2026-08", D("700.01")),
    ],
    ids=lambda x: "case",
)
def test_every_schedule_input_moves_the_hash(
    arrangement: sch.Arrangement, period: str, gl: D
) -> None:
    assert sch.inputs_hash(arrangement, period, gl) != SCH_DIGEST


# --- JE scoring --------------------------------------------------------------------------------

_JS = js.Inputs(
    criteria=(
        js.Criterion("round_amount", 40, {"multiple": "1000"}),
        js.Criterion("keywords", 30, {"words": "reclass,adjust"}),
    ),
    holidays=js.HolidaySet("2026.1", frozenset({date(2026, 7, 3), date(2026, 9, 7)})),
    period_end=date(2026, 8, 31),
    roles={"u2": "senior_management", "u1": "accounting_staff"},
    fields_available=frozenset({"entered_at", "posted_by"}),
)
_ENTRIES = (
    js.JeEntry(
        "je-2",
        date(2026, 8, 31),
        D("5000.00"),
        ("Reclass", "accrual"),
        "u2",
        datetime(2026, 9, 2, 10, 0),
        "manual",
    ),
    js.JeEntry("je-1", date(2026, 8, 15), D("12.34"), ("Rent",), None, None, None),
)
JS_DIGEST = "2a29569e4bfa8ca727450ffe0d5458de42feeaf83f09762c683318c0c2520a0e"


def test_the_je_scoring_inputs_hash_is_pinned() -> None:
    assert js.inputs_hash(_JS, _ENTRIES) == JS_DIGEST
    assert js.inputs_hash(_JS, _ENTRIES[::-1]) == JS_DIGEST  # entries sort before hashing


def _entry(**kw: object) -> tuple[js.JeEntry, ...]:
    return (replace(_ENTRIES[0], **kw), _ENTRIES[1])


@pytest.mark.parametrize(
    ("inputs", "entries"),
    [
        (replace(_JS, criteria=_JS.criteria[:1]), _ENTRIES),
        (
            replace(
                _JS,
                criteria=(js.Criterion("round_amount", 41, {"multiple": "1000"}), _JS.criteria[1]),
            ),
            _ENTRIES,
        ),
        (
            replace(
                _JS,
                criteria=(js.Criterion("round_amount", 40, {"multiple": "500"}), _JS.criteria[1]),
            ),
            _ENTRIES,
        ),
        (replace(_JS, holidays=js.HolidaySet("2026.2", _JS.holidays.dates)), _ENTRIES),
        (replace(_JS, holidays=js.HolidaySet("2026.1", frozenset({date(2026, 7, 3)}))), _ENTRIES),
        (replace(_JS, period_end=date(2026, 9, 30)), _ENTRIES),
        (replace(_JS, roles={"u2": "system", "u1": "accounting_staff"}), _ENTRIES),
        (replace(_JS, fields_available=frozenset({"entered_at"})), _ENTRIES),
        (_JS, _entry(ref="je-3")),
        (_JS, _entry(posted_on=date(2026, 8, 30))),
        (_JS, _entry(amount=D("5000.01"))),
        (_JS, _entry(descriptions=("Reclass",))),
        (_JS, _entry(posted_by="u1")),
        (_JS, _entry(entered_at=datetime(2026, 9, 2, 10, 1))),
        (_JS, _entry(source="system")),
        (_JS, _ENTRIES[:1]),
    ],
    ids=lambda x: "case",
)
def test_every_je_scoring_input_moves_the_hash(
    inputs: js.Inputs, entries: tuple[js.JeEntry, ...]
) -> None:
    assert js.inputs_hash(inputs, entries) != JS_DIGEST


# --- JE selection ------------------------------------------------------------------------------

_SCORES = (jsel.Scored("je-1", 80), jsel.Scored("je-2", 55), jsel.Scored("je-3", 10))
SEL_DIGEST = "e39c86ece3e07f53c1aaa888af8f917f7c98552713625b2f4196fe834c10f5e7"
SEL_ITEMS = "3ba20e01eba3322b471e6d0ed2550fd5821d9bd24fc61443e0316dbd9b0bdc5e"


def _draw(**kw: object) -> str:
    args: dict[str, object] = {"score_min": 50, "top_n": None, "unpredictable_n": 1, "seed": 7}
    args.update(kw)
    return jsel.inputs_hash(_SCORES if "scores" not in args else args.pop("scores"), **args)  # type: ignore[arg-type]  # the keyword set is select()'s


def test_the_je_selection_hashes_are_pinned() -> None:
    assert _draw() == SEL_DIGEST
    draw = jsel.select(_SCORES, score_min=50, top_n=None, unpredictable_n=1, seed=7)
    assert jsel.items_hash(draw.picks) == SEL_ITEMS


@pytest.mark.parametrize(
    "kw",
    [
        {"score_min": 51},
        {"score_min": None, "top_n": 2},
        {"top_n": 3},
        {"unpredictable_n": 2},
        {"seed": 8},
        {"scores": _SCORES[:2]},
        {"scores": (jsel.Scored("je-1", 81), *_SCORES[1:])},
        {"scores": (jsel.Scored("je-9", 80), *_SCORES[1:])},
    ],
    ids=lambda x: "case",
)
def test_every_je_selection_input_moves_the_hash(kw: dict[str, object]) -> None:
    assert _draw(**kw) != SEL_DIGEST
