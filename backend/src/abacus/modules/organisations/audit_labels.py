"""ADM-07's and AUD-29's labels for clients (Q-03-T235; DEC-3304): the client's name, read as the
event's firm. Confidential, never Restricted."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import AuditLabel, register_audit_tenant_labeler


async def label_clients(tenant: TenantContext, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
    wanted: list[UUID] = []
    for value in ids:
        try:
            wanted.append(UUID(value))
        except ValueError:
            continue
    if not wanted:
        return {}
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text("SELECT id, name FROM clients WHERE id = ANY(:ids)"), {"ids": wanted}
            )
        ).all()
    return {str(r.id): AuditLabel(str(r.name), "confidential") for r in rows if r.name}


def register() -> None:
    register_audit_tenant_labeler("client", label_clients)
