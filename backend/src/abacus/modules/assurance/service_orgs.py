"""A-04-T07: the service-organization inventory AUD-04 and AUD-10 share (A-04 §4.2 M2, AC7.1;
DEC-1867).

One row per organization on the audit work item (0613's `service_organizations`). A person adds
one (409 `duplicate_name` for a name the work item already holds) and edits its services,
relevance and evidence type against the version they saw (409 `version_conflict`). The status
moves with the SOC work (A-04-T25, T31), never here. Writes are audited `service_org.created`
and `service_org.edited`. The routes have authorised `service_org.read` or `service_org.edit`
and the flags.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import FetchedValue, func, insert, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.clock import now
from abacus.kernel.db import Base, TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import assurance_item_id
from abacus.modules.identity.api import AuthContext


class ServiceOrganization(Base):
    __tablename__ = "service_organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    name: Mapped[str]
    services: Mapped[str] = mapped_column(server_default=FetchedValue())
    relevant: Mapped[bool] = mapped_column(server_default=FetchedValue())
    evidence_type: Mapped[str] = mapped_column(server_default=FetchedValue())
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    subservice_orgs: Mapped[list[dict[str, Any]]] = mapped_column(  # Any: JSON
        JSONB, server_default=FetchedValue()
    )
    third_party_contact_id: Mapped[UUID | None]
    soc_report_id: Mapped[UUID | None]
    row_version: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class DuplicateName(DomainConflict):
    """The work item already lists an organization by this name."""

    code = "duplicate_name"


class OrganizationMoved(DomainConflict):
    """The organization changed since the caller read it."""

    code = "version_conflict"


async def _work_item(ctx: AuthContext, engagement_id: UUID) -> UUID:
    found = await assurance_item_id(ctx.tenant, engagement_id)
    if found is None:
        raise NotFound("service_organization")
    return found


async def organizations(ctx: AuthContext, engagement_id: UUID) -> list[ServiceOrganization]:
    work_item = await _work_item(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        return list(
            (
                await session.execute(
                    select(ServiceOrganization)
                    .where(ServiceOrganization.work_item_id == work_item)
                    .order_by(func.lower(ServiceOrganization.name))
                )
            ).scalars()
        )


async def organization(ctx: AuthContext, engagement_id: UUID, org_id: UUID) -> ServiceOrganization:
    work_item = await _work_item(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        found = await session.get(ServiceOrganization, org_id)
    if found is None or found.work_item_id != work_item:
        raise NotFound("service_organization")
    return found


async def add(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    name: str,
    services: str,
    relevant: bool,
    evidence_type: str,
) -> ServiceOrganization:
    work_item = await _work_item(ctx, engagement_id)
    clean = name.strip()
    try:
        async with uow(ctx.tenant) as tx:
            # Only the columns the app role inserts (0613): the rest are the server's.
            org_id = (
                await tx.session.execute(
                    insert(ServiceOrganization)
                    .values(
                        tenant_id=ctx.tenant_id,
                        engagement_id=engagement_id,
                        work_item_id=work_item,
                        name=clean,
                        services=services.strip(),
                        relevant=relevant,
                        evidence_type=evidence_type,
                    )
                    .returning(ServiceOrganization.id)
                )
            ).scalar_one()
            tx.record(
                "service_org.created",
                target=Target("service_organization", org_id),
                after=Ref(relevant=int(relevant)),
            )
    except IntegrityError as exc:
        if "service_organizations_tenant_id_work_item_id_name_key" in str(exc.orig):
            raise DuplicateName from None
        raise
    return await organization(ctx, engagement_id, org_id)


async def edit(
    ctx: AuthContext,
    engagement_id: UUID,
    org_id: UUID,
    *,
    expected_version: int,
    services: str | None,
    relevant: bool | None,
    evidence_type: str | None,
) -> ServiceOrganization:
    work_item = await _work_item(ctx, engagement_id)
    async with uow(ctx.tenant) as tx:
        found = (
            await tx.session.execute(
                select(ServiceOrganization)
                .where(
                    ServiceOrganization.id == org_id,
                    ServiceOrganization.work_item_id == work_item,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if found is None:
            raise NotFound("service_organization")
        if found.row_version != expected_version:
            raise OrganizationMoved(facts={"current": found.row_version})
        if services is not None:
            found.services = services.strip()
        if relevant is not None:
            found.relevant = relevant
        if evidence_type is not None:
            found.evidence_type = evidence_type
        found.row_version = found.row_version + 1
        found.updated_at = await now(ctx.tenant)
        tx.record(
            "service_org.edited",
            target=Target("service_organization", org_id),
            after=Ref(relevant=int(found.relevant), row_version=found.row_version),
        )
    return await organization(ctx, engagement_id, org_id)


AUDIT_KINDS = frozenset({"service_organization"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `service_organization` rows named by an audit event: id -> the owning engagement
    (SPEC-304; DEC-121). Unknown ids are left out."""
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(ServiceOrganization.id, ServiceOrganization.engagement_id).where(
                ServiceOrganization.id.in_(list(ids))
            )
        )
        return {found: owned for found, owned in rows}
