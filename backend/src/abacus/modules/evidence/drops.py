"""Portal drops and their code-rule sort (R-01-T09; R-01 Story 2.1, 2.3; DEC-58 a, c, g; ADR-005,
ADR-050; DEC-323). PROTECTED.

**The drop** (`drop_file`, `POST /v1/portal/binders/{id}/drops`): a client drops a file anywhere
on a published binder in their scope. Authorised `evidence.upload` on the binder with its client
facts (a forged, unpublished or out-of-scope binder answers 404, INV-4) **before** the replay
lookup, and before a byte of the body is read (`check_drop`, called by the route first), so a
replay is checked like the first call. The file goes through the one upload policy
every channel uses (`uploads.screened`: 50 MB, the byte-sniffed allowlist with its extension check,
the malware scan, active content kept and flagged; DEC-296), is stored content-addressed (DEC-297:
inbox files are) and waits in the engagement inbox as a `portal_drop`, one per (dropper,
`X-Drop-Batch`, `Idempotency-Key`). The same bytes as a version of the engagement are accepted and
flagged for the firm (`duplicate_of_version_id`), never refused (DEC-58 g); the client is never
told (no oracle on versions they can't see).

**The sort** (`sort_drop`, `upload_processing` v6 `patched("portal_drop_sort")`, after the
extraction): code scores the requests **the dropper can see** in the binder: client-visible, open,
never a draft and not delegated (`requests.drop_items`), each kept only when the dropper may upload
to it now (`member_could`, the per-request upload's own rule). When the match is decisive
(`not should_match(...)`: the top request matched on kind plus a date or an account and scores at
least twice the next), the file becomes a version on that request and `fulfil_by_rule` links it as
a `rule` fulfilment, as the platform acting for the dropper (`system`, `on_behalf_of` the dropper,
INV-5): a suggestion a named person accepts (ADR-005). The link checks everything again inside its
own unit of work, the request row-locked: the binder still published, the request still
client-visible, open and not delegated (`requests.drop_target`), the dropper still allowed
(`member_could`), and the same bytes not already on that request. An active-content file is never
rule-linked. Otherwise, or with `portal.drop_sort` off, it stays `waiting`, the engagement's leads
get `portal.drop_unsorted`, and the matcher may look at it now its PII scan is done
(`inbox_file.extracted` again; the matcher reads only its masked projection). Once sorted, a drop
is never sorted again (the outcome is written once, by trigger).

**The poll** (`drop_batch`, `GET /v1/portal/drops/{batch_id}`): the dropper's own files in one
batch with their outcomes, every binder they were dropped on still in the dropper's scope;
anyone else's batch answers 404.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from abacus.kernel._flags import PORTAL_DROP_SORT
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import check_facts, gate_client_data, get_ref, lock_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.active_content import REASON_CODES
from abacus.modules.evidence.events import (
    EvidenceUploaded,
    InboxFileAdded,
    InboxFileExtracted,
    PortalDropUnsorted,
)
from abacus.modules.evidence.matching import EngagementFacts, facts_of, score_all, should_match
from abacus.modules.evidence.models import InboxFile
from abacus.modules.evidence.repository import (
    decide_inbox_file,
    drop_by_key,
    drops_of_batch,
    fingerprint_among,
    insert_inbox_file,
    lock_inbox_file,
    newest_extraction,
    other_version_with_fingerprint,
    set_sort_outcome,
)
from abacus.modules.evidence.service import NewItem, Provenance, add_version
from abacus.modules.evidence.uploads import (
    ON_BEHALF_SOURCE,
    SOURCE,
    clean_name,
    item_resource,
    screened,
)
from abacus.modules.evidence.workflow_types import INBOX, UploadInput
from abacus.modules.identity.api import AuthContext, member_could, system_context_for_run
from abacus.modules.requests.api import (
    DropBinder,
    ItemNotFulfillable,
    RequestItemRef,
    RequestItemView,
    drop_binder,
    drop_binder_open,
    drop_items,
    drop_target,
    fulfil_by_rule,
    item_versions,
)

_log = get_logger(__name__)

PORTAL_DROP: Final = "portal_drop"
_NIL: Final = UUID(int=0)
Outcome = Literal["rule_linked", "waiting"]


@dataclass(frozen=True)
class DropAccepted:
    batch_id: UUID
    file_id: UUID


@dataclass(frozen=True)
class DropFileView:
    file_id: UUID
    file_name: str
    outcome: str | None  # rule_linked or waiting; None while being sorted
    request_item_id: UUID | None


@dataclass(frozen=True)
class DropBatchView:
    batch_id: UUID
    binder_id: UUID
    files: list[DropFileView]
    settled: bool


async def _existing(
    tenant: TenantContext, batch_id: UUID, key: str, dropped_by: UUID
) -> InboxFile | None:
    async with tenant_session(tenant) as session:
        return await drop_by_key(session, batch_id, key, dropped_by)


def _replayed(row: InboxFile, binder_id: UUID) -> DropAccepted:
    """The first call's answer; the same key on another binder is not that drop."""
    if row.drop_binder_id != binder_id:
        raise NotFound("drop")
    return DropAccepted(row.drop_batch_id or _NIL, row.id)


