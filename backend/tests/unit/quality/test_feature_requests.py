"""F-09-T128: every partner feature request has a written answer naming the epic, the deferral or
the exclusion (D1-D10, X-01-X-08; DEC-19)."""

from __future__ import annotations

import pytest

from abacus_tools.quality import feature_requests as fr

EPICS = frozenset({"R-01", "P-07", "A-09"})
HEAD = "| " + " | ".join(fr.COLUMNS) + " |\n" + "|---" * len(fr.COLUMNS) + "|\n"


def _row(verdict: str, names: str, **over: str) -> str:
    cells = {
        "#": "1",
        "Received": "2027-02-03",
        "Pilot": "PF-A1",
        "Request": "Bulk-remind every overdue request at once",
        "Verdict": verdict,
        "Names": names,
        "Answered on": "2027-02-05",
        "Answer (vault)": "V-120",
    }
    cells.update(over)
    return "| " + " | ".join(cells[c] for c in fr.COLUMNS) + " |\n"


@pytest.mark.parametrize(
    ("verdict", "names"),
    [
        ("epic", "R-01"),
        ("epic", "R-01 S18"),
        ("deferred", "P-07 cut list"),
        ("deferred", "D10"),
        ("excluded", "X-07"),
        ("excluded", "D4"),
    ],
)
def test_a_row_naming_what_its_verdict_needs_passes(verdict: str, names: str) -> None:
    assert fr.check(HEAD + _row(verdict, names), EPICS) == []


@pytest.mark.parametrize(
    ("verdict", "names", "words"),
    [
        ("epic", "Z-99", "an epic that exists"),
        ("deferred", "later", "'<epic> cut list' or D10"),
        ("deferred", "Z-99 cut list", "'<epic> cut list' or D10"),
        ("excluded", "D2", "X-01 to X-08 or D4, D6, D7, D8"),
        ("maybe", "R-01", "epic, deferred or excluded"),
    ],
)
def test_a_verdict_must_name_its_epic_deferral_or_exclusion(
    verdict: str, names: str, words: str
) -> None:
    assert any(words in p for p in fr.check(HEAD + _row(verdict, names), EPICS))


def test_every_request_has_a_written_answer() -> None:
    problems = fr.check(
        HEAD + _row("epic", "R-01", **{"Answered on": "", "Answer (vault)": "—"}), EPICS
    )
    assert any("answered in writing" in p for p in problems)
    assert any("vault reference" in p for p in problems)


def test_pilot_codes_only() -> None:
    assert any(
        "pilot code" in p
        for p in fr.check(HEAD + _row("epic", "R-01", Pilot="Okonkwo LLP"), EPICS)
    )


def test_the_committed_log_passes_and_knows_the_plans_epics() -> None:
    assert fr.check(fr.LOG.read_text(encoding="utf-8"), fr.known_epics()) == []
    assert {"R-01", "P-07", "F-09"} <= fr.known_epics()
