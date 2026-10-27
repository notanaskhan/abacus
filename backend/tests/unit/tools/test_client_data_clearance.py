"""SPEC-036 AC-4 (TASK-075; ADR-114): an agent is cleared for client data only with committed
Bedrock evaluation and route parity reports. The provider terms register is checked and
compiled."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from abacus.modules.agents.spec import AGENTS, cleared_for_client_data
from abacus_tools.codegen import agent_specs, provider_terms
from abacus_tools.codegen.agent_specs import ClearanceRefused, check_clearance, reports_dir
from abacus_tools.codegen.provider_terms import TermsInvalid, validate

SPEC: dict[str, object] = {
    "id": "evidence.upload_reviewer",
    "evaluation_suite": "evals/upload_review",
}


def test_ac4_no_agent_is_cleared_yet() -> None:
    assert not any(cleared_for_client_data(a) for a in AGENTS)
    assert not cleared_for_client_data("no.such_agent")


def test_ac4_reports_live_beside_the_suite_s_name() -> None:
    assert reports_dir("evals/upload_review").name == "upload-review"


def test_ac4_cleared_needs_both_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(agent_specs, "OPERATIONS", tmp_path)
    cleared: dict[str, object] = {**SPEC, "client_data": "cleared"}
    with pytest.raises(ClearanceRefused, match="evaluation report"):
        check_clearance(cleared)
    (tmp_path / "upload-review").mkdir()
    (tmp_path / "upload-review" / "bedrock-2026-11-01-prompt-v3-passed.json").write_text("{}")
    with pytest.raises(ClearanceRefused, match="route parity"):
        check_clearance(cleared)
    (tmp_path / "route-parity").mkdir()
    (tmp_path / "route-parity" / "bedrock-2026-11-01.json").write_text("{}")
    check_clearance(cleared)
    check_clearance(SPEC)  # not cleared: nothing needed


def test_adr114_the_register_compiles_and_matches() -> None:
    assert provider_terms.TARGET.read_text() == provider_terms.render(
        provider_terms.SOURCE.read_text()
    )


def _entry(**changes: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "route": "bedrock",
        "provider": "Amazon Web Services",
        "documents": [
            {"title": "Service terms", "version": "2026-09", "accepted_on": date(2026, 10, 1)}
        ],
        "training": "none",
        "retention": {"beyond_processing": False, "exceptions": []},
        "region": "us-east-1",
        "subprocessors": [],
        "breach_notice": "Without undue delay",
        "second_approver": "counsel",  # Q-02-T18 (ADR-114 Q3)
        "second_approved_on": date(2026, 9, 28),
        "approved_by": "founder",
        "approved_on": date(2026, 10, 1),
        "review_by": date(2027, 9, 30),
    }
    return {**entry, **changes}


def test_adr114_a_complete_entry_is_accepted() -> None:
    validate(_entry())


@pytest.mark.parametrize(
    "changes",
    [
        {"route": "direct"},
        {"training": "opt_out"},
        {"retention": {"beyond_processing": True}},
        {
            "retention": {
                "beyond_processing": False,
                "exceptions": [{"purpose": "abuse", "max_days": 31}],
            }
        },
        {"region": "eu-west-1"},
        {"approved_by": "someone"},
        {"review_by": date(2027, 10, 15)},
        {"documents": []},
    ],
)
def test_adr114_an_entry_missing_a_condition_is_refused(changes: dict[str, object]) -> None:
    with pytest.raises(TermsInvalid):
        validate(_entry(**changes))


def test_q4_a_new_review_date_keeps_the_material_terms() -> None:
    from abacus_tools.codegen.provider_terms import material

    base = _entry()
    assert material(base) == material(_entry(review_by=date(2027, 6, 30)))
    assert material(base) != material(_entry(region="us-west-2"))
    assert material(base) != material(_entry(subprocessors=["Another Co"]))
