"""Q-03-T097: the flaky-test quarantine. At most 5 held, none past 10 working days; the tree holds
none today; a malformed marker, a sixth test and an overdue one each fail the check."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from abacus_tools.quality import quarantine as q

MARKED = (
    "import pytest\n\n"
    '@pytest.mark.quarantine(issue="#1", owner="ayushkbhatia", since="{since}")\n'
    "def test_{n}() -> None:\n    pass\n"
)


def _seed(root: Path, count: int, since: str = "2027-06-01") -> None:
    root.mkdir(parents=True, exist_ok=True)
    for n in range(count):
        (root / f"test_flaky_{n}.py").write_text(MARKED.format(since=since, n=n), "utf-8")


def test_ac_the_tree_holds_nothing_in_quarantine() -> None:
    held, problems = q.check(date(2026, 10, 29))
    assert (held, problems) == ([], [])


def test_the_deadline_is_ten_working_days() -> None:
    assert q.add_working_days(date(2027, 6, 1), 10) == date(2027, 6, 15)  # a Tuesday
    assert q.working_days_between(date(2027, 6, 1), date(2027, 6, 15)) == 10


def test_five_in_time_pass_and_a_sixth_or_an_overdue_fails(tmp_path: Path) -> None:
    tests, web = tmp_path / "tests", tmp_path / "web"
    _seed(tests, 5)
    assert q.check(date(2027, 6, 15), tests, web)[1] == []
    _seed(tests, 6)
    assert q.check(date(2027, 6, 15), tests, web)[1] == ["6 tests in quarantine (at most 5)"]
    assert len(q.check(date(2027, 6, 16), tests, web)[1]) == 7


def test_a_marker_without_its_owner_is_a_problem(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_bad.py").write_text(
        'import pytest\n\n@pytest.mark.quarantine(issue="#2")\ndef test_x() -> None:\n    pass\n',
        "utf-8",
    )
    assert list(q.backend(tests)) == [
        "tests/test_bad.py::test_x: quarantine needs issue, owner and since"
    ]


def test_a_playwright_annotation_is_read(tmp_path: Path) -> None:
    spec = tmp_path / "apps" / "web" / "e2e" / "flaky.spec.ts"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "// quarantine: issue=#9 owner=ayushkbhatia since=2027-06-01\ntest('x', () => {});\n",
        "utf-8",
    )
    [found] = list(q.web(tmp_path / "apps" / "web"))
    assert (found.issue, found.owner, found.deadline) == ("#9", "ayushkbhatia", date(2027, 6, 15))
