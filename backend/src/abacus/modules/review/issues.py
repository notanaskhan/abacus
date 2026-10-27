"""Issues service, part 1 (P-04-T30; ADR-160; SPEC-360; DEC-714): create, update and assign, list
on the envelope, get; the blocks facet the sign-off and final-approval checks read; `source_ref`
dedupe for engine diagnostics; the `issue_assigned` notification.

- An issue sits on a reviewable record (`record_type`, `record_id`, resolved through the review
  slots, so walls and the engagement's matrix apply) and is authorised on that record's engagement.
- Its title, internal note and client wording are sealed, bound to the issue's own id; each read
  of them writes an access event (`record_text_reads`). Codes and ids are all the audit carries.
- Kinds, priorities and statuses are the registry's (`IssueKind`, `issue_severity`, `issue`);
  this part writes `open` only. Resolve, verify, reopen, mark not applicable, send to client and
  fix instructions are part 2 (P-04-T31) and keep their 501.
- Engine diagnostics (`record_engine_issue`) are deduplicated on `(work item, source_ref)`: the
  same diagnostic twice is one issue.
- `open_blocking(tenant, record, block)` is what eligibility reads: one failing check, however
  many issues block (SHL-12; "eleven open Ridgeline issues ... one failing check").
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import AuthContext, Resource, allowed_actions, authorise, names_of
from abacus.modules.review.sealing import open_text, record_text_reads, seal_text
from abacus.modules.review.slots import reviewable_facts

SUBJECT: Final = "issue"
OPEN_STATUSES: Final = frozenset({"open", "in_progress", "reopened"})
ROW_ACTIONS: Final = ("issue.update", "issue.resolve", "issue.verify", "issue.reopen")


class IssueChanged(DomainConflict):
    """The issue changed since it was read (`seen_version`)."""

    code = "issue_changed"


class IssueAssigned(DomainEvent):
    """An issue was assigned to a person (identifiers only)."""

    event_type: ClassVar[str] = "issue.assigned"

    issue_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    assignee_user_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class IssueRow:
    id: UUID
    engagement_id: UUID | None
    work_item_id: UUID | None
    record_type: str
    record_id: UUID
    kind: str
    priority: str
    status: str
    instructions_required: bool
    assignee_user_id: UUID | None
    assignee_agent: bool
    blocks: tuple[str, ...]
    link_count: int
    version: int
    created_at: datetime
    title_sealed: bytes
    internal_note_sealed: bytes | None
    client_wording_sealed: bytes | None


@dataclass(frozen=True)
class IssueText:
    title: str
    internal_note: str | None
    client_wording: str | None
    record_label: str


_SELECT_ONE: Final = text(
    "SELECT i.id, i.engagement_id, i.work_item_id, i.record_ref, i.kind, i.priority, i.status, "
    "i.instructions_required, i.assignee_user_id, i.assignee_agent, i.blocks, i.version, "
    "i.created_at, i.title_sealed, i.internal_note_sealed, i.client_wording_sealed, "
    "(SELECT count(*) FROM issue_links l WHERE l.issue_id = i.id) AS link_count "
    "FROM issues i WHERE i.id = :id"
)
_SELECT_LIST: Final = text(
    "SELECT i.id, i.engagement_id, i.work_item_id, i.record_ref, i.kind, i.priority, i.status, "
    "i.instructions_required, i.assignee_user_id, i.assignee_agent, i.blocks, i.version, "
    "i.created_at, i.title_sealed, i.internal_note_sealed, i.client_wording_sealed, "
    "(SELECT count(*) FROM issue_links l WHERE l.issue_id = i.id) AS link_count "
    "FROM issues i WHERE i.engagement_id = :e "
    "AND (CAST(:r AS text) IS NULL OR i.record_ref ->> 'id' = CAST(:r AS text)) "
    "ORDER BY i.created_at, i.id"
)
_UPDATE: Final = text(
    "UPDATE issues SET title_sealed = coalesce(CAST(:title AS bytea), title_sealed), "
    "kind = coalesce(CAST(:kind AS text), kind), "
    "priority = coalesce(CAST(:priority AS text), priority), "
    "assignee_user_id = coalesce(CAST(:assignee AS uuid), assignee_user_id), "
    "assignee_agent = coalesce(CAST(:agent AS boolean), assignee_agent), "
    "version = version + 1 WHERE id = :id AND version = :v RETURNING id"
)


def _row(r: object) -> IssueRow:
    m = cast(dict[str, object], getattr(r, "_mapping", r))
    ref = cast(dict[str, str], m["record_ref"])
    return IssueRow(
        cast(UUID, m["id"]),
        cast(UUID | None, m["engagement_id"]),
        cast(UUID | None, m["work_item_id"]),
        str(ref["type"]),
        UUID(str(ref["id"])),
        str(m["kind"]),
        str(m["priority"]),
        str(m["status"]),
        bool(m["instructions_required"]),
        cast(UUID | None, m["assignee_user_id"]),
        bool(m["assignee_agent"]),
        tuple(cast(list[str], m["blocks"])),
        int(cast(int, m["link_count"])),
        int(cast(int, m["version"])),
        cast(datetime, m["created_at"]),
        cast(bytes, m["title_sealed"]),
        cast(bytes | None, m["internal_note_sealed"]),
        cast(bytes | None, m["client_wording_sealed"]),
    )


async def _record(
    ctx: AuthContext, record_type: str, record_id: UUID
) -> tuple[UUID, Resource, str]:
    facts = await reviewable_facts(ctx.tenant, record_type, record_id)
    resource = await engagement_resource_of(ctx.tenant, facts.engagement_id)
    return facts.engagement_id, resource, facts.label


async def create_issue(
    ctx: AuthContext,
    *,
    record_type: str,
    record_id: UUID,
    kind: str,
    priority: str,
    title: str,
    internal_note: str | None,
    client_wording: str | None,
    client_contact_id: UUID | None,
    assignee_user_id: UUID | None,
    assignee_agent: bool,
    blocks: Sequence[str],
    source_ref: str | None = None,
    work_item_id: UUID | None = None,
) -> UUID:
    engagement_id, resource, _ = await _record(ctx, record_type, record_id)
    await authorise(ctx, "issue.create", resource)
    issue_id = uuid4()
    sealed = {
        "title_sealed": await seal_text(ctx.tenant, title, SUBJECT, issue_id, "title"),
        "internal_note_sealed": (
            await seal_text(ctx.tenant, internal_note, SUBJECT, issue_id, "internal_note")
            if internal_note
            else None
        ),
        "client_wording_sealed": (
            await seal_text(ctx.tenant, client_wording, SUBJECT, issue_id, "client_wording")
            if client_wording
            else None
        ),
    }
    async with uow(ctx.tenant) as tx:
        if source_ref is not None:
            existing = await tx.session.scalar(
                text(
                    "SELECT id FROM issues WHERE work_item_id IS NOT DISTINCT FROM :w "
                    "AND source_ref = :s"
                ),
                {"w": work_item_id, "s": source_ref},
            )
            if isinstance(existing, UUID):
                return existing  # an engine diagnostic seen before is the same issue
        await tx.session.execute(
            text(
                "INSERT INTO issues (id, tenant_id, engagement_id, work_item_id, record_ref, "
                "kind, priority, title_sealed, assignee_user_id, assignee_agent, "
                "client_contact_id, client_wording_sealed, internal_note_sealed, blocks, "
                "source_ref) VALUES (:id, :t, :e, :w, CAST(:ref AS jsonb), :k, :p, :title, :a, "
                ":agent, :contact, :wording, :note, CAST(:blocks AS text[]), :src)"
            ),
            {
                "id": issue_id,
                "t": ctx.tenant_id,
                "e": engagement_id,
                "w": work_item_id,
                "ref": json.dumps({"type": record_type, "id": str(record_id)}),
                "k": kind,
                "p": priority,
                "title": sealed["title_sealed"],
                "a": assignee_user_id,
                "agent": assignee_agent,
                "contact": client_contact_id,
                "wording": sealed["client_wording_sealed"],
                "note": sealed["internal_note_sealed"],
                "blocks": "{" + ",".join(sorted(set(blocks))) + "}",
                "src": source_ref,
            },
        )
        await tx.session.execute(
            text(
                "INSERT INTO issue_events (tenant_id, issue_id, event) VALUES (:t, :i, 'created')"
            ),
            {"t": ctx.tenant_id, "i": issue_id},
        )
        tx.record(
            "issue.created",
            target=Target(SUBJECT, issue_id),
            after=Ref(kind=kind, priority=priority, record=record_id),
            scope=Scope(engagement_id=engagement_id),
        )
        if assignee_user_id is not None:
            await _assigned(tx, ctx, issue_id, engagement_id, assignee_user_id)
    return issue_id


async def _assigned(
    unit: UnitOfWork, ctx: AuthContext, issue_id: UUID, engagement_id: UUID, assignee: UUID
) -> None:
    await unit.session.execute(
        text("INSERT INTO issue_events (tenant_id, issue_id, event) VALUES (:t, :i, 'assigned')"),
        {"t": ctx.tenant_id, "i": issue_id},
    )
    unit.record(
        "issue.assigned",
        target=Target(SUBJECT, issue_id),
        after=Ref(assignee=assignee),
        scope=Scope(engagement_id=engagement_id),
    )
    unit.emit(
        IssueAssigned(issue_id=issue_id, engagement_id=engagement_id, assignee_user_id=assignee)
    )


async def _one(tenant: TenantContext, issue_id: UUID) -> IssueRow:
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                _SELECT_ONE,
                {"id": issue_id},
            )
        ).first()
    if found is None:
        raise NotFound(SUBJECT)
    return _row(found)


async def update_issue(
    ctx: AuthContext,
    issue_id: UUID,
    *,
    seen_version: int,
    title: str | None,
    kind: str | None,
    priority: str | None,
    assignee_user_id: UUID | None,
    assignee_agent: bool | None,
) -> None:
    current = await _one(ctx.tenant, issue_id)
    _, resource, _ = await _record(ctx, current.record_type, current.record_id)
    await authorise(ctx, "issue.update", resource)
    sealed = (
        await seal_text(ctx.tenant, title, SUBJECT, issue_id, "title")
        if title is not None
        else None
    )
    reassigned = assignee_user_id is not None and assignee_user_id != current.assignee_user_id
    fields = sum(v is not None for v in (title, kind, priority, assignee_agent)) + int(reassigned)
    async with uow(ctx.tenant) as tx:
        changed = await tx.session.execute(
            _UPDATE,
            {
                "title": sealed,
                "kind": kind,
                "priority": priority,
                "assignee": assignee_user_id if reassigned else None,
                "agent": assignee_agent,
                "id": issue_id,
                "v": seen_version,
            },
        )
        if changed.first() is None:
            raise IssueChanged(facts={"version": current.version})
        tx.record(
            "issue.updated",
            target=Target(SUBJECT, issue_id),
            after=Ref(fields=fields),
            scope=Scope(engagement_id=current.engagement_id),
        )
        if reassigned and current.engagement_id is not None:
            await _assigned(tx, ctx, issue_id, current.engagement_id, cast(UUID, assignee_user_id))


@dataclass(frozen=True)
class IssuePage:
    rows: list[IssueRow]
    counts: dict[str, int]
    by_kind: dict[str, int]
    names: dict[UUID, str]
    allowed: dict[UUID, list[str]]


async def list_issues(
    ctx: AuthContext,
    *,
    record_type: str | None,
    record_id: UUID | None,
    engagement_id: UUID | None,
    status: str | None,
    kind: str | None,
    limit: int,
) -> IssuePage:
    if record_type is not None and record_id is not None:
        engagement, resource, _ = await _record(ctx, record_type, record_id)
    elif engagement_id is not None:
        engagement, resource = (
            engagement_id,
            await engagement_resource_of(ctx.tenant, engagement_id),
        )
    else:
        raise NotFound(SUBJECT)
    await authorise(ctx, "issue.read", resource)
    async with tenant_session(ctx.tenant) as session:
        rows = [
            _row(r)
            for r in await session.execute(
                _SELECT_LIST, {"e": engagement, "r": str(record_id) if record_id else None}
            )
        ]
    counts = dict(Counter(r.status for r in rows))
    by_kind = dict(Counter(r.kind for r in rows))
    shown = [
        r
        for r in rows
        if (status is None or r.status == status) and (kind is None or r.kind == kind)
    ]
    names = await names_of([r.assignee_user_id for r in shown if r.assignee_user_id is not None])
    found = await allowed_actions(ctx, resource, ROW_ACTIONS)
    allowed = {r.id: [a for a in ROW_ACTIONS if a in found] for r in shown}
    return IssuePage(shown[:limit], counts, by_kind, names, allowed)


async def read_issue(ctx: AuthContext, issue_id: UUID) -> tuple[IssueRow, IssueText, list[str]]:
    row = await _one(ctx.tenant, issue_id)
    _, resource, label = await _record(ctx, row.record_type, row.record_id)
    await authorise(ctx, "issue.read", resource)
    if row.engagement_id is not None:
        await record_text_reads(
            ctx.tenant,
            SUBJECT,
            [issue_id],
            engagement_id=row.engagement_id,
            client_id=resource.client_id,
            work_item_id=row.work_item_id,
        )
    texts = IssueText(
        await open_text(ctx.tenant, row.title_sealed, SUBJECT, issue_id, "title"),
        await open_text(ctx.tenant, row.internal_note_sealed, SUBJECT, issue_id, "internal_note")
        if row.internal_note_sealed
        else None,
        await open_text(ctx.tenant, row.client_wording_sealed, SUBJECT, issue_id, "client_wording")
        if row.client_wording_sealed
        else None,
        label,
    )
    found = await allowed_actions(ctx, resource, ROW_ACTIONS)
    return row, texts, [a for a in ROW_ACTIONS if a in found]


async def open_blocking(tenant: TenantContext, record_id: UUID, block: str) -> list[UUID]:
    """Open issues on a record that block `block` (`sign_off`, `final_approval`, ...)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT id FROM issues WHERE record_ref ->> 'id' = :r AND :b = ANY(blocks) "
                "AND status = ANY(CAST(:open AS text[])) ORDER BY created_at, id"
            ),
            {"r": str(record_id), "b": block, "open": "{" + ",".join(sorted(OPEN_STATUSES)) + "}"},
        )
        return [cast(UUID, r[0]) for r in rows]


async def record_engine_issue(
    ctx: AuthContext,
    *,
    record_type: str,
    record_id: UUID,
    work_item_id: UUID,
    source_ref: str,
    title: str,
    blocks: Sequence[str] = ("final_approval",),
) -> UUID:
    """An engine diagnostic as an issue, once per `(work item, source_ref)`."""
    return await create_issue(
        ctx,
        record_type=record_type,
        record_id=record_id,
        kind="engine_diagnostic",
        priority="high",
        title=title,
        internal_note=None,
        client_wording=None,
        client_contact_id=None,
        assignee_user_id=None,
        assignee_agent=False,
        blocks=blocks,
        source_ref=source_ref,
        work_item_id=work_item_id,
    )
