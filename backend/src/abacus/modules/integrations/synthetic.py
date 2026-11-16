"""The synthetic seed of Connect installs (W-01-T11; SPEC-659 AC-1 to AC-3, AC-20; DF-34).

The scenario loader replays the Brightwater Hale `connect` slice through these: a firm or personal
install at its E0 state, and the install's timeline events (CCH Axcess Tax: connected Jan 14,
2026 9:12 AM by Felix Andersen, through Sep 14). Refused outside the synthetic environments and
for a firm that is not synthetic; no secret is stored (the fakes need none). Platform content
(the catalogue) is the operator's import, never seeded here: an install of a key the catalogue
does not hold fails on its foreign key.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import insert

from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import is_synthetic_firm
from abacus.modules.integrations.models import FirmIntegration, IntegrationEvent, UserIntegration
from abacus.modules.integrations.secrets import TARGET, USER_TARGET

ACTOR: Final = "integrations:scenario"
Scope = Literal["firm", "user"]


class SyntheticInstallRefused(Exception):
    """Not a synthetic environment, or not a synthetic firm."""


async def _system(tenant_id: UUID) -> TenantContext:
    tenant = TenantContext(tenant_id, "system", ACTOR)
    if settings().environment not in SYNTHETIC_ENVIRONMENTS or not await is_synthetic_firm(tenant):
        raise SyntheticInstallRefused(str(tenant_id))
    return tenant


async def seed_synthetic_install(
    tenant_id: UUID,
    *,
    catalog_key: str,
    scope: Scope,
    user_id: UUID | None,
    mode: str,
    status: str,
    connected_by: UUID | None,
    connected_at: datetime,
    last_sync_at: datetime | None,
    granted_scopes: Sequence[str],
    consent_version: int | None,
) -> UUID:
    """One install at its seeded state; its id."""
    tenant = await _system(tenant_id)
    async with uow(tenant) as tx:
        if scope == "firm":
            found = await tx.session.scalar(
                insert(FirmIntegration)
                .values(
                    tenant_id=tenant_id,
                    catalog_key=catalog_key,
                    status=status,
                    mode=mode,
                    created_by=connected_by,
                    status_changed_at=connected_at,
                    connected_by=connected_by,
                    connected_at=connected_at,
                    granted_scopes=list(granted_scopes),
                    consent_version=consent_version,
                )
                .returning(FirmIntegration.id)
            )
            target = TARGET
        else:
            if user_id is None:
                raise SyntheticInstallRefused("a personal install names its person")
            found = await tx.session.scalar(
                insert(UserIntegration)
                .values(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    catalog_key=catalog_key,
                    status=status,
                    status_changed_at=connected_at,
                    connected_at=connected_at,
                    granted_scopes=list(granted_scopes),
                    consent_version=consent_version,
                )
                .returning(UserIntegration.id)
            )
            target = USER_TARGET
        if found is None:
            raise SyntheticInstallRefused(catalog_key)
        tx.record("integration.seeded", target=Target(target, found), after=Ref(n=1))
    if last_sync_at is not None:
        await seed_synthetic_event(
            tenant_id,
            install_id=found,
            scope=scope,
            catalog_key=catalog_key,
            kind="synced",
            at=last_sync_at,
            actor=None,
        )
    return found


async def seed_synthetic_event(
    tenant_id: UUID,
    *,
    install_id: UUID,
    scope: Scope,
    catalog_key: str,
    kind: str,
    at: datetime,
    actor: UUID | None,
    code: str | None = None,
) -> None:
    """One timeline event of a seeded install (WB-11 c's health list)."""
    tenant = await _system(tenant_id)
    async with uow(tenant) as tx:
        await tx.session.execute(
            insert(IntegrationEvent).values(
                tenant_id=tenant_id,
                install_kind=scope,
                install_id=install_id,
                catalog_key=catalog_key,
                kind=kind,
                at=at,
                actor_user_id=actor,
                code=code,
            )
        )
        tx.record(
            "integration.event_seeded",
            target=Target(TARGET if scope == "firm" else USER_TARGET, install_id),
            after=Ref(n=1),
        )
