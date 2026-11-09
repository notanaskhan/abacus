"""P-09-T15 (TASK-6520; SPEC-648 AC-6; DEC-3120): the AgentBlocks conformance suite's runner.

Row acceptance: "The suite scores 1.0 on every case on every repeat, a seeded regression removing
one lint rule fails it, and the HMAC-signed report publishes."
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from abacus.modules.agents import blocks
from abacus_tools.evals import agent_blocks as suite


def test_the_suite_scores_one_on_every_repeat() -> None:
    report = suite.run_suite(suite.load())
    assert report["status"] == "passed" and report["pass_rate"] == 1.0
    assert set(report["by_category"].values()) == {1.0}  # type: ignore[union-attr]  # a dict


def test_removing_one_lint_rule_fails_the_suite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(blocks, "_HUMAN_ACT", re.compile(r"(?!x)x"))  # the seeded regression
    report = suite.run_suite(suite.load())
    assert report["status"] == "failed" and report["failed_cases"]


def test_the_report_is_signed_when_ci_holds_the_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ABACUS_EVAL_SIGNING_KEY", "ci-key")
    assert suite.main(tmp_path) == 0
    written = json.loads((tmp_path / "agent_blocks.json").read_text())
    assert len(written["signature"]) == 64
