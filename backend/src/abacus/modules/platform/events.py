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
