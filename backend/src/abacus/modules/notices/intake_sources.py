"""N-04-T13: where notice intakes come from (NOT-01; N-04 §3 US-1; DEC-2245).

- **Answer effect** `route_upload_to_notices` (T-03's slot): an organizer upload answered with
  an IRS letter (Q8) creates exactly one intake from its evidence version; an upload with no
  evidence version leaves the handler unavailable, so the engine records `pending_handler` and
  the upload stays in the binder (`notices.workspace` retired, DEC-2602).
- **Triage destinations** (N-01): `notice_intake` ("New notice from this file") and `notice`
  (supporting documents filed to an existing notice: Stein-style). `notice` places the file on
  the notice's work item; `notice_intake` files it to the client's permanent file, from which
  the intake is created when the person opens it (NOT-01 b).
- The portal's "Upload something else" reaches an intake through the same answer effect when the
  firm's organizer routes it.

Each intake records its source; a replayed effect creates nothing more (the engine's row per
answer and rule).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, UnitOfWork, uow
from abacus.modules.communications.api import (
    IntakeDestination,
    IntakeNode,
    register_intake_destination,
)
from abacus.modules.communications.api import Placement as IntakePlacement
from abacus.modules.identity.api import AuthContext
from abacus.modules.organisations.api import client_of_entity
from abacus.modules.requests.api import (
    EffectRequest,
    EffectResult,
    HandlerUnavailable,
    register_answer_effect,
)


async def route_upload_to_notices(request: EffectRequest) -> EffectResult:
    tenant = TenantContext(request.tenant_id, "system", "answer_effects")
    if request.evidence_version_id is None:
        raise HandlerUnavailable
    async with uow(tenant) as tx:
        # The intake's named creator is the organizer's owner (the effect is the rule's, the
        # system's act; a person is named, never the agent). The engine hands it over.
        creator = request.owner_user_id
        intake_id = await tx.session.scalar(
            text(
                "INSERT INTO notice_intakes (tenant_id, source, evidence_version_id, status, "
                "extraction_mode, created_by) VALUES (:t, 'organizer', :ev, 'manual_entry', "
                "'manual', :by) RETURNING id"
            ),
            {"t": request.tenant_id, "ev": request.evidence_version_id, "by": creator},
        )
        tx.record(
            "notice_intake.created",
            target=Target("notice_intake", UUID(str(intake_id))),
        )
    return EffectResult("notice_intake", UUID(str(intake_id)))


async def _notice_nodes(
    ctx: AuthContext, client_id: UUID, parent: UUID | None
) -> Sequence[IntakeNode]:
    """The client's open notices (supporting documents file to one)."""
    if parent is not None:
        return []
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT n.work_item_id, n.notice_code, n.tax_year, n.client_entity_id "
                    "FROM notices n WHERE n.status <> 'closed' ORDER BY n.received_on DESC"
                )
            )
        ).all()
    # The entity's client through organisations' own read (OWN-001); a firm has few open notices.
    owners = {e: await client_of_entity(ctx.tenant, e) for e in {r[3] for r in rows}}
    return [
        IntakeNode("notice", wid, f"{code or 'Notice'} · {year or ''}".strip(" ·"))
        for wid, code, year, entity in rows
        if owners.get(entity) == client_id
    ]


async def _place_notice(tenant: TenantContext, tx: UnitOfWork, notice_id: UUID) -> IntakePlacement:
    row = (
        await tx.session.execute(
            text("SELECT engagement_id, client_entity_id FROM notices WHERE work_item_id = :w"),
            {"w": notice_id},
        )
    ).one()
    client_id = await client_of_entity(tenant, row.client_entity_id)
    if client_id is None:
        raise NotFound("notice")
    return IntakePlacement(row.engagement_id, notice_id, client_id)


async def _intake_nodes(
    ctx: AuthContext, client_id: UUID, parent: UUID | None
) -> Sequence[IntakeNode]:
    if parent is not None:
        return []
    return [IntakeNode("notice_intake", client_id, "New notice from this file")]


async def _place_intake(tenant: TenantContext, tx: UnitOfWork, client_id: UUID) -> IntakePlacement:
    del tenant, tx
    return IntakePlacement(None, None, client_id)


def register() -> None:
    register_answer_effect("route_upload_to_notices", route_upload_to_notices)
    register_intake_destination(IntakeDestination("notice", _notice_nodes, _place_notice))
    register_intake_destination(IntakeDestination("notice_intake", _intake_nodes, _place_intake))
