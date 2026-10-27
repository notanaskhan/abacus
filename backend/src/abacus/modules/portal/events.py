"""Domain events the portal module announces (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class PortalSettingsPublished(DomainEvent):
    """R-01-T26: a firm published its portal settings; consumers read the new version."""

    event_type: ClassVar[str] = "portal_settings.published"

    version: Annotated[int, classified("internal")]
