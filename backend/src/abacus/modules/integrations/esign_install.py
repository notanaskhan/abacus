"""A firm's DocuSeal install (N-02-T18 install path; ADR-342; TASK-2152; DEC-1279).

The adapter runs for a firm only with a connected `docuseal` install whose sealed secret opens
(`secrets.esign_install_secret`, which also needs W7). These are the operator's writes, each one
unit of work in the operator's context (`operator:<handle>`, INV-5), called by
`abacus_tools.esign_install`:

- `connect_esign_install`: the firm's install (`mode token`, `created_by` a member of the firm,
  the person who asked) and its sealed secret; refused while a live install exists.
- `rotate_esign_secret`: the live install's secret erased and sealed again (a new key).
- `disconnect_esign_install`: the secret erased (the only sealed copy) and the install marked
  `disconnected`; a later connect makes a new install.
- `esign_install_state`: whether the firm has a connected install (never the key).

The secret is DocuSeal's account JSON (`api_key`, `api_host`), Restricted: never logged, never
returned. Audit rows name the install by id only.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import insert, select, update

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.integrations.models import FirmIntegration
from abacus.modules.integrations.secrets import (
    ESIGN_CATALOG,
    TARGET,
    connected_integration,
    erase_secret,
    store_secret,
)

_LIVE: Final = ("connected", "needs_attention")


class EsignInstallExists(DomainConflict):
    """The firm already has a live DocuSeal install: rotate or disconnect it instead."""

    code = "esign_install_exists"


async def _live(tenant: TenantContext) -> UUID | None:
    async with tenant_session(tenant) as session:
        return await session.scalar(
            select(FirmIntegration.id).where(
                FirmIntegration.catalog_key == ESIGN_CATALOG, FirmIntegration.status.in_(_LIVE)
            )
        )


async def connect_esign_install(tenant: TenantContext, created_by: UUID, secret: bytes) -> UUID:
    """The firm's DocuSeal install and its sealed secret, in one unit of work."""
    if await _live(tenant) is not None:
        raise EsignInstallExists(ESIGN_CATALOG)
    async with uow(tenant) as tx:
        install = await tx.session.scalar(
            insert(FirmIntegration)
            .values(
                tenant_id=tenant.tenant_id,
                catalog_key=ESIGN_CATALOG,
                status="connected",
                mode="token",
                created_by=created_by,
            )
            .returning(FirmIntegration.id)
        )
        if install is None:  # an INSERT … RETURNING returns its row; never reached
            raise NotFound("firm_integration")
        await store_secret(tx, tenant.tenant_id, install, secret)
        tx.record("firm_integration.connected", target=Target(TARGET, install))
    return install


async def rotate_esign_secret(tenant: TenantContext, secret: bytes) -> UUID:
    """The live install's secret replaced: the old sealed copy erased, the new one sealed."""
    install = await _live(tenant)
    if install is None:
        raise NotFound("firm_integration")
    async with uow(tenant) as tx:
        await erase_secret(tx, install)
        await store_secret(tx, tenant.tenant_id, install, secret)
    return install


async def disconnect_esign_install(tenant: TenantContext) -> UUID:
    """The secret erased and the install disconnected; nothing is sent for the firm after."""
    install = await _live(tenant)
    if install is None:
        raise NotFound("firm_integration")
    async with uow(tenant) as tx:
        await erase_secret(tx, install)
        await tx.session.execute(
            update(FirmIntegration)
            .where(FirmIntegration.id == install)
            .values(status="disconnected", version=FirmIntegration.version + 1)
        )
        tx.record("firm_integration.disconnected", target=Target(TARGET, install))
    return install


async def esign_install_state(tenant: TenantContext) -> str:
    """`connected` or `none`: whether the adapter could find the firm's install."""
    return "connected" if await connected_integration(tenant, ESIGN_CATALOG) else "none"
