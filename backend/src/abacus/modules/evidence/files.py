"""The Files read model (N-01-T19; N-01 §3.7, §4.3; ADR-158, ADR-024; DEC-33, DEC-43; DEC-1051).

FIL-01 is read-only in N-01 (DV-10). What it reads:

- **Tree:** client > Permanent file (client-scoped items) · years (the work items' seasons) >
  work items > the five folder kinds, with item counts. Only rows the viewer may see count:
  engagement-scoped items through `visible(evidence.read_metadata)` on their engagement,
  client-scoped ones through `visible_scope(..., "client")` (DEC-33); walled clients count
  nowhere (DEC-43). Work items come from the engagements' index under the same `visible()`.
- **Folder:** one row per document (its newest version that is not a virtual split), plus each
  superseded version kept and struck ("Superseded · Replaced by …"), with its virtual children.
- **Drawer:** the document card, virtual children and their total (the tie to a TB account needs
  a C9 mapping, which no work item has yet: `ties` stays None, DV-13), what it supports (the
  request items it fulfils), its versions, the retention readout and any legal hold, the P and R
  sign-off slots (read only; no document sign-off exists in N-01) and client access (`off` until
  the FIL-01 writes slice). Content fields (page count, thumbnail) need `evidence.read`; a
  metadata-only viewer (firm admin, practice leader, security admin) gets nulls (ADR-024, DV-11).
- **Access log:** audit events on the item and its versions, in the actor grammar, newest first.

A walled, hidden or other firm's item answers 404 everywhere.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_, select

from abacus.kernel._statuses import FileDocumentStatus
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.holds import HoldCheckMissing, held_versions
from abacus.kernel.listing import (
    Position,
    clamp_limit,
    decode_cursor,
    envelope,
    query_hash,
)
from abacus.kernel.uow import AuditRow
from abacus.modules.engagements.api import engagement_resource_of, work_item_index
from abacus.modules.evidence.files_shapes import (
    AccessLogRow,
    Channel,
    DrawerOut,
    FileRow,
    FileTreeOut,
    FileVersionOut,
    FolderItemsOut,
    FolderKind,
    LinkOut,
    NodeKind,
    RetentionOut,
    SignOffSlotOut,
    TieOut,
    TreeNode,
    VirtualChild,
)
from abacus.modules.evidence.models import (
    EvidenceItem,
    EvidenceVersion,
    EvidenceWithdrawal,
    ReviewDecision,
    UploadExtraction,
)
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    names_of,
    target_events,
    visible,
    visible_scope,
)
from abacus.modules.requests.api import fulfilled_items

READ_METADATA: Final = "evidence.read_metadata"
READ_CONTENT: Final = "evidence.read"
READ_ACCESS_LOG: Final = "evidence.read_access_log"
FOLDER_KINDS: Final[tuple[FolderKind, ...]] = (
    "source_documents",
    "workpapers",
    "correspondence",
    "deliverables",
    "signed_authorizations",
)
_RESOURCE: Final = "files.folder"
_LOG_CAP: Final = 200  # per target, before paging (an item has a handful of versions)
# Actions as the access log says them ("Olivia Brandt revealed Borrower TIN"); others are
# shown by their code, so nothing is hidden.
_VERBS: Final[dict[str, str]] = {
    "evidence.version_created": "uploaded",
    "evidence.version_viewed": "viewed",
    "evidence.downloaded": "downloaded",
    "evidence.accepted": "accepted",
    "evidence.rejected": "rejected",
    "evidence.withdrawn": "withdrew",
    "pii.revealed": "revealed",
    "evidence.filed": "filed",
}


# --- Visibility ----------------------------------------------------------------------------------


def _visible_item(ctx: AuthContext, action: str) -> ColumnElement[bool]:
    """An item the viewer may `action`: by its engagement, or by its client when client-scoped
    (DEC-33). Building it records the route's check."""
    return or_(
        and_(EvidenceItem.scope == "engagement", visible(ctx, action, EvidenceItem.engagement_id)),
        and_(
            EvidenceItem.scope == "client",
            visible_scope(ctx, action, "client", EvidenceItem.client_id),
        ),
    )


