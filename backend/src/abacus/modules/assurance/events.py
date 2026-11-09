"""The assurance module's outbox events (A-04 §4.5): identifiers only (ADR-007)."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class MaterialityDecided(DomainEvent):
    """The engagement partner decided materiality: A-03's sampling hold and I-01 read it."""

    event_type: ClassVar[str] = "materiality.decided"

    version_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    decision_id: Annotated[UUID, classified("internal")]


class MaterialityReassessed(DomainEvent):
    """The partner recorded a reassessment at the final basis: No change or Revise (AC3.6)."""

    event_type: ClassVar[str] = "materiality.reassessed"

    version_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    decision_id: Annotated[UUID, classified("internal")]
    revised: Annotated[bool, classified("internal")]


class MaterialityRevised(DomainEvent):
    """A revision's impact list (AC3.7): the preparers of each impacted workpaper are told
    (`materiality_revised`); nothing is recomputed silently."""

    event_type: ClassVar[str] = "materiality.revised"

    version_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]


class FraudMinutesAwaitingApproval(DomainEvent):
    """A person wrote or adopted the fraud brainstorm's minutes: the engagement partners are told
    (`fraud_minutes_awaiting_approval`, C16) and HOME-02's gate opens (A-04-T19)."""

    event_type: ClassVar[str] = "fraud_minutes.awaiting_approval"

    session_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]


class RiskRegisterApproved(DomainEvent):
    """The engagement partner approved the risk register at its hash (A-04-T18): G4 reads it."""

    event_type: ClassVar[str] = "risk_register.approved"

    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    decision_id: Annotated[UUID, classified("internal")]
    register_hash: Annotated[str, classified("internal")]


class ControlExceptionRecorded(DomainEvent):
    """A-04-T25 (DEC-2206): a row of the Exceptions sheet was recorded or replaced (identifiers
    only); A-06's findings and AUD-09's read model hear it."""

    event_type: ClassVar[str] = "control_exception.recorded"

    engagement_id: Annotated[UUID, classified("internal")]
    workpaper_id: Annotated[UUID, classified("internal")]
    control_exception_id: Annotated[UUID, classified("internal")]
    sheet_row: Annotated[int, classified("internal")]


class ServiceOrgRelianceConcluded(DomainEvent):
    """A-04-T31 (DEC-2236): the engagement partner decided reliance on a SOC 1 report (identifiers
    only); AUD-09's control reliance and the A-07 governance letter's service-organisation facts
    read it."""

    event_type: ClassVar[str] = "service_org.reliance_concluded"

    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    soc_report_id: Annotated[UUID, classified("internal")]
    service_organization_id: Annotated[UUID, classified("internal")]
    decision_id: Annotated[UUID, classified("internal")]
    relied: Annotated[bool, classified("internal")]


class ReportReleased(DomainEvent):
    """G8 (A-07-T30; A-07 §4.6): the engagement partner released the report in Accrued. The P-14
    retention clock, PostReleaseClocksWorkflow (A-07-T36), A-06's findings communicated and the
    HOME-02 projector read it."""

    event_type: ClassVar[str] = "report.released"

    release_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    report_version_id: Annotated[UUID, classified("internal")]
    final_document_version_id: Annotated[UUID, classified("internal")]
