"""The integrations module's domain events (W-01-T07). Identifiers only (ADR-090, C16)."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class IntegrationAvailable(DomainEvent):
    """W-01-T07 (AC-33): an integration a person asked about (Notify me) can now be enabled; the
    person is told once (C16 `integration_available`)."""

    event_type: ClassVar[str] = "integration.available"

    user_id: Annotated[UUID, classified("internal")]
    catalog_key: Annotated[str, classified("public")]
