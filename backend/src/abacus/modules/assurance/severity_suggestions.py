"""A-06-T16 seam (DEC-2952): the agent's proposed deficiency severity, as a suggestion.

The agent proposes a severity through `agents.api.create_suggestion` with the deficiency as target
(`deficiency_severity`, field `severity`). The `suggestion.created` subscriber mirrors it on the
deficiency as the agent's proposal (`severity_proposed_by_kind` agent), unless a person proposed
one first; the AUD-15 card reads it as "Agent recommendation". Adopting it makes it the person's
proposal. Concluding stays the engagement partner's decision (`deficiency_severity` decision kind,
FINDING-001): nothing here sets `severity_concluded`.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.api import AdoptedValue, pending_suggestion
from abacus.modules.identity.api import AuthContext

SEVERITY_SUGGESTION_TARGET: Final = "deficiency_severity"
FIELD: Final = "severity"
SEVERITIES: Final = frozenset({"deficiency", "significant_deficiency", "material_weakness"})
_ACTOR: Final = "assurance:severity_suggestion"


class SeverityConcluded(DomainConflict):
    """The deficiency is concluded or past proposal: a suggestion no longer changes it."""

    code = "severity_concluded"


def suggested_severity(value: dict[str, object]) -> str | None:
    found = value.get("v")
    return found if isinstance(found, str) and found in SEVERITIES else None


async def deficiency_engagement(tenant: TenantContext, deficiency_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        return await session.scalar(
            text("SELECT engagement_id FROM deficiencies WHERE id = :id"), {"id": deficiency_id}
        )


async def on_suggestion_created(event: OutboxEvent) -> None:
    """Mirror a pending severity as the agent's proposal; a person's proposal stands."""
    if event.payload.get("target_type") != SEVERITY_SUGGESTION_TARGET:
        return
    tenant = TenantContext(event.tenant_id, "system", _ACTOR)
    found = await pending_suggestion(tenant, UUID(str(event.payload["suggestion_id"])))
    if found is None or found.target_type != SEVERITY_SUGGESTION_TARGET:
        return
    severity = suggested_severity(found.proposed_value)
    if severity is None or found.field_key != FIELD:
        return
    # Nothing to mirror (a person proposed first, or the row moved on): the unit of work has no
    # event to record, so it commits nothing, and redelivery finds the same.
    with suppress(MissingAuditEvent):
        await _mirror(tenant, found.target_id, found.suggestion_id, severity)


async def _mirror(tenant: TenantContext, target: UUID, suggestion: UUID, severity: str) -> None:
    async with uow(tenant) as tx:
        moved = await tx.session.scalar(
            text(
                "UPDATE deficiencies SET severity_proposed = :sev, "
                "severity_proposed_by_kind = 'agent', severity_suggestion_id = :sugg, "
                "version = version + 1 WHERE id = :id AND status = 'proposed' "
                "AND severity_concluded IS NULL "
                "AND (severity_proposed IS NULL OR severity_proposed_by_kind = 'agent') "
                "RETURNING id"
            ),
            {"sev": severity, "sugg": suggestion, "id": target},
        )
        if moved is None:
            return
        tx.record(
            "deficiency.severity_suggested",
            target=Target("deficiency", target),
            after=Ref(suggestion=suggestion),
        )


async def apply_severity_suggestion(
    tx: UnitOfWork, ctx: AuthContext, adopted: AdoptedValue
) -> None:
    """The applier, in the adopting unit of work: the severity becomes the person's proposal."""
    del ctx
    severity = suggested_severity(adopted.value)
    if severity is None:
        raise NotFound("severity")
    moved = await tx.session.scalar(
        text(
            "UPDATE deficiencies SET severity_proposed = :sev, "
            "severity_proposed_by_kind = 'human', severity_suggestion_id = :sugg, "
            "version = version + 1 WHERE id = :id AND status = 'proposed' "
            "AND severity_concluded IS NULL RETURNING id"
        ),
        {"sev": severity, "sugg": adopted.suggestion_id, "id": adopted.target_id},
    )
    if moved is None:
        raise SeverityConcluded
    tx.record(
        "deficiency.severity_proposed",
        target=Target("deficiency", adopted.target_id),
        after=None if adopted.suggestion_id is None else Ref(suggestion=adopted.suggestion_id),
    )


SUBSCRIPTIONS: Final = {"suggestion.created": on_suggestion_created}
__all__ = [
    "SEVERITY_SUGGESTION_TARGET",
    "SUBSCRIPTIONS",
    "apply_severity_suggestion",
    "deficiency_engagement",
    "on_suggestion_created",
]
