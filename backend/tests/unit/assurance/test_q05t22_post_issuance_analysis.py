"""Q-05-T22 (TASK-8909; Q-05 §6; SPEC-711 AC-15, AC-16; red): `assurance.post_issuance_analysis`
v1.

Row acceptance: "A committed Bedrock report passes every frozen threshold at 1.0, and run #4511 on
PI-01 ends with I have not decided whether this needs action." Here: code settles the analysis
(numbers by reference only, the tag only on the option code marks eligible, quotes from both
certifications, the closing sentences appended so PI-01's analysis ends with AC-16's sentence);
the spec is a single_call pinned to `audit.post_issuance_analysis@v1` with untrusted inputs and
no tools; the capability run over Q-05-T10's frozen suite passes on the fake model and signs; no
real firm is cleared until a person records a Bedrock report. The Bedrock run is the evaluation
account's (DEC-5901).
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from abacus.modules.assurance import post_issuance_analysis as pia
from abacus_tools.evals import post_issuance_analysis_run as pi_run

ROOT = Path(pia.__file__).resolve().parents[5]
PROMPTS = Path(pia.__file__).resolve().parents[2] / "ai_gateway" / "prompts"


def _given(eligible: str | None = "no_action") -> pia.PostIssuanceAnalysisInput:
    return pia.PostIssuanceAnalysisInput.model_validate(
        {
            "case_ref": "PI-01",
            "facts": [
                {"id": "difference", "kind": "money", "value": "-12250.00"},
                {"id": "clearly_trivial", "kind": "money", "value": "12610.00"},
                {"id": "overall_materiality", "kind": "money", "value": "252200.00"},
                {"id": "share_pct", "kind": "percent", "value": "4.9"},
                {"id": "lines", "kind": "count", "value": "3"},
            ],
            "options": ["no_action", "revise_and_reissue", "notify_users"],
            "eligible": eligible,
            "sources": [
                {"source": "certified", "evidence_version_id": str(uuid4()), "pages": [1]},
                {"source": "corrected", "evidence_version_id": str(uuid4()), "pages": [1]},
            ],
        }
    )


def _text(settled: pia.Settled) -> str:
    from typing import cast

    parts = cast("list[dict[str, list[dict[str, str]]]]", settled.blocks["parts"])
    return " ".join(
        seg.get("text", "{" + seg.get("fact_id", "") + "}")
        for part in parts
        for seg in part["segments"]
    )


def test_pi01s_analysis_ends_with_the_not_decided_sentence() -> None:
    settled = pia.settle(_given(), pia.FAKE_RESPONSES["PI-01"])
    assert _text(settled).rstrip().endswith("I have not decided whether this needs action.")
    assert pia.SUITE_NOT_DECIDED in _text(settled)
    assert settled.recommendation == "no_action"
    assert {q.source for q in settled.quotes} == {"certified", "corrected"}


def test_a_tag_on_an_option_code_does_not_mark_eligible_is_refused() -> None:
    with pytest.raises(pia.OutputRefused) as caught:
        pia.settle(_given(eligible=None), pia.FAKE_RESPONSES["PI-01"])
    assert caught.value.facts == {"reason": "recommendation_not_eligible"}
    untagged = pia.FAKE_RESPONSES["PI-01"].model_copy(update={"recommendation": None})
    assert pia.settle(_given(eligible=None), untagged).recommendation is None


def test_a_free_number_is_refused() -> None:
    bad = pia.FAKE_RESPONSES["PI-01"].model_copy(
        update={
            "blocks": {
                "version": 1,
                "parts": [
                    {
                        "kind": "p",
                        "segments": [
                            {"kind": "text", "text": "The difference is 12,250, immaterial."}
                        ],
                    }
                ],
            }
        }
    )
    with pytest.raises(pia.OutputRefused):
        pia.settle(_given(), bad)


def test_quotes_must_come_from_both_certifications_on_offered_pages() -> None:
    one = pia.FAKE_RESPONSES["PI-01"].model_copy(
        update={"quotes": [pia.QuoteOut(source="corrected", page=1, quote="Corrected"),
                           pia.QuoteOut(source="corrected", page=1, quote="certification")]}
    )  # fmt: skip
    with pytest.raises(pia.OutputRefused) as caught:
        pia.settle(_given(), one)
    assert caught.value.facts == {"reason": "citation_coverage"}
    off = pia.FAKE_RESPONSES["PI-01"].model_copy(
        update={"quotes": [pia.QuoteOut(source="certified", page=9, quote="Statement"),
                           pia.QuoteOut(source="corrected", page=1, quote="Corrected")]}
    )  # fmt: skip
    with pytest.raises(pia.OutputRefused):
        pia.settle(_given(), off)


def test_the_output_carries_no_action_field() -> None:
    assert "actions" not in pia.PostIssuanceAnalysisOutput.model_fields
    with pytest.raises(ValueError):
        pia.PostIssuanceAnalysisOutput.model_validate(
            {**pia.FAKE_RESPONSES["PI-01"].model_dump(mode="json"), "actions": ["report.reissue"]}
        )


def test_the_spec_is_a_pinned_single_call() -> None:
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(pia.CAPABILITY)
    assert (spec.shape, spec.prompt, spec.limits.max_steps) == (
        "single_call", "audit.post_issuance_analysis@v1", 1,
    )  # fmt: skip
    assert not spec.tools.names()
    assert {"corrected_certification", "certified_trust_report"} <= set(spec.untrusted_inputs)
    assert spec.evaluation_suite == "evals/post_issuance_analysis"
    assert (PROMPTS / "audit.post_issuance_analysis" / "v1.txt").exists()


def test_no_real_firm_is_cleared_without_a_recorded_bedrock_report() -> None:
    from abacus.modules.agents.api import spec_v2

    clearance = yaml.safe_load(
        (ROOT / "evals" / "post_issuance_analysis" / "clearance.yaml").read_text(encoding="utf-8")
    )
    assert clearance["agent"] == pia.CAPABILITY
    if not clearance["records"]:
        assert spec_v2(pia.CAPABILITY).client_data == "none"


def test_the_fake_model_run_passes_the_frozen_suite_and_signs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(pi_run.SIGNING_KEY_ENV, "test-key")
    assert pi_run.fake_main(tmp_path) == 0
    report = json.loads((tmp_path / "post_issuance_analysis-fake.json").read_text())
    assert report["passed"] and report["golden_ends_not_decided"]
    assert all(v == 1.0 for v in report["rates"].values())
    assert report["clears_real_firms"] is False and isinstance(report.get("signature"), str)


def test_the_route_runs_the_capability() -> None:
    contract = (Path(pia.__file__).parent / "post_issuance_contract.py").read_text(
        encoding="utf-8"
    )
    assert "await pia.analyse(ctx, work_item_id, case_id)" in contract
    assert "raise NotImplementedYet" not in contract
