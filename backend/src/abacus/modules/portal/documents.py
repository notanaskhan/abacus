"""The portal PBC read model (R-01-T07; C5 section `portal-pbc`; POR-03, POR-04; DEC-240,
DEC-333). A BFF over `requests.api`, `evidence.api`, `engagements.api` and `identity.api`: it owns
no business truth.

- The binder picker: every binder the person reads a request of, through their full-client grants
  (a third party, a K-1 recipient or a firm member has none: 404), each authorised for
  `portal_documents.read` on its work item (`scope_only`); a closed binder is read-only.
- POR-03: one binder through the grant, its requests in client words (To do · Done · Ignored ·
  Returned), receipts by kind and date, code-computed category completion and counts, the
  firm-provided and connected-source rows (DEC-58 f), the firm's client-visible return note, Mark
  as Done's state, the organisations delegated requests went to (client admins only, never their
  titles) and `allowed_actions` from the portal's one vocabulary.
- POR-04: one request with its firm-written guidance, last year's file (roll-forward), the
  mechanical pre-checks in fixed codes (DEC-58 e) and the shared thread's size.

INV-4: a binder outside the grant, a draft, an internal-only or delegated request, or a forged id
answers 404, the same answer for every case. No field carries a firm status code, an amount, a
confidence, a screening verdict or the agent; withdrawn files are never listed (DEC-298). Nothing
here writes.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Final, cast, get_args
from uuid import UUID
from zoneinfo import ZoneInfo

from abacus.kernel import clock
from abacus.kernel._flags import EVIDENCE_WITHDRAWAL
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.engagements.api import (
    EngagementRef,
    client_contact_organisations,
    client_contact_organisations_of_users,
    get_ref,
)
from abacus.modules.evidence.api import PortalFile, client_pre_checks, portal_files
from abacus.modules.identity.api import (
    FULL_ROLES,
    AuthContext,
    Forbidden,
    ItemFacts,
    Resource,
    ScopeFacts,
    allowed_actions,
    authorise,
    engagement_role_of,
    firm_time_zone,
    names_of,
    portal_scopes,
    scope_facts,
)
from abacus.modules.portal.pbc_contract import (
    BinderFilter,
    ClientStatus,
    PortalAction,
    PortalBandOut,
    PortalBinderListOut,
    PortalBinderOut,
    PortalBinderRefOut,
    PortalCategoryOut,
    PortalCategoryRefOut,
    PortalFileOut,
    PortalGroupOut,
    PortalMarkDoneOut,
    PortalPriorYearOut,
    PortalReceiptOut,
    PortalRequestOut,
    PortalReturnedOut,
    PortalRowOut,
    PreCheckCode,
    ReceiptKind,
    ReturnReason,
    RowKind,
)
from abacus.modules.requests.api import (
    PortalBinder,
    PortalBinderRef,
    PortalItem,
    portal_binder_ref,
    portal_binder_refs,
    portal_binder_view,
    portal_item_binder,
    portal_item_view,
    prior_year_link,
)

READ: Final = "portal_documents.read"
# The per-row actions probed on each request's own client facts.
_ROW_ACTIONS: Final = (
    "evidence.upload",
    "request_item.ignore",
    "comment.create",
    "evidence.withdraw",
)
# Statuses a client may still upload to, ignore, or undo an Ignore on (C2).
_UPLOADABLE: Final = frozenset({"requested", "uploaded", "returned"})
_IGNORABLE: Final = frozenset({"requested", "returned"})
_DONE: Final = frozenset({"uploaded", "received"})
_PRE_CHECKS: Final = frozenset(get_args(PreCheckCode))
# Audit binders lay out as folder bands (POR-03 i); the household binders as section cards.
_BANDED: Final = frozenset({"pbc", "third_party"})
# A send-back for the wrong period reads "wrong year" on a household (tax) binder.
_YEARLY: Final = frozenset({"organizer", "intake"})
_MATCHED_BY: Final = frozenset({"rule", "agent"})
UNCATEGORISED: Final = "uncategorised"
# The grants that open documents: the full-client roles except `delegate`, which P-06's
# delegation issues on one request (a third party's, the room's), never the binder (DEC-333).
DOCUMENT_ROLES: Final = FULL_ROLES - {"delegate"}
_CLIENT_ROLES: Final = frozenset({"client_admin", "client_contributor"})


def code_of(name: str) -> str:
    """A label's stable code ("Health & Medical" -> `health_medical`), the `?category=` value."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_name.casefold()).strip("_") or UNCATEGORISED


