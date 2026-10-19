"""SPEC-037 AC-1, AC-2 (TASK-083): a synthetic ledger with test entries still reconciles, parses
into a population that ties, and journal entry testing selects every planted entry."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from abacus.modules.connections.gl_parse import parse_gl_to_file, read_entries
from abacus.modules.ledger.api import TbAccount, validate_gl
from abacus.modules.sampling.api import (
    Parameters,
    build_population,
    manual_kinds_for,
    select,
    tie_out,
)
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.general_ledger import build, qbo_general_ledger_csv


def test_ac2_every_planted_entry_is_selected(tmp_path: Path) -> None:
    balances = generate(7).client_entities[0].trial_balances
    tb = next(
        t
        for t in reversed(balances)
        if any(x.account_code[:1] not in "123" and x.debit != x.credit for x in t.lines)
    )
    start, end = date(tb.as_of.year, 1, 1), tb.as_of
    content = qbo_general_ledger_csv(build(tb, start=start, test_entries=True), year=end.year)
    out = tmp_path / "entries.csv"
    summary = parse_gl_to_file(content, "qbo_gl_csv", start, end, str(out))
    accounts = [TbAccount(x.account_code, x.account_name, x.debit - x.credit) for x in tb.lines]
    assert validate_gl(summary, accounts, period_start=start, period_end=end).failure is None
    population = build_population(read_entries(str(out)))
    assert (
        tie_out(population, line_count=summary.line_count, total_debit=summary.total_debit) is None
    )
    params = Parameters(
        threshold=Decimal(100_000),
        trivial=Decimal(5_000),
        year_end=end,
        manual_kinds=manual_kinds_for("import_qbo_gl_csv"),
        rare_count=0,
    )
    chosen = {s.entry.key[2]: s.rules for s in select(population, params)}
    for ref in ("TE-LARGE", "TE-ROUND", "TE-YE", "TE-WKND"):
        assert ref in chosen, ref
        assert "manual" in chosen[ref]
    assert "large" in chosen["TE-LARGE"]
    assert "round" in chosen["TE-ROUND"]
    assert {"near_year_end", "keywords"} <= set(chosen["TE-YE"])
    assert {"weekend", "keywords"} <= set(chosen["TE-WKND"])
