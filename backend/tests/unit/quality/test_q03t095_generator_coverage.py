"""Q-03-T095 (ADR-080): the generator-coverage sweep finds nothing on this tree, and finds what it
is seeded with: an unregistered table in a module's SQL, a decision with no tests, prose that only
looks like SQL."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import generator_coverage as g


def test_ac_the_tree_has_no_generator_gaps() -> None:
    assert g.sweep() == {"tables": [], "isolation": [], "conditions": [], "decisions": []}


def test_a_table_outside_the_registries_is_a_gap(tmp_path: Path) -> None:
    source = tmp_path / "repository.py"
    source.write_text(
        'SQL = "SELECT id FROM shadow_ledger_rows WHERE tenant_id = :t"\n', encoding="utf-8"
    )
    found = g.tables_named(source.read_text(encoding="utf-8"))
    assert found == {"shadow_ledger_rows"}


@pytest.mark.parametrize(
    "source",
    [
        '"""Every row from FIRST_LINE_ROW to the Total row."""\n',
        'SQL = "WITH recent AS (SELECT 1) SELECT * FROM recent"\n',
        'SQL = "SELECT * FROM unnest(:ids)"\n',
    ],
)
def test_prose_ctes_and_functions_are_not_tables(source: str) -> None:
    assert g.tables_named(source) == set()


def test_an_untested_decision_is_a_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    coverage = dict(g.DECISION_COVERAGE)
    coverage.pop("delegated_only")
    monkeypatch.setattr(g, "DECISION_COVERAGE", coverage)
    assert "decision `delegated_only` has no tests listed" in g.decision_gaps()