def year_of(name: str) -> int | None:
    """The binder's year from its name ("2025 Binder", template `{year} Binder`)."""
    found = re.search(r"\b(19|20)\d{2}\b", name)
    return int(found.group(0)) if found else None


def return_reason(reason_code: str | None, binder_kind: str) -> ReturnReason:
    if reason_code == "wrong_period":
        return "wrong_year" if binder_kind in _YEARLY else "wrong_period"
    return "other"


def client_status(item: PortalItem) -> ClientStatus:
    """The request in the client's words (status registry `client_label`); a firm-provided row
    asks nothing of the client, so it reads Done."""
    if item.kind == "firm_provided":
        return "done"
    if item.status == "not_applicable" or item.client_ignored_at is not None:
        return "ignored"
    if item.status == "returned":
        return "returned"
    if item.status in _DONE:
        return "done"
    return "to_do"


def receipt_kind(file: PortalFile, linked_by: str, me: UUID) -> ReceiptKind:
    if linked_by == "rule" and not file.accepted:
        return "rule_linked_pending"  # "Suggested — {firm} will confirm" (DEC-58 a)
    if file.arrived == "email":
        return "emailed"
    if file.arrived == "client_upload":
        return "uploaded" if file.uploader_user_id == me else "uploaded_by_other_contact"
    return "received"


def row_kind(item: PortalItem, files: Sequence[PortalFile]) -> RowKind:
    if item.kind == "firm_provided":
        return "firm_provided"
    if any(f.arrived == "connection" for f in files):
        return "provided_by_connection"
    return "request"


def keep(item: PortalItem, status: ClientStatus, mine: bool, today: date, filt: str) -> bool:
    """`requested`: what the firm still asks for (a request it waived is left out); `all`: every
    row; `uploaded_by_me`: rows with a file the person uploaded; `needs_follow_up`: returned, or
    to do and past due."""
    if filt == "requested":
        return item.status != "not_applicable"
    if filt == "uploaded_by_me":
        return mine
    if filt == "needs_follow_up":
        return status == "returned" or (
            status == "to_do" and item.due_on is not None and item.due_on < today
        )
    return True


@dataclass(frozen=True)
class _Seen:
    """What one read needs about the person and the binder."""

    me: UUID
    role: str | None
    zone: ZoneInfo
    today: date
    read_only: bool
    withdrawal_on: bool
    binder_kind: str


def _on(at: datetime, zone: ZoneInfo) -> date:
    return at.astimezone(zone).date()


async def _grant_held(ctx: AuthContext) -> None:
    """A person with no full-client grant has no documents (a third party has the room)."""
    held = await portal_scopes(ctx)
    if not any(g.role in DOCUMENT_ROLES for g in held.scopes):
        raise NotFound("portal_scope")


async def _authorised(ctx: AuthContext, ref: PortalBinderRef) -> EngagementRef:
    """`portal_documents.read` on the binder's work item (`scope_only`); any refusal is 404."""
    try:
        engagement = await get_ref(ctx, ref.engagement_id)
        resource = replace(engagement.resource(), work_item_id=ref.work_item_id)
        await authorise(ctx, READ, resource)
    except (Forbidden, NotFound):
        raise NotFound("binder") from None
    return engagement


async def list_binders(ctx: AuthContext, scope_id: UUID | None) -> PortalBinderListOut:
    """The binder picker: newest published first; with `scope_id`, that grant's scope only."""
    held = await portal_scopes(ctx)
    grants = [g for g in held.scopes if g.role in DOCUMENT_ROLES]
    if scope_id is not None:
        grants = [g for g in grants if g.scope_id == scope_id]
    if not grants:
        raise NotFound("portal_scope")
    facts = [await scope_facts(ctx.tenant, g.scope_kind, g.scope_id) for g in grants]
    items: list[PortalBinderRefOut] = []
    checked = False
    for ref in await portal_binder_refs(ctx):
        try:
            engagement = await _authorised(ctx, ref)
        except NotFound:
            continue
        checked = True
        if scope_id is not None and not any(
            f is not None
            and (
                f.work_item_id == ref.work_item_id
                if f.work_item_id is not None
                else f.engagement_id == ref.engagement_id
                if f.engagement_id is not None
                else f.client_id == engagement.client_id
            )
            for f in facts
        ):
            continue
        closed = ref.status == "closed"
        items.append(
            PortalBinderRefOut(
                id=ref.id,
                title=ref.name,
                year=year_of(ref.name),
                closed=closed,
                read_only=closed or engagement.archived,
            )
        )
    if not checked:
        await _scope_readable(ctx, [f for f in facts if f is not None])
    return PortalBinderListOut(items=items, total=len(items))


