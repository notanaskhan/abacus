"""POR-23: the component auditor's room (A-09-T33; A-09 §3.7; SPEC-658 F7; DEC-5407; amber).

A room is one component; only a live client person holding an active `component_auditor`
grant on that component's scope opens it (`scope_only`): any other component, and every firm
record (the consolidation, eliminations, scoping, group materiality), is 404 (INV-4). Every
projection field is on the room allowlist (`ROOM_FIELDS`, tested): the group's and component's
names, the firm's name, the instructions as sent (component PM and the clearly-trivial threshold
only), the deliverables in client words (Due · ✓ You uploaded · Overdue · Returned), counts, and
the Questions thread on `component_thread`. No firm-only word, no agent, no "Accrued".

Uploads are new evidence versions (`component_auditor_upload`) linked to their deliverable; a
drop with no deliverable picked answers the "Which deliverable is this for?" picker (None), and
an upload to another component's deliverable is 404.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.modules.identity.api import AuthContext, active_grants

ROLE: Final = "component_auditor"
SCOPE: Final = "component"
ClientWord = Literal["due", "you_uploaded", "overdue", "returned"]
# The room's allowlist: nothing outside these names leaves the room (INV-4; tested).
ROOM_FIELDS: Final = frozenset(
    {
        "id",
        "group_name",
        "component_name",
        "firm_name",
        "acknowledged_on",
        "uploaded",
        "expected",
        "deliverables",
        "title",
        "due_on",
        "word",
        "uploaded_on",
        "return_note",
        "sections",
        "sent_on",
        "number",
        "body",
    }
)


class InstructionsNotSent(DomainConflict):
    code = "instructions_not_sent"


class LetterRendering(DomainConflict):
    code = "letter_rendering"


@dataclass(frozen=True)
class RoomDeliverable:
    id: UUID
    title: str
    due_on: date
    word: ClientWord
    uploaded_on: date | None
    return_note: str | None


@dataclass(frozen=True)
class Room:
    id: UUID
    group_name: str
    component_name: str
    firm_name: str
    acknowledged_on: date | None
    uploaded: int
    expected: int
    deliverables: tuple[RoomDeliverable, ...]


@dataclass(frozen=True)
class RoomSection:
    number: int
    title: str
    body: str


def client_word(status: str, due_on: date, returned: bool, today: date) -> ClientWord:
    """The client's words for a deliverable (never Expected, Received, Reviewed or Late)."""
    if status in ("received", "reviewed"):
        return "you_uploaded"
    if returned:
        return "returned"
    return "overdue" if today > due_on else "due"


_ROOM: Final = text(
    "SELECT c.id, c.engagement_id, c.work_item_id, c.consolidation_entity_id, a.id AS auditor_id, "
    "i.id AS instructions_id, i.status AS instructions_status, i.current_version_id, "
    "i.sent_at, i.acknowledged_at FROM components c JOIN component_auditors a "
    "ON a.component_id = c.id LEFT JOIN component_instructions i ON i.component_auditor_id = a.id "
    "WHERE c.id = :c"
)
_DELIVERABLES: Final = text(
    "SELECT id, title, due_on, status, received_at, returned_at, return_reason "
    "FROM component_deliverables WHERE component_auditor_id = :a ORDER BY due_on, created_at"
)
_SECTIONS: Final = text("SELECT sections FROM component_instruction_versions WHERE id = :v")


async def _granted(ctx: AuthContext, room_id: UUID) -> dict[str, object]:
    """The room, for a live client person holding the component's grant; else 404."""
    if ctx.tenant.actor_kind != "human" or not ctx.client:
        raise NotFound("component_room")
    grants = await active_grants(ctx.tenant, ctx.user_id)
    if not any(g.role == ROLE and g.scope_kind == SCOPE and g.scope_id == room_id for g in grants):
        raise NotFound("component_room")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_ROOM, {"c": room_id})).mappings().first()
    if row is None or row["instructions_status"] in (None, "draft"):
        raise NotFound("component_room")
    return dict(row)


async def _names(tenant: TenantContext, row: dict[str, object]) -> tuple[str, str, str]:
    """(group, component, firm): "Harlow & Pike Holdings, Inc. · FY2026 group audit", the
    component's entity, and the firm's own name (never the platform's)."""
    from abacus.modules.engagements.api import engagement_label
    from abacus.modules.identity.api import firm_name
    from abacus.modules.ledger import api as ledger
    from abacus.modules.organisations.api import client_names

    label = await engagement_label(tenant, cast(UUID, row["engagement_id"]))
    group = "" if label is None else f"{label.client_entity_name} · {label.name}"
    entity: UUID | None = None
    for consolidation_id in await ledger.consolidations_of(
        tenant, cast(UUID, row["work_item_id"])
    ):
        facts = await ledger.consolidation_facts(tenant, consolidation_id)
        found = next((e for e in facts.entities if e.id == row["consolidation_entity_id"]), None)
        if found is not None:
            entity = found.client_entity_id
            break
    component = ""
    if entity is not None:
        async with tenant_session(tenant) as session:
            names = await client_names(session, [entity])
        component = names[entity].client_entity_name if entity in names else ""
    return group, component, await firm_name(tenant.tenant_id)


