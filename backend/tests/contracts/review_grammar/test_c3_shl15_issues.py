"""C3 v1 consumer tests (P-04-T12), the SHL-15 a to e shapes: the issue composer reads an issue
with its sealed title, internal note and client wording, sets fix instructions that always
propose, sends only the client wording to the client, and shows the agent's explanation. Each
artboard's fields with their classification tags, and the §8 part 3 examples as the doc wrote
them (Feld issue 3 of 4, K-1 box 18A, 1,550; Northwind's four opt-outs)."""

from __future__ import annotations

import re
from typing import cast, get_args

import pytest
from pydantic import BaseModel, ValidationError

from abacus.kernel.classification import Classification
from abacus.kernel.listing import ListPage
from abacus.modules.review.contract import (
    BulkFixInstructionsIn,
    BulkFixInstructionsOut,
    BulkFixItemOut,
    CitedSourceOut,
    ExplainAcceptedOut,
    FixExclusionCode,
    FixInstructionsAcceptedOut,
    FixInstructionsIn,
    IssueClientContactOut,
    IssueCreateIn,
    IssueDetailOut,
    IssueExplanationOut,
    IssueFixInstructionsOut,
    IssueFixRunOut,
    IssueFixSuggestionOut,
    IssueItemOut,
    IssueLinkOut,
    IssueResolutionIn,
    IssueSendToClientIn,
    IssueUpdateIn,
)

from ._c3 import (
    Json,
    conforms,
    dec,
    example,
    example_where,
    inline_example,
    level,
    restricted_anywhere,
    wire,
)

NEEDS: dict[str, list[tuple[type[BaseModel], str, Classification]]] = {
    "a": [
        (IssueDetailOut, "title", "restricted"),
        (IssueDetailOut, "record_label", "confidential"),
        (IssueDetailOut, "links", "confidential"),
        (IssueDetailOut, "suggestion", "restricted"),
        (IssueItemOut, "kind", "internal"),
        (IssueItemOut, "priority", "internal"),
        (IssueItemOut, "assignee_agent", "internal"),
        (IssueItemOut, "instructions_required", "internal"),
        (IssueItemOut, "version", "internal"),
        (IssueLinkOut, "kind", "internal"),
        (IssueLinkOut, "label", "confidential"),
        (IssueFixSuggestionOut, "text", "restricted"),
        (FixInstructionsIn, "text", "restricted"),
        (FixInstructionsIn, "scope", "internal"),
        (FixInstructionsIn, "seen_version", "internal"),
        (FixInstructionsAcceptedOut, "agent_run_id", "internal"),
        (IssueFixInstructionsOut, "text", "restricted"),
        (IssueFixInstructionsOut, "set_by_name", "internal"),
        # a-prime and a-double-prime: the run row, then its proposal.
        (IssueDetailOut, "fix_run", "restricted"),
        (IssueFixRunOut, "label", "restricted"),
        (IssueFixRunOut, "status", "internal"),
        (IssueFixRunOut, "proposal_id", "internal"),
    ],
    "b": [
        (IssueCreateIn, "title", "restricted"),
        (IssueCreateIn, "internal_note", "restricted"),
        (IssueCreateIn, "client_wording", "restricted"),
        (IssueCreateIn, "client_contact_id", "internal"),
        (IssueCreateIn, "assignee_user_id", "internal"),
        (IssueCreateIn, "links", "confidential"),
        (IssueDetailOut, "internal_note", "restricted"),
        (IssueDetailOut, "client_wording", "restricted"),
        (IssueDetailOut, "client_contact", "confidential"),
        (IssueDetailOut, "request_item_id", "internal"),
        (IssueClientContactOut, "name", "confidential"),
        (IssueClientContactOut, "role_label", "confidential"),
        (IssueSendToClientIn, "client_wording", "restricted"),
        (IssueSendToClientIn, "contact_id", "internal"),
    ],
    "c": [
        (IssueCreateIn, "kind", "internal"),
        (IssueLinkOut, "anchor", "confidential"),
        (IssueItemOut, "assignee_name", "internal"),
        (IssueUpdateIn, "seen_version", "internal"),
    ],
    "d": [
        (IssueDetailOut, "explanations", "restricted"),
        (IssueExplanationOut, "text", "restricted"),
        (IssueExplanationOut, "explained_at", "internal"),
        (IssueExplanationOut, "citations", "confidential"),
        (IssueExplanationOut, "pinned", "internal"),
        (CitedSourceOut, "label", "confidential"),
        (ExplainAcceptedOut, "agent_run_id", "internal"),
    ],
    "e": [
        (BulkFixInstructionsIn, "issues", "internal"),
        (BulkFixInstructionsIn, "text", "restricted"),
        (BulkFixInstructionsOut, "results", "internal"),
        (BulkFixInstructionsOut, "accepted", "internal"),
        (BulkFixItemOut, "detail", "internal"),
    ],
}
CASES = [(a, m, f, c) for a, rows in NEEDS.items() for m, f, c in rows]
ISSUE = example("issue", "record_label", "suggestion")
OPT_OUTS = example_where("kind", "waiting_on_client")
FLAG = example_where("kind", "review_point")