async def check_drop(ctx: AuthContext, binder_id: UUID) -> DropBinder:
    """Whether this person may drop on this binder at all: called before the body is read."""
    target = await drop_binder(ctx, binder_id, "evidence.upload")  # 404 outside the scope
    await gate_client_data(ctx, target.engagement_id, "evidence.upload")  # SPEC-025 AC-7
    return target


async def drop_file(
    ctx: AuthContext,
    binder_id: UUID,
    *,
    batch_id: UUID,
    key: str,
    file_name: str,
    content: bytes,
) -> DropAccepted:
    """One dropped file (POR-03 b): stored in the engagement inbox for the code-rule sort."""
    target = await check_drop(ctx, binder_id)  # again, the route checked before reading
    found = await _existing(ctx.tenant, batch_id, key, ctx.user_id)
    if found is not None:
        return _replayed(found, binder_id)
    name = clean_name(file_name)
    checked = await screened(ctx, target.engagement_id, content, name)  # the one policy
    async with tenant_session(ctx.tenant) as session:
        duplicate = await other_version_with_fingerprint(
            session, target.engagement_id, checked.fingerprint, _NIL
        )
    stored = await storage.put(ctx.tenant_id, content)
    try:
        async with uow(ctx.tenant) as tx:
            row = await insert_inbox_file(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=target.engagement_id,
                file_name=name,
                media_type=checked.media_type,
                size_bytes=len(content),
                fingerprint=checked.fingerprint,
                storage_key=stored.key,
                storage_version_id=stored.version_id,
                uploaded_by=ctx.user_id,
                uploaded_by_staff=not ctx.client,
                note=None,
                channel=PORTAL_DROP,
                drop_batch_id=batch_id,
                drop_binder_id=binder_id,
                drop_key=key,
                duplicate_of_version_id=duplicate,
            )
            tx.record(
                "portal.drop_received",
                target=Target("inbox_file", row.id),
                after=Ref(
                    engagement_id=target.engagement_id,
                    binder_id=binder_id,
                    batch_id=batch_id,
                    size=len(content),
                ),
            )
            if duplicate is not None:  # DEC-58 g: accepted and flagged for a person
                tx.record(
                    "inbox_file.duplicate_flagged",
                    target=Target("inbox_file", row.id),
                    after=Ref(evidence_version_id=duplicate),
                )
            if checked.active_content is not None:  # DEC-296: kept, flagged, never read
                tx.record(
                    "inbox_file.flagged",
                    target=Target("inbox_file", row.id),
                    after=Ref(reason=REASON_CODES[checked.active_content]),
                )
            tx.emit(
                InboxFileAdded(
                    engagement_id=target.engagement_id, inbox_file_id=row.id, suggestions=0
                )
            )
    except IntegrityError:  # the same (batch, key) at the same moment
        again = await _existing(ctx.tenant, batch_id, key, ctx.user_id)
        if again is None:
            raise
        return _replayed(again, binder_id)
    return DropAccepted(batch_id, row.id)


# --- The sort (upload_processing v6) -------------------------------------------------------------


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "evidence.portal_drop_sort")