def _shown_version() -> ColumnElement[bool]:
    """Not withdrawn by the client (P-06-T19)."""
    # Named first: mutmut 3.8 drops the parentheses of a `return (~…)` it mutates (Q-03-T147).
    withdrawn = (
        select(EvidenceWithdrawal.evidence_version_id)
        .where(EvidenceWithdrawal.evidence_version_id == EvidenceVersion.id)
        .exists()
    )
    return ~withdrawn


# --- Tree ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _WorkItem:
    id: UUID
    engagement_id: UUID
    name: str
    client_id: UUID
    client_name: str
    season: str


async def _work_items(ctx: AuthContext, client_id: UUID | None) -> list[_WorkItem]:
    wi = work_item_index()
    stmt = select(
        wi.c.id, wi.c.engagement_id, wi.c.name, wi.c.client_id, wi.c.client_name, wi.c.season
    ).where(visible(ctx, READ_METADATA, wi.c.engagement_id))
    if client_id is not None:
        stmt = stmt.where(wi.c.client_id == client_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(stmt)).all()
    return [
        _WorkItem(
            r.id,
            r.engagement_id,
            r.name,
            r.client_id,
            r.client_name or "",
            str(r.season) if r.season is not None else "",
        )
        for r in rows
    ]


async def _counts(
    ctx: AuthContext, client_ids: Sequence[UUID]
) -> dict[tuple[UUID, UUID | None, str, str], int]:
    """(client, work item, scope, folder kind) -> visible items with at least one shown version."""
    if not client_ids:
        return {}
    stmt = (
        select(
            EvidenceItem.client_id,
            EvidenceItem.work_item_id,
            EvidenceItem.scope,
            EvidenceItem.folder_kind,
            func.count(func.distinct(EvidenceItem.id)),
        )
        .join(EvidenceVersion, EvidenceVersion.evidence_item_id == EvidenceItem.id)
        .where(
            EvidenceItem.client_id.in_(list(client_ids)),
            EvidenceVersion.parent_version_id.is_(None),
            _shown_version(),
            _visible_item(ctx, READ_METADATA),
        )
        .group_by(
            EvidenceItem.client_id,
            EvidenceItem.work_item_id,
            EvidenceItem.scope,
            EvidenceItem.folder_kind,
        )
    )
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(stmt)).all()
    return {(r[0], r[1], r[2], r[3]): int(r[4]) for r in rows}


def _node(
    ref: str,
    kind: str,
    label: str,
    count: int,
    children: list[TreeNode],
    *,
    folder_kind: FolderKind | None = None,
    expanded: bool = True,
) -> TreeNode:
    return TreeNode(
        ref=ref,
        kind=cast(NodeKind, kind),
        label=label,
        folder_kind=folder_kind,
        count=count,
        has_children=bool(children),
        on_hold=False,
        locked=False,
        children=children if expanded else [],
    )


