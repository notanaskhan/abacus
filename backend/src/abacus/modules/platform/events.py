"""Domain events the platform module emits (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class TenantProvisioned(DomainEvent):
    """Q-01-T45 (platform-ops contract section 7): a firm finished `TenantProvisioningWorkflow`.
    Consumers: G-04's tenant directory, later."""

    event_type: ClassVar[str] = "tenant.provisioned"

    tenant_id: Annotated[UUID, classified("internal")]
    plan: Annotated[str, classified("internal")]
    synthetic: Annotated[bool, classified("internal")]
    operator: Annotated[str, classified("internal")]


class IncidentRecorded(DomainEvent):
    """Q-02-T33: a firm's QI recorded a security incident (`incident_recorded`, C16: the QI and
    partner-level members, never the person who recorded it)."""

    event_type: ClassVar[str] = "incident.recorded"

    incident_id: Annotated[UUID, classified("internal")]
    notification_event: Annotated[bool, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class IncidentPropagated(DomainEvent):
    """Q-02-T33 (RB-27): platform staff propagated an Accrued incident into this firm's register
    (`incident_from_accrued`, C16: the QI and firm admins, email even with digests on)."""

    event_type: ClassVar[str] = "incident.propagated"

    incident_id: Annotated[UUID, classified("internal")]
    notification_event: Annotated[bool, classified("internal")]


class IncidentDecisionRequested(DomainEvent):
    """G-02-T18 (AC-22): the first decider named the second (`incident_decision_requested`, to
    the named person only)."""

    event_type: ClassVar[str] = "incident.decision_requested"

    incident_id: Annotated[UUID, classified("internal")]
    waiting_for_user_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class IncidentDeadlineApproaching(DomainEvent):
    """G-02-T18 (AC-23): day 20, 25 or 29 of an open notification event's FTC clock
    (`incident_deadline_approaching`, to the QI and the partners)."""

    event_type: ClassVar[str] = "incident.deadline_approaching"

    incident_id: Annotated[UUID, classified("internal")]
    day: Annotated[int, classified("internal")]


class WispPackRequested(DomainEvent):
    """G-02-T20: the QI asked for the WISP evidence pack; its subscriber starts the build."""

    event_type: ClassVar[str] = "wisp_pack.requested"

    pack_id: Annotated[UUID, classified("internal")]
    requested_by: Annotated[UUID, classified("internal")]
