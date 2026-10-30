"""Reference-set publication fan-out, the activity (K-02-T12; K-02 §4.6; ADR-300; SPEC-500 AC-49
to AC-51; DEC-1358).

Reference sets are global; firms learn of a published (or withdrawn) version through one audit
event and one outbox event per active tenant, `reference_set.published` (or
`reference_set.withdrawn`), naming the version, its set key and the operator and approver
handles, never a rule's value. Consumers subscribe to the outbox event (tax recomputes unfiled
returns' due dates); C16 turns it into "Rules table updated" for firm admins.

The owner-role CLI reads the handles and `active_tenant_ids()` (the worker's app role has no
grant on 0400's tables) and starts the run with them. Idempotent on (tenant, version, action): an
announcement already in the tenant's audit trail is not written again.
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Final
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.platform.reference_fanout_workflow import (
    FanOutInput,
    ReferenceSetFanOutWorkflow,
    fanout_workflow_id,
)

ACTOR: Final = "system:reference_fanout"
_SEEN = text(
    "SELECT 1 FROM audit_events WHERE action = :action AND target_type = 'reference_set_version' "
    "AND target_id = :id LIMIT 1"
)


class ReferenceSetPublished(DomainEvent):
    """A platform reference set version took effect for every firm (identifiers only)."""

    event_type: ClassVar[str] = "reference_set.published"

    version_id: Annotated[UUID, classified("internal")]
    set_key: Annotated[str, classified("public")]


class ReferenceSetWithdrawn(DomainEvent):
    event_type: ClassVar[str] = "reference_set.withdrawn"

    version_id: Annotated[UUID, classified("internal")]
    set_key: Annotated[str, classified("public")]


@activity.defn(name="platform.reference_set_announce")
async def reference_set_announce(tenant_id: str, request: FanOutInput) -> bool:
    """One tenant's announcement; False when it was already written (idempotent)."""
    tenant = TenantContext(UUID(tenant_id), "system", ACTOR)
    version = UUID(request.version_id)
    audit_action = f"reference_set.{request.action}"
    async with tenant_session(tenant) as session:
        seen = await session.execute(_SEEN, {"action": audit_action, "id": request.version_id})
        if seen.first() is not None:
            return False
    async with uow(tenant) as tx:
        tx.record(
            audit_action,
            target=Target("reference_set_version", version),
            after=Ref(
                set_key=request.set_key,
                operator=request.operator[:80],
                approver=request.approver[:80],
            ),
        )
        tx.emit(
            ReferenceSetPublished(version_id=version, set_key=request.set_key)
            if request.action == "published"
            else ReferenceSetWithdrawn(version_id=version, set_key=request.set_key)
        )
    return True


async def start_fanout(request: FanOutInput) -> None:
    """After `refdata publish|withdraw` (owner role): one run per version and action."""
    await dispatch(
        ReferenceSetFanOutWorkflow,
        request,
        id=fanout_workflow_id(request.version_id, request.action),
    )


ACTIVITIES: Final[tuple[object, ...]] = (reference_set_announce,)
