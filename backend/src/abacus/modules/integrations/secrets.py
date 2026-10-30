"""Sealed integration secrets (A-02-T12; ADR-035; P-65 / ADR-139; SPEC-333 AC-13.3).

An install's credentials are sealed with the tenant's key, with the install's row id
(`firm_integrations.id`, the owner) as associated data: a blob copied onto another install, or
into another firm, does not open. The plaintext is never logged, stored elsewhere or returned by
a route (Restricted, ADR-031). Erasing deletes the row, the only sealed copy, under the tenant
key (as `connection_secrets`, DEC-379): the tenant key is not destroyed, so this is not a key
destruction; a per-install data key that can be destroyed is follow-up work. Sealing and erasing
run in the caller's unit of work (after its `authorise`) and are audited by target id only.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import delete, insert, select

from abacus.kernel.crypto import key_service, open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, UnitOfWork
from abacus.modules.integrations.capabilities import write_capability
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
    """Delete the only sealed copy (a row delete under the tenant key). True when one was."""
    gone = await tx.session.scalar(
        delete(IntegrationSecret)
        .where(IntegrationSecret.firm_integration_id == firm_integration_id)
        .returning(IntegrationSecret.id)
    )
    if gone is not None:
        tx.record("integration_secret.erased", target=Target(TARGET, firm_integration_id))
    return gone is not None


async def connected_integration(tenant: TenantContext, catalog_key: str) -> UUID | None:
    """N-02-T18: the firm's connected install of `catalog_key` (DocuSeal's per-firm enablement),
    or None when it has none or it needs attention or was disconnected."""
    async with tenant_session(tenant) as session:
        return await session.scalar(
            select(FirmIntegration.id).where(
                FirmIntegration.catalog_key == catalog_key, FirmIntegration.status == "connected"
            )
        )


ESIGN_W7: Final = "esignature_envelope_send"
ESIGN_CATALOG: Final = "docuseal"  # ADR-342


async def esign_install_secret(tenant: TenantContext) -> bytes | None:
    """N-02-T18: the firm's opened DocuSeal install secret, only when the W7 capability is enabled
    (v1: never) and the install is connected; for the worker to give signatures (ADR-008)."""
    entry = write_capability(ESIGN_W7)
    if entry is None or not entry.enabled:
        return None
    install = await connected_integration(tenant, ESIGN_CATALOG)
    if install is None:
        return None
    return await open_secret(tenant, install)
