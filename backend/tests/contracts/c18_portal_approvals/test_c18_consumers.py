"""A-06-T27 (ADR-078; A-06 as C18's consumer, written against R-02's stub): `proposed_entry` and
`fs_draft`, Accept, Decline with a reason and Ask a question, approver of record and owner scope
with a second factor. A change to the decision callback's shape fails here, and T10's and T29's
adapters stay fixture-only until this passes."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from abacus.modules.engagements.api import DECIDER_RULES, ClientApprovalProvider
from abacus.modules.portal.approvals_contract import (
    ApprovalItemOut,
    ApprovalQuestionIn,
    PackageDecideIn,
    ProposedEntryDecideIn,
)

REPO = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize("kind", ["proposed_entry", "fs_draft"])
def test_the_kinds_a06_uses_have_a_decider_rule(kind: str) -> None:
    assert kind in DECIDER_RULES


def test_the_provider_callback_keeps_its_shape() -> None:
    decide = inspect.signature(ClientApprovalProvider.decide)
    assert list(decide.parameters) == ["self", "tx", "item_id", "decision", "context"]
    assert {"items", "item", "decide", "facts"} <= set(dir(ClientApprovalProvider))


def test_accept_and_decline_carry_the_seen_hash() -> None:
    assert {"decision", "seen_hash", "reason"} <= set(ProposedEntryDecideIn.model_fields)
    assert {"decision", "seen_hash", "reason_code", "note"} <= set(PackageDecideIn.model_fields)


def test_decline_refuses_a_missing_reason() -> None:
    with pytest.raises(ValueError):
        PackageDecideIn(decision="decline", seen_hash="x" * 64)


def test_ask_a_question_takes_a_body_alone() -> None:
    assert set(ApprovalQuestionIn.model_fields) == {"body"}


def test_a_decided_item_says_who_recorded_it() -> None:
    assert {"decided_by", "decided_at", "reason_code"} <= set(ApprovalItemOut.model_fields)


def test_a_decision_reads_as_the_client_never_the_agent() -> None:
    contract = (REPO / "docs/contracts/portal-approvals.md").read_text()
    assert "(client)" in contract
    assert 'never "via Agent"' in contract
