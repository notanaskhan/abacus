"""What the matcher's intake mode reads of firm intake (N-01-T22; N-01 §6).

`intake_attachment_facts` names one attachment's client, file name, channel and status for the
agents module (identifiers and the file's own name only; never the sender's address or the
message). `intake_folder_destinations` lists the client's selectable folder destinations
(the permanent file, each work item's folder, and any kind another module registers except
requests, which the matcher reads from requests itself), through INB-02's picker for the person
the run acts for: their walls, the flag and the triage permission apply exactly as in the picker.
Nothing here files anything; Apply stays a person's (I-AGENT-NEVER).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.communications.triage_apply import Node, destinations
from abacus.modules.identity.api import AuthContext

_FACTS = text(
    "SELECT a.id, a.client_id, t.client_entity_id, a.file_name, a.media_type, a.status, "
    "t.source_kind FROM inbox_attachments a JOIN inbox_threads t ON t.id = a.thread_id "
    "WHERE a.id = :id"
)


@dataclass(frozen=True)
class IntakeAttachmentFacts:
    attachment_id: UUID
    client_id: UUID | None
    client_entity_id: UUID | None
    file_name: str
    media_type: str
    status: str
    channel: str  # the thread's source kind: mailbox, portal or staff


@dataclass(frozen=True)
class FolderDestination:
    kind: str
    id: UUID
    label: str


async def intake_attachment_facts(
    tenant: TenantContext, attachment_id: UUID
) -> IntakeAttachmentFacts | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_FACTS, {"id": attachment_id})).one_or_none()
    if row is None:
        return None
    return IntakeAttachmentFacts(
        row.id,
        row.client_id,
        row.client_entity_id,
        row.file_name,
        row.media_type,
        row.status,
        row.source_kind,
    )


async def intake_folder_destinations(ctx: AuthContext, client_id: UUID) -> list[FolderDestination]:
    """The client's selectable destinations other than requests, one level below each
    non-selectable parent (a work item and its folder), in the picker's order."""
    out: list[FolderDestination] = []
    for node in await destinations(ctx, client_id, None, None):
        if node.kind == "request":
            continue
        if node.selectable:
            out.append(FolderDestination(node.kind, node.id, node.label))
        elif node.has_children:
            out.extend(
                FolderDestination(child.kind, child.id, f"{node.label}: {child.label}")
                for child in await _children(ctx, client_id, node)
                if child.selectable and child.kind != "request"
            )
    return out


async def _children(ctx: AuthContext, client_id: UUID, parent: Node) -> list[Node]:
    kind = "work_item_folder" if parent.kind == "work_item" else parent.kind
    return await destinations(ctx, client_id, kind, parent.id)
