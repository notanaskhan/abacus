"""C10's reader check (R-02-T07; R-02 §3.15 AC-38 to AC-41; DEC-93). Contract:
`docs/contracts/deliverables.md`.

`reader_version` answers, for a client person, one deliverable version they may read, or
`NotFound` (404, the same answer whatever the reason, AC-41). A version is readable when:

- the caller is a client principal (a firm user, support or the platform never reads here);
- the version is published and not withdrawn;
- one of the person's active grants covers one of the deliverable's audiences, by role and scope:
  a `tcwg` grant reaches only a `governance_room` audience naming its room, and no other grant
  reaches a governance room (privacy per role and per scope, DEC-93); delegates, third parties,
  K-1 recipients, prospects and component auditors reach nothing here (T-02 owns K-1 delivery);
- a draft is a C11 render in `draft` mode, which C11 always draws with the DRAFT mark (P-11
  AC2.2): a draft without one is never served (`watermarked` false and the serving refuses).

Identifiers and facts only; no bytes. Serving is `evidence.api` (`deliverable_page`,
`issue_deliverable_download`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.evidence.api import ServableVersion
from abacus.modules.identity.api import (
    AuthContext,
    active_grants,
    grant_contact_ids,
    scope_facts,
)

# Grant roles that never read a C10 deliverable (T-02 serves K-1s; a delegate reaches a request).
_NEVER: Final = frozenset(
    {"delegate", "third_party", "k1_recipient", "prospect", "component_auditor"}
)
# Deliverables that carry tax return information (C19): their reads are marked `tri`.
TRI_KINDS: Final = frozenset({"return_copy", "filing_letter"})


@dataclass(frozen=True)
class Audience:
    scope_kind: str
    scope_id: UUID


@dataclass(frozen=True)
class ReaderVersion:
    deliverable_id: UUID
    version_id: UUID
    version_no: int
    evidence_version_id: UUID
    is_draft: bool
    watermarked: bool  # a draft is a C11 draft-mode render (always DRAFT-marked)
    page_count: int
    kind: str
    title: str
    client_id: UUID
    engagement_id: UUID | None
    work_item_id: UUID | None
    tri: bool
    contact_id: UUID
    grant_id: UUID

    def servable(self) -> ServableVersion:
        """What `evidence.api`'s serving calls take."""
        return ServableVersion(
            version_id=self.version_id,
            version_no=self.version_no,
            evidence_version_id=self.evidence_version_id,
            is_draft=self.is_draft,
            watermarked=self.watermarked,
            page_count=self.page_count,
            title=self.title,
            client_id=self.client_id,
            engagement_id=self.engagement_id,
            work_item_id=self.work_item_id,
            tri=self.tri,
            contact_id=self.contact_id,
        )


_VERSION = text(
    """
    SELECT d.id AS deliverable_id, d.kind, d.title, d.client_id, d.client_entity_id,
           d.engagement_id,
           d.work_item_id, d.source_module, v.id AS version_id, v.version_no,
           v.evidence_version_id, v.is_draft, v.page_count,
           EXISTS (
               SELECT 1 FROM generated_document_files f
                 JOIN generated_document_versions gv ON gv.id = f.version_id
                WHERE f.evidence_version_id = v.evidence_version_id
                  AND gv.generated_document_id = v.generated_document_id
                  AND gv.mode = 'draft'
           ) AS draft_render,
           EXISTS (
               SELECT 1 FROM deliverable_events e
                WHERE e.deliverable_version_id = v.id AND e.kind = 'withdrawn'
           ) AS withdrawn,
           EXISTS (
               SELECT 1 FROM deliverable_events e
                WHERE e.deliverable_version_id = v.id AND e.kind = 'published'
           ) AS published
      FROM deliverables d
      JOIN deliverable_versions v ON v.deliverable_id = d.id
     WHERE d.id = :deliverable_id AND v.version_no = :version_no
    """
)
_AUDIENCES = text(
    "SELECT scope_kind, scope_id FROM deliverable_audiences WHERE deliverable_id = :id"
)


