"""The glossary report counts terms and "Don't use" entries per section."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import glossary_report as gr

REPO = Path(__file__).resolve().parents[4]
SAMPLE = """# Glossary

## First

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| Firm | The tenant. | `firm` | `company`, `org` |
| Abacus | Namespace. | `abacus` | — |

## Second

| Never write | Instead | Rule |
|---|---|---|
| "task" | "To-do" | R6 |

| Term | Meaning | Code name | Don't use |
|---|---|---|---|
| To-do | Work. | `todos` | `task` |
"""


def test_counts_terms_and_bans_per_section() -> None:
    assert gr.count_sections(SAMPLE) == [("First", 2, 2), ("Second", 1, 1)]


def test_real_glossary_has_non_zero_totals(capsys: pytest.CaptureFixture[str]) -> None:
    assert gr.main([str(REPO / "docs" / "product" / "glossary.md")]) == 0
    total = capsys.readouterr().out.strip().splitlines()[-1].split()
    assert total[0] == "Total"
    assert int(total[-2]) > 0
    assert int(total[-1]) > 0