async def tree(
    ctx: AuthContext, client_id: UUID | None, expand: Sequence[str] = ()
) -> FileTreeOut:
    """`GET /v1/files/tree`. With a client, its whole tree; without, each visible client
    collapsed unless its ref is in `expand`."""
    items = await _work_items(ctx, client_id)
    clients: dict[UUID, str] = {w.client_id: w.client_name for w in items}
    counts = await _counts(ctx, list(clients))
    for c, _w, _s, _k in counts:
        clients.setdefault(c, "")
    out: list[TreeNode] = []
    for cid, cname in sorted(clients.items(), key=lambda kv: (kv[1], str(kv[0]))):
        permanent = sum(n for (c, _w, s, _k), n in counts.items() if c == cid and s == "client")
        children = [
            _node(
                f"permanent:{cid}",
                "permanent_file",
                "Permanent file",
                permanent,
                [
                    _node(
                        f"permanent:{cid}:{k}",
                        "folder",
                        k,
                        counts.get((cid, None, "client", k), 0),
                        [],
                        folder_kind=k,
                    )
                    for k in FOLDER_KINDS
                    if counts.get((cid, None, "client", k), 0)
                ],
            )
        ]
        seasons = sorted({w.season for w in items if w.client_id == cid}, reverse=True)
        for season in seasons:
            year_children: list[TreeNode] = []
            for w in sorted(
                (w for w in items if w.client_id == cid and w.season == season),
                key=lambda w: (w.name, str(w.id)),
            ):
                folders = [
                    _node(
                        f"folder:{w.id}:{k}",
                        "folder",
                        k,
                        counts.get((cid, w.id, "engagement", k), 0),
                        [],
                        folder_kind=k,
                    )
                    for k in FOLDER_KINDS
                ]
                year_children.append(
                    _node(
                        f"work_item:{w.id}",
                        "work_item",
                        w.name,
                        sum(f.count for f in folders),
                        folders,
                    )
                )
            children.append(
                _node(
                    f"year:{cid}:{season}",
                    "year",
                    season or "Other",
                    sum(n.count for n in year_children),
                    year_children,
                )
            )
        # The client's count is what its tree shows (the permanent file and its years): an item
        # on no work item sits in no folder and is not counted (review).
        total = sum(n.count for n in children)
        show = client_id is not None or f"client:{cid}" in expand
        out.append(_node(f"client:{cid}", "client", cname, total, children, expanded=show))
    return FileTreeOut(nodes=out)


# --- Folder --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Folder:
    client_id: UUID | None
    work_item_id: UUID | None
    folder_kind: FolderKind | None


def parse_folder_ref(ref: str) -> _Folder:
    """`folder:<work item>:<kind>`, `permanent:<client>` or `permanent:<client>:<kind>`; anything
    else is 404 (a ref names nothing the viewer can't already see)."""
    parts = ref.split(":")
    try:
        if parts[0] == "folder" and len(parts) == 3 and parts[2] in FOLDER_KINDS:
            return _Folder(None, UUID(parts[1]), parts[2])
        if parts[0] == "permanent" and len(parts) == 2:
            return _Folder(UUID(parts[1]), None, None)
        if parts[0] == "permanent" and len(parts) == 3 and parts[2] in FOLDER_KINDS:
            return _Folder(UUID(parts[1]), None, parts[2])
    except ValueError:
        pass
    raise NotFound("folder")


@dataclass(frozen=True)
class _Row:
    item: EvidenceItem
    version: EvidenceVersion


def _name(v: EvidenceVersion, item: EvidenceItem) -> str:
    return v.display_name or item.title


async def _folder_rows(ctx: AuthContext, folder: _Folder, q: str | None) -> list[_Row]:
    stmt = (
        select(EvidenceItem, EvidenceVersion)
        .join(EvidenceVersion, EvidenceVersion.evidence_item_id == EvidenceItem.id)
        .where(_visible_item(ctx, READ_METADATA), _shown_version())
    )
    if folder.work_item_id is not None:
        stmt = stmt.where(
            EvidenceItem.work_item_id == folder.work_item_id, EvidenceItem.scope == "engagement"
        )
    else:
        stmt = stmt.where(
            EvidenceItem.client_id == folder.client_id, EvidenceItem.scope == "client"
        )
    if folder.folder_kind is not None:
        stmt = stmt.where(EvidenceItem.folder_kind == folder.folder_kind)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(stmt)).all()
    out = [_Row(i, v) for i, v in rows]
    if q:
        needle = q.casefold()
        out = [r for r in out if needle in _name(r.version, r.item).casefold()]
    return out