async def _scope_readable(ctx: AuthContext, facts: list[ScopeFacts]) -> None:
    """No binder was listed, so none was authorised: the picker still answers only for a scope
    the caller may read the documents of (`portal_documents.read`), else 404 as with no grant
    (a client with nothing published gets an empty picker, never the route guard's 500)."""
    for f in facts:
        try:
            if f.engagement_id is not None:
                engagement = await get_ref(ctx, f.engagement_id)
                resource = replace(engagement.resource(), work_item_id=f.work_item_id)
            else:
                resource = Resource.client(ctx.tenant_id, f.client_id)
            await authorise(ctx, READ, resource)
            return
        except (Forbidden, NotFound):
            continue
    raise NotFound("portal_scope")


async def _seen(ctx: AuthContext, engagement: EngagementRef, binder: PortalBinder) -> _Seen:
    zone = ZoneInfo(await firm_time_zone(ctx.tenant))
    return _Seen(
        me=ctx.user_id,
        role=await engagement_role_of(ctx.tenant, engagement.id, ctx.user_id),
        zone=zone,
        today=await clock.today(ctx.tenant, zone),
        read_only=binder.status == "closed" or engagement.archived,
        withdrawal_on=await flag_enabled(ctx.tenant, EVIDENCE_WITHDRAWAL),
        binder_kind=binder.kind,
    )


def _item_resource(engagement: EngagementRef, binder: PortalBinder, item: PortalItem) -> Resource:
    return replace(
        engagement.resource(),
        work_item_id=binder.work_item_id,
        item=ItemFacts(item.client_visible, item.client_assignee_user_id),
    )


@dataclass(frozen=True)
class _Row:
    item: PortalItem
    out: PortalRowOut
    files: list[PortalFile]
    mine: bool  # a file the person uploaded


async def _rows(
    ctx: AuthContext,
    engagement: EngagementRef,
    binder: PortalBinder,
    seen: _Seen,
) -> list[_Row]:
    files = {
        item.id: await portal_files(
            ctx.tenant, item.id, [link.evidence_version_id for link in item.links]
        )
        for item in binder.items
    }
    people = {
        u
        for fs in files.values()
        for f in fs
        for u in (f.uploader_user_id, f.sent_back.by_user_id if f.sent_back else None)
        if u is not None
    }
    names = await names_of(sorted(people, key=str))
    # An uploader is named only to the engagement's client people: one with a client role on it
    # (a first name, "Jonah"), else a third party by its organisation ("Harborline"), else not
    # at all (DEC-333, security review).
    uploaders = {f.uploader_user_id for fs in files.values() for f in fs} - {None, seen.me}
    roles = {
        u: await engagement_role_of(ctx.tenant, engagement.id, u)
        for u in sorted((u for u in uploaders if u is not None), key=str)
    }
    organisations = await client_contact_organisations_of_users(
        ctx.tenant, engagement.id, [u for u, role in roles.items() if role not in _CLIENT_ROLES]
    )
    shown_as = {
        u: names.get(u, "").split(" ")[0] or None
        if role in _CLIENT_ROLES
        else organisations.get(u)
        for u, role in roles.items()
    }
    rows: list[_Row] = []
    for item in binder.items:
        own = files[item.id]
        linked_by = {link.evidence_version_id: link.created_by_kind for link in item.links}
        status = client_status(item)
        actions: set[str] = set()
        if not seen.read_only:
            actions = set(
                await allowed_actions(ctx, _item_resource(engagement, binder, item), _ROW_ACTIONS)
            )
        returned = None
        newest_back = own[0].sent_back if own and status == "returned" else None
        if newest_back is not None:
            returned = PortalReturnedOut(
                reason=return_reason(newest_back.reason_code, seen.binder_kind),
                note=newest_back.note,
                by_name=names.get(newest_back.by_user_id, "")
                if newest_back.by_user_id is not None
                else "",
                on=_on(newest_back.at, seen.zone),
            )
        out_files: list[PortalFileOut] = []
        for n, f in enumerate(own):
            kind = receipt_kind(f, linked_by.get(f.version_id, "human"), seen.me)
            other = (
                shown_as.get(f.uploader_user_id)
                if kind == "uploaded_by_other_contact" and f.uploader_user_id is not None
                else None
            )
            withdrawable = (
                seen.withdrawal_on
                and f.withdrawable_kind
                and "evidence.withdraw" in actions
                and (f.uploader_user_id == seen.me or seen.role == "client_admin")
            )
            out_files.append(
                PortalFileOut(
                    id=f.version_id,
                    name=f.name,
                    size_bytes=f.size_bytes,
                    receipt=PortalReceiptOut(
                        kind=kind, on=_on(f.created_at, seen.zone), by_first_name=other or None
                    ),
                    withdrawable=withdrawable,
                    struck=n == 0 and newest_back is not None,
                )
            )
        kind = row_kind(item, own)
        allowed: list[PortalAction] = []
        if kind == "request" and not seen.read_only:
            ignored = item.client_ignored_at is not None
            if item.status in _UPLOADABLE and not ignored and "evidence.upload" in actions:
                allowed.append("upload")
            if item.status in _IGNORABLE and not ignored and "request_item.ignore" in actions:
                allowed.append("ignore")
            if (
                ignored
                and item.ignored_by == seen.me
                and item.status in _IGNORABLE
                and "request_item.ignore" in actions
            ):
                allowed.append("undo_ignore")
            if any(f.withdrawable for f in out_files):
                allowed.append("withdraw")
        if "comment.create" in actions and not seen.read_only:
            allowed.append("comment")
        rows.append(
            _Row(
                item,
                PortalRowOut(
                    id=item.id,
                    engagement_id=item.engagement_id,
                    title=item.title,
                    kind=kind,
                    client_status=status,
                    files=out_files,
                    returned=returned,
                    ignored_on=_on(item.client_ignored_at, seen.zone)
                    if item.client_ignored_at is not None
                    else None,
                    due_on=item.due_on,
                    uploading_count=item.uploading,
                    allowed_actions=allowed,
                ),
                own,
                any(f.arrived == "client_upload" and f.uploader_user_id == seen.me for f in own),
            )
        )
    return rows


