"""ADM-07's and AUD-29's labels for engagements and work items (Q-03-T235; DEC-3304): the name a
person sees on the engagement, read as the event's firm (the label index has no viewer). A
target whose event the reader may see may show its engagement's name; nothing Restricted."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import (
    AuditLabel,
    register_audit_noun,
    register_audit_tenant_labeler,
)


def _ids(values: Sequence[str]) -> list[UUID]:
    out: list[UUID] = []
    for value in values:
        try:
            out.append(UUID(value))
        except ValueError:
            continue
    return out


async def _named(tenant: TenantContext, sql: str, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
    wanted = _ids(ids)
    if not wanted:
        return {}
    async with tenant_session(tenant) as session:
        rows = (await session.execute(text(sql), {"ids": wanted})).all()
    return {str(r.id): AuditLabel(str(r.label), "confidential") for r in rows if r.label}


async def label_engagements(tenant: TenantContext, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
    return await _named(
        tenant, "SELECT id, name AS label FROM engagements WHERE id = ANY(:ids)", ids
    )


async def label_work_items(tenant: TenantContext, ids: Sequence[str]) -> Mapping[str, AuditLabel]:
    return await _named(
        tenant,
        "SELECT w.id, COALESCE(NULLIF(w.name, ''), e.name) AS label FROM work_items w "
        "JOIN engagements e ON e.id = w.engagement_id WHERE w.id = ANY(:ids)",
        ids,
    )


def register() -> None:
    register_audit_tenant_labeler("engagement", label_engagements)
    register_audit_tenant_labeler("work_item", label_work_items)
    register_audit_noun("engagement", "Engagement")
