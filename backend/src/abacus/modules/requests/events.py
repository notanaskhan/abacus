"""Domain events published by the requests module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class RequestItemCreated(DomainEvent):
    event_type: ClassVar[str] = "request_item.created"

    request_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]


class RequestItemClassified(DomainEvent):
    """An item became retrievable tier A with a dataset (SPEC-022): connections may retrieve it
    automatically when the live connection delivers that dataset."""

    event_type: ClassVar[str] = "request_item.classified"

    request_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
