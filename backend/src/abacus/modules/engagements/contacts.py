"""Engagement contact designations (F-03-T25; DEC-63): a client's contact named on one
engagement as its approver of record, SKE designee, signing officer, plan administrator, TCWG
member or primary contact. The designations are letter variables and mirror onto client grants
(F-03-T26). Insert-only: a designation is never edited."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.engagements.repository import get_engagement
from abacus.modules.engagements.service import client_of, get_ref, lock_ref
from abacus.modules.identity.api import (
    AccessChanged,
    AuthContext,
    InvitationParties,
    ScopeFacts,
    authorise,
    contact_user_ids,
    grant_contact_ids,
)
from abacus.modules.organisations.api import (
    attest_client_of,
    client_exists,
    client_names,
    client_of_entity,
    contact_client,
    contact_facts,
    contacts_of_user,
)

Designation = Literal[
    "approver_of_record",
    "ske_designee",
    "signing_officer",
    "plan_administrator",
    "tcwg_member",
    "primary_contact",
]

_INSERT = text(
    "INSERT INTO engagement_contacts "
    "(tenant_id, engagement_id, contact_id, designation, designated_by) "
    "VALUES (:tenant_id, :engagement_id, :contact_id, :designation, :designated_by) "
    "ON CONFLICT DO NOTHING RETURNING contact_id"
)
# DEC-34, DEC-63: the designations that sign or approve, so require the portal's second step.
MFA_DESIGNATIONS: frozenset[str] = frozenset(
    {"approver_of_record", "signing_officer", "ske_designee"}
)
_DESIGNATED = text(
    "SELECT EXISTS (SELECT 1 FROM engagement_contacts WHERE contact_id = ANY(:ids) "
    "AND designation = ANY(:designations))"
)
_OF = text(
    "SELECT contact_id, designation, designated_by, designated_at FROM engagement_contacts "
    "WHERE engagement_id = :engagement_id ORDER BY designation, contact_id"
)


@dataclass(frozen=True)
class EngagementContact:
    contact_id: UUID
    designation: str
    designated_by: UUID
    designated_at: datetime


async def designate_contact(
    ctx: AuthContext, engagement_id: UUID, contact_id: UUID, designation: Designation
) -> bool:
    """Name the engagement's client's contact in a designation (engagement partner or manager).
    `NotFound` when the contact isn't the engagement's client's. Whether a row was written
    (False: already designated)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "engagement_contact.designate", ref.resource())
        if await contact_client(tx.session, contact_id) != ref.client_id:
            raise NotFound("contact")
        written = await tx.session.execute(
            _INSERT,
            {
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "contact_id": contact_id,
                "designation": designation,
                "designated_by": ctx.user_id,
            },
        )
        tx.record("engagement_contact.designated", target=Target("engagement", engagement_id))
        added = written.first() is not None
        if added and designation in MFA_DESIGNATIONS:
            # P-08-T17: the person now needs the second step, so their portal sessions and
            # trusted devices end (identity consumes `access.changed`).
            facts = (await contact_facts(tx.session, [contact_id])).get(contact_id)
            users = set(await contact_user_ids(tx.session, contact_id))
            if facts is not None and facts.user_id is not None:
                users.add(facts.user_id)
            for user_id in sorted(users):
                tx.emit(AccessChanged(user_id=user_id))
        return added


async def designations_of(session: AsyncSession, engagement_id: UUID) -> list[EngagementContact]:
    """The engagement's designations, for a caller that authorised `client_contact.read`."""
    rows = await session.execute(_OF, {"engagement_id": engagement_id})
    return [
        EngagementContact(r.contact_id, str(r.designation), r.designated_by, r.designated_at)
        for r in rows
    ]


async def engagement_contacts(ctx: AuthContext, engagement_id: UUID) -> list[EngagementContact]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "client_contact.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        return await designations_of(session, engagement_id)


async def client_contact_names(
    tenant: TenantContext, engagement_id: UUID, contact_ids: list[UUID]
) -> dict[UUID, str]:
    """P-06-T07 (binder recipients): which of `contact_ids` are the engagement's client's
    contacts, with their names. Others (another client's, unknown) are left out. For a caller
    that authorised an action on the engagement."""
    client = await client_of(tenant, engagement_id)
    if client is None or not contact_ids:
        return {}
    async with tenant_session(tenant) as session:
        found = await contact_facts(session, contact_ids)
    return {cid: f.display_name for cid, f in found.items() if f.client_id == client}


async def client_contact_organisations(
    tenant: TenantContext, engagement_id: UUID, contact_ids: list[UUID]
) -> list[str]:
    """R-01-T07 (POR-03 i, "Some requests go to Keystone, Harborline … directly"): the distinct
    organisation names of those of `contact_ids` that are the engagement's client's contacts, in
    name order; a contact with no organisation is left out (never a person's name). For a caller
    that authorised a read of the engagement."""
    client = await client_of(tenant, engagement_id)
    if client is None or not contact_ids:
        return []
    async with tenant_session(tenant) as session:
        found = await contact_facts(session, contact_ids)
    return sorted(
        {
            f.organisation_name
            for f in found.values()
            if f.client_id == client and f.organisation_name
        },
        key=str.casefold,
    )


