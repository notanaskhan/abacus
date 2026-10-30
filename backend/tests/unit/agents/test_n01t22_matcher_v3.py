"""N-01-T22 (TASK-2230; DEC-1276): the matcher's v3 spec, its two modes and its intake module's
reach. No code path in intake mode files, ignores, holds or supersedes (the row's acceptance)."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from abacus.ai_gateway import EVAL_SUITES
from abacus.ai_gateway._eval_suites import EVAL_SUITE_MODES
from abacus.ai_gateway.prompts import prompt
from abacus.modules.agents import intake_match
from abacus.modules.agents.handoff import IntakeMatchOutput
from abacus.modules.agents.spec import spec

MODULE = Path(intake_match.__file__)
# Whatever decides an attachment lives behind these names; the matcher may import none of them.
DECIDES = ("apply", "file_intake", "ignore", "hold", "supersede", "keep_both", "rename", "triage")


def test_v3_describes_intake_and_keeps_engagement_on_v2() -> None:
    matcher = spec("evidence.matcher")
    assert matcher.version == 3
    assert (matcher.prompt, matcher.input_schema, matcher.output_schema) == (
        "evidence.inbox_match@v3",
        "IntakeMatchInput",
        "IntakeMatchOutput",
    )
    assert matcher.limits.max_cost_usd == Decimal("0.015")
    engagement = matcher.modes["engagement"]
    assert (engagement.prompt, engagement.output_schema) == (
        "evidence.inbox_match@v2",
        "MatchOutput",
    )
    assert engagement.max_cost_usd == Decimal("0.01")
    assert matcher.confidence_routing.below == Decimal("0.5")
    assert matcher.task_scope == frozenset({"evidence.read", "inbox_match.run"})


def test_both_prompts_are_registered_and_eligible_on_their_own_evaluation() -> None:
    assert prompt("evidence.inbox_match@v3")
    assert prompt("evidence.inbox_match@v2")
    assert EVAL_SUITES["evidence.matcher"][0] == "evidence.inbox_match@v3"
    assert "evidence.inbox_match@v2" in EVAL_SUITE_MODES["evidence.matcher"]


def test_the_output_is_proposals_or_none_fit_never_both() -> None:
    classification = {"form_family": None, "kind": "receipt", "confidence": 0.4}
    IntakeMatchOutput.model_validate(
        {"none_fit": True, "classification": classification, "proposals": []}
    )
    with pytest.raises(ValidationError):
        IntakeMatchOutput.model_validate(
            {"none_fit": False, "classification": classification, "proposals": []}
        )
    with pytest.raises(ValidationError):  # references are D1..D60 only
        IntakeMatchOutput.model_validate(
            {
                "none_fit": False,
                "classification": classification,
                "proposals": [
                    {
                        "destination": "R1",
                        "confidence": 0.9,
                        "rationale": "x",
                        "citations": [{"page": 1, "quote": "x"}],
                    }
                ],
            }
        )


def test_intake_mode_imports_nothing_that_decides_an_attachment() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]
    modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not [n for n in imported if any(word in n.lower() for word in DECIDES)]
    assert not [m for m in modules if "triage" in m or "intake_filing" in m]
    # What it may read and write of other modules, and nothing more.
    assert {n for n, m in _from(tree) if m == "abacus.modules.communications.api"} == {
        "IntakeAttachmentFacts",
        "intake_attachment_facts",
        "intake_folder_destinations",
    }
    assert {n for n, m in _from(tree) if m == "abacus.modules.evidence.api"} == {
        "intake_masked_text",
        "record_agent_classification",
    }


def _from(tree: ast.Module) -> list[tuple[str, str]]:
    return [
        (alias.name, node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]
