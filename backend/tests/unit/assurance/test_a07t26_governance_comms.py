"""A-07-T26 (TASK-6311; A-07 F4; AU-C 260, 265, 703; DEC-83, DEC-3011): governance communications.

Row acceptance: "The Northwind planning letter reaches only Benefits Committee grant holders, Dana
Kowalski's management grant cannot read it (INV-4), and an acknowledgement moves the row to
Acknowledged." The reading half is the room's (R-02-T12's suite); this suite holds the service's
code: composition, the regenerate merge, the output checks and AU-C 265's due date.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from abacus.modules.assurance import governance_comms as gc

FACTS = gc.Facts(
    significant_risks=(("R1", "Contributions and remittance"), ("R4", "Participant data")),
    service_organizations=((uuid.uuid4(), "Keystone Retirement Services"),),
    deficiencies=(("F-01", "significant_deficiency"),),
    findings=("F-01", "F-02"),
)


def test_the_planning_letter_is_built_from_risks_and_service_organisations() -> None:
    sections = {s.key: s for s in gc.compose("planning_260", FACTS)}
    assert list(sections) == [
        "responsibilities", "scope_timing", "significant_risks", "service_organizations",
    ]  # fmt: skip
    assert sections["significant_risks"].built_from == ("R1", "R4")
    assert "Contributions and remittance (R1)" in sections["significant_risks"].body
    assert "Keystone Retirement Services" in sections["service_organizations"].body
    assert not any(s.human_edited for s in sections.values())


def test_the_265_letter_combines_703_and_names_concluded_deficiencies() -> None:
    sections = {s.key: s for s in gc.compose("sd_mw_265", FACTS)}
    assert set(sections) == {"deficiencies", "reportable_703"}
    assert sections["deficiencies"].body == "- F-01: a significant deficiency"
    assert gc.STANDARD["sd_mw_265"] == "AU-C 265 · 703"


def test_regenerate_keeps_a_persons_edit_and_refreshes_the_rest() -> None:
    first = gc.compose("planning_260", FACTS)
    edited = [
        gc.LetterPart(s.key, s.heading, "Our words.", s.built_from, True)
        if s.key == "responsibilities"
        else s
        for s in first
    ]
    later = gc.Facts(significant_risks=(("R7", "Loans"),))
    merged = {s.key: s for s in gc.merge(edited, gc.compose("planning_260", later))}
    assert merged["responsibilities"].body == "Our words."
    assert merged["responsibilities"].human_edited
    assert merged["significant_risks"].built_from == ("R7",)


def test_output_checks_refuse_materiality_amounts_and_sas_114() -> None:
    clean = gc.compose("planning_260", FACTS)
    assert gc.letter_checks("planning_260", clean) == []
    with_materiality = [*clean, gc.LetterPart("x", "Scope", "Planning materiality is low.")]
    assert "materiality_in_planning_letter" in gc.letter_checks("planning_260", with_materiality)
    with_amount = [*clean, gc.LetterPart("x", "Scope", "Net assets of $16,812,400.")]
    assert "amount_in_planning_letter" in gc.letter_checks("planning_260", with_amount)
    old = [gc.LetterPart("x", "Basis", "Communicated under SAS 114.")]
    assert gc.letter_checks("completion_260", old) == ["sas_114"]
    # Materiality may be discussed at completion; only the planning letter refuses it.
    assert gc.letter_checks("completion_260", with_materiality[-1:]) == []


def test_au_c_265_is_due_60_days_after_release() -> None:
    released = datetime(2026, 10, 2, 21, 0, tzinfo=UTC)
    assert gc.due_on("sd_mw_265", released) == date(2026, 12, 1)
    assert gc.due_on("sd_mw_265", None) is None
    assert gc.due_on("planning_260", released) is None


def test_the_content_hash_follows_the_sections() -> None:
    a = gc.canonical(gc.compose("planning_260", FACTS))[1]
    b = gc.canonical(gc.compose("planning_260", FACTS))[1]
    c = gc.canonical(gc.compose("planning_260", gc.Facts()))[1]
    assert a == b != c
