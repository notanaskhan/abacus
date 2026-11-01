"""A-05-T12 (TASK-2909; A-05 §6; DEC-1956): the EBP modes on the one section drafter.

Row acceptance (spec half): "agents/specs holds one workpapers.section_drafter spec with one
evaluation_suite." The six EBP modes are versions of that spec, each mode runs only on its plan's
paper kinds, and the run half (suggestions only, verified citations, "<person> via Agent") is the
workflow's own, unchanged (A-04-T11's suite covers it).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import abacus.modules.assurance.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the EBP mode plans
from abacus.modules.agents.section_draft import DRAFTER, EBP_MODES, mode_call
from abacus.modules.agents.section_sources import mode_kinds
from abacus.modules.agents.spec import spec

SPECS = Path(__file__).resolve().parents[3] / "src" / "abacus" / "modules" / "agents" / "specs"


def test_one_section_drafter_spec_with_one_suite() -> None:
    files = [p for p in SPECS.glob("*.yaml") if "section_drafter" in p.name]
    assert [p.name for p in files] == ["workpapers.section_drafter.yaml"]
    drafter = spec(DRAFTER)
    assert drafter.version == 3
    assert drafter.evaluation_suite == "evals/workpapers_section_drafter"
    assert "ebp.read" in drafter.task_scope


@pytest.mark.parametrize("mode", sorted(EBP_MODES))
def test_each_ebp_mode_is_declared_with_a_budget(mode: str) -> None:
    prompt, budget = mode_call(spec(DRAFTER), mode)
    # A-05-T13 gave ebp_provisions its own prompt (`section_draft_ebp_provisions`).
    assert prompt.startswith("workpapers.section_draft")
    assert budget > 0


def test_each_mode_drafts_only_its_plans_papers() -> None:
    assert mode_kinds("ebp_provisions") == frozenset({"ebp_provisions"})
    assert mode_kinds("ebp_trust") == frozenset({"ebp_investments"})
    assert mode_kinds("related_parties") == frozenset()
    assert mode_kinds("gap") is None  # planning modes run on any paper the source returns
