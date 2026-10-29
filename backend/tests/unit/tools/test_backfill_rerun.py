"""Q-03-T059: the re-run plan reads the tracker's 44 rows (tranche 0 and back-filled) and resolves
each row's suites to test paths; a row naming none falls back to the tests citing its SPEC."""

from __future__ import annotations

from pathlib import Path

from abacus_tools.quality.backfill_rerun import TRACKER, plan, rows

ROW = "| {task} | red | Area | {spec} | S8 | T022 | {status} | {suites} |"


def _table(*lines: str) -> str:
    head = "| TASK | Zone | Area | Spec | Sprint | Q-03 row | Status | Suite or closing task |\n"
    return head + "|---|---|---|---|---|---|---|---|\n" + "\n".join(lines)


def test_the_tracker_names_44_suites_to_re_run() -> None:
    plans = plan(TRACKER.read_text(encoding="utf-8"))
    assert len(plans) == 44
    assert all(p.python or p.web for p in plans)


def test_paths_resolve_from_the_tracker_shorthand(tmp_path: Path) -> None:
    text = _table(
        ROW.format(
            task="036",
            spec="SPEC-020",
            status="back-filled",
            suites="`backfill/test_a.py`, `test_b.py`; AC-9 `legacy/spec025states.test.tsx`",
        ),
        ROW.format(task="028", spec="SPEC-013", status="superseded", suites="`backfill/x.py`"),
    )
    [found] = plan(text, tests=tmp_path)
    assert found.python == [
        "tests/integration/backfill/test_a.py",
        "tests/integration/backfill/test_b.py",
    ]
    assert found.web == ["src/legacy/spec025states.test.tsx"]
    assert [r.task for r in rows(text)] == ["036", "028"]


def test_a_row_naming_no_suite_runs_the_tests_citing_its_spec(tmp_path: Path) -> None:
    (tmp_path / "unit").mkdir()
    (tmp_path / "unit" / "test_cites.py").write_text('"""SPEC-006 AC-1."""\n')
    (tmp_path / "unit" / "test_other.py").write_text('"""SPEC-007."""\n')
    text = _table(ROW.format(task="021", spec="SPEC-006", status="tranche 0", suites="re-run"))
    [found] = plan(text, tests=tmp_path)
    assert len(found.python) == 1 and found.python[0].endswith("test_cites.py")
