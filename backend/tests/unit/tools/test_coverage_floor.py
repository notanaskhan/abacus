"""Coverage floor with a dated exception (DEC-10, F-01-T05): the floor stays 95; an exception
only ratchets up toward it and expires; nothing can lower the floor itself."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from abacus_tools.ci import coverage_floor as cf

BACKEND = Path(__file__).resolve().parents[3]

EXCEPTION = """
decision = "DEC-10"
reason = "Measured 70% against the 95 floor; back-fill in tranches."
expires = 2026-12-01
steps = [
  { from = 2026-10-20, min = 70 },
  { from = 2026-11-06, min = 78 },
  { from = 2026-11-20, min = 87 },
]
"""


def _exception(tmp_path: Path, text: str = EXCEPTION) -> Path:
    path = tmp_path / "coverage-exception.toml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 10, 20), 70),
        (date(2026, 11, 5), 70),
        (date(2026, 11, 6), 78),
        (date(2026, 11, 30), 87),
        (date(2026, 12, 1), 95),
        (date(2027, 1, 1), 95),
    ],
)
def test_the_floor_ratchets_up_and_returns_to_95_when_the_exception_expires(
    tmp_path: Path, today: date, expected: int
) -> None:
    assert cf.effective_floor(95, cf.load(_exception(tmp_path)), today) == expected


def test_before_the_first_step_the_full_floor_applies(tmp_path: Path) -> None:
    assert cf.effective_floor(95, cf.load(_exception(tmp_path)), date(2026, 10, 1)) == 95


def test_no_exception_file_means_the_full_floor(tmp_path: Path) -> None:
    assert cf.load(tmp_path / "missing.toml") is None
    assert cf.effective_floor(95, None, date(2026, 10, 20)) == 95


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (EXCEPTION.replace("min = 78", "min = 65"), "only ratchet up"),
        (EXCEPTION.replace("min = 87", "min = 95"), "below the floor"),
        (EXCEPTION.replace('decision = "DEC-10"\n', ""), "decision"),
        (EXCEPTION.replace("expires = 2026-12-01\n", ""), "expires"),
        (
            EXCEPTION.replace("expires = 2026-12-01", "expires = 2026-10-19"),
            "after the first step",
        ),
        (EXCEPTION.replace("from = 2026-11-06", "from = 2026-10-01"), "in date order"),
    ],
)
def test_an_exception_that_could_lower_the_bar_is_refused(
    tmp_path: Path, text: str, message: str
) -> None:
    with pytest.raises(cf.ExceptionInvalid, match=message):
        cf.load(_exception(tmp_path, text))


def test_the_repository_floor_is_95_and_its_exception_ends_by_december_1() -> None:
    assert cf.configured_floor(BACKEND / "pyproject.toml") == 95
    exception = cf.load(BACKEND / "coverage-exception.toml")
    if exception is not None:
        assert exception.decision == "DEC-10"
        assert exception.expires <= date(2026, 12, 1)
