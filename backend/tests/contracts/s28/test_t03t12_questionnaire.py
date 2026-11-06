"""T-03-T12 (TASK-3330): AC tests for the questionnaire service and answer effects, from the row:
"The suite fails against a build where the preview leaks internal_helper, an effect runs twice or a
non-owner publishes a template." The template freeze and owner-only publish, with T-03-T05's lifecycle
routes partial, are pinned on the matrix here and join the database suite once the routes land.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
import yaml

from abacus.modules.requests.answer_effects import matching, normalise
from abacus.modules.requests.questionnaire_editor import CLIENT_FIELDS, client_view, effects_to_fire

ROOT = Path(__file__).resolve().parents[4]


def _matrix(module: str) -> dict[str, dict[str, object]]:
    doc = yaml.safe_load((ROOT / f"docs/architecture/permission-matrix/{module}.yaml").read_text())
    return cast(dict[str, dict[str, object]], doc["actions"])


def test_ac_the_preview_never_leaks_helper_rules_or_tags() -> None:
    question = {
        "key": "q5",
        "client_wording": "Did you make estimated payments?",
        "type": "yes_no",
        "required": True,
        "internal_helper": "Check TAX-06",
        "effect_rules": [{"key": "r1"}],
        "effects": [{"title": "x"}],
    }
    view = client_view(question)
    for hidden in ("internal_helper", "effect_rules", "effects"):
        assert hidden not in view
        assert hidden not in CLIENT_FIELDS
    assert view["client_wording"] == question["client_wording"]


def test_ac_a_known_rule_never_fires_again_on_save() -> None:
    answered = SimpleNamespace(key="q5", answered=True, effect_rules=[{"key": "r1"}])
    current = SimpleNamespace(questions=[answered])
    proposed = [
        {
            "key": "q5",
            "effect_rules": [
                {"key": "r1", "kind": "request_item_created", "title": "Old"},
                {"key": "r2", "kind": "review_point_raised", "title": "New"},
            ],
        }
    ]
    fired = effects_to_fire(current, proposed)  # type: ignore[arg-type]
    assert [f["rule_key"] for f in fired] == ["r2"]


def test_ac_a_rule_on_an_unanswered_question_does_not_fire() -> None:
    fresh = SimpleNamespace(key="q5", answered=False, effect_rules=[])
    proposed = [{"key": "q5", "effect_rules": [{"key": "r1", "kind": "k", "title": "t"}]}]
    assert effects_to_fire(SimpleNamespace(questions=[fresh]), proposed) == []  # type: ignore[arg-type]


def test_ac_normalise_and_matching_are_exact_after_case() -> None:
    assert normalise("Yes") == normalise(" yes ")
    assert normalise(True) == normalise("yes")
    rules = [{"key": "r", "when": {"equals": "yes"}}]
    assert matching(rules, "No") == []  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "action",
    ["questionnaire.edit", "questionnaire_template.draft", "questionnaire_template.publish"],
)
def test_ac_agent_and_portal_are_denied(action: str) -> None:
    row = _matrix("requests")[action]
    for principal in ("agent", "client_admin", "client_contributor", "third_party"):
        assert row.get(principal, "deny") == "deny", (action, principal)
