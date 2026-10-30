"""Reference-set publication fan-out, the activities (K-02-T12; K-02 §4.6; ADR-300; SPEC-500
AC-49 to AC-51).

Reference sets are global; firms learn of a published (or withdrawn) version through one audit
event and one outbox event per active tenant, `reference_set.published` (or
`reference_set.withdrawn`), naming the version, its set key and the operator and approver
handles, never a rule's value. Consumers subscribe to the outbox event (tax recomputes unfiled
returns' due dates); C16 turns it into "Rules table updated" for firm admins and tax partners.

Idempotent on (tenant, version, action): an announcement already in the tenant's audit trail is
not written again, so a re-run or a retried activity adds nothing.
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Final
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
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


@activity.defn(name="platform.reference_set_tenants")
async def reference_set_tenants() -> list[str]:
    """Every active tenant (0400's owner-only `active_tenant_ids()`)."""
    async with platform_transaction(ACTOR) as conn:
        rows = await conn.execute(text("SELECT tenant_id FROM active_tenant_ids()"))
        return [str(r[0]) for r in rows]


async def _publication(version_id: UUID, action: str) -> tuple[str, str, str] | None:
    async with platform_transaction(ACTOR) as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT v.set_key, p.operator, p.approver "
                    "FROM reference_set_publications p "
                    "JOIN reference_set_versions v ON v.id = p.version_id "
                    "WHERE p.version_id = :id AND p.action = :action "
                    "ORDER BY p.at DESC LIMIT 1"
                ),
                {"id": version_id, "action": action},
            )
        ).first()
    return None if row is None else (str(row[0]), str(row[1]), str(row[2]))


@activity.defn(name="platform.reference_set_announce")
async def reference_set_announce(tenant_id: str, version_id: str, action: str) -> bool:
    """One tenant's announcement; False when it was already written (idempotent)."""
    tenant = TenantContext(UUID(tenant_id), "system", ACTOR)
    version = UUID(version_id)
    audit_action = f"reference_set.{action}"
    async with tenant_session(tenant) as session:
        if (await session.execute(_SEEN, {"action": audit_action, "id": version_id})).first():
            return False
    found = await _publication(version, action)
    if found is None:
        return False  # nothing was published or withdrawn under that id
    set_key, operator, approver = found
    async with uow(tenant) as tx:
        tx.record(
            audit_action,
            target=Target("reference_set_version", version),
            after=Ref(set_key=set_key, operator=operator[:80], approver=approver[:80]),
        )
        event = (
            ReferenceSetPublished(version_id=version, set_key=set_key)
            if action == "published"
            else ReferenceSetWithdrawn(version_id=version, set_key=set_key)
        )
        tx.emit(event)
    return True


async def start_fanout(version_id: UUID, action: str) -> None:
    """After `refdata publish|withdraw`: one fan-out run per version and action."""
    await dispatch(
        ReferenceSetFanOutWorkflow,
        FanOutInput(str(version_id), action),
        id=fanout_workflow_id(str(version_id), action),
    )


ACTIVITIES: Final[tuple[object, ...]] = (reference_set_tenants, reference_set_announce)
