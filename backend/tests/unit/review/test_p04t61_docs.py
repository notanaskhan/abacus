"""P-04-T61 (TASK-3222): the review-grammar runbook covers its four incident shapes, and each
consumer note names the slot it registers and its first reviewable or decision kind."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
_RUNBOOK = _ROOT / "docs/runbooks/review-grammar.md"
_NOTES = _ROOT / "docs/architecture/reference/review-slot-consumers.md"
_SKILL = _ROOT / ".claude/skills/backend-module/SKILL.md"

_CONSUMERS = ("A-04", "A-05", "A-06", "A-07", "T-01", "T-02", "T-04", "I-01", "P-09", "P-10")


def test_ac1_runbook_covers_each_incident_shape() -> None:
    text = _RUNBOOK.read_text()
    for heading in ("Stale storms", "Projector rebuild", "Undo-window incidents", "Grant voids"):
        assert f"## {heading}" in text or heading.lower() in text.lower()
    assert "reproject_human_gates" in text
    assert "## Rehearsal log" in text


def test_ac2_each_consumer_note_names_slot_and_first_kind() -> None:
    rows = {
        line.split("|")[1].strip().split(" ")[0]: line
        for line in _NOTES.read_text().splitlines()
        if line.startswith("| ") and line.split("|")[1].strip()[:4] in _CONSUMERS
    }
    for epic in _CONSUMERS:
        assert epic in rows, epic
        cells = [c.strip() for c in rows[epic].split("|")]
        slot, first = cells[2], cells[3]
        assert "register_" in slot or "reads only" in slot, epic
        assert first, epic


def test_ac3_skill_has_the_review_slots_section() -> None:
    text = _SKILL.read_text()
    assert "## Registering with the review grammar" in text
    for slot in ("register_reviewable", "register_decision_kind", "register_gate_kind"):
        assert slot in text
