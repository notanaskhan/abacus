"""Q-03-T087: every register ID appears once (the integration lane).

A batch of stacked PRs squash-merged one by one left five decision rows twice and one decision in
two versions on `main` (found and fixed by this task). The check names each repeated ID, says
whether the copies are the same row or two versions, and reads only the decision log's
`## Decisions` section (its facts table repeats DEC-01 to DEC-101 by design).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from abacus_tools.quality import register_ids as rid

DEC = re.compile(r"^\| (DEC-\d+) \|")


def test_a_repeated_id_is_found_with_its_lines() -> None:
    text = "## Decisions\n| DEC-1 | a |\n| DEC-2 | b |\n| DEC-1 | a |\n"
    assert rid.repeated(text, DEC, "## Decisions") == {"DEC-1": [2, 4]}


def test_rows_outside_the_section_are_not_checked() -> None:
    text = (
        "## Register facts\n| DEC-1 | fact |\n"
        "## Decisions\n| DEC-1 | decision |\n"
        "## After\n| DEC-1 | x |\n"
    )
    assert rid.repeated(text, DEC, "## Decisions") == {}


def test_check_says_same_row_or_two_versions(tmp_path: Path) -> None:
    log = tmp_path / "log.md"
    log.write_text("| ED-1 | a |\n| ED-1 | a |\n| ED-2 | a |\n| ED-2 | b |\n", encoding="utf-8")
    problems = rid.check((rid.Register(log, re.compile(r"^\| (ED-\d+) \|")),))
    assert len(problems) == 2
    assert "ED-1 on lines 1, 2 (the same row twice)" in problems[0]
    assert "ED-2 on lines 3, 4 (two versions of the row)" in problems[1]


@pytest.mark.source_scan
def test_the_committed_registers_hold_each_id_once() -> None:
    assert rid.check() == []