@pytest.mark.parametrize(
    ("artboard", "model", "field", "classification"),
    CASES,
    ids=[f"SHL-15{a}-{m.__name__}.{f}" for a, m, f, _c in CASES],
)
def test_shl15_the_frame_reads_its_fields_with_their_tags(
    artboard: str, model: type[BaseModel], field: str, classification: Classification
) -> None:
    assert field in model.model_fields, f"SHL-15 {artboard} needs {model.__name__}.{field}"
    assert level(model, field) == classification


def test_shl15_the_list_row_carries_nothing_restricted() -> None:
    """Titles, notes and client wording are sealed; a list never carries them (§3)."""
    assert restricted_anywhere(IssueItemOut) == []
    assert "title" not in IssueItemOut.model_fields


# --- a. Set fix instructions -------------------------------------------------------------------


def test_shl15a_the_issue_example_is_the_wire_shape() -> None:
    detail = conforms(IssueDetailOut, ISSUE)
    assert detail.title == "Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet"
    assert (detail.issue.kind, detail.issue.priority) == ("missing_information", "high")
    assert detail.issue.status == "open" and detail.issue.instructions_required
    assert detail.issue.assignee_agent and detail.issue.assignee_user_id is None
    assert [link.kind for link in detail.links] == ["file", "form_field"]
    assert detail.issue.link_count == len(detail.links)
    assert detail.links[1].label == "Form 1040 · line 2a"


def test_shl15a_assigning_the_agent_enables_fix_instructions() -> None:
    detail = conforms(IssueDetailOut, ISSUE)
    assert "fix_instruction.set" in detail.issue.allowed_actions
    # The agent never resolves its own issue: no resolution is the agent's (ISSUE-001).
    assert detail.fix_instructions is None and detail.fix_run is None


def test_shl15a_use_suggestion_then_add_one_constraint() -> None:
    detail = conforms(IssueDetailOut, ISSUE)
    request = FixInstructionsIn.model_validate(example("seen_version", "scope", "text"))
    assert detail.suggestion is not None
    first, constraint = request.text.split("\n")
    assert first == detail.suggestion.text
    assert constraint == "Don't change taxable interest on line 2b (6,910)."
    assert request.scope == "this_issue" and request.seen_version == detail.issue.version


def test_shl15a_fix_runs_always_propose() -> None:
    """DF-13: no direct-edit mode, so there is no such field to turn off."""
    assert not [f for f in FixInstructionsIn.model_fields if "direct" in f or "propose" in f]
    accepted = FixInstructionsAcceptedOut.model_validate(wire(inline_example("The 202 is")))
    assert accepted.status == "in_progress"


def test_shl15a_prime_and_double_prime_the_run_then_its_proposal_of_1550() -> None:
    run = IssueFixRunOut.model_validate(wire(inline_example("The detail's `fix_run` is")))
    assert run.status == "running" and run.proposal_id is None
    amounts = re.findall(r"\d{1,3}(?:,\d{3})+", run.label)
    assert [dec(a) for a in amounts] == [dec("1,550")]
    # The suggestion the proposal carries adopts the same 1,550 (part 2, SHL-10 b).
    detail = conforms(IssueDetailOut, ISSUE)
    assert detail.suggestion is not None and "1,550" in detail.suggestion.text
    assert IssueFixRunOut.model_fields["proposal_id"].annotation is not None


# --- b. New audit issue, sent to the client ----------------------------------------------------


def test_shl15b_the_create_example_is_the_wire_shape() -> None:
    create = IssueCreateIn.model_validate(wire(OPT_OUTS))
    assert (create.kind, create.priority, create.assignee_agent) == (
        "waiting_on_client",
        "high",
        False,
    )
    assert create.internal_note is not None and create.client_wording is not None
    assert create.client_contact_id is not None


def test_shl15b_four_cells_four_participants() -> None:
    create = IssueCreateIn.model_validate(wire(OPT_OUTS))
    cells = next(link for link in create.links if link.kind == "cell_range")
    assert cells.anchor is not None
    match = re.fullmatch(r"([A-Z]+)(\d+):\1(\d+)", cells.anchor)
    assert match is not None
    rows = int(match.group(3)) - int(match.group(2)) + 1
    assert rows == 4 and create.title.startswith(f"Opt-out elections missing for {rows} ")


