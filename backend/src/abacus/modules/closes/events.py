"""Domain events the closes module publishes (ADR-018; C-01 §4.6). Identifiers and enums only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import Field

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent

_I = classified("internal")


class CloseStatusChanged(DomainEvent):
    """A close moved (C-01-T14, AC-9): the home count, K-04's board and C-02 listen."""

    event_type: ClassVar[str] = "close.status_changed"

    close_id: Annotated[UUID, _I]
    from_status: Annotated[str, _I]
    to_status: Annotated[str, _I]


class ClosePlanPublishRequested(DomainEvent):
    """A Senior asked the engagement's Managers and Partners to publish a draft (QC-8): C13
    raises one HOME-02 gate (`gate_sources.py`)."""

    event_type: ClassVar[str] = "close_plan.publish_requested"

    plan_id: Annotated[UUID, _I]
    version_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


class ClosePlanPublished(DomainEvent):
    """A version published (AC-17): the gate closes; later closes pin it at BD1."""

    event_type: ClassVar[str] = "close_plan.published"

    plan_id: Annotated[UUID, _I]
    version_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


class CloseRequestsPublished(DomainEvent):
    """C-01-T19: a close's requests were generated and published at BD1 from its pinned plan
    version (the preparer's digest, C16 `close_requests_published`; POR-11's close home)."""

    event_type: ClassVar[str] = "close_requests.published"

    close_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    binder_id: Annotated[UUID, _I]
    plan_version: Annotated[int, _I]
    count: Annotated[int, _I]
    # C-01-T26: the preparer's digest (C16 `close_requests_published`).
    recipient_user_ids: Annotated[list[UUID], _I] = Field(default_factory=list[UUID])


class CloseCreated(DomainEvent):
    """C-01-T19: a close was generated; its BD1 publish workflow starts after commit (the worker's
    relay), so a request path never needs Temporal."""

    event_type: ClassVar[str] = "close.created"

    close_id: Annotated[UUID, _I]
    period: Annotated[str, _I]


# --- C-01-T26 (DEC-5412): what C13's close gates and C16's close kinds read ----------------------


class ReconciliationComputed(DomainEvent):
    """A reconciliation version was written (C-01 §4.6): its L1 gate is reconsidered."""

    event_type: ClassVar[str] = "reconciliation.computed"

    reconciliation_id: Annotated[UUID, _I]
    close_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


class ReconcilingItemResolved(DomainEvent):
    """A person carried forward or cleared an item: an L1 may now be due."""

    event_type: ClassVar[str] = "reconciling_item.resolved"

    reconciliation_id: Annotated[UUID, _I]
    close_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


class AnalyticSetComputed(DomainEvent):
    """A flux set version was written; its acceptance gate is reconsidered."""

    event_type: ClassVar[str] = "analytic_set.computed"

    set_id: Annotated[UUID, _I]
    close_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]


class AnalyticLineExplained(DomainEvent):
    """A person explained a flux line: it waits on a Manager's or Partner's acceptance."""

    event_type: ClassVar[str] = "analytic_line.explained"

    set_id: Annotated[UUID, _I]
    close_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    line_key: Annotated[str, _I]


class CloseRunFinished(DomainEvent):
    """A close run ended "Complete with exceptions": C16 `close_run_finished` to the close's
    preparer and reviewer (C-01 §4.6). Counts only."""

    event_type: ClassVar[str] = "close_run.finished"

    close_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    run_id: Annotated[UUID, _I]
    open_issues: Annotated[int, _I]
    recipient_user_ids: Annotated[list[UUID], _I]


class CloseRunNeedsInput(DomainEvent):
    """A close run waits on a person: C16 `close_run_needs_input` to the run's starter."""

    event_type: ClassVar[str] = "close_run.needs_input"

    close_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    run_id: Annotated[UUID, _I]
    recipient_user_ids: Annotated[list[UUID], _I]


class CloseQuestionAnswered(DomainEvent):
    """A client answered a close's transaction question: C16 `transaction_question_answered` to
    the issue's assignee."""

    event_type: ClassVar[str] = "close_question.answered"

    close_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    question_id: Annotated[UUID, _I]
    issue_id: Annotated[UUID, _I]
    recipient_user_ids: Annotated[list[UUID], _I]
