"""P-06-T21 (P-06 §6; SPEC-030 AC-8): the upload reviewer's fake-model fast run, on a throwaway
stack (containers), as `make evals-review-fast` runs it.

- With the recorded answers, the fast run passes: every case once, every attempt reviewed,
  showing exactly its case's flags, at the protected thresholds.
- A changed answer fails it: a fabricated quote (code doesn't verify it, so the flag isn't
  shown) and a wrong verdict ("no concerns" for the 1099-NEC uploaded to a W-2 request).

The fake model answers only from the recorded files; no model is called, nothing is spent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from abacus.modules.agents.api import REVIEWER, spec
from abacus_tools.evals.runner import prepare
from abacus_tools.evals.upload_review import (
    FAKE_ANSWERS,
    evaluate,
    fake_answers,
    fake_reviewer,
    load_suite,
)
from abacus_tools.stack import Stack, run_with_stack

FABRICATED = "Invoice number INV-0000 for freight services"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The stack rewrites these process settings; restore them after the test."""
    monkeypatch.setenv("ABACUS_FAKE_CONNECTOR_DIR", str(tmp_path / "fake"))
    monkeypatch.delenv("ABACUS_EVAL_SIGNING_KEY", raising=False)


def _changed(case_id: str, response: dict[str, object]) -> dict[tuple[str, str], str]:
    """The recorded answers with `case_id`'s replaced by `response`."""
    answers = fake_answers()
    for path in FAKE_ANSWERS.glob("*.json"):
        raw = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
        if raw["case"] == case_id:
            key = (str(raw["prompt_ref"]), str(raw["content_sha256"]))
            assert key in answers
            answers[key] = json.dumps(response)
            return answers
    raise AssertionError(f"no recorded answer for {case_id}")


def _recorded(case_id: str) -> dict[str, object]:
    for path in FAKE_ANSWERS.glob("*.json"):
        raw = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
        if raw["case"] == case_id:
            return cast(dict[str, object], raw["response"])
    raise AssertionError(f"no recorded answer for {case_id}")


def test_the_fast_run_passes_and_a_changed_answer_fails_it(tmp_path: Path) -> None:
    suite = load_suite()
    tier = spec(REVIEWER).tier
    fabricated = _recorded("statement_for_invoice")
    flags = cast(list[dict[str, object]], fabricated["flags"])
    flags[0]["citations"] = [{"page": 1, "quote": FABRICATED}]
    runs = {
        "honest": fake_answers(),
        "fabricated_quote": _changed("statement_for_invoice", fabricated),
        "wrong_verdict": _changed("wrong_form_for_w2", {"no_concerns": True, "flags": []}),
    }
    reports: dict[str, dict[str, object]] = {}

    async def record(stack: Stack) -> None:
        world = await prepare(stack)
        for name, answers in runs.items():
            with fake_reviewer(answers):
                reports[name] = await evaluate(
                    stack, world, suite, tier, "fake", tmp_path / name, "fast"
                )

    run_with_stack(record)

    honest = reports["honest"]
    attempts = cast(list[dict[str, object]], honest["attempts"])
    assert honest["status"] == "passed", honest["reasons"]
    assert honest["fake"] is True and honest["subset"] == "fast"
    assert len(attempts) == len(suite.cases)  # every case once
    assert all(a["stage"] == "reviewed" and a["shown"] == a["expected"] for a in attempts)
    metrics = cast(dict[str, float], honest["metrics"])
    assert all(metrics[t.metric] >= t.minimum for t in suite.thresholds)
    assert metrics["citation_verification"] == 1.0
    assert metrics["adversarial_containment"] == 1.0

    fabricated_run = reports["fabricated_quote"]
    assert fabricated_run["status"] == "failed"
    reasons = cast(list[str], fabricated_run["reasons"])
    assert "case:statement_for_invoice" in reasons
    assert any(r.startswith("flag_recall_irrelevant:") for r in reasons)

    wrong = reports["wrong_verdict"]
    assert wrong["status"] == "failed"
    reasons = cast(list[str], wrong["reasons"])
    assert "case:wrong_form_for_w2" in reasons
    assert any(r.startswith("flag_recall_irrelevant:") for r in reasons)
