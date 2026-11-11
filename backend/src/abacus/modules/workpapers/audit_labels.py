"""ADM-07's and AUD-29's labels for working papers (Q-03-T235; DEC-3304): "EBP-04 Contributions &
Remittance", read as the event's firm. The code and title are the firm's own; internal."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import AuditLabel, register_audit_tenant_labeler


async def label_workpapers(tenant: TenantContext, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
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
                text("SELECT id, code, title FROM workpapers WHERE id = ANY(:ids)"),
                {"ids": wanted},
            )
        ).all()
    return {str(r.id): AuditLabel(f"{r.code} {r.title}".strip(), "internal") for r in rows}


def register() -> None:
    register_audit_tenant_labeler("workpaper", label_workpapers)
