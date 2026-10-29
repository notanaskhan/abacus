"""Q-03-T094: the fakes register names real files, and a fake not checked against its provider's
sandbox within the window is unverified (the quality report counts them)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from abacus_tools.quality import fakes


def test_ac_every_listed_fake_and_suite_exists() -> None:
    _, listed = fakes.load()
    assert listed
    assert fakes.problems(listed) == []


def test_a_fake_never_verified_or_verified_too_long_ago_is_unverified() -> None:
    never = fakes.Fake("a.py", "P", "t.py", None)
    recent = fakes.Fake("b.py", "P", "t.py", date(2027, 6, 1))
    old = fakes.Fake("c.py", "P", "t.py", date(2027, 1, 2))
    assert fakes.unverified([never, recent, old], date(2027, 6, 30), 92) == [never, old]


def test_a_missing_file_is_a_problem(tmp_path: Path) -> None:
    (tmp_path / "t.py").write_text("", "utf-8")
    assert fakes.problems([fakes.Fake("gone.py", "P", "t.py", None)], tmp_path) == [
        "gone.py does not exist"
    ]
