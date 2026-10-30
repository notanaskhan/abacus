"""Q-03-T085: the M8 quality rows are derived from the registers, never set by hand.

Acceptance: both founders sign the quality rows on Fri May 28, 2027. The rows must therefore be
re-derivable on the pinned SHA: 55 back-fill items closed as 44 / 7 / 4, the back-filled suites
green (or each red one ticketed), coverage 95% global with no exception and 97% on red modules,
mutation floors recorded, no back-fill defect above SEV3, every escaped defect with its layer.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from abacus_tools.quality import m8_evidence as m8
from abacus_tools.quality.mutation import SCOPES

COLUMNS = ("TASK", "Zone", "Area", "Spec", "Sprint", "Q-03 row", "Status", "Suite or closing task")
HEAD = "| " + " | ".join(COLUMNS) + " |\n" + "|---" * len(COLUMNS) + "|\n"


def _item(task: str, status: str, q03: str = "T059", suite: str = "`backfill/test_x.py`") -> str:
    return f"| {task} | red | Area | SPEC-001 | S6 | {q03} | {status} | {suite} |\n"


def _register(backfilled: int = 44, ac: int = 7, legacy: int = 4) -> list[m8.Item]:
    rows = [_item(f"{n:03d}", "back-filled") for n in range(backfilled)]
    rows += [_item(f"{200 + n:03d}", "superseded", "T065") for n in range(ac)]
    rows += [_item(f"{300 + n:03d}", "superseded", "T065, T524") for n in range(legacy)]
    return m8.register(HEAD + "".join(rows))


def test_q1_the_planned_split_is_ready() -> None:
    check = m8.q1_backfill_closed(_register())
    assert check.ready, check.evidence


@pytest.mark.parametrize(("split"), [(43, 7, 4), (44, 8, 3), (44, 7, 5)])
def test_q1_any_other_split_is_not_ready(split: tuple[int, int, int]) -> None:
    assert not m8.q1_backfill_closed(_register(*split)).ready


def test_q1_an_open_item_or_an_unnamed_closing_suite_is_not_ready() -> None:
    items = _register()
    open_item = m8.Item("999", "T059", "todo", "`x`")
    assert "not closed: TASK-999" in m8.q1_backfill_closed([*items[:-1], open_item]).evidence
    unnamed = m8.Item("998", "T065", "superseded", "see P-07")
    assert "without a named suite: 998" in m8.q1_backfill_closed([*items[:-1], unnamed]).evidence


def _rerun(tmp_path: Path, *rows: tuple[str, str]) -> Path:
    body = "| TASK | Spec | Suites | Result | Failing |\n|---|---|---|---|---|\n"
    body += "".join(f"| {t} | SPEC-1 | 1 | {r} | — |\n" for t, r in rows)
    path = tmp_path / "backfill-rerun-2027-05-27.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_q2_all_green_is_ready_and_an_unticketed_red_is_not(tmp_path: Path) -> None:
    assert m8.q2_backfill_green(_rerun(tmp_path, ("075", "green")), "").ready
    red = _rerun(tmp_path, ("075", "green"), ("049", "red"))
    assert not m8.q2_backfill_green(red, "no ticket").ready
    assert m8.q2_backfill_green(red, "| ED-099 | ... | TASK-049 |").ready
    assert not m8.q2_backfill_green(None, "").ready


def _backend(
    tmp_path: Path, *, fail_under: int = 95, exception: str | None = None, line: int = 97
) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f"[tool.coverage.report]\nfail_under = {fail_under}\n", encoding="utf-8"
    )
    if exception is not None:
        (tmp_path / "coverage-exception.toml").write_text(
            f"expires = {exception}\n", encoding="utf-8"
        )
    (tmp_path / "coverage-thresholds.yaml").write_text(
        f"schema: 1\nline:\n  kernel/db: {line}\nbranch:\n  kernel/db: 90\n", encoding="utf-8"
    )
    return tmp_path


def test_q3_the_floor_with_no_exception_and_red_at_97_is_ready(tmp_path: Path) -> None:
    assert m8.q3_coverage(_backend(tmp_path), date(2027, 5, 28)).ready


def test_q3_a_live_exception_a_low_floor_or_a_red_module_under_97_is_not(tmp_path: Path) -> None:
    day = date(2027, 5, 28)
    assert not m8.q3_coverage(_backend(tmp_path / "a", exception="2027-06-01"), day).ready
    assert not m8.q3_coverage(_backend(tmp_path / "b", fail_under=90), day).ready
    assert not m8.q3_coverage(_backend(tmp_path / "c", line=96), day).ready
    expired = m8.q3_coverage(_backend(tmp_path / "d", exception="2026-12-01"), day)
    assert not expired.ready and "expired but is still in the tree" in expired.evidence


@pytest.fixture(autouse=True)
def _dirs(tmp_path: Path) -> None:
    for name in ("a", "b", "c", "d"):
        (tmp_path / name).mkdir()


def test_q4_every_scope_needs_a_floor(tmp_path: Path) -> None:
    body = "schema: 1\nfloors:\n" + "".join(f"  {s}: 80\n" for s in SCOPES)
    (tmp_path / "mutation-thresholds.yaml").write_text(body, encoding="utf-8")
    assert m8.q4_mutation(tmp_path).ready
    first = next(iter(SCOPES))
    (tmp_path / "mutation-thresholds.yaml").write_text(
        body.replace(f"  {first}: 80\n", ""), encoding="utf-8"
    )
    assert not m8.q4_mutation(tmp_path).ready


DEFECT_COLUMNS = (
    "ID",
    "Found",
    "Sprint",
    "Zone",
    "Path",
    "Introduced by",
    "Found by",
    "Severity",
    "Should have been caught by",
    "State",
    "Fix or holding test",
)


def _defect(*cells: str) -> str:
    return "| " + " | ".join(cells) + " |\n"


DEFECTS = (
    _defect(*DEFECT_COLUMNS)
    + "|---" * len(DEFECT_COLUMNS)
    + "|\n"
    + _defect("ED-001", "2027-01-04", "S6", "red", "`x`", "TASK-030", "Q-03-T059", "SEV4").replace(
        " |\n", " | integration | fixed | t |\n"
    )
    + _defect("ED-002", "2027-01-05", "S6", "red", "`y`", "TASK-031", "Q-03-T059", "SEV2").replace(
        " |\n", " | integration | open | t |\n"
    )
    + _defect("ED-003", "2027-01-06", "S6", "red", "`z`", "TASK-032", "Q-03-T999", "SEV1").replace(
        " |\n", " | — | open | t |\n"
    )
)


def test_q5_an_open_back_fill_defect_above_sev3_is_not_ready() -> None:
    rows = m8.defects(DEFECTS)
    check = m8.q5_backfill_severity(rows, {"Q-03-T059"})
    assert not check.ready and "ED-002" in check.evidence and "ED-003" not in check.evidence
    assert m8.q5_backfill_severity(rows[:1], {"Q-03-T059"}).ready


def test_q6_a_finding_without_its_layer_is_not_ready() -> None:
    rows = m8.defects(DEFECTS)
    check = m8.q6_layers(rows)
    assert not check.ready and "ED-003" in check.evidence
    assert m8.q6_layers(rows[:2]).ready


def test_write_replaces_only_the_generated_block(tmp_path: Path) -> None:
    gate = tmp_path / "gate.md"
    gate.write_text(f"before\n{m8.START}\nold\n{m8.END}\nafter\n", encoding="utf-8")
    m8.write(gate, "new\n")
    m8.write(gate, "newer\n")
    assert gate.read_text(encoding="utf-8") == f"before\n{m8.START}\nnewer\n{m8.END}\nafter\n"


def test_the_table_never_marks_the_sign_off_derived() -> None:
    text = m8.table([m8.Check("Q-1", "x", True, "e")], "abc1234", date(2027, 5, 28))
    assert "on `abc1234`" in text and "| Q-7 |" in text and "| by hand |" in text


@pytest.mark.source_scan
def test_the_committed_gate_has_the_generated_block() -> None:
    text = m8.GATE.read_text(encoding="utf-8")
    assert m8.START in text and m8.END in text and "| Q-1 |" in text
