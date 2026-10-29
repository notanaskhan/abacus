# ac-test-author: ayushkbhatia
"""Q-03-T088 (ADR-078; chapter 10 §10.4.2, §10.14.2; DEC-10, DEC-365): the 2027 Q2 catch-up lane,
part 1, written from chapter 10 and the rows' acceptance, not from the code, for N's quality
tooling:

- T003 (weekly quality report): every §10.14.2 metric area publishes, with no commit, build or
  deploy (the report writes nothing inside the repository);
- T066 (red-module coverage floors): a PR dropping a red module below 97% line fails stage 2;
- T026 (mutation wiring): mutation jobs run only inside their budget (nightly 60 minutes, weekly 4
  hours a shard), and the nightly job mutates only red files changed in the last 24 hours;
- T027 (protected thresholds): a PR lowering a mutation floor, or dropping a scope, is refused.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus_tools.quality import mutation, mutation_floors, report

REPO = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO / ".github" / "workflows"

# Chapter 10 §10.14.2, typed by hand: the metric areas, in the chapter's order.
AREAS_10_14_2 = (
    "CI",
    "Flow",
    "Tests",
    "Security",
    "Contracts",
    "Journeys",
    "Design",
    "Accessibility",
    "Compute",
    "AI",
    "Ops",
    "Cost",
)


# --- T003: the weekly quality report -------------------------------------------------------------


def test_ac1_every_10_14_2_area_publishes_with_no_inputs(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    before = {p for p in REPO.rglob("*") if p.is_file() and ".git" not in p.parts}
    assert report.main(["--inputs", str(tmp_path / "empty"), "--out", str(out)]) in (0, 1)
    text = out.read_text(encoding="utf-8")
    for area in AREAS_10_14_2:
        assert re.search(rf"^#+ .*\b{re.escape(area)}\b", text, re.MULTILINE), area
    after = {p for p in REPO.rglob("*") if p.is_file() and ".git" not in p.parts}
    assert after == before, "the report wrote inside the repository"


def test_ac1_the_report_workflow_neither_commits_nor_deploys() -> None:
    flow = yaml.safe_load((WORKFLOWS / "quality-report.yml").read_text(encoding="utf-8"))
    runs = " ".join(
        str(step.get("run", "")) + " " + str(step.get("uses", ""))
        for job in flow["jobs"].values()
        for step in job.get("steps", [])
    )
    assert not re.search(r"git (commit|push)|deploy|terraform apply|aws s3 cp", runs)
    permissions = [flow.get("permissions", {})] + [
        job.get("permissions", {}) for job in flow["jobs"].values()
    ]
    granted = [cast(dict[str, str], p) for p in permissions if isinstance(p, dict)]
    assert all(p.get("contents", "read") == "read" for p in granted)
    assert "GITHUB_STEP_SUMMARY" in runs  # published as the job summary


# --- T066: red modules at 97% line ---------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="Q-03-T066 (red-module coverage floors) is not built yet: no per-module floor fails "
    "stage 2 (TASK-2013 records the gap)",
)
def test_ac2_a_red_module_below_97_percent_line_fails_stage_2() -> None:
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "coverage_floors" in ci


def test_ac2_the_report_flags_a_red_module_under_97(tmp_path: Path) -> None:
    """Until T066 lands, the weekly report still names a red module below 97% line."""
    coverage = {
        "files": {
            "src/abacus/modules/evidence/service.py": {
                "summary": {"covered_lines": 90, "num_statements": 100}
            },
            "src/abacus/modules/identity/authz/__init__.py": {
                "summary": {"covered_lines": 99, "num_statements": 100}
            },
        }
    }
    rows = list(report.coverage_rows(coverage))
    text = " ".join(str(vars(r)) for r in rows)
    assert "evidence" in text and "97" in text


# --- T026: mutation inside its budget -----------------------------------------------------------


def _steps(name: str) -> list[dict[str, object]]:
    flow = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    return [s for job in flow["jobs"].values() for s in job.get("steps", [])]


def _minutes(run: str) -> int | None:
    m = re.search(r"timeout\s+--signal=\w+\s+(\d+)m\s+uv run --with mutmut", run)
    return int(m.group(1)) if m else None


def test_ac3_nightly_mutmut_is_cut_at_60_minutes() -> None:
    limits = [_minutes(str(s.get("run", ""))) for s in _steps("mutation-nightly.yml")]
    bounded = [m for m in limits if m is not None]
    assert bounded and all(m <= 60 for m in bounded)


def test_ac3_weekly_mutmut_is_cut_inside_4_hours_a_shard() -> None:
    limits = [_minutes(str(s.get("run", ""))) for s in _steps("mutation-weekly.yml")]
    bounded = [m for m in limits if m is not None]
    assert bounded and all(m <= 240 for m in bounded)


def test_ac3_nightly_mutates_only_changed_red_files() -> None:
    changed = [
        "backend/src/abacus/modules/evidence/service.py",
        "backend/src/abacus/modules/review/notes.py",  # not a red scope
        "apps/web/src/main.tsx",
    ]
    picked = mutation.changed_red_files(changed)
    assert picked and all("evidence" in p for p in picked)


# --- T027: floors only rise --------------------------------------------------------------------

FLOORS = "floors:\n  evidence: 60\n  kernel/db: 70\n"


def test_ac4_a_lowered_floor_is_refused() -> None:
    lowered = FLOORS.replace("evidence: 60", "evidence: 55")
    assert mutation_floors.check(lowered, FLOORS)


def test_ac4_a_dropped_scope_is_refused() -> None:
    dropped = "floors:\n  evidence: 60\n"
    assert mutation_floors.check(dropped, FLOORS)


def test_ac4_a_raised_floor_passes() -> None:
    raised = FLOORS.replace("evidence: 60", "evidence: 65")
    assert mutation_floors.check(raised, FLOORS) == []
