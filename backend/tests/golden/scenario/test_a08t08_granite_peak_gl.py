"""A-08-T08 (TASK-8050; SPEC-657 AC-0.8, AC-1.1, AC-1.2; DEC-5035): Granite Peak's FY2026 GL.

The generated export carries 18,426 entries and 412,903 lines; its in-period activity parses
through the NetSuite format and ties to the Jun 30 trial balance for 214 of 214 accounts at $0.00;
the firm's criteria hit exactly 142 · 38 · 61 · 17 · 9 for 236 unique entries, 34 at 61 or more;
JE-26-17994 and JE-26-17950 read as the screens show; the export fits the import cap.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

from abacus.modules.connections.gl_parse import MAX_GL_BYTES, parse_gl_to_file
from abacus.modules.ledger.general_ledger import TbAccount, validate_gl
from abacus.modules.sampling.compute import je_scoring as js
from abacus_tools.synthetic.scenarios.brightwater_hale import granite_peak_gl as g


@cache
def _entries() -> tuple[g.Entry, ...]:
    return tuple(g.entries())


@cache
def _scored() -> js.Scored:
    return js.score(g.inputs(), g.je_entries(list(_entries())))


def test_ac0_8_the_population_has_the_seed_counts() -> None:
    entries = _entries()
    assert len(entries) == g.ENTRIES == 18_426
    assert sum(e.line_count for e in entries) == g.LINES == 412_903
    assert len({e.ref for e in entries}) == len(entries)
    assert len(g.accounts()) == g.ACCOUNTS == 214


def test_ac0_8_criteria_hit_exactly_and_34_score_61_or_more() -> None:
    scored = _scored()
    assert [c.hit_count for c in scored.criteria] == [142, 38, 61, 17, 9]
    assert scored.unique_flagged == 236
    assert len(js.select_by_score(scored, g.SCORE_MIN)) == 34
    assert all(s.reason_codes for s in scored.scores if s.score)


def test_ac1_2_weekend_hits_are_true_weekends_or_published_holidays() -> None:
    by_ref = {e.ref: e for e in _entries()}
    for s in _scored().scores:
        if "weekend" in s.reason_codes:
            assert by_ref[s.entry_ref].posted_on.weekday() >= 5
        if "holiday" in s.reason_codes:
            assert by_ref[s.entry_ref].posted_on in g.HOLIDAYS.dates
    jul3 = [s for s in _scored().scores if by_ref[s.entry_ref].posted_on == date(2026, 7, 3)]
    assert jul3
    assert all("holiday" in s.reason_codes for s in jul3)


def test_the_two_named_entries_read_as_the_screens_show() -> None:
    by_ref = {s.entry_ref: s for s in _scored().scores}
    interest = next(e for e in _entries() if e.ref == "JE-26-17994")
    assert interest.amount == Decimal("100000.00")
    assert interest.posted_on == g.PERIOD_END
    assert by_ref["JE-26-17994"].reason_codes == ("round_amount", "post_close")
    bonus = next(e for e in _entries() if e.ref == "JE-26-17950")
    assert bonus.amount == Decimal("50000.00")
    assert bonus.approver is None
    assert "manual_by_role" in by_ref["JE-26-17950"].reason_codes


def test_ac1_1_the_in_period_activity_ties_214_of_214(tmp_path: Path) -> None:
    entries = list(_entries())
    raw = g.netsuite_csv(entries, through=g.PERIOD_END)
    assert len(g.netsuite_csv(entries)) <= MAX_GL_BYTES
    summary = parse_gl_to_file(
        raw, "netsuite_gl_csv", g.PERIOD_START, g.PERIOD_END, str(tmp_path / "entries.csv")
    )
    tb = [TbAccount(c, n, v) for c, n, v in g.trial_balance(entries)]
    check = validate_gl(summary, tb, period_start=g.PERIOD_START, period_end=g.PERIOD_END)
    assert check.failure is None
    assert len(check.balances) == 214
    assert sum(b.closing - b.tb_closing for b in check.balances) == Decimal("0.00")
    assert summary.je_fields_available == g.JE_FIELDS
