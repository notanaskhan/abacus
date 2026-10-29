"""Q-03-T084 (F-09 §3.7 G3): the Pilot 0 top-10 log and its exit check.

Acceptance: the ten issues in F-09's Pilot 0 log are closed or re-filed against an owning epic
before Tue Jun 1, 2027. The check keeps the log to pilot codes, real screens and epics, makes a
closed row name its fix and a re-filed row its cut-list issue, never lets a capability be closed
as a defect, and refuses an exit with fewer than ten rows or any still open.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import pilot_log as pl

EPICS = frozenset({"R-01", "P-07", "A-01"})
SCREENS = frozenset({"POR-03", "AUD-03", "CLI-02"})
HEAD = "| " + " | ".join(pl.COLUMNS) + " |\n"
SEP = "|---|---|---|---|---|---|---|---|---|---|\n"


def _row(n: int, **over: str) -> str:
    cells = {
        "#": str(n),
        "Issue": f"#{900 + n}",
        "Pilot": "PF-A1",
        "Screen": "POR-03",
        "State": "c",
        "Severity": "SEV3",
        "Owning epic": "R-01",
        "Kind": "defect",
        "Status": "closed",
        "Resolution": f"fixed in #{1000 + n}",
    }
    cells.update(over)
    return "| " + " | ".join(cells[c] for c in pl.COLUMNS) + " |\n"


def _check(*rows: str, exit_review: bool = False) -> list[str]:
    return pl.check(HEAD + SEP + "".join(rows), EPICS, SCREENS, exit_review=exit_review)


def test_a_well_formed_resolved_row_passes() -> None:
    assert _check(_row(1)) == []


def test_an_empty_log_passes_the_shape_check_but_not_the_exit() -> None:
    assert _check() == []
    assert any("needs the top 10" in p for p in _check(exit_review=True))


def test_ten_resolved_rows_pass_the_exit() -> None:
    rows = [_row(n) for n in range(1, 9)]
    rows += [_row(9, Kind="capability", Status="re-filed", Resolution="cut list #77")]
    rows += [
        _row(10, Status="re-filed", Resolution="moved to A-01 #78", **{"Owning epic": "A-01"})
    ]
    assert _check(*rows, exit_review=True) == []


def test_an_open_row_fails_the_exit() -> None:
    rows = [_row(n) for n in range(1, 10)] + [_row(10, Status="open", Resolution="")]
    problems = _check(*rows, exit_review=True)
    assert problems == ["line 12: #910 is still open at the PW0 exit"]


@pytest.mark.parametrize(
    ("over", "words"),
    [
        ({"Pilot": "Okonkwo & Reyes LLP"}, "pilot code"),
        ({"Screen": "XYZ-99"}, "not a screen"),
        ({"State": "seven"}, "State must be"),
        ({"Severity": "high"}, "SEV1, SEV2 or SEV3"),
        ({"Owning epic": "Z-99"}, "does not exist"),
        ({"Kind": "bug"}, "defect or capability"),
        ({"Status": "done"}, "open, closed or re-filed"),
        ({"Issue": "PW0-1"}, "issue reference"),
        ({"Resolution": "fixed"}, "names its fix PR"),
        ({"Kind": "capability"}, "re-filed to its epic's cut list"),
    ],
)
def test_each_rule_refuses_its_row(over: dict[str, str], words: str) -> None:
    problems = _check(_row(1, **over))
    assert any(words in p for p in problems), problems


def test_more_than_ten_rows_is_refused() -> None:
    assert any("top 10" in p for p in _check(*(_row(n) for n in range(1, 12))))


def test_a_table_with_other_columns_is_refused() -> None:
    text = "| # | Issue | Firm |\n|---|---|---|\n"
    assert any("columns must be" in p for p in pl.check(text, EPICS, SCREENS, exit_review=False))


@pytest.mark.source_scan
def test_the_committed_log_is_well_formed_and_the_plan_knows_its_screens() -> None:
    text = pl.LOG.read_text(encoding="utf-8")
    assert pl.check(text, pl.known_epics(), pl.known_screens(), exit_review=False) == []
    assert {"POR-02", "POR-03", "AUD-03"} <= pl.known_screens()  # the screens the row exercises
    assert {"P-07", "R-01", "A-01", "K-01", "P-08"} <= pl.known_epics()


def test_the_main_entry_reads_a_given_log(tmp_path: Path) -> None:
    log = tmp_path / "log.md"
    log.write_text(HEAD + SEP + _row(1, Status="open", Resolution=""), encoding="utf-8")
    assert pl.main(["--log", str(log)]) == 0
    assert pl.main(["--log", str(log), "--exit"]) == 1
