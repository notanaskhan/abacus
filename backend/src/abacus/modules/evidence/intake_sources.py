"""Intake attachments as upload subjects (N-01-T12; N-01 §4.4; DEC-1058).

An intake attachment (communications' `inbox_attachments`, N-01-T09) runs the same upload steps
as an evidence version: extraction, the word layer, the PII scan and the masked preview. Its row
belongs to communications, so evidence never reads that table: communications registers the
resolver here, and the steps read the file's storage facts through it. An attachment belongs to
no engagement until it is filed, so its derived rows carry `inbox_attachment_id` and no
engagement (0370). Filing reuses them (`derivations_for_attachment`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext
from abacus.modules.evidence.models import EvidenceVersion, InboxFile
from abacus.modules.evidence.repository import get_inbox_file, get_version
from abacus.modules.evidence.workflow_types import INTAKE, VERSION


@dataclass(frozen=True)
class IntakeSource:
    """What an upload step reads of an intake attachment: identifiers and storage facts."""

    id: UUID
    tenant_id: UUID
    storage_key: str
    storage_version_id: str
    fingerprint: str
    size_bytes: int
    media_type: str
    # ADR-137: a portal intake sealed under its own data key keeps its derivations under it.
    detached_key: UUID | None = None
    engagement_id: None = None
    channel: str = "intake"
    status: str = "intake"


IntakeResolver = Callable[[TenantContext, UUID], Awaitable[IntakeSource | None]]
_resolver: IntakeResolver | None = None


def register_intake_source(resolver: IntakeResolver) -> None:
    """communications, at import: how an attachment's storage facts are read."""
    global _resolver
    _resolver = resolver


async def intake_source(tenant: TenantContext, attachment_id: UUID) -> IntakeSource | None:
    """The attachment's facts, or None when it is gone or no resolver is registered (an upload
    step then answers 404 and nothing is derived: fail closed)."""
    if _resolver is None:
        return None
    return await _resolver(tenant, attachment_id)


async def source_of(
    session: AsyncSession, tenant: TenantContext, kind: str, source_id: UUID
) -> EvidenceVersion | InboxFile | IntakeSource | None:
    """The upload a step works on, by its kind (VERSION, INBOX or INTAKE)."""
    if kind == VERSION:
        return await get_version(session, source_id)
    if kind == INTAKE:
        return await intake_source(tenant, source_id)
    return await get_inbox_file(session, source_id)


def target_type(kind: str) -> str:
    """The audit target an upload step's event names."""
    return {VERSION: "evidence_version", INTAKE: "inbox_attachment"}.get(kind, "inbox_file")
