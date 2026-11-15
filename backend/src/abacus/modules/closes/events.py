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