async def client_contact_organisations_of_users(
    tenant: TenantContext, engagement_id: UUID, user_ids: list[UUID]
) -> dict[UUID, str]:
    """R-01-T07 (security review): for each of `user_ids` that is the portal user of one of the
    engagement's client's contacts with an organisation, that organisation's name ("Harborline"):
    how a third party's upload is attributed to a client, never by a person's name. For a caller
    that authorised a read of the engagement."""
    client = await client_of(tenant, engagement_id)
    if client is None or not user_ids:
        return {}
    found: dict[UUID, str] = {}
    async with tenant_session(tenant) as session:
        for user_id in user_ids:
            facts = await contact_facts(session, await contacts_of_user(session, user_id))
            names = sorted(
                f.organisation_name
                for f in facts.values()
                if f.client_id == client and f.organisation_name
            )
            if names:
                found[user_id] = names[0]
    return found


async def contact_portal_user(
    tenant: TenantContext, engagement_id: UUID, contact_id: UUID
) -> UUID | None:
    """P-06-T10 (delegation): the portal user of one of the engagement's client's contacts, or
    None (another client's, unknown, or not signed in yet). For a caller that authorised."""
    client = await client_of(tenant, engagement_id)
    if client is None:
        return None
    async with tenant_session(tenant) as session:
        found = (await contact_facts(session, [contact_id])).get(contact_id)
    return found.user_id if found is not None and found.client_id == client else None


async def attest_of(tenant: TenantContext, engagement_id: UUID) -> bool | None:
    """F-03-T24 `attest_client`: whether the engagement's client is an attest client (DEC-128)."""
    client = await client_of(tenant, engagement_id)
    return None if client is None else await attest_client_of(tenant, client)


# --- F-03-T26: the client-access scopes engagements resolves (ADR-146) -------------------------

_WORK_ITEM = text("SELECT client_id, engagement_id FROM work_items WHERE id = :id")


async def work_item_scope(tenant: TenantContext, work_item_id: UUID) -> ScopeFacts | None:
    """A `work_item` grant's scope: the work item, inside its engagement and client."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_WORK_ITEM, {"id": work_item_id})).first()
    if row is None:
        return None
    return ScopeFacts(row.client_id, engagement_id=row.engagement_id, work_item_id=work_item_id)


async def client_scope(tenant: TenantContext, client_id: UUID) -> ScopeFacts | None:
    """A `client` grant's scope: every engagement of the client."""
    return ScopeFacts(client_id) if await client_exists(tenant, client_id) else None


async def client_entity_scope(tenant: TenantContext, entity_id: UUID) -> ScopeFacts | None:
    """A `client_entity` grant's scope: its client's facts. Its engagement role covers only the
    entity's engagements (DEC-211), so `scope_only` never reaches past them."""
    client_id = await client_of_entity(tenant, entity_id)
    return ScopeFacts(client_id) if client_id is not None else None


async def contact_ids_of_user(tenant: TenantContext, user_id: UUID) -> frozenset[UUID]:
    """T-02-T22: the person's contacts in the firm (linked by `contacts.user_id` or named by one
    of their grants), for an addressee check (an inquiry is its addressee's only)."""
    async with tenant_session(tenant) as session:
        return frozenset(await contacts_of_user(session, user_id)) | frozenset(
            await grant_contact_ids(session, user_id)
        )


async def mfa_designated(tenant: TenantContext, user_id: UUID) -> bool:
    """The MFA floor's `engagement_designation` predicate (P-08-T17): whether any of the person's
    contacts in the firm (linked by `contacts.user_id` or named by one of their grants) is
    designated to sign or approve on any engagement."""
    async with tenant_session(tenant) as session:
        contact_ids = sorted(
            set(await contacts_of_user(session, user_id))
            | set(await grant_contact_ids(session, user_id))
        )
        if not contact_ids:
            return False
        found = await session.execute(
            _DESIGNATED, {"ids": contact_ids, "designations": sorted(MFA_DESIGNATIONS)}
        )
        return bool(found.scalar_one())


async def invitation_parties(
    tenant: TenantContext, engagement_id: UUID, contact_id: UUID | None
) -> InvitationParties | None:
    """POR-01 d's names for an invitation to the engagement (P-08-T18): the engagement's client
    entity as the scope, and the invited contact's name and organisation when it is the
    engagement client's. None for an engagement outside the firm."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
        if engagement is None:
            return None
        names = await client_names(session, [engagement.client_entity_id])
        found = (
            (await contact_facts(session, [contact_id])).get(contact_id)
            if contact_id is not None
            else None
        )
    entity = names.get(engagement.client_entity_id)
    if entity is None:
        return None
    if found is None or found.client_id != engagement.client_id:
        return InvitationParties(entity.client_entity_name)
    return InvitationParties(
        entity.client_entity_name, found.display_name, found.organisation_name
    )
