"""POR-09's live reads over C10 (S33 partials round; R-02-T09/T16/T17; DEC-3136).

- **The person's clients** (`portal_client_ids`): every client one of their active grants covers
  (a grant on an engagement, work item, entity or governance room covers its client); narrowed to
  one scope's client when the rail is asked for a scope it holds.
- **One deliverable** (`portal_deliverable`): its published versions, newest last, each read
  through C10's reader rule (`reader_version`: a client person holding an audience grant; 404
  alike for anyone else, AC-41). A version that has a C18 approval item takes that item's
  `seen_hash` (what the client reads is what they approve, AC-4) and offers `approve` only while
  the item waits, on the newest version, never on a withdrawn one; any other version's hash is
  its render hash. `comment` follows `page_comments`; `download` is every readable version's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.engagements.api import client_approval_provider
from abacus.modules.identity.api import AuthContext, active_grants, scope_facts
from abacus.modules.reporting.deliverable_reads import reader_version

DeliverableAction = Literal["download", "approve", "comment"]
_WAITING: Final = frozenset({"waiting", "question_sent"})


async def portal_client_ids(ctx: AuthContext, scope_id: UUID | None = None) -> list[UUID]:
    """The clients the person's active grants cover; one scope's client when asked for it."""
    clients: list[UUID] = []
    for grant in await active_grants(ctx.tenant, ctx.user_id):
        if scope_id is not None and grant.scope_id != scope_id:
            continue
        facts = await scope_facts(ctx.tenant, grant.scope_kind, grant.scope_id)
        if facts is not None and facts.client_id not in clients:
            clients.append(facts.client_id)
    return clients


@dataclass(frozen=True)
class PortalVersion:
    version_no: int
    is_draft: bool
    page_count: int
    page_comments: bool
    published_at: datetime
    seen_hash: str
    withdrawn_on: date | None
    allowed_actions: tuple[DeliverableAction, ...]


@dataclass(frozen=True)
class PortalDeliverable:
    id: UUID
    kind: str
    title: str
    status: str
    restricted_use: bool
    legend_kind: str | None
    versions: tuple[PortalVersion, ...]


_DELIVERABLE = text(
    "SELECT id, kind, title, restricted_use, legend_kind FROM deliverables WHERE id = :id"
)
_VERSIONS = text(
    """
    SELECT v.version_no, v.is_draft, v.page_count, v.page_comments, v.render_hash,
           v.approval_kind, v.approval_item_id,
           (SELECT max(e.created_at) FROM deliverable_events e
             WHERE e.deliverable_version_id = v.id AND e.kind = 'published') AS published_at,
           (SELECT max(e.created_at) FROM deliverable_events e
             WHERE e.deliverable_version_id = v.id AND e.kind = 'withdrawn') AS withdrawn_at
      FROM deliverable_versions v
     WHERE v.deliverable_id = :id
     ORDER BY v.version_no
    """
)


async def portal_deliverable(ctx: AuthContext, deliverable_id: UUID) -> PortalDeliverable:
    """The deliverable with the versions the person may read; 404 when they may read none."""
    async with tenant_session(ctx.tenant) as session:
        head = (await session.execute(_DELIVERABLE, {"id": deliverable_id})).first()
        rows = (await session.execute(_VERSIONS, {"id": deliverable_id})).all()
    if head is None:
        raise NotFound("deliverable")
    published = [r for r in rows if r.published_at is not None]
    newest = published[-1].version_no if published else None
    versions: list[PortalVersion] = []
    approved = False
    for r in published:
        withdrawn = r.withdrawn_at is not None
        if not withdrawn:
            try:
                await reader_version(ctx, deliverable_id, int(r.version_no))
            except NotFound:
                continue
        seen = str(r.render_hash)
        actions: list[DeliverableAction] = [] if withdrawn else ["download"]
        if r.approval_kind is not None and r.approval_item_id is not None:
            item = await client_approval_provider(str(r.approval_kind)).item(
                ctx.tenant, r.approval_item_id
            )
            if item is not None:
                seen = item.seen_hash
                approved = approved or item.state == "approved"
                if (
                    not withdrawn
                    and r.version_no == newest
                    and item.sent_to_client
                    and item.state in _WAITING
                ):
                    actions.append("approve")
        if r.page_comments and not withdrawn:
            actions.append("comment")
        versions.append(
            PortalVersion(
                version_no=int(r.version_no),
                is_draft=bool(r.is_draft),
                page_count=int(r.page_count),
                page_comments=bool(r.page_comments),
                published_at=r.published_at,
                seen_hash=seen,
                withdrawn_on=None if r.withdrawn_at is None else r.withdrawn_at.date(),
                allowed_actions=tuple(actions),
            )
        )
    readable = [v for v in versions if v.withdrawn_on is None]
    if not readable:
        raise NotFound("deliverable")
    latest = readable[-1]
    status = (
        "approved_by_you"
        if approved and latest.is_draft
        else ("for_your_review" if latest.is_draft else "final")
    )
    return PortalDeliverable(
        id=deliverable_id,
        kind=str(head.kind),
        title=str(head.title),
        status=status,
        restricted_use=bool(head.restricted_use),
        legend_kind=None if head.legend_kind is None else str(head.legend_kind),
        versions=tuple(versions),
    )


@dataclass(frozen=True)
class ApprovalTarget:
    """The C18 item a deliverable version's approval decides (its kind and id)."""

    kind: str
    item_id: UUID


_APPROVAL = text(
    "SELECT v.approval_kind, v.approval_item_id, "
    "(SELECT max(x.version_no) FROM deliverable_versions x "
    "  WHERE x.deliverable_id = v.deliverable_id) AS newest "
    "FROM deliverable_versions v WHERE v.deliverable_id = :id AND v.version_no = :no"
)


async def approval_target(
    ctx: AuthContext, deliverable_id: UUID, version_no: int
) -> ApprovalTarget | None:
    """For the approve route: the version must be readable and the newest; then its C18 item, or
    None when the version carries no approval (the route answers 409)."""
    await reader_version(ctx, deliverable_id, version_no)
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_APPROVAL, {"id": deliverable_id, "no": version_no})).first()
    if row is None or row.approval_kind is None or row.approval_item_id is None:
        return None
    if int(row.newest) != version_no:
        return None
    return ApprovalTarget(str(row.approval_kind), row.approval_item_id)