async def _decisive(row: InboxFile, tenant_id: UUID) -> UUID | None:
    """The one request the drop decisively matches among those the dropper may upload to."""
    tenant = _system(tenant_id)
    if row.drop_binder_id is None:
        return None
    if await drop_binder_open(tenant, row.drop_binder_id) != row.engagement_id:
        return None  # the binder closed, or isn't this engagement's
    acting = system_context_for_run(
        tenant_id=tenant_id,
        run_id=row.id,
        engagement_id=row.engagement_id,
        on_behalf_of=row.uploaded_by,
    )
    base = (await get_ref(acting, row.engagement_id)).resource()
    candidates: list[RequestItemView] = []
    for item in await drop_items(tenant, row.drop_binder_id):
        ref = RequestItemRef(
            item.id,
            item.engagement_id,
            item.status,
            item.client_visible,
            item.client_assignee_user_id,
        )
        if await member_could(
            tenant_id, row.uploaded_by, "evidence.upload", item_resource(ref, base)
        ):
            candidates.append(item)
    if not candidates:
        return None
    async with tenant_session(tenant) as session:
        content = facts_of(await newest_extraction(session, inbox_file_id=row.id))
    engagement = await check_facts(tenant, row.engagement_id)
    context = (
        EngagementFacts(engagement.fiscal_period_end, engagement.client_entity_name, {})
        if engagement is not None
        else None
    )
    scored = score_all(row.file_name, candidates, content, context)
    if should_match(scored):
        return None
    return scored[0].request_item_id


class _NoLink(Exception):
    """The link's re-check failed: nothing is written, the drop waits for a person."""


async def _active(tenant_id: UUID, file_id: UUID) -> bool:
    """DEC-296: a file kept with active content (its extraction says so) is never rule-linked."""
    async with tenant_session(_system(tenant_id)) as session:
        row = await newest_extraction(session, inbox_file_id=file_id)
    return row is not None and row.reason == "active_content"


async def _link(row: InboxFile, tenant_id: UUID, item_id: UUID) -> bool:
    """The rule link, as the platform acting for the dropper, with the scope checked again inside
    its own unit of work; False when anything changed (the drop then waits for a person)."""
    if row.drop_binder_id is None or await _active(tenant_id, row.id):
        return False
    acting = system_context_for_run(
        tenant_id=tenant_id,
        run_id=row.id,
        engagement_id=row.engagement_id,
        on_behalf_of=row.uploaded_by,
    )
    try:
        async with uow(acting.tenant) as tx:
            locked = await lock_inbox_file(tx.session, row.id)
            if locked is None or locked.status != "waiting" or locked.sort_outcome is not None:
                raise _NoLink
            target = await drop_target(tx, row.drop_binder_id, item_id)  # row-locked
            if target is None or target.engagement_id != row.engagement_id:
                raise _NoLink
            engagement = await lock_ref(tx, row.engagement_id)
            if not await member_could(
                tenant_id,
                row.uploaded_by,
                "evidence.upload",
                item_resource(target, engagement.resource()),
            ):
                raise _NoLink  # the dropper's access changed since the drop
            on_item = await item_versions(tx, item_id)
            if await fingerprint_among(tx.session, on_item, locked.fingerprint):
                raise _NoLink  # the same bytes are already on that request
            stored = storage.StoredObject(
                locked.storage_key,
                locked.storage_version_id,
                locked.fingerprint,
                locked.size_bytes,
            )
            version = await add_version(
                tx,
                engagement_id=row.engagement_id,
                item=NewItem(title=locked.file_name),
                stored=stored,
                media_type=locked.media_type,
                provenance=Provenance(
                    source=ON_BEHALF_SOURCE if locked.uploaded_by_staff else SOURCE,
                    method="uploaded",
                ),
                requested_by=row.uploaded_by,
            )
            await fulfil_by_rule(
                tx, acting, request_item_id=item_id, evidence_version_id=version.id
            )
            await decide_inbox_file(
                tx.session,
                row.id,
                status="assigned",
                assigned_item_id=item_id,
                assigned_version_id=version.id,
                decided_by=None,
            )
            await set_sort_outcome(tx.session, row.id, "rule_linked")
            tx.record(
                "portal.drop_sorted",
                target=Target("inbox_file", row.id),
                after=Ref(request_item_id=item_id, evidence_version_id=version.id),
            )
            tx.emit(
                EvidenceUploaded(
                    engagement_id=row.engagement_id,
                    request_item_id=item_id,
                    evidence_version_id=version.id,
                    uploaded_by=row.uploaded_by,
                )
            )
    except (_NoLink, ItemNotFulfillable, NotFound):
        return False
    return True


