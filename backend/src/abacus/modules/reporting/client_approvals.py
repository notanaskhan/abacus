"""C18's `fs_draft` kind (R-02-T11; R-02 §3.1; SPEC-646; A-06-T29; DEC-3009). PROTECTED.

Management approval of a draft financial statement version through the portal (POR-08 and C10's
draft deliverable). A version is before the client once a `sent_for_approval` row was written for
it on the portal channel (A-06-T29's send-draft); it is waiting until a client person who is the
decider approves it, which writes the insert-only `statement_approvals` row
(`approved_by_management`, principal `contact`, channel `portal`, the grant as the item ref),
moves the statement's management approval, and emits `fs.approved_by_management` for A-07's
completion items (AUD-24, AUD-19). A person's record mode stays `record_management_approval`.

`seen_hash` is the version's `content_hash` with its number: what the client read is what they
approved (AC-4).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy import RowMapping, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.engagements.api import (
    ApprovalFacts,
    ApprovalItem,
    ClientApprovalState,
    ClientDecision,
    ClientDecisionContext,
    ItemChanged,
)
from abacus.modules.reporting.statements import FsApprovedByManagement

_SENT = (
    "SELECT v.id, v.engagement_id, v.work_item_id, v.version_no, v.content_hash, "
    "v.statement_document_id, "
    "EXISTS (SELECT 1 FROM statement_approvals a WHERE a.statement_version_id = v.id "
    "AND a.event = 'approved_by_management') AS approved, "
    "(SELECT max(a.created_at) FROM statement_approvals a WHERE a.statement_version_id = v.id "
    "AND a.event = 'approved_by_management') AS approved_at "
    "FROM statement_versions v WHERE EXISTS (SELECT 1 FROM statement_approvals s "
    "WHERE s.statement_version_id = v.id AND s.event = 'sent_for_approval' "
    "AND s.channel = 'portal')"
)
# Constant SQL only: the two filters append fixed text to `_SENT`; values are bound parameters.
_ON_SCOPE_SQL = _SENT + " AND (v.work_item_id = :scope OR v.engagement_id = :scope)"
_ONE_SQL = _SENT + " AND v.id = :id"
_ON_SCOPE = text(_ON_SCOPE_SQL)
_ONE = text(_ONE_SQL)


def seen_hash(version_id: UUID, version_no: int, content_hash: str) -> str:
    return hashlib.sha256(f"{version_id}:{version_no}:{content_hash}".encode()).hexdigest()


def _item(r: RowMapping) -> ApprovalItem:
    state: ClientApprovalState = "approved" if r["approved"] else "waiting"
    return ApprovalItem(
        kind="fs_draft",
        item_id=cast(UUID, r["id"]),
        scope_kind="work_item",
        scope_id=cast(UUID, r["work_item_id"]),
        sent_to_client=True,
        title=f"Financial statements · draft {r['version_no']}",
        state=state,
        seen_hash=seen_hash(
            cast(UUID, r["id"]), cast(int, r["version_no"]), str(r["content_hash"])
        ),
        decided_at=r["approved_at"],
    )


class FsDraftApprovals:
    """C18's `fs_draft` provider (registered from `reporting.api`)."""

    async def items(self, tenant: TenantContext, scope_id: UUID) -> Sequence[ApprovalItem]:
        async with tenant_session(tenant) as session:
            rows = (await session.execute(_ON_SCOPE, {"scope": scope_id})).mappings().all()
        return [_item(r) for r in rows]

    async def item(self, tenant: TenantContext, item_id: UUID) -> ApprovalItem | None:
        async with tenant_session(tenant) as session:
            row = (await session.execute(_ONE, {"id": item_id})).mappings().first()
        return None if row is None else _item(row)

    async def decide(
        self,
        tx: UnitOfWork,
        item_id: UUID,
        decision: ClientDecision,
        context: ClientDecisionContext,
    ) -> ApprovalItem:
        if decision.decision != "approve":
            raise ItemChanged
        row = (
            (
                await tx.session.execute(
                    text(
                        "SELECT v.id, v.tenant_id, v.engagement_id, v.work_item_id, "
                        "v.statement_document_id FROM statement_versions v WHERE v.id = :id "
                        "FOR UPDATE"
                    ),
                    {"id": item_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound("statement_version")
        already = (
            await tx.session.execute(
                text(
                    "SELECT 1 FROM statement_approvals WHERE statement_version_id = :v "
                    "AND event = 'approved_by_management'"
                ),
                {"v": item_id},
            )
        ).first()
        if already is not None:
            raise ItemChanged
        # S32 review: only the newest version of the statement can be approved; an older draft
        # still in the portal answers item_changed (the client reloads the current one).
        newer = (
            await tx.session.execute(
                text(
                    "SELECT 1 FROM statement_versions WHERE statement_document_id = :d "
                    "AND version_no > (SELECT version_no FROM statement_versions WHERE id = :v)"
                ),
                {"d": row["statement_document_id"], "v": item_id},
            )
        ).first()
        if newer is not None:
            raise ItemChanged
        await tx.session.execute(
            text(
                "INSERT INTO statement_approvals (tenant_id, statement_version_id, event, "
                "actor_principal, channel, approval_item_ref) VALUES (:t, :v, "
                "'approved_by_management', 'contact', 'portal', :ref)"
            ),
            {"t": row["tenant_id"], "v": item_id, "ref": f"grant:{context.grant_id}"},
        )
        await tx.session.execute(
            text(
                "UPDATE statement_documents SET management_approval = 'approved_by_management', "
                "row_version = row_version + 1 WHERE id = :d"
            ),
            {"d": row["statement_document_id"]},
        )
        tx.emit(
            FsApprovedByManagement(
                statement_version_id=item_id,
                engagement_id=row["engagement_id"],
                work_item_id=row["work_item_id"],
            )
        )
        tx.record(
            "statement.management_approved_in_portal",
            target=Target("statement_version", item_id),
            after=Ref(
                contact=context.contact_id,
                grant=context.grant_id,
                session=context.session_id,
            ),
            scope=Scope(engagement_id=row["engagement_id"], work_item_id=row["work_item_id"]),
        )
        return ApprovalItem(
            kind="fs_draft",
            item_id=item_id,
            scope_kind="work_item",
            scope_id=row["work_item_id"],
            sent_to_client=True,
            title="",
            state="approved",
            seen_hash="",
        )

    async def facts(self, tenant: TenantContext, item_id: UUID) -> ApprovalFacts:
        found = await self.item(tenant, item_id)
        if found is None:
            raise NotFound("statement_version")
        return ApprovalFacts(False, found.scope_id)
