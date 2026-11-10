"""T-04-T18 (TASK-6722; T-04 §6): the tax return suite skeleton on the fake model.

Row acceptance: "The suite runs on the fake model in CI with every section 6 threshold frozen, and
a TRI case without both consents fails unless the tool layer refuses before any model call."
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from abacus_tools.evals import tax_return as t


def _cases() -> dict[str, t.Case]:
    return {c.id: c for c in t.load()[1]}


def test_ac_the_suite_passes_on_the_fake_model_with_every_threshold_frozen() -> None:
    thresholds, cases = t.load()
    assert thresholds == {k: dict(v) for k, v in t.FROZEN.items()}
    assert set(thresholds) == set(t.CAPABILITIES)
    assert len(cases) >= 30
    report = t.run_suite(thresholds, cases)
    assert report["status"] == "passed", report
    assert report["graders_without_a_seeded_case"] == []


def test_ac_a_changed_threshold_is_refused(tmp_path: Path) -> None:
    raw = yaml.safe_load(t.SUITE.read_text(encoding="utf-8"))
    raw["thresholds"]["tax.return_drafter"]["change_accuracy"] = 0.9
    lowered = tmp_path / "suite.yaml"
    lowered.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(t.ThresholdsChanged):
        t.load(lowered)


@pytest.mark.parametrize(
    "case_id", ["adv_drafter_tri_without_consent", "adv_assistant_tri_without_consent"]
)
def test_ac_tri_without_both_consents_passes_only_when_the_tool_layer_refuses_first(
    case_id: str,
) -> None:
    case = _cases()[case_id]
    assert t.grade_case(case).passed
    consent = case.output.consent
    called = case.model_copy(
        update={
            "output": case.output.model_copy(
                update={"consent": consent.model_copy(update={"model_called": True})}
            )
        }
    )
    assert "consent_refusal_7216" in t.grade_case(called).failed_graders
    at_gateway = case.model_copy(
        update={
            "output": case.output.model_copy(
                update={"consent": consent.model_copy(update={"refused_at": "gateway"})}
            )
        }
    )
    assert "consent_refusal_7216" in t.grade_case(at_gateway).failed_graders


def test_the_net_change_ties_in_code_and_a_draft_k1_value_needs_its_flag() -> None:
    cases = _cases()
    assert t.grade_case(cases["drafter_feld_net_change"]).passed
    seeded = t.grade_case(cases["seeded_drafter_wrong_and_untied"])
    assert {"change_accuracy", "net_change_tie"} <= set(seeded.failed_graders)
    assert "draft_k1_flag" in t.grade_case(cases["seeded_drafter_draft_k1_and_gap"]).failed_graders


def test_first_person_approval_and_reserved_actions_are_caught() -> None:
    result = t.grade_case(_cases()["seeded_assistant_i_approved_and_reserved"])
    assert {"first_person_approval", "reserved_actions_absent"} <= set(result.failed_graders)
