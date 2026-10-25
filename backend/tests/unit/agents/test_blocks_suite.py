"""P-09-T15 (TASK-5006): the AgentBlocks conformance suite scores 1.0, every case, every repeat,
and removing any one lint rule makes it fail (the seeded regression)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
import yaml

from abacus.ai_gateway.output_checks import run_output_check
from abacus.modules.agents import blocks
from abacus.modules.agents.blocks import BlocksTurn, Fact

SUITE = Path(__file__).resolve().parents[4] / "evals" / "agent_blocks" / "suite.yaml"
_TEXT = SUITE.read_text(encoding="utf-8")
DATA = cast(dict[str, Any], yaml.safe_load(_TEXT))  # ANY-001: the YAML suite
FACTS = {k: Fact(id=k, **v) for k, v in DATA["facts"].items()}
CITES = {UUID(c) for c in DATA["citations"]}
CASES = cast(list[dict[str, Any]], DATA["cases"])  # ANY-001: YAML cases


def _payload(case: dict[str, Any]) -> object:  # ANY-001: a YAML case
    if "raw" in case:
        return case["raw"]
    if "badge" in case:
        obj, code = case["badge"]
        return {"parts": [{"kind": "badge", "object": obj, "code": code}]}
    if "cite" in case:
        return {
            "parts": [
                {
                    "kind": "cite_list",
                    "cites": [{"kind": "cite", "citation_id": case["cite"], "n": 1}],
                }
            ]
        }
    segments: list[dict[str, str]] = [{"kind": "text", "text": case["text"]}]
    if "fact" in case:
        segments.append({"kind": "fact", "fact_id": case["fact"]})
    return {"parts": [{"kind": "p", "segments": segments}]}


def _outcome(case: dict[str, Any]) -> str:  # ANY-001: a YAML case
    failure = run_output_check("agent_blocks", BlocksTurn(_payload(case), FACTS, CITES))
    return "pass" if failure is None else failure.code


def score() -> float:
    hits = sum(_outcome(c) == c["expect"] for _ in range(DATA["repeats"]) for c in CASES)
    return hits / (len(CASES) * DATA["repeats"])


def test_suite_covers_its_declared_categories() -> None:
    assert {c["category"] for c in CASES} == set(DATA["covers"])
    assert len({c["id"] for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case: dict[str, Any]) -> None:  # ANY-001: a YAML case
    assert _outcome(case) == case["expect"]


def test_the_suite_scores_one_on_every_repeat() -> None:
    assert score() == DATA["required_pass_rate"] == 1.0


@pytest.mark.parametrize(
    "rule",
    ["_NUMBER", "_HTML", "_MARKDOWN", "_HUMAN_ACT", "_BANNED", "_DECEPTIVE", "_PERCENT_WORDS"],
)
def test_a_seeded_regression_removing_one_rule_fails_the_suite(
    rule: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(blocks, rule, re.compile(r"(?!x)x"))  # matches nothing
    assert score() < 1.0
