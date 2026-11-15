"""Domain events of the governing-instrument reading (T-07-T03 part, TASK-8069; T-07 §4.8;
SPEC-656 AC-4.1). Identifiers and codes only (ADR-018): C13 raises and closes the
`instrument_interpretation_approval` gate on them, and C16 fans out
`instrument_interpretation_ready` and `instrument_read_finished`."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent

_I = classified("internal")


class InstrumentInterpretationAdopted(DomainEvent):
    """A person's L1 write adopted the interpretation (AC-4.1): the manager's L3 gate opens and
    `instrument_interpretation_ready` goes to the engagement's managers."""

    event_type: ClassVar[str] = "instrument_interpretation.adopted"

    interpretation_id: Annotated[UUID, _I]
    work_item_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    by_user: Annotated[UUID, _I]


class InstrumentInterpretationApproved(DomainEvent):
    """The L3 sign-off locked it (AC-4.2): the gate closes."""

    event_type: ClassVar[str] = "instrument_interpretation.approved"

    interpretation_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


class InstrumentInterpretationReopened(DomainEvent):
    """A Manager or Partner reopened it with a reason (AC-5.2): the gate stays closed until a
    person's write adopts it again."""

    event_type: ClassVar[str] = "instrument_interpretation.reopened"

    interpretation_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


class InstrumentReadFinished(DomainEvent):
    """The reader's run ended (T-07 §4.8): proposed, nothing to propose or refused, to the person
    who started it (`user_id`)."""

    event_type: ClassVar[str] = "instrument_read.finished"

    run_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    work_item_id: Annotated[UUID, _I]
    user_id: Annotated[UUID, _I]
    outcome: Annotated[str, _I]  # proposed, nothing_to_propose or refused
    code: Annotated[str | None, _I] = None
