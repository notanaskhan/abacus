"""POR-08's "Download entries": a C18 item's entries journal as a C11 document (R-02-T14
remainder; R-02 §5 `GET /portal/approvals/{kind}/{item_id}/journal`; DEC-44; DEC-3172).

The `client_entries_journal` kind is composed by code, never from a firm template: the item's
title, then one table of its lines (Account · Debit · Credit, "$" with cents, "—" when a side is
empty; the handoff's POR-08 lines table), in the code-only `financial_statements` layout. No
agent text, no citation, no figure computed here: the lines are the provider's own.

- **Owner.** The C18 item (`client_approval_item`): one generated document per item. A sent item
  is frozen while it waits (its `seen_hash` names what the client reads), so the first successful
  render is served again; a failed render is rendered again.
- **Deterministic.** The same item composes the same blocks, so the snapshot, content hash and
  bytes repeat (DEC-44).
- **Who.** The portal route admits the client person first (C18's covering grant, as POR-08's
  detail does); the render is requested in their name and draws the DRAFT mark like every C11
  draft render. Serving is the API's own byte route (ADR-104: no object key or presigned URL).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.modules.engagements.api import (
    ApprovalItem,
    client_approval_kinds,
    client_approval_provider,
)

if TYPE_CHECKING:
    from abacus.modules.reporting.api import Requester

KIND: Final = "client_entries_journal"
OWNER: Final = "client_approval_item"
RECORD_TYPE: Final = "derived_rendering"
COLUMNS: Final = ("Account", "Debit", "Credit")
EMPTY_SIDE: Final = "—"


def money(value: Decimal | None) -> str:
    """POR-08's lines: "$" with cents and thousands; an empty side is "—"."""
    if value is None:
        return EMPTY_SIDE
    text_ = f"${abs(value):,.2f}"
    return f"({text_})" if value < 0 else text_


def compose(item: ApprovalItem) -> list[object]:
    """The journal's DocBlocks from the item (pure)."""
    return [
        {"type": "heading", "level": 1, "text": item.title},
        {
            "type": "table",
            "columns": list(COLUMNS),
            "rows": [[line.account, money(line.debit), money(line.credit)] for line in item.lines],
        },
    ]


async def _item(tenant: TenantContext, item_id: UUID) -> ApprovalItem | None:
    for kind in sorted(client_approval_kinds()):
        found = await client_approval_provider(kind).item(tenant, item_id)
        if found is not None:
            return found
    return None


async def _body(tenant: TenantContext, owner: object, _scope: object) -> Sequence[object]:
    from abacus.modules.reporting.api import OwnerRef

    if not isinstance(owner, OwnerRef) or owner.type != OWNER:
        return []
    item = await _item(tenant, owner.id)
    if item is None or not item.sent_to_client:
        raise NotFound("client_approval")
    return compose(item)


async def _no_values(_owner: object, _scope: object) -> Mapping[str, str]:
    return {}


async def _no_approval(_ref: object) -> tuple[UUID, str] | None:
    return None  # a journal is a copy of the entries the client reads; it is never final


def ensure_kind() -> None:
    """Register the kind with C11 once per process (and again after a test resets)."""
    from abacus.modules.reporting import api as c11

    try:
        c11.document_kind(KIND)
    except c11.UnknownDocumentKind:
        c11.register_document_kind(
            c11.DocumentKind(
                kind=KIND,
                layout="financial_statements",
                variables_provider=_no_values,
                approval_provider=_no_approval,
                retention_record_type=RECORD_TYPE,
                formats=("pdf",),
                body_provider=_body,
            )
        )


@dataclass(frozen=True)
class JournalPending:
    """The render is queued or running: the route answers 202 with the job."""

    render_job_id: UUID


@dataclass(frozen=True)
class JournalReady:
    """The PDF is filed as evidence: the route answers 302 to the byte route."""

    evidence_version_id: UUID


_LATEST = text(
    "SELECT v.version_no, j.id AS job_id FROM generated_document_versions v "
    "LEFT JOIN render_jobs j ON j.generated_document_id = v.generated_document_id "
    "AND j.target_version_no = v.version_no "
    "WHERE v.generated_document_id = :d ORDER BY v.version_no DESC LIMIT 1"
)
_JOB = text(
    "SELECT id FROM render_jobs WHERE generated_document_id = :d AND target_version_no = :n"
)


async def journal(
    tenant: TenantContext,
    requested_by: UUID,
    item: ApprovalItem,
    *,
    client_id: UUID,
    engagement_id: UUID | None,
    work_item_id: UUID | None,
) -> JournalPending | JournalReady:
    """The item's journal for a person the caller has admitted: ready, or rendering (a first
    request starts the render; a failed one renders again)."""
    from abacus.modules.reporting import api as c11

    ensure_kind()
    owner = c11.OwnerRef(OWNER, item.item_id)
    requester = c11.Requester("human", user_id=requested_by)
    document_id = await c11.document_of_owner(tenant, owner, KIND)
    if document_id is None:
        try:
            async with uow(tenant) as tx:
                ticket = await c11.render(
                    tx,
                    c11.RenderRequest(
                        kind=KIND,
                        owner_ref=owner,
                        scope=c11.RenderScope(
                            client_id=client_id,
                            engagement_id=engagement_id,
                            work_item_id=work_item_id,
                        ),
                        template_version_id=None,
                        requested_by=requester,
                        formats=("pdf",),
                    ),
                )
        except IntegrityError:
            # End-pass review: a concurrent first request made the item's one document (0430's
            # unique owner and kind); answer that render instead of a 500.
            document_id = await c11.document_of_owner(tenant, owner, KIND)
            if document_id is None:
                raise
            return await _existing(tenant, document_id, requester)
        return await _pending(tenant, ticket.generated_document_id, ticket.version_no)
    return await _existing(tenant, document_id, requester)


async def _existing(
    tenant: TenantContext, document_id: UUID, requester: Requester
) -> JournalPending | JournalReady:
    """The item's document: filed, still rendering, or (after a failure) rendered again."""
    from abacus.modules.reporting import api as c11

    async with tenant_session(tenant) as session:
        latest = (await session.execute(_LATEST, {"d": document_id})).first()
    if latest is not None:
        outcome = await c11.render_outcome(tenant, document_id, int(latest.version_no))
        if outcome.status == "succeeded" and outcome.evidence_version_id is not None:
            return JournalReady(outcome.evidence_version_id)
        if outcome.status != "failed" and latest.job_id is not None:
            return JournalPending(latest.job_id)
    async with uow(tenant) as tx:
        ticket = await c11.regenerate(tx, document_id, requester)
    return await _pending(tenant, ticket.generated_document_id, ticket.version_no)


async def _pending(tenant: TenantContext, document_id: UUID, version_no: int) -> JournalPending:
    async with tenant_session(tenant) as session:
        job = await session.scalar(_JOB, {"d": document_id, "n": version_no})
    if job is None:
        raise NotFound("render_job")
    return JournalPending(job)