async def _statuses(
    ctx: AuthContext, versions: Sequence[EvidenceVersion], superseded: set[UUID]
) -> dict[UUID, FileDocumentStatus]:
    ids = [v.id for v in versions]
    if not ids:
        return {}
    async with tenant_session(ctx.tenant) as session:
        extracted = set(
            (
                await session.execute(
                    select(UploadExtraction.evidence_version_id).where(
                        UploadExtraction.evidence_version_id.in_(ids)
                    )
                )
            ).scalars()
        )
        decided = (
            await session.execute(
                select(ReviewDecision.evidence_version_id, ReviewDecision.decision)
                .where(ReviewDecision.evidence_version_id.in_(ids))
                .order_by(ReviewDecision.created_at)
            )
        ).all()
    latest: dict[UUID, str] = {}
    for vid, decision in decided:
        latest[vid] = decision
    try:
        held = await held_versions(ctx.tenant, ids)
    except HoldCheckMissing:
        held = frozenset[UUID]()
    out: dict[UUID, FileDocumentStatus] = {}
    for v in versions:
        if v.id in superseded:
            out[v.id] = FileDocumentStatus.SUPERSEDED
        elif v.id in held:
            out[v.id] = FileDocumentStatus.ON_HOLD
        elif latest.get(v.id) == "accept":
            out[v.id] = FileDocumentStatus.ACCEPTED
        elif v.id not in extracted and v.storage_mode != "external":
            out[v.id] = FileDocumentStatus.PROCESSING
        else:
            out[v.id] = FileDocumentStatus.NEEDS_REVIEW
    return out


def _virtual(children: Sequence[EvidenceVersion]) -> list[VirtualChild]:
    out: list[VirtualChild] = []
    for c in sorted(children, key=lambda c: (c.page_range.lower or 0) if c.page_range else 0):
        rng = c.page_range
        first = int(rng.lower) if rng is not None and rng.lower is not None else 1
        upper = int(rng.upper) if rng is not None and rng.upper is not None else first
        last = upper if rng is not None and rng.upper_inc else max(first, upper - 1)
        out.append(
            VirtualChild(
                id=c.id,
                label=c.virtual_label or "",
                first_page=first,
                last_page=last,
                amount=c.virtual_amount,
            )
        )
    return out


def _documents(
    rows: Sequence[_Row],
) -> tuple[list[_Row], dict[UUID, list[EvidenceVersion]], dict[UUID, EvidenceVersion]]:
    """The rows a folder lists (each item's newest real version, and every version a later one
    superseded), the virtual children per version, and each superseded version's replacement."""
    real = [r for r in rows if r.version.parent_version_id is None]
    children: dict[UUID, list[EvidenceVersion]] = {}
    for r in rows:
        if r.version.parent_version_id is not None:
            children.setdefault(r.version.parent_version_id, []).append(r.version)
    replaced_by: dict[UUID, EvidenceVersion] = {
        r.version.supersedes_version_id: r.version
        for r in real
        if r.version.supersedes_version_id is not None
    }
    newest: dict[UUID, _Row] = {}
    for r in real:
        known = newest.get(r.item.id)
        if known is None or r.version.version_no > known.version.version_no:
            newest[r.item.id] = r
    listed = list(newest.values()) + [
        r for r in real if r.version.id in replaced_by and newest[r.item.id] is not r
    ]
    return listed, children, replaced_by


