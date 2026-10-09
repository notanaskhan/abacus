"""A request item's evidence for the firm's item page (SPEC-021; TASK-037).

Versions with their provenance and decisions, and each version's content as an audited,
fingerprint-verified download. Firm-side only (SPEC-021 Q4): client roles are refused here even
where the matrix's item conditions would let them read the item.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.logging import get_logger
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.repository import get_item, get_version, item_versions_with_decisions
from abacus.modules.evidence.service import read_version
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    authorise,
    engagement_role_of,
    names_of,
)
from abacus.modules.requests.api import read_item, read_item_versions

_CLIENT_ROLES = frozenset({"client_admin", "client_contributor"})
_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")
_EXTENSIONS = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "text/csv": "csv",
    "application/json": "json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
_log = get_logger(__name__)


class IntegrityFailed(DomainConflict):
    """The stored content doesn't match its fingerprint, or is missing (ADR-016)."""

    code = "integrity_failed"


@dataclass(frozen=True)
class DecisionSummary:
    decision: str
    reason_code: str | None
    decided_by: UUID | None
    decided_by_name: str
    decided_at: datetime


@dataclass(frozen=True)
class ItemVersion:
    id: UUID
    version_no: int
    method: str
    source: str
    period_start: date | None
    period_end: date | None
    pulled_at: datetime | None
    created_at: datetime
    size_bytes: int
    media_type: str
    fingerprint: str
    file_name: str | None
    uploaded_by: UUID | None
    uploaded_by_name: str
    decision: DecisionSummary | None


def _user(actor_id: str) -> UUID | None:
    try:
        return UUID(actor_id)
    except ValueError:
        return None


async def _firm_side(ctx: AuthContext, engagement_id: UUID) -> None:
    """SPEC-021 Q4: clients don't use these routes yet."""
    if await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id) in _CLIENT_ROLES:
        raise Forbidden("evidence.read", "role")


async def item_versions(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> list[ItemVersion]:
    """AC-1: the item's versions, newest first, with provenance and this item's decisions."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "evidence.read", engagement.resource())
    await _firm_side(ctx, engagement_id)
    await read_item(ctx.tenant, engagement_id, item_id)  # NotFound outside this engagement
    async with tenant_session(ctx.tenant) as session:
        rows = await item_versions_with_decisions(
            session, item_id, await read_item_versions(ctx.tenant, item_id)
        )
    people = {
        u
        for version, item, decision in rows
        for u in (
            _user(item.created_by_id) if version.method == "uploaded" else None,
            _user(decision.actor_id) if decision is not None else None,
        )
        if u is not None
    }
    names = await names_of(sorted(people, key=str))
    result: list[ItemVersion] = []
    for version, item, decision in rows:
        uploader = _user(item.created_by_id) if version.method == "uploaded" else None
        decider = _user(decision.actor_id) if decision is not None else None
        result.append(
            ItemVersion(
                version.id,
                version.version_no,
                version.method,
                version.source,
                version.period_start,
                version.period_end,
                version.pulled_at,
                version.created_at,
                version.size_bytes,
                version.media_type,
                version.fingerprint,
                item.title if version.method == "uploaded" else None,
                uploader,
                names.get(uploader, "") if uploader is not None else "",
                None
                if decision is None
                else DecisionSummary(
                    decision.decision,
                    decision.reason_code,
                    decider,
                    names.get(decider, "") if decider is not None else "",
                    decision.created_at,
                ),
            )
        )
    return result


@dataclass(frozen=True)
class Download:
    content: bytes
    media_type: str
    file_name: str


def download_name(title: str | None, version_no: int, period_end: date | None, media: str) -> str:
    extension = _EXTENSIONS.get(media, "bin")
    if title:
        safe = _UNSAFE.sub("_", title).strip(" ._") or "evidence"
        return safe if "." in safe else f"{safe}.{extension}"
    period = f"-{period_end.isoformat()}" if period_end is not None else ""
    return f"evidence-v{version_no}{period}.{extension}"


async def download(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> Download:
    """AC-2: the version's bytes for an attachment; authorised, audited and verified by
    `read_version`. A mismatch is refused, never served."""
    async with tenant_session(ctx.tenant) as session:
        version = await get_version(session, version_id)
        item = None if version is None else await get_item(session, version.evidence_item_id)
    if version is None or item is None or version.engagement_id != engagement_id:
        raise NotFound("evidence_version")
    await _firm_side(ctx, engagement_id)
    try:
        content = await read_version(ctx, version_id)
    except storage.IntegrityError:
        _log.error("evidence.integrity_failed", evidence_version_id=str(version_id))
        raise IntegrityFailed from None
    title = item.title if version.method == "uploaded" else None
    return Download(
        content,
        version.media_type,
        download_name(title, version.version_no, version.period_end, version.media_type),
    )
