"""A-05-T27 (TASK-3219; DEC-2219): mode `ebp_reconcile`.

Pinned here: the mode has its own prompt on spec v8 and a registered mapping; the prompt never
lets the model compute or decide; code's facts are named totals as decimal strings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from abacus.modules.agents.specs import _specs
from abacus.modules.assurance import ebp_reconcile

PROMPT = (
    Path(__file__).resolve().parents[3]
    / "src/abacus/ai_gateway/prompts/workpapers.section_draft.ebp_reconcile/v1.txt"
)


def test_the_mode_has_its_own_prompt_on_the_one_spec() -> None:
    spec = cast("dict[str, Any]", _specs.SPECS["workpapers.section_drafter"])
    assert spec["version"] >= 8  # v8 added this mode; later modes bump the spec (v9 is A-04-T29)
    assert spec["modes"]["ebp_reconcile"]["prompt"] == "workpapers.section_draft.ebp_reconcile@v1"


def test_the_prompt_forbids_arithmetic_and_decisions() -> None:
    body = " ".join(PROMPT.read_text().split())  # the prompt wraps its lines
    assert "Never add, subtract or compute anything" in body
    assert "never sign off, approve, decide" in body
    assert "<untrusted>" in body


def test_code_facts_are_decimal_strings() -> None:
    name, value = ebp_reconcile._fact("register_match", 392100)  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    assert name == "register_match"
    assert value == {"t": "decimal", "v": "392100"}
