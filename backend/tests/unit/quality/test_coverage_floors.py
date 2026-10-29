"""Q-03-T066 (DEC-907): coverage floors per red module only rise, and stage 2 fails a red module
under its floor."""

from __future__ import annotations

import pytest

from abacus_tools.quality import coverage_floors as subject
from abacus_tools.quality.mutation import SCOPES

RUNNER = "/home/runner/work/abacus/abacus/backend"
GOOD = """# comment
schema: 1
line:
  identity/authz: 86
  evidence: 92  # trailing
branch:
  identity/authz: 52
  evidence: 76
"""


def _entry(statements: int, missing: int, branches: int, covered: int) -> dict[str, object]:
    return {
        "summary": {
            "num_statements": statements,
            "missing_lines": missing,
            "num_branches": branches,
            "covered_branches": covered,
        }
    }


def test_the_committed_file_parses_and_names_every_red_module() -> None:
    floors = subject.parse(subject.FILE.read_text(encoding="utf-8"))
    assert set(floors["line"]) == set(SCOPES) == set(floors["branch"])
    assert all(0 <= v <= 100 for kind in subject.KINDS for v in floors[kind].values())


def test_parse_reads_both_blocks() -> None:
    floors = subject.parse(GOOD)
    assert floors == {
        "line": {"identity/authz": 86, "evidence": 92},
        "branch": {"identity/authz": 52, "evidence": 76},
    }


@pytest.mark.parametrize(
    "text",
    [
        "line:\n  identity/authz: 86\n",  # no branch block
        "line:\n  identity/authz: 101\nbranch:\n  identity/authz: 1\n",  # over 100
        "line:\n  identity/authz: 86\n  identity/authz: 87\nbranch:\n  identity/authz: 1\n",
        "line:\n  nowhere: 86\nbranch:\n  nowhere: 1\n",  # not a red module
        "line:\n  identity/authz: eighty\nbranch:\n  identity/authz: 1\n",
        "  identity/authz: 86\n",  # outside a block
    ],
)
def test_parse_refuses_a_malformed_file(text: str) -> None:
    with pytest.raises(subject.FloorsInvalid):
        subject.parse(text)


def test_a_floor_may_rise_but_never_fall_or_go() -> None:
    base = subject.parse(GOOD)
    raised = subject.parse(GOOD.replace("86", "90"))
    assert subject.lowered(base, raised) == []
    fell = subject.parse(GOOD.replace("  evidence: 76", "  evidence: 70"))
    assert subject.lowered(base, fell) == ["evidence: branch 76 lowered to 70"]
    gone = subject.parse(GOOD.replace("  evidence: 92  # trailing\n", ""))
    assert subject.lowered(base, gone) == ["evidence: the line floor (92) was removed"]


def test_check_compares_with_the_base_and_reports_a_bad_head() -> None:
    assert subject.check(GOOD, GOOD) == []
    assert subject.check(GOOD, None) == []
    assert subject.check("nonsense: 1\n", GOOD)[0].startswith(subject.REL)
    lower = GOOD.replace("86", "80")
    assert subject.check(lower, GOOD) == [f"{subject.REL}: identity/authz: line 86 lowered to 80"]


def test_measure_groups_files_by_red_module_and_skips_generated_ones() -> None:
    report: dict[str, object] = {
        "files": {
            f"{RUNNER}/src/abacus/modules/identity/authz/__init__.py": _entry(100, 10, 40, 30),
            "src/abacus/modules/identity/authz/conditions.py": _entry(100, 0, 10, 10),
            "src/abacus/modules/identity/authz/_matrix.py": _entry(1000, 1000, 0, 0),
            "src/abacus/modules/practice/home.py": _entry(50, 50, 0, 0),
        }
    }
    measured = subject.measure(report)
    authz = measured["identity/authz"]
    assert (authz.files, authz.statements, authz.missing) == (2, 200, 10)
    assert authz.line == pytest.approx(95.0)
    assert authz.branch == pytest.approx(80.0)
    assert measured["compute"].files == 0


def test_below_names_each_floor_missed_and_skips_an_unmeasured_module() -> None:
    floors = subject.parse(
        "line:\n  identity/authz: 97\n  compute: 100\n"
        "branch:\n  identity/authz: 80\n  compute: 100\n"
    )
    measured = {
        "identity/authz": subject.Measured(2, 200, 10, 50, 40),
        "compute": subject.Measured(0, 0, 0, 0, 0),
    }
    assert subject.below(floors, measured) == ["identity/authz: line 95.0% is under its floor 97%"]
    met = {"identity/authz": subject.Measured(2, 200, 2, 50, 45)}
    assert subject.below(floors, met) == []
