"""Sealed integration secrets (A-02-T12; ADR-035; P-65 / ADR-139; SPEC-333 AC-13.3).

An install's credentials are sealed with the tenant's key, with the install's row id
(`firm_integrations.id`, the owner) as associated data: a blob copied onto another install, or
into another firm, does not open. The plaintext is never logged, stored elsewhere or returned by
a route (Restricted, ADR-031). Erasing deletes the only copy: a crypto-erase. Sealing and erasing
run in the caller's unit of work (after its `authorise`) and are audited by target id only.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, insert, select

from abacus.kernel.crypto import key_service, open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, UnitOfWork
from abacus.modules.integrations.models import FirmIntegration, IntegrationSecret

TARGET = "firm_integration"


def binding(firm_integration_id: UUID) -> str:
    """The associated data beside the tenant: the owner row's id."""
    return f"firm_integration:{firm_integration_id}"


async def store_secret(
    tx: UnitOfWork, tenant_id: UUID, firm_integration_id: UUID, plaintext: bytes
) -> UUID:
    """Seal and store an install's secret (one per install)."""
    owner = await tx.session.scalar(
        select(FirmIntegration.id).where(FirmIntegration.id == firm_integration_id)
    )
    if owner is None:
        raise NotFound("firm_integration")
    sealed = await seal(tenant_id, plaintext, binding(firm_integration_id))
    secret_id = await tx.session.scalar(
        insert(IntegrationSecret)
        .values(
            tenant_id=tenant_id,
            firm_integration_id=firm_integration_id,
            sealed=sealed,
            key_id=key_service().key_id(tenant_id),
        )
        .returning(IntegrationSecret.id)
    )
    if secret_id is None:  # an INSERT … RETURNING returns its row; never reached
        raise NotFound("integration_secret")
    tx.record("integration_secret.stored", target=Target(TARGET, firm_integration_id))
    return secret_id


async def open_secret(tenant: TenantContext, firm_integration_id: UUID) -> bytes | None:
    """The plaintext for an adapter call, or None when there is none (erased)."""
    async with tenant_session(tenant) as session:
        sealed = await session.scalar(
            select(IntegrationSecret.sealed).where(
                IntegrationSecret.firm_integration_id == firm_integration_id
            )
        )
    if sealed is None:
        return None
    return await open_sealed(tenant.tenant_id, sealed, binding(firm_integration_id))


async def erase_secret(tx: UnitOfWork, firm_integration_id: UUID) -> bool:
    """Crypto-erase: delete the only sealed copy. True when one was there."""
    gone = await tx.session.scalar(
        delete(IntegrationSecret)
        .where(IntegrationSecret.firm_integration_id == firm_integration_id)
        .returning(IntegrationSecret.id)
    )
    if gone is not None:
        tx.record("integration_secret.erased", target=Target(TARGET, firm_integration_id))
    return gone is not None
