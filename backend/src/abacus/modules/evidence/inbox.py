"""The engagement inbox (SPEC-023 AC-2 to AC-5; TASK-039).

Files dropped at the engagement level are stored once (the SPEC-020 checks) and wait until a
person assigns each to a request item, which makes it evidence exactly as a per-item upload does
(`uploads.attach`), or discards it. Suggestions are computed on read (D2), from the items the
reader can see, so a contributor only ever sees their assigned items.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import gate_client_data, get_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import InboxFileAdded
from abacus.modules.evidence.matching import Suggestion, suggest
from abacus.modules.evidence.models import InboxFile
from abacus.modules.evidence.repository import (
    decide_inbox_file,
    insert_inbox_file,
    lock_inbox_file,
    waiting_inbox,
    waiting_with_fingerprint,
)
from abacus.modules.evidence.uploads import (
    ON_BEHALF_SOURCE,
    SOURCE,
    DuplicateUpload,
    attach,
    checked,
    clean_name,
    clean_note,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    authorise,
    engagement_role_of,
    names_of,
)
from abacus.modules.requests.api import RequestItemView, request_items_for

_STAFF: Final = frozenset({"engagement_partner", "manager", "senior", "staff", "reviewer"})


class InboxFileGone(DomainConflict):
    """Already assigned or discarded (someone else got there first)."""

    code = "inbox_file_gone"


@dataclass(frozen=True)
class InboxEntry:
    id: UUID
    file_name: str
    media_type: str
    size_bytes: int
    uploaded_by: UUID
    uploaded_by_name: str
    uploaded_by_staff: bool
    note: str | None
    created_at: datetime
    suggestions: tuple[Suggestion, ...]


async def _role(ctx: AuthContext, engagement_id: UUID) -> str:
    """Authorise dropping files into this engagement's inbox: anyone allowed `evidence.upload`
    on it, and client contributors (who may assign only to their own items)."""
    engagement = await get_ref(ctx, engagement_id)
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    try:
        await authorise(ctx, "evidence.upload", engagement.resource())
    except Forbidden as denied:
        if denied.layer != "role" or role != "client_contributor":
            raise
    return role or ""


def _sees(role: str, ctx: AuthContext, row: InboxFile) -> bool:
    if role in _STAFF:
        return True
    if role == "client_admin":
        return not row.uploaded_by_staff
    return row.uploaded_by == ctx.user_id


async def check_inbox(ctx: AuthContext, engagement_id: UUID) -> None:
    """Before the body is read (as SPEC-020)."""
    await _role(ctx, engagement_id)


async def add_to_inbox(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    file_name: str,
    content: bytes,
    note: str | None = None,
) -> InboxEntry:
    """AC-2: store the file and list it as waiting."""
    role = await _role(ctx, engagement_id)
    await gate_client_data(ctx, engagement_id, "evidence.upload")  # SPEC-025 AC-7
    media_type, digest = checked(content)
    async with tenant_session(ctx.tenant) as session:
        if await waiting_with_fingerprint(session, engagement_id, digest):
            raise DuplicateUpload
    stored = await storage.put(ctx.tenant_id, content)
    staff = role in _STAFF
    # SPEC-027 (TASK-050): how many items the matching rule suggests, for the agent's feed.
    suggested = len(suggest(clean_name(file_name), await request_items_for(ctx, engagement_id)))
    try:
        async with uow(ctx.tenant) as tx:
            row = await insert_inbox_file(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                file_name=clean_name(file_name),
                media_type=media_type,
                size_bytes=len(content),
                fingerprint=digest,
                storage_key=stored.key,
                storage_version_id=stored.version_id,
                uploaded_by=ctx.user_id,
                uploaded_by_staff=staff,
                note=clean_note(note) if staff else None,
            )
            tx.record(
                "inbox_file.added",
                target=Target("inbox_file", row.id),
                after=Ref(engagement_id=engagement_id, fingerprint=digest, size=len(content)),
            )
            tx.emit(
                InboxFileAdded(
                    engagement_id=engagement_id, inbox_file_id=row.id, suggestions=suggested
                )
            )
    except IntegrityError:
        raise DuplicateUpload from None  # the same file, added at the same moment
    entries = await _entries(ctx, engagement_id, [row])
    return entries[0]


async def _entries(
    ctx: AuthContext, engagement_id: UUID, rows: list[InboxFile]
) -> list[InboxEntry]:
    items: Sequence[RequestItemView] = await request_items_for(ctx, engagement_id) if rows else ()
    names = await names_of(sorted({r.uploaded_by for r in rows}, key=str))
    return [
        InboxEntry(
            r.id,
            r.file_name,
            r.media_type,
            r.size_bytes,
            r.uploaded_by,
            names.get(r.uploaded_by, ""),
            r.uploaded_by_staff,
            r.note,
            r.created_at,
            tuple(suggest(r.file_name, items)),
        )
        for r in rows
    ]


async def inbox(ctx: AuthContext, engagement_id: UUID) -> list[InboxEntry]:
    """AC-2, AC-3: the waiting files this person may see, each with its suggestions."""
    role = await _role(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        rows = [r for r in await waiting_inbox(session, engagement_id) if _sees(role, ctx, r)]
    return await _entries(ctx, engagement_id, rows)


async def assign(
    ctx: AuthContext,
    engagement_id: UUID,
    file_id: UUID,
    *,
    request_item_id: UUID,
    followed_suggestion: bool,
) -> UUID:
    """AC-4: the file becomes evidence on the item (as a per-item upload), once."""
    role = await _role(ctx, engagement_id)
    await gate_client_data(ctx, engagement_id, "evidence.upload")  # SPEC-025 AC-7
    async with uow(ctx.tenant) as tx:
        row = await lock_inbox_file(tx.session, file_id)
        if row is None or row.engagement_id != engagement_id or not _sees(role, ctx, row):
            raise NotFound("inbox_file")
        if row.status != "waiting":
            raise InboxFileGone
        stored = storage.StoredObject(
            row.storage_key, row.storage_version_id, row.fingerprint, row.size_bytes
        )
        version_id = await attach(
            tx,
            ctx,
            engagement_id=engagement_id,
            item_id=request_item_id,
            stored=stored,
            name=row.file_name,
            media_type=row.media_type,
            source=ON_BEHALF_SOURCE if row.uploaded_by_staff else SOURCE,
            note=row.note,
        )
        await decide_inbox_file(
            tx.session,
            file_id,
            status="assigned",
            assigned_item_id=request_item_id,
            assigned_version_id=version_id,
            decided_by=ctx.user_id,
        )
        tx.record(
            "inbox_file.assigned",
            target=Target("inbox_file", file_id),
            after=Ref(
                request_item_id=request_item_id,
                evidence_version_id=version_id,
                followed_suggestion=int(followed_suggestion),
            ),
        )
    return version_id


async def discard(ctx: AuthContext, engagement_id: UUID, file_id: UUID) -> None:
    """AC-5: by the person who added it, or the firm's team."""
    role = await _role(ctx, engagement_id)
    async with uow(ctx.tenant) as tx:
        row = await lock_inbox_file(tx.session, file_id)
        if row is None or row.engagement_id != engagement_id or not _sees(role, ctx, row):
            raise NotFound("inbox_file")
        if row.status != "waiting":
            raise InboxFileGone
        if role not in _STAFF and row.uploaded_by != ctx.user_id:
            raise Forbidden("evidence.upload", "role")
        await decide_inbox_file(tx.session, file_id, status="discarded", decided_by=ctx.user_id)
        tx.record("inbox_file.discarded", target=Target("inbox_file", file_id))
