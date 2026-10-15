"""SPEC-034 AC-2, AC-3, AC-5 (TASK-069): general ledgers generated from synthetic trial balances
reconcile in both formats; each flaw gives its own check, with details computed by code."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.modules.connections.gl_parse import (
    parse_gl_isolated,
    parse_gl_to_file,
    read_entries,
)
from abacus.modules.ledger.api import GlSummary, NormaliseError, TbAccount, validate_gl
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.general_ledger import (
    build,
    intacct_general_ledger_csv,
    netsuite_general_ledger_csv,
    qbd_general_ledger_xlsx,
    qbo_general_ledger_csv,
    xero_general_ledger_xlsx,
)
from abacus_tools.synthetic.model import TrialBalance

WRITERS = {
    "qbo_gl_csv": qbo_general_ledger_csv,
    "xero_gl_xlsx": xero_general_ledger_xlsx,
    "qbd_gl_xlsx": qbd_general_ledger_xlsx,  # TASK-071
    "netsuite_gl_csv": netsuite_general_ledger_csv,
    "intacct_gl_csv": intacct_general_ledger_csv,
}


def _world(seed: int) -> tuple[TrialBalance, date, date]:
    """The year's last trial balance before closing (income accounts still open)."""
    balances = generate(seed).client_entities[0].trial_balances
    tb = next(
        t
        for t in reversed(balances)
        if any(x.account_code[:1] not in "123" and x.debit != x.credit for x in t.lines)
    )
    return tb, date(tb.as_of.year, 1, 1), tb.as_of


def _tb(tb: TrialBalance) -> list[TbAccount]:
    return [TbAccount(x.account_code, x.account_name, x.debit - x.credit) for x in tb.lines]


def _parse(content: bytes, fmt: str, start: date, end: date, tmp: Path) -> GlSummary:
    return parse_gl_to_file(content, fmt, start, end, str(tmp / "entries.csv"))


@pytest.mark.parametrize("fmt", sorted(WRITERS))
@pytest.mark.parametrize("seed", [1, 7, 11, 23, 42])
def test_ac3_a_ledger_built_from_a_trial_balance_reconciles(
    fmt: str, seed: int, tmp_path: Path
) -> None:
    tb, start, end = _world(seed)
    gl = build(tb, start=start)
    summary = _parse(WRITERS[fmt](gl, year=end.year), fmt, start, end, tmp_path)
    check = validate_gl(summary, _tb(tb), period_start=start, period_end=end)
    assert check.failure is None
    assert all(b.closing == b.tb_closing for b in check.balances)
    entries = list(read_entries(str(tmp_path / "entries.csv")))
    assert len(entries) == summary.line_count == len(gl.postings)
    assert sum((e.debit for e in entries), Decimal(0)) == summary.total_debit
    assert summary.total_debit == summary.total_credit


@pytest.mark.parametrize("fmt", sorted(WRITERS))
@pytest.mark.parametrize(
    ("flaw", "code"),
    [
        ("missing_month", "period_mismatch"),
        ("outside_period", "period_mismatch"),
        ("unbalanced", "unbalanced"),
        ("missing_account", "missing_account"),
        ("extra_account", "extra_account"),
        ("drift", "roll_forward"),
    ],
)
def test_ac5_each_flaw_fails_its_own_check(fmt: str, flaw: str, code: str, tmp_path: Path) -> None:
    tb, start, end = _world(11)
    summary = _parse(
        WRITERS[fmt](build(tb, start=start, flaws=[flaw]), year=end.year),
        fmt,
        start,
        end,
        tmp_path,
    )
    check = validate_gl(summary, _tb(tb), period_start=start, period_end=end)
    assert check.failure == code
    if flaw == "drift":
        assert {d for _, d in check.accounts} == {Decimal("0.01"), Decimal("-0.01")}
    if flaw == "missing_month":
        assert check.months == (f"{start.year}-03",)
    if flaw == "extra_account":
        assert check.accounts == (("9999", Decimal("250.00")),)


def test_q6_without_printed_openings_balance_sheet_openings_are_derived(tmp_path: Path) -> None:
    tb, start, end = _world(11)
    gl = build(tb, start=start)
    bare = type(gl)(gl.accounts, {}, gl.postings)  # an export that prints no openings
    summary = _parse(
        qbo_general_ledger_csv(bare, year=end.year), "qbo_gl_csv", start, end, tmp_path
    )
    assert not summary.has_openings
    check = validate_gl(summary, _tb(tb), period_start=start, period_end=end)
    assert check.failure is None
    assert any(b.opening_derived for b in check.balances)
    assert not any(b.opening_derived for b in check.balances if b.code[:1] not in "123")


@pytest.mark.parametrize(
    ("content", "fmt", "code"),
    [
        (b"", "qbo_gl_csv", "unrecognised_format"),
        (b"PK\x03\x04garbage", "qbo_gl_csv", "unrecognised_format"),
        (b"Date,Amount\n", "nope", "unknown_format"),
        (b"just,a,csv\n1,2,3\n", "qbo_gl_csv", "unrecognised_format"),
    ],
)
def test_ac2_malformed_files_are_refused_by_code(
    content: bytes, fmt: str, code: str, tmp_path: Path
) -> None:
    with pytest.raises(NormaliseError) as refused:
        _parse(content, fmt, date(2026, 1, 1), date(2026, 12, 31), tmp_path)
    assert refused.value.code == code


def test_ac2_the_isolated_parse_returns_only_a_summary(tmp_path: Path) -> None:
    tb, start, end = _world(7)
    content = qbo_general_ledger_csv(build(tb, start=start), year=end.year)
    out = str(tmp_path / "entries.csv")
    summary = parse_gl_isolated(content, "qbo_gl_csv", start, end, out)
    assert summary.line_count == sum(1 for _ in read_entries(out))
    with pytest.raises(NormaliseError) as refused:
        parse_gl_isolated(b"\x00" * 10, "xero_gl_xlsx", start, end, out)
    assert refused.value.code == "unrecognised_format"


@pytest.mark.parametrize("made", sorted(WRITERS))
@pytest.mark.parametrize("chosen", sorted(WRITERS))
def test_ac2_a_file_from_another_system_is_refused(made: str, chosen: str, tmp_path: Path) -> None:
    """TASK-071: every format's required headers differ, so no export reads as another's."""
    tb, start, end = _world(11)
    content = WRITERS[made](build(tb, start=start), year=end.year)
    if made == chosen:
        assert _parse(content, chosen, start, end, tmp_path).line_count > 0
        return
    with pytest.raises(NormaliseError) as refused:
        _parse(content, chosen, start, end, tmp_path)
    assert refused.value.code == "unrecognised_format"