def _category_of(binder: PortalBinder) -> dict[UUID, tuple[str, str, int]]:
    """Each category id -> (code, label, position)."""
    return {c.id: (code_of(c.name), c.name, c.position) for c in binder.categories}


async def read_binder(
    ctx: AuthContext, binder_id: UUID, filt: BinderFilter, category: str | None
) -> PortalBinderOut:
    await _grant_held(ctx)
    ref = await portal_binder_ref(ctx, binder_id)
    if ref is None:
        raise NotFound("binder")
    engagement = await _authorised(ctx, ref)
    binder = await portal_binder_view(ctx, binder_id)
    if binder is None:
        raise NotFound("binder")
    seen = await _seen(ctx, engagement, binder)
    if not binder.items and seen.role != "client_admin":
        raise NotFound("binder")  # nothing of it is this person's (INV-4)
    rows = await _rows(ctx, engagement, binder, seen)
    cats = _category_of(binder)

    def cat_code(item: PortalItem) -> str:
        found = cats.get(item.category_id) if item.category_id is not None else None
        return found[0] if found is not None else UNCATEGORISED

    categories: list[PortalCategoryOut] = []
    for cid, (code, label, _) in sorted(cats.items(), key=lambda kv: kv[1][2]):
        inside = [r for r in rows if r.item.category_id == cid]
        categories.append(
            PortalCategoryOut(
                code=code,
                label=label,
                complete=bool(inside)
                and all(r.out.client_status in ("done", "ignored") for r in inside),
                requested=len(inside),
            )
        )
    shown = [
        r
        for r in rows
        if keep(r.item, r.out.client_status, r.mine, seen.today, filt)
        and (category is None or cat_code(r.item) == category)
    ]
    position = {cid: p for cid, (_, _, p) in cats.items()}
    shown.sort(
        key=lambda r: (
            position.get(r.item.category_id, 1_000_000) if r.item.category_id else 1_000_000
        )
    )
    groups: list[PortalGroupOut] = []
    bands: list[PortalBandOut] = []
    banded = binder.kind in _BANDED
    order: dict[tuple[str, str], list[PortalRowOut]] = {}
    for r in shown:
        key = (cat_code(r.item), "" if banded else r.item.group)
        order.setdefault(key, []).append(r.out)
    used: set[str] = set()
    for (ccode, group), outs in order.items():
        if banded:
            label = next((lbl for c, lbl, _ in cats.values() if c == ccode), shown[0].item.group)
            bands.append(PortalBandOut(code=ccode, label=label, rows=outs))
            continue
        code = code_of(group)
        if code in used:
            code = f"{ccode}_{code}"
        used.add(code)
        groups.append(PortalGroupOut(code=code, label=group, category_code=ccode, rows=outs))
    open_count = sum(1 for r in rows if r.out.client_status in ("to_do", "returned"))
    marked = binder.status == "complete"
    names = (
        await names_of([binder.marked_done_by])
        if marked and binder.marked_done_by is not None
        else {}
    )
    mark_done = PortalMarkDoneOut(
        state="marked" if marked else ("ready" if open_count == 0 else "tonal"),
        marked_on=_on(binder.marked_done_at, seen.zone)
        if marked and binder.marked_done_at is not None
        else None,
        marked_by_name=names.get(binder.marked_done_by) if binder.marked_done_by else None,
    )
    allowed: list[PortalAction] = []
    if not seen.read_only:
        if any("upload" in r.out.allowed_actions for r in rows):
            allowed.append("upload")
        mine = any(r.item.client_assignee_user_id == seen.me for r in rows)
        facts = ItemFacts(True, seen.me if mine else None)
        resource = replace(engagement.resource(), work_item_id=binder.work_item_id, item=facts)
        may_mark = "binder.mark_done" in await allowed_actions(ctx, resource, ["binder.mark_done"])
        if may_mark and binder.status == "published":
            allowed.append("mark_done")
        if (
            may_mark
            and marked
            and binder.marked_done_by == seen.me
            and not binder.firm_acted_since_done
        ):
            allowed.append("undo_mark_done")
    other_parties = (
        await client_contact_organisations(
            ctx.tenant, engagement.id, list(binder.delegated_contacts)
        )
        if seen.role == "client_admin"
        else []
    )
    closed = binder.status == "closed"
    return PortalBinderOut(
        binder=PortalBinderRefOut(
            id=binder.id,
            title=binder.name,
            year=year_of(binder.name),
            closed=closed,
            read_only=seen.read_only,
        ),
        layout="bands" if banded else "groups",
        filter=filt,
        categories=categories,
        groups=groups,
        bands=bands,
        total=len(rows),
        done_count=len(rows) - open_count,
        open_count=open_count,
        sorted_count=sum(
            1 for r in rows for link in r.item.links if link.created_by_kind in _MATCHED_BY
        ),
        mark_done=mark_done,
        other_parties=other_parties,
        allowed_actions=allowed,
    )