async def _wait(row: InboxFile, tenant_id: UUID) -> None:
    async with uow(_system(tenant_id)) as tx:
        locked = await lock_inbox_file(tx.session, row.id)
        if locked is None or locked.sort_outcome is not None:
            tx.record("portal.drop_sort_exists", target=Target("inbox_file", row.id))
            return
        await set_sort_outcome(tx.session, row.id, "waiting")
        tx.record("portal.drop_unsorted", target=Target("inbox_file", row.id))
        tx.emit(PortalDropUnsorted(engagement_id=row.engagement_id, inbox_file_id=row.id))
        # Its PII scan has run (v5 before v6): the matcher may look at its masked projection.
        tx.emit(InboxFileExtracted(engagement_id=row.engagement_id, inbox_file_id=row.id))


async def sort_drop(given: UploadInput) -> str:
    """The `upload.portal_drop_sort` activity's body: the drop's outcome (`rule_linked`,
    `waiting`), or `not_a_drop` for any other upload. Idempotent: a sorted drop keeps it."""
    if given.kind != INBOX:
        return "not_a_drop"
    tenant_id = UUID(given.tenant_id)
    async with tenant_session(_system(tenant_id)) as session:
        row = await session.get(InboxFile, UUID(given.source_id))
    if row is None or row.channel != PORTAL_DROP:
        return "not_a_drop"
    if row.sort_outcome is not None:
        return row.sort_outcome
    if row.status != "waiting":
        return "not_a_drop"  # a person sorted it first
    linked = False
    if await flag_enabled(_system(tenant_id), PORTAL_DROP_SORT) and not await _active(
        tenant_id, row.id
    ):
        item_id = await _decisive(row, tenant_id)
        linked = item_id is not None and await _link(row, tenant_id, item_id)
    if not linked:
        await _wait(row, tenant_id)
    outcome = "rule_linked" if linked else "waiting"
    _log.info("portal.drop_sorted", outcome=outcome)
    return outcome


# --- The poll ----------------------------------------------------------------------------------


def _drop_file_view(r: InboxFile) -> DropFileView:
    """A duplicate reads `waiting`: the firm sees the flag, not the client. A rule link reads as
    one only while it stands (status `assigned`, decided by no one): once a person voided it the
    file reads `waiting`, and a request a person later assigns it to is never shown to the
    dropper (R-01 Story 2.2 security review; INV-4)."""
    linked = r.sort_outcome == "rule_linked"
    standing = linked and r.status == "assigned" and r.decided_by is None
    outcome = "waiting" if linked and not standing else r.sort_outcome
    return DropFileView(r.id, r.file_name, outcome, r.assigned_item_id if standing else None)


async def drop_batch(ctx: AuthContext, batch_id: UUID) -> DropBatchView:
    """The dropper's files in one batch (POR-03 c, d). Someone else's batch answers 404."""
    async with tenant_session(ctx.tenant) as session:
        rows = await drops_of_batch(session, batch_id, ctx.user_id)
    if not rows:
        raise NotFound("drop_batch")
    binders = sorted({r.drop_binder_id for r in rows if r.drop_binder_id is not None}, key=str)
    if not binders:
        raise NotFound("drop_batch")
    for binder in binders:  # every row's binder, still in the caller's scope
        await drop_binder(ctx, binder, "portal_documents.read")
    binder_id = rows[0].drop_binder_id or binders[0]
    files = [_drop_file_view(r) for r in rows]
    return DropBatchView(batch_id, binder_id, files, all(f.outcome is not None for f in files))


__all__ = [
    "DropAccepted",
    "DropBatchView",
    "DropFileView",
    "check_drop",
    "drop_batch",
    "drop_file",
    "sort_drop",
]
