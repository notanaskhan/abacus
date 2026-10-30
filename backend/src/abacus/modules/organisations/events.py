"""Domain events published by the organisations module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class ClientUpdated(DomainEvent):
    """A person changed the client record (P-07-T09): which fields, never their values."""

    event_type: ClassVar[str] = "client.updated"

    client_id: Annotated[UUID, classified("internal")]
    fields: Annotated[list[str], classified("internal")]


class ContactCreated(DomainEvent):
    """A person added a client contact (P-07-T25; CLI-04): identifiers only."""

    event_type: ClassVar[str] = "contact.created"

    client_id: Annotated[UUID, classified("internal")]
    contact_id: Annotated[UUID, classified("internal")]


class OfficeCreated(DomainEvent):
    """A firm admin added an office (G-01-T08)."""

    event_type: ClassVar[str] = "office.created"

    office_id: Annotated[UUID, classified("internal")]


class OfficeUpdated(DomainEvent):
    """A firm admin changed an office (G-01-T08): which fields, never their values."""

    event_type: ClassVar[str] = "office.updated"

    office_id: Annotated[UUID, classified("internal")]
    fields: Annotated[list[str], classified("internal")]


class TeamMemberAdded(DomainEvent):
    """Someone joined a team or group (G-01-T08; F-03's event)."""

    event_type: ClassVar[str] = "team.member_added"

    team_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class TeamMemberRemoved(DomainEvent):
    """Someone left a team or group (G-01-T08)."""

    event_type: ClassVar[str] = "team.member_removed"

    team_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class ConsentExpiring(DomainEvent):
    """T-01-T16: a signed §7216 consent is 30 days or fewer from expiry (the sweep, once)."""

    event_type: ClassVar[str] = "consent.expiring"

    consent_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    requested_by: Annotated[UUID, classified("internal")]


class ConsentExpired(DomainEvent):
    """T-01-T16: a signed consent passed its expiry; the gate refuses from now."""

    event_type: ClassVar[str] = "consent.expired"

    consent_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