async def folder_items(
    ctx: AuthContext,
    folder_ref: str,
    *,
    q: str | None,
    cursor: str | None,
    limit: int | None,
) -> FolderItemsOut:
    """`GET /v1/files/folders/{folder_ref}/items`: newest first, keyset-paged. A folder is
    bounded (one work item's documents), so it is read whole and paged in order."""
    folder = parse_folder_ref(folder_ref)
    rows = await _folder_rows(ctx, folder, q)
    listed, children, replaced_by = _documents(rows)
    statuses = await _statuses(ctx, [r.version for r in listed], set(replaced_by))
    # Security review (S15 end review): a client-scoped document can fulfil requests on any of
    # the client's engagements, some the viewer may not see; only an engagement-scoped one names
    # what it supports (its own engagement, which the viewer was just authorised on).
    supports = await _supports(ctx, [r.version.id for r in listed if r.item.scope == "engagement"])
    listed.sort(key=lambda r: (r.version.created_at, str(r.version.id)), reverse=True)
    size = clamp_limit(limit)
    query = query_hash(folder=folder_ref, q=q or "")
    if cursor:
        after = decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=_RESOURCE, query=query)
        listed = [
            r
            for r in listed
            if (r.version.created_at.isoformat(), str(r.version.id)) < (str(after.key), after.id)
        ]
    page = listed[:size]
    more = len(listed) > size
    items = [
        FileRow(
            evidence_item_id=r.item.id,
            version_id=r.version.id,
            display_name=_name(r.version, r.item),
            classification_label=None,
            channel=cast(Channel | None, r.version.channel),
            status=statuses[r.version.id],
            superseded_by_name=(
                _name(replaced_by[r.version.id], r.item) if r.version.id in replaced_by else None
            ),
            superseded_on=(
                replaced_by[r.version.id].created_at.date()
                if r.version.id in replaced_by
                else None
            ),
            supports=supports.get(r.version.id),
            received_at=r.version.created_at,
            virtual_children=_virtual(children.get(r.version.id, [])),
        )
        for r in page
    ]
    position = (
        Position(key=page[-1].version.created_at.isoformat(), id=str(page[-1].version.id))
        if more and page
        else None
    )
    shell = envelope(
        items,
        next_position=position,
        tenant_id=ctx.tenant_id,
        resource=_RESOURCE,
        query=query,
        total=(len(listed), False),
    )
    documents = len({r.item.id for r in rows if r.version.parent_version_id is None})
    virtual = sum(len(v) for v in children.values())
    return FolderItemsOut(**shell.model_dump(), documents=documents, virtual=virtual)


async def _supports(ctx: AuthContext, version_ids: Sequence[UUID]) -> dict[UUID, str]:
    """The first request item each version fulfils ("Supports"), for the list column."""
    out: dict[UUID, str] = {}
    for vid in version_ids:
        found = await fulfilled_items(ctx.tenant, vid)
        if found:
            out[vid] = found[0].description
    return out


# --- Drawer --------------------------------------------------------------------------------------


async def _readable_item(ctx: AuthContext, item_id: UUID, action: str) -> EvidenceItem:
    async with tenant_session(ctx.tenant) as session:
        item = (
            await session.execute(
                select(EvidenceItem).where(EvidenceItem.id == item_id, _visible_item(ctx, action))
            )
        ).scalar_one_or_none()
    if item is None:
        raise NotFound("evidence_item")
    return item


async def _can_read_content(ctx: AuthContext, item_id: UUID) -> bool:
    try:
        await _readable_item(ctx, item_id, READ_CONTENT)
    except NotFound:
        return False
    return True


async def drawer(ctx: AuthContext, item_id: UUID) -> DrawerOut:
    """`GET /v1/evidence-items/{id}/drawer` (O2)."""
    item = await _readable_item(ctx, item_id, READ_METADATA)
    content = await _can_read_content(ctx, item_id)
    async with tenant_session(ctx.tenant) as session:
        versions = list(
            (
                await session.execute(
                    select(EvidenceVersion)
                    .where(EvidenceVersion.evidence_item_id == item.id, _shown_version())
                    .order_by(EvidenceVersion.version_no.desc())
                )
            ).scalars()
        )
        real = [v for v in versions if v.parent_version_id is None]
        if not real:
            raise NotFound("evidence_item")
        head = real[0]
        pages = (
            await session.execute(
                select(UploadExtraction.page_count).where(
                    UploadExtraction.evidence_version_id == head.id
                )
            )
        ).scalar_one_or_none()
    superseded = {v.supersedes_version_id for v in real if v.supersedes_version_id is not None}
    status = (await _statuses(ctx, [head], superseded))[head.id]
    children = [v for v in versions if v.parent_version_id == head.id]
    virtual = _virtual(children)
    amounts = [c.amount for c in virtual if c.amount is not None]
    tie = (
        TieOut(total=sum(amounts, Decimal(0)), account_number=None, ties=None) if amounts else None
    )
    linked = (
        [
            LinkOut(kind="request", label=r.description, route=f"/requests/items/{r.id}")
            for r in await fulfilled_items(ctx.tenant, head.id)
        ]
        if item.scope == "engagement"
        else []  # as `supports`: never another engagement's request (security review)
    )
    try:
        held = await held_versions(ctx.tenant, [head.id])
    except HoldCheckMissing:
        held = frozenset[UUID]()
    return DrawerOut(
        evidence_item_id=item.id,
        display_name=_name(head, item),
        status=status,
        folder_kind=cast(FolderKind, item.folder_kind),
        scope="client" if item.scope == "client" else "engagement",
        page_count=pages if content else None,
        size_bytes=head.size_bytes,
        fingerprint=head.fingerprint,
        masked_tin=None,
        thumbnail_ref=None,
        virtual_children=virtual,
        tie=tie,
        linked_to=linked,
        versions=[
            FileVersionOut(
                id=v.id,
                version_no=v.version_no,
                file_name=_name(v, item),
                channel=cast(Channel | None, v.channel),
                created_at=v.created_at,
                superseded=v.id in superseded,
            )
            for v in real
        ],
        retention=RetentionOut(
            policy_label=None,
            eligible_on=None,
            hold_label="On hold" if head.id in held else None,
            hold_placed_by=None,
            hold_placed_on=None,
        ),
        sign_off_slots=[
            SignOffSlotOut(level="preparer", initials=None, signed_at=None),
            SignOffSlotOut(level="reviewer", initials=None, signed_at=None),
        ],
        client_access="off",
        allowed_actions=[],
    )


