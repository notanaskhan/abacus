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
from abacus.modules.engagements.service import client_of, get_ref, lock_ref
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.organisations.api import attest_client_of, contact_client

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
        return written.first() is not None


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


async def attest_of(tenant: TenantContext, engagement_id: UUID) -> bool | None:
    """F-03-T24 `attest_client`: whether the engagement's client is an attest client (DEC-128)."""
    client = await client_of(tenant, engagement_id)
    return None if client is None else await attest_client_of(tenant, client)
