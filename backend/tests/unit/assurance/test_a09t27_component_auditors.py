"""A-09-T27 (TASK-8406; SPEC-658 F6; AUD-35 a, b): the instructions merge and the derived
deliverable words. The letter states only the component PM 105,000 and the 12,000 threshold;
a section with an unanswered placeholder Needs input, which blocks Send."""

from __future__ import annotations

from datetime import date

from abacus.modules.assurance import component_auditors as ca

TEMPLATE = [
    ("Materiality", ["Component performance materiality: {{component_pm}}."]),
    ("Misstatements", ["Report misstatements above {{clearly_trivial_threshold}}."]),
    ("Required communications", ["{{required_communications}}"]),
    ("Independence", ["Confirm your independence of the group."]),
    ("Group risks", ["{{group_risks}}"]),
]


def test_the_letter_states_only_the_component_pm_and_the_threshold() -> None:
    sections = ca.merge(
        TEMPLATE,
        {
            "component_pm": "105,000",
            "clearly_trivial_threshold": "12,000",
            "required_communications": "Interim memo: Nov 30, 2026",
        },
    )
    body = " ".join(s.body for s in sections)
    assert "105,000" in body and "12,000" in body
    assert "240,000" not in body and "180,000" not in body  # never group materiality or PM
    five = sections[4]
    assert five.number == 5 and five.needs_input and "{{group_risks}}" in five.body
    assert [s.needs_input for s in sections[:4]] == [False, False, False, False]


def test_template_sections_from_c11_blocks() -> None:
    blocks = [
        {"type": "heading", "level": 2, "text": "Materiality"},
        {"type": "paragraph", "runs": [{"type": "text", "text": "PM {{component_pm}}."}]},
        {"type": "heading", "level": 2, "text": "Timetable"},
        {"type": "paragraph", "runs": [{"type": "text", "text": "Dates."}]},
    ]
    assert ca.template_sections(blocks) == [
        ("Materiality", ["PM {{component_pm}}."]),
        ("Timetable", ["Dates."]),
    ]


def test_deliverable_words_are_derived() -> None:
    today = date(2026, 12, 1)
    assert ca.deliverable_status("expected", date(2026, 11, 30), False, today) == ("late", 1)
    assert ca.deliverable_status("expected", date(2026, 12, 5), True, today) == ("returned", None)
    assert ca.deliverable_status("received", date(2026, 11, 30), False, today) == (
        "received",
        None,
    )


def test_make_reference_question_round_trips() -> None:
    import uuid

    auditor = uuid.uuid4()
    key = ca.make_reference_question(auditor)
    assert key.startswith("make_reference.") and uuid.UUID(hex=key.split(".", 1)[1]) == auditor