async def room(ctx: AuthContext, room_id: UUID) -> Room:
    from abacus.kernel.clock import today

    row = await _granted(ctx, room_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_DELIVERABLES, {"a": row["auditor_id"]})).mappings().all()
    now = await today(ctx.tenant)
    items = tuple(
        RoomDeliverable(
            id=cast(UUID, r["id"]),
            title=str(r["title"]),
            due_on=cast(date, r["due_on"]),
            word=client_word(
                str(r["status"]), cast(date, r["due_on"]), r["returned_at"] is not None, now
            ),
            uploaded_on=(
                cast(datetime, r["received_at"]).date() if r["received_at"] is not None else None
            ),
            return_note=cast(str | None, r["return_reason"]),
        )
        for r in rows
    )
    group, component, firm = await _names(ctx.tenant, row)
    acknowledged = cast(datetime | None, row["acknowledged_at"])
    return Room(
        id=room_id,
        group_name=group,
        component_name=component,
        firm_name=firm,
        acknowledged_on=acknowledged.date() if acknowledged else None,
        uploaded=sum(1 for d in items if d.word == "you_uploaded"),
        expected=len(items),
        deliverables=items,
    )


async def instructions(ctx: AuthContext, room_id: UUID) -> tuple[tuple[RoomSection, ...], date]:
    row = await _granted(ctx, room_id)
    async with tenant_session(ctx.tenant) as session:
        raw = await session.scalar(_SECTIONS, {"v": row["current_version_id"]})
    stored = cast(
        "list[dict[str, object]]", json.loads(raw) if isinstance(raw, str) else raw or []
    )
    sections = tuple(
        RoomSection(int(cast(int, s["number"])), str(s["title"]), str(s["body"])) for s in stored
    )
    return sections, cast(datetime, row["sent_at"]).date()


async def instructions_pdf(ctx: AuthContext, room_id: UUID) -> bytes:
    """The sent letter's final PDF (C11); 409 `letter_rendering` until its render is filed."""
    from abacus.modules.evidence.api import version_content
    from abacus.modules.reporting import api as c11

    row = await _granted(ctx, room_id)
    document = await c11.document_of_owner(
        ctx.tenant,
        c11.OwnerRef("component_instruction_version", cast(UUID, row["current_version_id"])),
        "component_instructions",
    )
    final_no = None if document is None else await c11.final_version_no(ctx.tenant, document)
    if document is None or final_no is None:
        raise LetterRendering
    outcome = await c11.render_outcome(ctx.tenant, document, final_no)
    if outcome.status != "succeeded" or outcome.evidence_version_id is None:
        raise LetterRendering(facts={"status": outcome.status})
    system = TenantContext(ctx.tenant_id, "system", f"component_room:{room_id}")
    return await version_content(system, outcome.evidence_version_id)


async def acknowledge(ctx: AuthContext, room_id: UUID) -> date:
    """The auditor's contact acknowledges the instructions (once; a replay answers the date)."""
    from abacus.modules.assurance import component_auditors as ca
    from abacus.modules.organisations.api import contacts_of_user

    row = await _granted(ctx, room_id)
    if row["acknowledged_at"] is not None:
        return cast(datetime, row["acknowledged_at"]).date()
    async with tenant_session(ctx.tenant) as session:
        contacts = await contacts_of_user(session, ctx.user_id)
    if not contacts:
        raise NotFound("component_room")
    system = TenantContext(ctx.tenant_id, "system", f"component_room:{room_id}")
    await ca.acknowledge(system, cast(UUID, row["instructions_id"]), contacts[0])
    from abacus.kernel.clock import today

    return await today(ctx.tenant)


async def upload(
    ctx: AuthContext, room_id: UUID, deliverable_id: UUID | None, file_name: str, content: bytes
) -> tuple[UUID | None, UUID]:
    """A new evidence version; linked to its deliverable (which must be this room's), or left
    for the picker when none was named."""
    from abacus.modules.assurance import component_auditors as ca
    from abacus.modules.engagements.api import client_of
    from abacus.modules.evidence.api import file_component_upload

    row = await _granted(ctx, room_id)
    if deliverable_id is not None:
        async with tenant_session(ctx.tenant) as session:
            mine = await session.scalar(
                text(
                    "SELECT 1 FROM component_deliverables WHERE id = :d "
                    "AND component_auditor_id = :a"
                ),
                {"d": deliverable_id, "a": row["auditor_id"]},
            )
        if mine is None:
            raise NotFound("component_deliverable")
    engagement = cast(UUID, row["engagement_id"])
    client = await client_of(ctx.tenant, engagement)
    if client is None:
        raise NotFound("component_room")
    item, version = await file_component_upload(
        tenant_id=ctx.tenant_id,
        client_id=client,
        engagement_id=engagement,
        work_item_id=cast(UUID, row["work_item_id"]),
        file_name=file_name,
        content=content,
        user_id=ctx.user_id,
    )
    if deliverable_id is not None:
        system = TenantContext(ctx.tenant_id, "system", f"component_room:{room_id}")
        await ca.receive_deliverable(system, deliverable_id, item)
    return deliverable_id, version


async def questions(ctx: AuthContext, room_id: UUID) -> list[object]:
    from abacus.modules.assurance.component_auditors import THREAD_KIND
    from abacus.modules.collaboration.api import client_comments

    row = await _granted(ctx, room_id)
    return list(
        await client_comments(
            ctx, anchor_kind=THREAD_KIND, anchor_id=cast(UUID, row["auditor_id"])
        )
    )


async def ask(ctx: AuthContext, room_id: UUID, body: str) -> object:
    from abacus.modules.assurance.component_auditors import THREAD_KIND
    from abacus.modules.collaboration.api import post_client_comment

    row = await _granted(ctx, room_id)
    return await post_client_comment(
        ctx,
        anchor_kind=THREAD_KIND,
        anchor_id=cast(UUID, row["auditor_id"]),
        locator=None,
        body=body,
    )
