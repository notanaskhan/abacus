"""C3 v1 consumer tests (P-04-T09), the SHL-10 a to g shapes: the approve-agent-output modal reads
the proposal projection (reasoning, the Field · Before → After · Cause diff, code-computed totals,
evidence, the policy note, the set link) and a named person approves, rejects, routes or undoes.
The Feld K-1 example foots as Decimal: 307,900 leaves line 28A (k) and enters (h), so the net
change to Form 1040 total income is 0, a tie (`docs/contracts/review-grammar.md` §8 part 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import get_args

import pytest
from pydantic import BaseModel, ValidationError

from abacus.kernel.classification import Classification
from abacus.modules.agents.contract import (
    AdoptSuggestionIn,
    AgentProposalOut,
    AgentSuggestionOut,
    ApproveProposalIn,
    DismissSuggestionIn,
    FollowUpIn,
    PolicyResult,
    ProposalDecisionOut,
    ProposalEditIn,
    ProposalEvidenceOut,
    ProposalPolicyOut,
    ProposalRowOut,
    ProposalSetOut,
    ProposalTotalOut,
    RejectProposalIn,
    RejectReason,
    RouteProposalIn,
    UndoProposalIn,
)

from ._c3 import conforms, dec, example, level, wire

NEEDS: dict[str, list[tuple[type[BaseModel], str, Classification]]] = {
    "a": [
        (AgentProposalOut, "title", "confidential"),
        (AgentProposalOut, "context_label", "confidential"),
        (AgentProposalOut, "state", "internal"),
        (AgentProposalOut, "version", "internal"),
        (AgentProposalOut, "change_count", "internal"),
        (AgentProposalOut, "agent_run_id", "internal"),
        (AgentProposalOut, "evidence", "confidential"),
        (AgentProposalOut, "checkpoint_id", "internal"),
        (AgentProposalOut, "allowed_actions", "internal"),
        # Agent reasoning, values and the policy note may hold return information (TRI): sealed.
        (AgentProposalOut, "reasoning", "restricted"),
        (AgentProposalOut, "rows", "restricted"),
        (AgentProposalOut, "totals", "restricted"),
        (AgentProposalOut, "policy", "restricted"),
        (AgentProposalOut, "decision", "restricted"),
        (ProposalRowOut, "label", "confidential"),
        (ProposalRowOut, "before", "restricted"),
        (ProposalRowOut, "after", "restricted"),
        (ProposalRowOut, "cause", "confidential"),
        (ProposalRowOut, "citation_ids", "internal"),
        (ProposalTotalOut, "label", "confidential"),
        (ProposalTotalOut, "value", "restricted"),
        (ProposalTotalOut, "ties", "internal"),
        (ProposalEvidenceOut, "label", "confidential"),
        (ProposalEvidenceOut, "citation_count", "internal"),
        (ProposalPolicyOut, "note", "restricted"),
        (ApproveProposalIn, "seen_version", "internal"),
    ],
    "b": [
        (AgentSuggestionOut, "field_key", "internal"),
        (AgentSuggestionOut, "proposed_value", "restricted"),
        (AgentSuggestionOut, "rationale", "restricted"),
        (AgentSuggestionOut, "citation_ids", "internal"),
        (AgentSuggestionOut, "status", "internal"),
        (AgentSuggestionOut, "decision", "internal"),
        (AgentSuggestionOut, "allowed_actions", "internal"),
        (AdoptSuggestionIn, "edited_value", "restricted"),
        (AdoptSuggestionIn, "citation_note", "restricted"),
        (DismissSuggestionIn, "reason_code", "internal"),
        (ApproveProposalIn, "edits", "restricted"),
        (ProposalEditIn, "after", "restricted"),
        (ProposalEditIn, "citation_note", "restricted"),
    ],
    "c": [
        (ProposalRowOut, "unsupported", "internal"),
        (ProposalRowOut, "citation_ids", "internal"),
        (FollowUpIn, "text", "restricted"),
    ],
    "d": [
        (ProposalPolicyOut, "policy_name", "internal"),
        (ProposalPolicyOut, "result", "internal"),
        (ProposalPolicyOut, "routed_to_user_id", "internal"),
        (ProposalPolicyOut, "routed_to_name", "internal"),
        (RouteProposalIn, "approver_user_id", "internal"),
    ],
    "e": [
        (ProposalPolicyOut, "result", "internal"),
        (ProposalTotalOut, "ties", "internal"),
    ],
    "e_prime": [
        (ProposalDecisionOut, "decision", "internal"),
        (ProposalDecisionOut, "decided_by_name", "internal"),
        (ProposalDecisionOut, "decided_at", "internal"),
        (ProposalDecisionOut, "undo_until", "internal"),
        (UndoProposalIn, "decision_id", "internal"),
    ],
    "f": [
        (RejectProposalIn, "reason_code", "internal"),
        (RejectProposalIn, "note", "restricted"),
        (ProposalDecisionOut, "reason_code", "internal"),
        (ProposalDecisionOut, "note", "restricted"),
    ],
    "g": [
        (AgentProposalOut, "set", "confidential"),
        (ProposalSetOut, "label", "confidential"),
        (ProposalSetOut, "results", "internal"),
        (ProposalSetOut, "exceptions", "internal"),
    ],
}
CASES = [(a, m, f, c) for a, rows in NEEDS.items() for m, f, c in rows]

K1 = example("reasoning", "rows", "totals")
# Lines that feed Form 1040 total income. The Form 8995-A QBI line is a separate form (§8).
TOTAL_INCOME_LINES = ("sch_e.",)


@pytest.mark.parametrize(
    ("artboard", "model", "field", "classification"),
    CASES,
    ids=[f"SHL-10{a}-{m.__name__}.{f}" for a, m, f, _c in CASES],
)
def test_shl10_the_frame_reads_its_fields_with_their_tags(
    artboard: str, model: type[BaseModel], field: str, classification: Classification
) -> None:
    assert field in model.model_fields, f"SHL-10 {artboard} needs {model.__name__}.{field}"
    assert level(model, field) == classification


# --- a. Feld K-1 treatment ---------------------------------------------------------------------


def test_shl10a_the_k1_example_is_the_wire_shape() -> None:
    p = conforms(AgentProposalOut, K1)
    assert (p.state, p.version, p.change_count) == ("pending", 1, len(p.rows))
    assert p.change_count == 4 and [r.n for r in p.rows] == [1, 2, 3, 4]
    assert all(r.citation_ids and not r.unsupported for r in p.rows)
    assert [e.citation_count for e in p.evidence] == [2, 1, 1]
    assert p.policy is not None and p.policy.routed_to_name is None
    assert set(p.allowed_actions) == {"proposal.approve", "proposal.reject", "proposal.follow_up"}


def test_shl10a_the_net_change_to_total_income_ties_at_zero() -> None:
    p = conforms(AgentProposalOut, K1)

    def amount(value: str | None) -> Decimal:
        return Decimal(0) if value is None else dec(value)

    lines = [r for r in p.rows if r.field_key.startswith(TOTAL_INCOME_LINES)]
    assert [r.field_key for r in lines] == ["sch_e.p2.28a_k", "sch_e.p2.28a_h"]
    net = sum((amount(r.after) - amount(r.before) for r in lines), Decimal(0))
    (total,) = p.totals
    assert total.label == "Net change to Form 1040 total income"
    assert net == dec(total.value) == Decimal(0) and total.ties
    moved = dec("307,900")
    assert (amount(lines[0].before), amount(lines[1].after)) == (moved, moved)
    qbi = next(r for r in p.rows if r.field_key.startswith("f8995a."))
    assert amount(qbi.after) == moved  # the QBI line records the same income on another form


def test_shl10a_approve_carries_the_version_seen() -> None:
    body = ApproveProposalIn.model_validate({"seen_version": 1, "edits": []})
    assert body.edits == []
    with pytest.raises(ValidationError):
        ApproveProposalIn.model_validate({"edits": []})


# --- b. Single source change; Approve with edits -----------------------------------------------


def test_shl10b_an_edit_needs_its_citation_note() -> None:
    with pytest.raises(ValidationError):
        ProposalEditIn.model_validate({"n": 1, "after": "1550", "citation_note": ""})
    edit = ProposalEditIn.model_validate({"n": 1, "after": "1550", "citation_note": "K-1 box 18A"})
    assert dec(edit.after) == dec("1,550")


def test_shl10b_adopting_the_line_2a_suggestion() -> None:
    assert AdoptSuggestionIn.model_validate({"seen_version": 1}).edited_value is None
    adopted = AgentSuggestionOut.model_validate(
        wire(
            {
                "id": "<s-line-2a>",
                "target_type": "tax_return",
                "target_id": "<feld-1040>",
                "field_key": "f1040.l2a",
                "proposed_value": "1550",
                "rationale": None,
                "citation_ids": ["<k1-18a>"],
                "status": "adopted",
                "version": 1,
                "agent_run_id": "<run>",
                "decision": "adopted",
                "decided_by_user_id": "<samuel>",
                "decided_at": "2026-09-14T14:24:00Z",
                "allowed_actions": [],
            }
        )
    )
    assert (adopted.status, adopted.decision) == ("adopted", "adopted")
    assert dec(adopted.proposed_value) == dec("1,550")


# --- c. Uncited value ---------------------------------------------------------------------------


def test_shl10c_the_uncited_row_blocks_approval() -> None:
    fragment = example("n", "unsupported")
    assert set(fragment) <= set(ProposalRowOut.model_fields)
    row = ProposalRowOut.model_validate(
        wire({**fragment, "suggestion_id": None, "field_key": "sch_a.l5b"})
    )
    assert row.unsupported and row.citation_ids == [] and row.n == 5
    assert dec(row.after or "") == dec("18,240")
    assert FollowUpIn.model_validate({"text": "Which document supports line 5b?"}).text


# --- d. Over threshold; e and e-prime. Within threshold, approved ----------------------------


def test_shl10d_aje05_is_over_the_10000_threshold_and_routes_to_a_person() -> None:
    fragment = example("policy_name", "result", "routed_to_name")
    assert set(fragment) <= set(ProposalPolicyOut.model_fields)
    policy = ProposalPolicyOut.model_validate(wire({**fragment, "note": None}))
    assert policy.result == "review_required" and policy.routed_to_name == "Priya Raman"
    # §8 SHL-10 d prose (constants copied from the doc): AJE-05 is 12,600.00 + 1,480.00 + 820.00.
    aje05 = dec("12,600.00") + dec("1,480.00") + dec("820.00")
    assert aje05 == dec("14,900.00") > dec("10,000")  # "above $10,000 other accruals"
    RouteProposalIn.model_validate(wire({"seen_version": 1, "approver_user_id": "<priya>"}))


def test_shl10e_prime_the_decision_is_a_named_person_with_a_10_second_undo() -> None:
    assert set(get_args(PolicyResult)) == {"within_threshold", "review_required"}
    decided_at = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
    decision = ProposalDecisionOut.model_validate(
        wire(
            {
                "id": "<decision>",
                "decision": "approved",
                "reason_code": None,
                "note": None,
                "decided_by_user_id": "<raj>",
                "decided_by_name": "Raj Malhotra",
                "decided_at": decided_at.isoformat(),
                "routed_to_user_id": None,
                "undo_until": (decided_at + timedelta(seconds=10)).isoformat(),
            }
        )
    )
    assert decision.undo_until is not None
    assert decision.undo_until - decision.decided_at == timedelta(seconds=10)
    UndoProposalIn.model_validate(wire({"decision_id": "<decision>"}))


# --- f. Reject; g. part of a set ---------------------------------------------------------------


def test_shl10f_reject_with_one_of_four_reasons() -> None:
    assert get_args(RejectReason) == (
        "wrong_treatment",
        "unsupported_value",
        "needs_client_input",
        "other",
    )
    body = RejectProposalIn.model_validate(
        {"seen_version": 1, "reason_code": "needs_client_input"}
    )
    assert body.note is None
    with pytest.raises(ValidationError):
        RejectProposalIn.model_validate({"seen_version": 1})


def test_shl10g_the_set_link_row() -> None:
    link = ProposalSetOut.model_validate(
        wire(
            {
                "set_type": "procedure_result_set",
                "set_id": "<bh-fs-430>",
                "label": "BH-FS-430 Search for unrecorded liabilities",
                "results": 40,
                "exceptions": 1,
            }
        )
    )
    assert (link.results, link.exceptions) == (40, 1)
