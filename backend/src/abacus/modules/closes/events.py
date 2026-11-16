"""Domain events the closes module publishes (ADR-018; C-01 §4.6). Identifiers and enums only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

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


class CloseCreated(DomainEvent):
    """C-01-T19: a close was generated; its BD1 publish workflow starts after commit (the worker's
    relay), so a request path never needs Temporal."""

    event_type: ClassVar[str] = "close.created"

    close_id: Annotated[UUID, _I]
    period: Annotated[str, _I]
