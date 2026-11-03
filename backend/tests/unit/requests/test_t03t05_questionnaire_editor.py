"""T-03-T05 (TASK-3261; SPEC-643 AC-5; DEC-2241): the organizer editor.

Row acceptance: "Kevin's edits save atomically with 412 on a stale version, the preview DTO
equals the portal DTO with no internal fields, and only the template owner can publish v7 with
fresh MFA." Here: the change list, the effects a save would fire, the client projection.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from abacus.modules.requests import questionnaire_editor as qe


def _q(key: str, wording: str, **extra: object) -> qe.EditorQuestion:
    base: dict[str, object] = {
        "id": uuid4(),
        "key": key,
        "section_key": "income",
        "parent_key": None,
        "position": 0,
        "type": "yes_no",
        "client_wording": wording,
        "help_text": None,
        "internal_helper": "Check the 1099s",
        "required": False,
        "show_when": None,
        "choices": [],
        "amount_parts": [],
        "effect_rules": [],
        "answer_value": None,
        "answered_on": None,
        "answered_by": None,
    }
    base.update(extra)
    return qe.EditorQuestion(**base)  # type: ignore[arg-type] -- boto3 ships no stubs


EDITOR = qe.Editor(
    uuid4(),
    "binder",
    "2025 organizer",
    uuid4(),
    ((uuid4(), "income", "Income", 0),),
    (
        _q("q1", "Did you sell any stock?", answer_value=True, answered_on=date(2026, 8, 20)),
        _q("q2", "Did you make estimated payments?", position=1),
    ),
    3,
)


def test_changes_list_wording_reorder_and_retire_in_order() -> None:
    proposed = [
        {"key": "q2", "client_wording": "Did you make estimated tax payments?", "required": True},
        {"key": "q3", "client_wording": "Any new dependents?"},
    ]
    kinds = [(c["question_key"], c["kind"]) for c in qe.changes(EDITOR, proposed)]
    assert ("q2", "wording") in kinds and ("q2", "required") in kinds
    assert ("q2", "reordered") in kinds
    assert ("q3", "added") in kinds
    assert ("q1", "retired") in kinds


def test_a_new_rule_on_an_answered_question_fires_on_save() -> None:
    proposed = [
        {
            "key": "q1",
            "client_wording": "Did you sell any stock?",
            "effect_rules": [
                {"key": "r1", "kind": "raise_review_point", "when_equals": "yes", "title": "Basis"}
            ],
        }
    ]
    fired = qe.effects_to_fire(EDITOR, proposed)
    assert fired == [
        {"question_key": "q1", "rule_key": "r1", "kind": "raise_review_point", "title": "Basis"}
    ]


def test_the_client_projection_never_carries_internal_fields() -> None:
    view = qe.client_view(EDITOR.questions[0])
    assert "internal_helper" not in view and "effect_rules" not in view
    assert set(view) == set(qe.CLIENT_FIELDS)


def test_counts_read_answered_of_total() -> None:
    counts = EDITOR.counts()
    assert (counts["answered"], counts["questions"]) == (1, 2)
    assert counts["last_answer_on"] == date(2026, 8, 20)
