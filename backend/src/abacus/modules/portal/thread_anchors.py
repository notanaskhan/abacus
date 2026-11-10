"""The portal's comment anchors (R-02-T22; SPEC-646 AC-31 to AC-33; R-02 §3.12).

Three kinds registered into collaboration's anchor slot (`collaboration.api.register_anchor`):

- `client_approval_item`: a C18 item a client approves (POR-08 "Ask about this entry"); locator
  `{kind}` names the item's kind. A client reads it while the item is sent and their grant covers
  it (`approvals.approval`); a firm member through the item's engagement.
- `deliverable_version`: a page of a deliverable version (POR-09 page comments); the anchor is the
  deliverable, locator `{version, page, line_ref}` or `{version, page, x, y}`. Client-visible only
  on a version that takes page comments (`page_comments`, the draft for review).
- `governance_communication`: a sent governance letter (POR-15 "Ask the auditor…"), with the
  **author-only** client reader policy (AC-33): each member's question is their own thread.

A provider never decides who may comment: it reports the anchor's facts for the caller (None: not
theirs to see, 404) and the caller authorises its action on `facts.resource()`.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.kernel.errors import NotFound
from abacus.modules.assurance.api import governance_communication_scope
from abacus.modules.collaboration.api import AnchorFacts, Locator
from abacus.modules.engagements.api import (
    ApprovalKindNotRegistered,
    client_approval_provider,
    client_of,
    engagement_label,
    get_ref,
)
from abacus.modules.identity.api import AuthContext, scope_facts
from abacus.modules.reporting.api import deliverable_scope, portal_deliverable

APPROVAL: Final = "client_approval_item"
PAGE: Final = "deliverable_version"
LETTER: Final = "governance_communication"


async def _facts(
    ctx: AuthContext,
    engagement_id: UUID | None,
    work_item_id: UUID | None,
    label: str,
    client_visible: bool,
) -> AnchorFacts | None:
    if engagement_id is None:
        return None
    if ctx.client:
        # A client principal holds no engagement read; the provider proved their grant, so the
        # anchor's facts come from a system read of the engagement's client.
        client_id = await client_of(ctx.tenant, engagement_id)
        if client_id is None:
            return None
        return AnchorFacts(
            ctx.tenant_id,
            engagement_id,
            client_id,
            label,
            work_item_id=work_item_id,
            client_visible=client_visible,
        )
    try:
        ref = await get_ref(ctx, engagement_id)
    except NotFound:
        return None
    names = await engagement_label(ctx.tenant, ref.id)
    client = names.client_name if names is not None else ""
    return AnchorFacts(
        ctx.tenant_id,
        ref.id,
        ref.client_id,
        f"{client} · {label}" if client else label,
        archived=ref.archived,
        work_item_id=work_item_id,
        client_visible=client_visible,
    )


class ApprovalAnchors:
    locator_keys: frozenset[str] = frozenset({"kind"})

    async def facts(
        self, ctx: AuthContext, anchor_id: UUID, locator: Locator | None
    ) -> AnchorFacts | None:
        kind = str((locator or {}).get("kind", ""))
        try:
            provider = client_approval_provider(kind)
        except ApprovalKindNotRegistered:  # an unregistered kind is not an anchor
            return None
        if ctx.client:
            from abacus.modules.portal.approvals import approval

            try:
                item = (await approval(ctx, kind, anchor_id)).item
            except NotFound:
                return None
        else:
            item = await provider.item(ctx.tenant, anchor_id)
            if item is None:
                return None
        scope = await scope_facts(ctx.tenant, item.scope_kind, item.scope_id)
        if scope is None:
            return None
        return await _facts(ctx, scope.engagement_id, scope.work_item_id, item.title, True)


class PageAnchors:
    locator_keys: frozenset[str] = frozenset({"version", "page", "line_ref", "x", "y"})

    async def facts(
        self, ctx: AuthContext, anchor_id: UUID, locator: Locator | None
    ) -> AnchorFacts | None:
        found = dict(locator or {})
        version = found.get("version")
        page = found.get("page")
        if not isinstance(version, int) or not isinstance(page, int) or page < 1:
            return None
        commentable = False
        title = "Deliverable"
        if ctx.client:
            try:
                shown = await portal_deliverable(ctx, anchor_id)
            except NotFound:
                return None
            match = next((v for v in shown.versions if v.version_no == version), None)
            if match is None or page > match.page_count:
                return None
            commentable = "comment" in match.allowed_actions
            title = shown.title
        scope = await deliverable_scope(ctx.tenant, anchor_id)
        if scope is None:
            return None
        return await _facts(
            ctx, scope.engagement_id, scope.work_item_id, f"{title} · page {page}", commentable
        )


class LetterAnchors:
    # `author` is the author-only policy's own key (collaboration.client_threads).
    locator_keys: frozenset[str] = frozenset({"author"})

    async def facts(
        self, ctx: AuthContext, anchor_id: UUID, locator: Locator | None
    ) -> AnchorFacts | None:
        del locator
        scope = await governance_communication_scope(ctx, anchor_id)
        if scope is None:
            return None
        return await _facts(
            ctx, scope.engagement_id, scope.work_item_id, "Governance letter", scope.client_visible
        )


APPROVAL_ANCHORS: Final = ApprovalAnchors()
PAGE_ANCHORS: Final = PageAnchors()
LETTER_ANCHORS: Final = LetterAnchors()

__all__ = [
    "APPROVAL",
    "APPROVAL_ANCHORS",
    "LETTER",
    "LETTER_ANCHORS",
    "PAGE",
    "PAGE_ANCHORS",
]