# --- Access log ----------------------------------------------------------------------------------


def _actor(row: AuditRow, names: Mapping[UUID, str]) -> str:
    if row.actor_kind == "agent":
        return "Accrued Agent"
    if row.actor_kind == "system":
        return "Accrued"
    try:
        return names.get(UUID(row.actor_id), "Former member")
    except ValueError:
        return "Former member"


async def access_log(
    ctx: AuthContext, item_id: UUID, *, cursor: str | None, limit: int | None
) -> tuple[list[AccessLogRow], str | None]:
    """`GET /v1/evidence-items/{id}/access-log`: audit events on the item and its versions,
    newest first. The cursor is the last row's audit sequence."""
    # `visible()` filters reads only, and the access log is not a read verb: the item is found as
    # metadata (walls and other firms 404), then the log's own action is authorised where the
    # item lives (its engagement; the firm for a client-scoped item, where only firm-level
    # roles such as security admin hold it).
    item = await _readable_item(ctx, item_id, READ_METADATA)
    resource = (
        await engagement_resource_of(ctx.tenant, item.engagement_id)
        if item.scope == "engagement"
        else Resource.firm(ctx.tenant_id)
    )
    await authorise(ctx, READ_ACCESS_LOG, resource)
    async with tenant_session(ctx.tenant) as session:
        versions = {
            v.id: v.version_no
            for v in (
                await session.execute(
                    select(EvidenceVersion).where(EvidenceVersion.evidence_item_id == item.id)
                )
            ).scalars()
        }
    before = int(cursor) if cursor and cursor.isdigit() else None
    rows: list[tuple[AuditRow, int | None]] = [
        (r, None)
        for r in await target_events(ctx.tenant, "evidence_item", item.id, before, _LOG_CAP)
    ]
    for vid, no in versions.items():
        rows += [
            (r, no)
            for r in await target_events(ctx.tenant, "evidence_version", vid, before, _LOG_CAP)
        ]
    rows.sort(key=lambda p: p[0].seq, reverse=True)
    size = clamp_limit(limit)
    page = rows[:size]
    names = await names_of(
        [UUID(r.actor_id) for r, _ in page if r.actor_kind == "human" and _is_uuid(r.actor_id)]
    )
    out = [
        AccessLogRow(
            occurred_at=r.occurred_at.astimezone(UTC) if r.occurred_at.tzinfo else r.occurred_at,
            actor_display=_actor(r, names),
            verb=_VERBS.get(r.action, r.action),
            version_no=no,
        )
        for r, no in page
    ]
    next_cursor = str(page[-1][0].seq) if len(rows) > size and page else None
    return out, next_cursor


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


__all__ = [
    "FOLDER_KINDS",
    "access_log",
    "drawer",
    "folder_items",
    "parse_folder_ref",
    "tree",
]
