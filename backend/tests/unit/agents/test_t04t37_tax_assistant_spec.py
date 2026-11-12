"""T-04-T37 (TASK-7317; T-04 §6; DEC-4316): `tax.assistant` v1's spec and prompt.

Row acceptance: "On the fake model the 9:29 AM question returns a cited answer and one proposal for
box 18A 1,550 with 2 citations, no reply contains 'I approved' or 'I changed', and an unconsented
taxpayer gets the agents-off state with no model call." The fake-model answer is the tax return
suite's `assistant_ridgeline_box18a_proposal` case; the consent gate is the integration test."""

from __future__ import annotations

from pathlib import Path

import abacus.modules.agents.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registries load first
from abacus.modules.agents.session_turns import read_only_tools, write_actions
from abacus.modules.agents.spec_v2 import spec_v2

PROMPT = Path(__file__).resolve().parents[3] / "src/abacus/ai_gateway/prompts/tax.assistant/v1.txt"


def test_a_loop_whose_inline_turns_read_and_whose_one_write_is_a_proposal() -> None:
    spec = spec_v2("tax.assistant")
    assert spec.shape == "loop" and spec.plan == "required_when_writes"
    assert "tax.propose_field_changes" not in read_only_tools(spec)
    assert write_actions(spec) == {"tax.propose_field_changes": "proposal.create"}
    assert "tri" in spec.data_classes and spec.autonomy == "propose"


def test_the_prompt_never_lets_it_claim_a_decision() -> None:
    text = PROMPT.read_text(encoding="utf-8")
    assert "Never say you approved, changed, signed, filed or sent anything" in text
    assert "<untrusted>" in text and "Never mention a TIN" in text
