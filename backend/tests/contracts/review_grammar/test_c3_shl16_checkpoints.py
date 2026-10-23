"""C3 v1 consumer tests (P-04-T12), the SHL-16 a to f shapes: the checkpoint drawer reads one
target's checkpoints newest first with a derived Current, a checkpoint's steps and code-computed
diff, and approves, rejects, restores as new, renames and stars. Each artboard's fields with their
classification tags, and the §8 part 3 examples as the doc wrote them (Feld Checkpoint 6, net
change 0, the same four rows as SHL-10 a)."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel, ValidationError

from abacus.kernel.classification import Classification
from abacus.modules.agents.contract import AgentProposalOut
from abacus.modules.review.contract import (
    CheckpointApproveIn,
    CheckpointCreateIn,
    CheckpointDecisionOut,
    CheckpointDetailOut,
    CheckpointDiffRowOut,
    CheckpointHistoryOut,
    CheckpointItemOut,
    CheckpointRejectIn,
    CheckpointRenameIn,
    CheckpointRestoreIn,
    CheckpointStepOut,
    CheckpointTotalOut,
)

from ._c3 import Json, conforms, example, inline_example, level, restricted_anywhere, wire

NEEDS: dict[str, list[tuple[type[BaseModel], str, Classification]]] = {
    "a": [
        (CheckpointHistoryOut, "items", "restricted"),
        (CheckpointHistoryOut, "current_checkpoint_id", "internal"),
        (CheckpointItemOut, "seq", "internal"),
        (CheckpointItemOut, "status", "internal"),
        (CheckpointItemOut, "author_kind", "internal"),
        (CheckpointItemOut, "author_name", "internal"),
        (CheckpointItemOut, "created_at", "internal"),
        (CheckpointItemOut, "summary", "restricted"),
        (CheckpointItemOut, "proposal_id", "internal"),
        (CheckpointItemOut, "allowed_actions", "internal"),
        (CheckpointDetailOut, "steps", "restricted"),
        (CheckpointDetailOut, "diff", "restricted"),
        (CheckpointDetailOut, "totals", "restricted"),
        (CheckpointStepOut, "kind", "internal"),
        (CheckpointStepOut, "title", "confidential"),
        (CheckpointStepOut, "detail", "restricted"),
        (CheckpointStepOut, "at", "internal"),
        (CheckpointDiffRowOut, "label", "confidential"),
        (CheckpointDiffRowOut, "old", "restricted"),
        (CheckpointDiffRowOut, "new", "restricted"),
        (CheckpointDiffRowOut, "cause", "confidential"),
        (CheckpointTotalOut, "value", "restricted"),
        (CheckpointTotalOut, "ties", "internal"),
        (CheckpointApproveIn, "seen_hash", "internal"),
    ],
    "b": [
        (CheckpointItemOut, "current", "internal"),
        (CheckpointItemOut, "decision", "restricted"),
        (CheckpointDecisionOut, "decided_by_name", "internal"),
        (CheckpointDecisionOut, "decided_at", "internal"),
        (CheckpointDecisionOut, "proposal_decision_id", "internal"),
    ],
    "c": [
        (CheckpointDetailOut, "compare", "internal"),
        (CheckpointDetailOut, "compared_to_id", "internal"),
        (CheckpointItemOut, "restored_from_id", "internal"),
        (CheckpointRestoreIn, "seen_hash", "internal"),
    ],
    "d": [
        (CheckpointItemOut, "name", "confidential"),
        (CheckpointItemOut, "starred", "internal"),
        (CheckpointRenameIn, "name", "confidential"),
        (CheckpointRenameIn, "starred", "internal"),
    ],
    "e": [
        (CheckpointDecisionOut, "reason", "restricted"),
        (CheckpointRejectIn, "reason", "restricted"),
    ],
    "f": [
        (CheckpointHistoryOut, "total", "internal"),
        (CheckpointHistoryOut, "allowed_actions", "internal"),
        (CheckpointCreateIn, "name", "confidential"),
    ],
}
CASES = [(a, m, f, c) for a, rows in NEEDS.items() for m, f, c in rows]
HISTORY = example("filter", "items", "current_checkpoint_id")
DETAIL = example("checkpoint", "steps", "diff")
FULL = "sha256:5e1d" + "0" * 56 + "a6f0"  # Checkpoint 6 as SHL-16 shows it, sha256:5e1d…a6f0


@pytest.mark.parametrize(
    ("artboard", "model", "field", "classification"),
    CASES,
    ids=[f"SHL-16{a}-{m.__name__}.{f}" for a, m, f, _c in CASES],
)
def test_shl16_the_frame_reads_its_fields_with_their_tags(
    artboard: str, model: type[BaseModel], field: str, classification: Classification
) -> None:
    assert field in model.model_fields, f"SHL-16 {artboard} needs {model.__name__}.{field}"
    assert level(model, field) == classification


# --- a. Agent proposed -------------------------------------------------------------------------


def test_shl16a_the_history_example_is_the_wire_shape() -> None:
    history = conforms(CheckpointHistoryOut, HISTORY)
    assert [c.seq for c in history.items] == [6, 5, 4, 3, 2, 1]
    assert history.total == len(history.items) == 6


def test_shl16a_current_is_derived_and_only_one_checkpoint_holds_it() -> None:
    history = conforms(CheckpointHistoryOut, HISTORY)
    current = [c for c in history.items if c.current]
    assert len(current) == 1 and current[0].id == history.current_checkpoint_id
    assert current[0].seq == 5 and current[0].author_name == "Kevin Osei"


def test_shl16a_the_cards_read_as_the_artboard() -> None:
    six, five, four, three, two, one = conforms(CheckpointHistoryOut, HISTORY).items
    assert (six.status, six.author_name, six.summary) == (
        "proposed",
        "Accrued Agent",
        "K-1 treatment: Ridgeline",
    )
    assert {"checkpoint.approve", "checkpoint.reject"} <= set(six.allowed_actions)
    assert four.status == three.status == "approved"
    assert four.summary == "Corrected Halvard 1099-INT (2,190 → 2,310)"
    assert four.decision is not None and four.decision.decided_by_name == "Kevin Osei"
    assert (two.author_kind, two.author_name, two.cause) == (
        "import",
        "Imported Return",
        "engine_import",
    )
    assert one.starred and one.name == "Extension estimate (4868)"
    assert {c.status for c in (five, two, one)} == {"saved"}


def test_shl16a_checkpoint_6_is_the_shl10a_proposal() -> None:
    """Approving here equals approving the same proposal in SHL-10 (ADR-160 clause 9)."""
    detail = conforms(CheckpointDetailOut, DETAIL)
    proposal = AgentProposalOut.model_validate(wire(example("reasoning", "rows", "totals")))
    assert detail.checkpoint.proposal_id is not None
    assert str(detail.checkpoint.proposal_id) == proposal.ref
    assert [r.field_key for r in detail.diff] == [r.field_key for r in proposal.rows]
    assert [(r.old, r.new) for r in detail.diff] == [(r.before, r.after) for r in proposal.rows]


def _amount(value: str | None) -> Decimal:
    return Decimal(value) if value is not None else Decimal(0)


def test_shl16a_the_net_change_to_total_income_is_zero_a_tie() -> None:
    """307,900 leaves line 28A (k) and enters line 28A (h); the QBI line is a separate form."""
    detail = conforms(CheckpointDetailOut, DETAIL)
    income = [r for r in detail.diff if r.field_key.startswith("sch_e.")]
    assert len(income) == 2
    net = sum((_amount(r.new) - _amount(r.old) for r in income), Decimal(0))
    (total,) = detail.totals
    assert total.label == "Net change to total income"
    assert net == Decimal(total.value) == 0 and total.ties
    qbi = next(r for r in detail.diff if r.field_key.startswith("f8995a."))
    assert _amount(qbi.new) == Decimal(307900)


def test_shl16a_the_steps_are_the_agents_in_order() -> None:
    detail = conforms(CheckpointDetailOut, DETAIL)
    assert [s.kind for s in detail.steps] == [
        "analyzed",
        "analyzed",
        "updated_worksheet",
        "updated_worksheet",
        "skipped_worksheet",
    ]
    assert [s.at for s in detail.steps] == sorted(s.at for s in detail.steps)
    assert detail.compare == "previous"


def test_shl16a_approve_with_the_full_digest() -> None:
    request = inline_example("<checkpoint-6>/approve` with")
    with pytest.raises(ValidationError):
        CheckpointApproveIn.model_validate(request)
    assert CheckpointApproveIn.model_validate({"seen_hash": FULL}).seen_hash == FULL


# --- b. Approved -------------------------------------------------------------------------------


def test_shl16b_approval_moves_current_and_links_the_proposal_decision() -> None:
    six = conforms(CheckpointHistoryOut, HISTORY).items[0]
    decision = {
        "id": "00000000-0000-4000-8000-000000000061",
        "decision": "approved",
        "reason": None,
        "decided_by_user_id": "00000000-0000-4000-8000-000000000062",
        "decided_by_name": "Samuel Ito",
        "decided_at": "2026-09-14T14:26:00Z",
        "proposal_decision_id": "00000000-0000-4000-8000-000000000063",
    }
    approved = CheckpointItemOut.model_validate(
        {**six.model_dump(), "status": "approved", "current": True, "decision": decision}
    )
    assert approved.decision is not None and approved.decision.proposal_decision_id is not None
    assert f"Checkpoint {approved.seq} approved" == "Checkpoint 6 approved"


# --- c. Older checkpoint; d. Rename; e. Rejected; f. Empty -------------------------------------


def test_shl16c_restore_is_a_new_checkpoint_and_deletes_nothing() -> None:
    fragment = inline_example("answers 201 with Checkpoint 7:")
    three = conforms(CheckpointHistoryOut, HISTORY).items[3]
    seven = CheckpointItemOut.model_validate({**three.model_dump(), **cast(Json, wire(fragment))})
    assert (seven.seq, seven.cause, seven.status) == (7, "restore", "saved")
    assert seven.restored_from_id == three.id
    assert CheckpointRestoreIn.model_validate({"seen_hash": FULL}).seen_hash == FULL


def test_shl16d_rename_and_star_change_only_name_and_starred() -> None:
    rename = CheckpointRenameIn.model_validate(inline_example("<checkpoint-5>` with"))
    assert (rename.name, rename.starred) == ("Before K-1 treatment", True)
    assert set(CheckpointRenameIn.model_fields) == {"name", "starred"}


def test_shl16e_reject_takes_a_reason() -> None:
    request = inline_example("<checkpoint-6>/reject` with")
    rejected = CheckpointRejectIn.model_validate({**request, "seen_hash": FULL})
    assert f"Samuel Ito · reason: {rejected.reason}" == "Samuel Ito · reason: Wait for final K-1"
    with pytest.raises(ValidationError):
        CheckpointRejectIn.model_validate({"seen_hash": FULL})


def test_shl16f_an_empty_history_still_offers_save() -> None:
    empty = conforms(CheckpointHistoryOut, inline_example("The history is"))
    assert empty.items == [] and empty.total == 0 and empty.current_checkpoint_id is None
    assert empty.allowed_actions == ["checkpoint.create"]


def test_shl16_restricted_data_lives_only_in_the_target_history_read() -> None:
    """A summary may carry return figures, so the history is a read of one target, never the
    list envelope (§2, DEC-145)."""
    assert "items.summary" in restricted_anywhere(CheckpointHistoryOut)
    assert "next_cursor" not in CheckpointHistoryOut.model_fields