def test_shl15b_client_wording_is_plain_and_carries_no_internal_note() -> None:
    create = IssueCreateIn.model_validate(wire(OPT_OUTS))
    wording = cast(str, create.client_wording)
    note = cast(str, create.internal_note)
    for internal in ("EPCRS", "QACA", "QNEC", "AUD-15", "control exception"):
        assert internal in note and internal not in wording
    assert "materiality" not in wording.lower()
    assert wording.startswith("Four employees")


def test_shl15b_send_to_client_carries_only_the_client_wording() -> None:
    send = IssueSendToClientIn.model_validate(wire(inline_example("`Idempotency-Key` and")))
    create = IssueCreateIn.model_validate(wire(OPT_OUTS))
    assert send.client_wording == create.client_wording
    assert send.contact_id == create.client_contact_id
    assert set(IssueSendToClientIn.model_fields) == {
        "seen_version",
        "client_wording",
        "contact_id",
        "due_on",
    }


# --- c. New issue from a field flag ------------------------------------------------------------


def test_shl15c_a_field_flag_raises_a_review_point_assigned_to_a_person() -> None:
    create = IssueCreateIn.model_validate(wire(FLAG))
    assert create.kind == "review_point" and not create.assignee_agent
    assert create.assignee_user_id is not None
    (link,) = create.links
    assert link.kind == "form_field" and link.anchor is not None
    assert create.priority == "medium"  # the default
    assert create.title == "Confirm Ridgeline K-1 amounts against the final K-1 before export"


def test_shl15c_feld_issues_move_4_to_5_on_the_list_total() -> None:
    row = conforms(IssueDetailOut, ISSUE).issue
    before = ListPage[IssueItemOut](items=[row] * 4, total=4, counts={"open": 4})
    after = ListPage[IssueItemOut](items=[*before.items, row], total=5, counts={"open": 5})
    assert (before.total, after.total) == (4, 5) and after.total == len(after.items)
    assert f"Issue 3 of {before.total}" == "Issue 3 of 4"


def test_shl15c_classes_are_the_registry_words_only() -> None:
    kinds = set(get_args(IssueCreateIn.model_fields["kind"].annotation))
    assert {"missing_information", "action_required", "review_point", "waiting_on_client"} <= kinds
    with pytest.raises(ValidationError):
        IssueCreateIn.model_validate({**cast(Json, wire(FLAG)), "kind": "urgent"})


# --- d. Explain --------------------------------------------------------------------------------


def test_shl15d_the_explanation_is_agent_text_with_three_citations() -> None:
    (explanation,) = conforms(IssueDetailOut, ISSUE).explanations
    assert [c.label for c in explanation.citations] == [
        "K-1 box 18A",
        "K-1 statement p. 3",
        "IT-201 instructions, line 20",
    ]
    assert "$1,550" in explanation.text and explanation.pinned
    accepted = ExplainAcceptedOut.model_validate(wire(inline_example("explanations` answers 202")))
    assert accepted.agent_run_id == explanation.agent_run_id


# --- e. Bulk instructions; resolutions ---------------------------------------------------------


def test_shl15e_bulk_records_one_instruction_per_issue_with_scope_locked() -> None:
    issue = "00000000-0000-4000-8000-0000000000"
    body = {
        "issues": [
            {"issue_id": f"{issue}01", "seen_version": 1},
            {"issue_id": f"{issue}02", "seen_version": 1},
        ],
        "text": "Obtain the confirmations",
    }
    bulk = BulkFixInstructionsIn.model_validate(body)
    assert len(bulk.issues) == 2 and "scope" not in BulkFixInstructionsIn.model_fields
    out = BulkFixInstructionsOut(
        results=[
            BulkFixItemOut(issue_id=i.issue_id, ok=True, agent_run_id=None, detail=None)
            for i in bulk.issues
        ],
        accepted=2,
        excluded=0,
    )
    assert out.accepted + out.excluded == len(out.results) == 2
    assert f"Set Fix Instructions for {len(bulk.issues)}" == "Set Fix Instructions for 2"
    assert set(get_args(FixExclusionCode)) == {
        "issue_changed",
        "fix_runner_unavailable",
        "level_not_permitted",
    }


def test_shl15_resolutions_take_the_version_seen() -> None:
    assert IssueResolutionIn.model_validate({"seen_version": 1}).note is None
    with pytest.raises(ValidationError):
        IssueResolutionIn.model_validate({})
