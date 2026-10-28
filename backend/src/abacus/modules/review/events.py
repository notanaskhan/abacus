"""Domain events the review module announces (P-04 §4.5). Identifiers and codes only (ADR-031)."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class SignOffRecorded(DomainEvent):
    """A person signed a target at a level (P-04-T18)."""

    event_type: ClassVar[str] = "sign_off.recorded"

    sign_off_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    level: Annotated[int, classified("internal")]
    signed_by: Annotated[UUID, classified("internal")]


class SignOffWentStale(DomainEvent):
    """A sign-off's target changed after it was signed (P-04-T19): the signer is told. Nothing
    about the sign-off row changes; staleness stays computed (ADR-160 clause 3)."""

    event_type: ClassVar[str] = "sign_off.went_stale"

    sign_off_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    level: Annotated[int, classified("internal")]
    signed_by: Annotated[UUID, classified("internal")]


# --- Review notes (P-04-T21; P-04 §4.5) --------------------------------------------------------


class ReviewNoteRaised(DomainEvent):
    """A person raised a note: the assignee (or, with none, the target's preparers) is told
    (`review_note_raised`). Never the body."""

    event_type: ClassVar[str] = "review_note.raised"

    note_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]


class ReviewNoteResponded(DomainEvent):
    event_type: ClassVar[str] = "review_note.responded"

    note_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class ReviewNoteCleared(DomainEvent):
    event_type: ClassVar[str] = "review_note.cleared"

    note_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class ReviewNoteReopened(DomainEvent):
    event_type: ClassVar[str] = "review_note.reopened"

    note_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class ReviewNoteWithdrawn(DomainEvent):
    event_type: ClassVar[str] = "review_note.withdrawn"

    note_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


# --- Decision cards (P-04-T23; ADR-160 clause 8) -----------------------------------------------


class DecisionCardRaised(DomainEvent):
    """A card waits on its reserved role: the reserved person, or the engagement's holders of the
    role, are told (`decision_assigned`)."""

    event_type: ClassVar[str] = "decision_card.raised"

    card_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    kind: Annotated[str, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]


class DecisionCardSuperseded(DomainEvent):
    event_type: ClassVar[str] = "decision_card.superseded"

    card_id: Annotated[UUID, classified("internal")]
    superseded_by_card_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    kind: Annotated[str, classified("internal")]


class DecisionDecided(DomainEvent):
    """The reserved person decided: the kind's owner applies it (P-10 resumes a waiting run)."""

    event_type: ClassVar[str] = "decision.decided"

    card_id: Annotated[UUID, classified("internal")]
    decision_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    kind: Annotated[str, classified("internal")]
    option_key: Annotated[str, classified("internal")]
    decided_by: Annotated[UUID, classified("internal")]


class DecisionNotifyRequested(DomainEvent):
    """ "Notify <person>" on a card: a mention to the reserved person (SHL-11 b)."""

    event_type: ClassVar[str] = "decision_card.notify_requested"

    card_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]
    assignee_user_id: Annotated[UUID, classified("internal")]


# --- Field values (P-04-T24 write path; ADR-160 clause 10) -------------------------------------


class FieldValueRecorded(DomainEvent):
    """A field's new version (`review.api.record_value`). Never the value."""

    event_type: ClassVar[str] = "field.value_recorded"

    engagement_id: Annotated[UUID | None, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    field_key: Annotated[str, classified("internal")]
    seq: Annotated[int, classified("internal")]
    cause: Annotated[str, classified("internal")]


class HumanGateReassigned(DomainEvent):
    """A person moved a gate to someone else (I-01-T07): the new person is told
    (`gate_reassigned`, C16)."""

    event_type: ClassVar[str] = "human_gate.reassigned"

    gate_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    to_user_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


# --- Checkpoints (P-04-T32; SHL-16; DEC-85) --------------------------------------------------


class CheckpointRecorded(DomainEvent):
    """A checkpoint was proposed (agent, import), saved or restored as a new checkpoint."""

    event_type: ClassVar[str] = "checkpoint.recorded"

    checkpoint_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    seq: Annotated[int, classified("internal")]
    status: Annotated[str, classified("internal")]
    cause: Annotated[str, classified("internal")]


class CheckpointApproved(DomainEvent):
    """A person approved a checkpoint; Current moved. Identifiers only: T-01 and N-02 read the
    summed amount deltas (`review.api.checkpoint_deltas`, Restricted, return figures) to void a
    signed 8879 above the Pub 1345 tolerances (DEC-85). `has_deltas` says whether there are any."""

    event_type: ClassVar[str] = "checkpoint.approved"

    checkpoint_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    decided_by: Annotated[UUID, classified("internal")]
    proposal_decision_id: Annotated[UUID | None, classified("internal")]
    has_deltas: Annotated[bool, classified("internal")]


class CheckpointRejected(DomainEvent):
    """A person rejected a proposed checkpoint (the reason stays sealed in the decision)."""

    event_type: ClassVar[str] = "checkpoint.rejected"

    checkpoint_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    decided_by: Annotated[UUID, classified("internal")]