async def read_request(ctx: AuthContext, item_id: UUID) -> PortalRequestOut:
    await _grant_held(ctx)
    ref = await portal_item_binder(ctx, item_id)
    if ref is None:
        raise NotFound("request_item")
    engagement = await _authorised(ctx, ref)
    binder = await portal_item_view(ctx, item_id)
    if binder is None or len(binder.items) != 1:
        raise NotFound("request_item")
    seen = await _seen(ctx, engagement, binder)
    [row] = await _rows(ctx, engagement, binder, seen)
    item = row.item
    cats = _category_of(binder)
    if item.category_id in cats:
        code, label, _ = cats[cast(UUID, item.category_id)]
    else:
        code, label = UNCATEGORISED, item.group
    prior = None
    found = await prior_year_link(ctx, binder, item)
    if found is not None:
        prior_binder, prior_item, link = found
        try:  # last year's binder is authorised like any other (`scope_only`, INV-4)
            await _authorised(ctx, prior_binder)
            prior_files = await portal_files(ctx.tenant, prior_item, [link.evidence_version_id])
        except NotFound:
            prior_files = []
        if prior_files:
            prior = PortalPriorYearOut(
                file_name=prior_files[0].name, sent_on=_on(prior_files[0].created_at, seen.zone)
            )
    checks: list[PreCheckCode] = []
    if row.files:
        checks = [
            cast(PreCheckCode, c)
            for c in await client_pre_checks(ctx.tenant, row.files[0].version_id)
            if c in _PRE_CHECKS
        ]
    requested = item.requested_at or binder.published_at
    return PortalRequestOut(
        id=item.id,
        engagement_id=item.engagement_id,
        binder_id=binder.id,
        variant="request",
        category=PortalCategoryRefOut(code=code, label=label),
        title=item.title,
        client_status=row.out.client_status,
        requested_on=_on(requested, seen.zone) if requested is not None else seen.today,
        due_on=item.due_on,
        guidance=item.guidance,
        prior_year=prior,
        files=row.out.files,
        returned=row.out.returned,
        pre_checks=checks,
        comment_count=item.comment_count,
        uploading_count=item.uploading,
        allowed_actions=row.out.allowed_actions,
    )