def covers(
    role: str,
    grant_kind: str,
    grant_scope: UUID,
    facts_client: UUID | None,
    facts_engagement: UUID | None,
    facts_work_item: UUID | None,
    audience: Audience,
    deliverable_engagement: UUID | None,
    deliverable_entity: UUID | None = None,
) -> bool:
    """Whether one grant reaches one audience (pure; the scope facts are resolved by the caller).
    A grant narrower than the audience reaches it only where it covers the deliverable itself."""
    if role in _NEVER:
        return False
    if (role == "tcwg") != (audience.scope_kind == "governance_room"):
        return False
    if audience.scope_kind == "governance_room":
        return grant_kind == "governance_room" and grant_scope == audience.scope_id
    if grant_kind == "governance_room":
        return False
    if audience.scope_kind == "client":
        return facts_client == audience.scope_id and (
            facts_engagement is None
            or (deliverable_engagement is not None and facts_engagement == deliverable_engagement)
        )
    if audience.scope_kind == "client_entity":
        if grant_kind == "client_entity":
            return grant_scope == audience.scope_id
        return grant_kind == "client" and deliverable_entity == audience.scope_id
    if audience.scope_kind == "engagement":
        if facts_work_item is not None:
            return False  # a work-item grant reaches a work-item audience only
        return facts_engagement == audience.scope_id or (
            facts_engagement is None and facts_client is not None and grant_kind == "client"
        )
    if audience.scope_kind == "work_item":
        if facts_work_item is not None:
            return facts_work_item == audience.scope_id
        return deliverable_engagement is not None and facts_engagement == deliverable_engagement
    return False


async def first_covering_grant(
    ctx: AuthContext,
    audiences: Sequence[Audience],
    client_id: UUID,
    engagement_id: UUID | None,
    entity_id: UUID | None,
) -> UUID | None:
    for grant in await active_grants(ctx.tenant, ctx.user_id):
        facts = await scope_facts(ctx.tenant, grant.scope_kind, grant.scope_id)
        if facts is None or facts.client_id != client_id:
            continue
        for audience in audiences:
            if covers(
                grant.role,
                grant.scope_kind,
                grant.scope_id,
                facts.client_id,
                facts.engagement_id,
                facts.work_item_id,
                audience,
                engagement_id,
                entity_id,
            ):
                return grant.id
    return None


async def reader_version(ctx: AuthContext, deliverable_id: UUID, version_no: int) -> ReaderVersion:
    """The version for a client person holding an audience grant; `NotFound` for anyone else."""
    if ctx.tenant.actor_kind != "human" or not ctx.client:
        raise NotFound("deliverable")
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    _VERSION, {"deliverable_id": deliverable_id, "version_no": version_no}
                )
            )
            .mappings()
            .first()
        )
        # End pass (DEC-2716): published means its `published` event exists, not only the row.
        if row is None or row["withdrawn"] or not row["published"]:
            raise NotFound("deliverable")
        audiences = [
            Audience(str(a.scope_kind), a.scope_id)
            for a in (await session.execute(_AUDIENCES, {"id": deliverable_id})).all()
        ]
        contacts = await grant_contact_ids(session, ctx.user_id)
    grant = await first_covering_grant(
        ctx, audiences, row["client_id"], row["engagement_id"], row["client_entity_id"]
    )
    if grant is None or not contacts:
        raise NotFound("deliverable")
    return ReaderVersion(
        deliverable_id=row["deliverable_id"],
        version_id=row["version_id"],
        version_no=row["version_no"],
        evidence_version_id=row["evidence_version_id"],
        is_draft=row["is_draft"],
        watermarked=bool(row["draft_render"]),
        page_count=row["page_count"],
        kind=row["kind"],
        title=row["title"],
        client_id=row["client_id"],
        engagement_id=row["engagement_id"],
        work_item_id=row["work_item_id"],
        tri=row["kind"] in TRI_KINDS or row["source_module"] == "tax",
        contact_id=contacts[0],
        grant_id=grant,
    )


# The audit trail places a deliverable version on its engagement (R-02-T07, S30 end pass); a
# client-level deliverable has none and stays with the firm-wide rows readers see under ADM-07.
AUDIT_KINDS: Final = frozenset({"deliverable_version"})
_OWNERS = text(
    "SELECT v.id, d.engagement_id FROM deliverable_versions v "
    "JOIN deliverables d ON d.id = v.deliverable_id WHERE v.id = ANY(:ids)"
)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    del kind
    if not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(_OWNERS, {"ids": list(ids)})
        return {found: owned for found, owned in rows if owned is not None}


@dataclass(frozen=True)
class DeliverableScope:
    engagement_id: UUID | None
    client_id: UUID
    work_item_id: UUID | None


async def deliverable_scope(
    tenant: TenantContext, deliverable_id: UUID
) -> DeliverableScope | None:
    """R-02-T22: a deliverable's engagement, client and work item, for an anchor provider whose
    caller authorises its own action on them (a firm member replying on a page comment)."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT engagement_id, client_id, work_item_id FROM deliverables "
                    "WHERE id = :id"
                ),
                {"id": deliverable_id},
            )
        ).first()
    if row is None:
        return None
    return DeliverableScope(row.engagement_id, row.client_id, row.work_item_id)
