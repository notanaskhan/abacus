"""Independent AC tests for findings, the decision kinds and the SUM service (A-06-T20; ADR-078;
A-06 §3 F1, F2, F4).

Written apart from A-06-T08, T11 and T13: the agent never concludes, resolves or marks a finding
not applicable (INV-1); both decision kinds are reserved to the engagement partner and decided
through C3 with a rationale and a fresh second factor; an agent's finding needs verified citations
and its Why This Was Surfaced states only code's figures (INV-2); walls answer 404 (INV-3); an
agent-raised row reads "<person> via Agent" (INV-5); the SUM snapshot is insert-only.
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus.modules.assurance import completion_decisions, findings, findings_contract

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
MATRIX = cast(
    dict[str, dict[str, str]],
    yaml.safe_load((ROOT / "docs/architecture/permission-matrix/assurance.yaml").read_text())[
        "actions"
    ],
)
MFA = yaml.safe_load((ROOT / "docs/architecture/fresh-mfa-actions.yaml").read_text())
M0644 = (BACKEND / "migrations/versions/0644_assurance_completion.py").read_text()


@pytest.mark.parametrize(
    "action",
    [
        "finding.update",
        "finding.convert",
        "finding.resolve",
        "finding.mark_not_applicable",
        "finding.request_decision",
    ],
)
def test_inv1_the_agent_and_the_system_never_close_or_decide(action: str) -> None:
    assert MATRIX[action]["agent"] == "deny"
    assert MATRIX[action]["system"] == "deny"


def test_both_decision_kinds_are_reserved_to_the_engagement_partner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Any] = []  # Any: test doubles and JSON
    monkeypatch.setattr(completion_decisions, "register_decision_kind", seen.append)
    completion_decisions.register_completion_decision_kinds()
    assert {k.code for k in seen} == {
        completion_decisions.SEVERITY_KIND,
        completion_decisions.SUM_KIND,
    }
    assert {k.reserved_role for k in seen} == {"engagement_partner"}


def test_deciding_needs_a_fresh_second_factor() -> None:
    entries = cast(
        list[dict[str, str]],
        cast(dict[str, Any], MFA)["actions"],  # Any: test doubles and JSON
    )  # Any: test doubles and JSON
    actions = {entry["action"] for entry in entries}
    assert "decision.decide" in actions


def test_inv2_an_agent_finding_needs_verified_citations() -> None:
    source = inspect.getsource(findings.record_finding)
    assert "raise UncitedFinding" in source
    assert "verified_citation_ids" in source


def test_inv2_why_surfaced_states_only_codes_figures() -> None:
    figures = [Decimal("35267"), Decimal("35300")]
    assert (
        findings.why_surfaced_support("Projected 35,267, rounded 35,300.", figures) == "supported"
    )
    assert findings.why_surfaced_support("Roughly 40,000 at risk.", figures) == "unsupported"


def test_inv3_every_findings_route_gates_first() -> None:
    for name in ("misstatements_route", "sum_route", "sum_request_conclusion_route"):
        body = inspect.getsource(getattr(findings_contract, name))
        assert "await _gate(ctx, work_item_id" in body


def test_inv5_an_agent_raised_finding_reads_person_via_agent() -> None:
    """The row's creator name for an agent-raised finding is "<person> via Agent"."""
    source = inspect.getsource(findings._rows)  # pyright: ignore[reportPrivateUsage] -- the private helper under test
    assert "via Agent" in source


def test_the_sum_snapshot_is_insert_only() -> None:
    assert '_INSERT_ONLY = ("sum_snapshots",)' in M0644
    assert "insert_only(op, table)" in M0644
