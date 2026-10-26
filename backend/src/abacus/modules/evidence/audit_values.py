"""Audit values for evidence versions and PII reveals (G-02-T09 gap; SPEC-349 AC-5, AC-10, AC-11;
DEC-60, DEC-459).

ADM-07's values section for events on `evidence_version` (and `pii_reveal`) targets, resolved at
read time for a viewer `audit_trail.values` has already let through (flag on, need to know).
Facts the event pins only, never a value that may have changed since:

- every row's item is the evidence item's title (Confidential; the file as the firm sees it);
- `pii.revealed` (the pii_reveal source): the region's kind and its masked token
  (`mask_token(kind, last4)`, `•••-••-2208`), Restricted and masked. The sealed value is never
  opened here: the token is built from the stored last four digits;
- a review assignment's person refs (`user_id` before and after): display names.

Anything else is `unavailable` ("Values not available"). When the event names an engagement,
the version must belong to it; when it names none (most writers pass no `Scope`), the viewer
must hold `engagement.read` on the version's own engagement (security review M1). Otherwise
`unavailable` (fail closed).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import RowMapping, text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.evidence.masking import mask_token
from abacus.modules.identity.api import (
    AuthContext,
    allowed_actions,
    engagement_resource,
    names_of,
)
from abacus.modules.platform.api import AuditEventRef, AuditValueRow, AuditValues

UNAVAILABLE: Final = AuditValues("unavailable")
CONTENT_READ: Final = "engagement.read"
_VERSION = text(
    "SELECT v.engagement_id, i.title FROM evidence_versions v "
    "JOIN evidence_items i ON i.id = v.evidence_item_id WHERE v.id = :id"
)
_REVEAL = text(
    "SELECT r.evidence_version_id, g.kind, g.last4 FROM pii_reveals r "
    "JOIN pii_regions g ON g.id = r.region_id WHERE r.id = :id"
)


def _uuid(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


async def _may_read(viewer: AuthContext, engagement_id: UUID) -> bool:
    """Security review M1: an event with no engagement of its own is not firm-level content when
    its target belongs to one; the reader must hold that engagement's content read, as
    `audit_trail.values` requires on an engagement event (a probe: no `authz.denied` logged)."""
    try:
        resource = await engagement_resource(viewer.tenant, engagement_id)
    except NotFound:
        return False
    return CONTENT_READ in await allowed_actions(viewer, resource, (CONTENT_READ,))


async def _person_rows(event: AuditEventRef, item: str) -> tuple[AuditValueRow, ...]:
    before = _uuid((event.before_ref or {}).get("user_id"))
    after = _uuid((event.after_ref or {}).get("user_id"))
    if before is None and after is None:
        return ()
    names = await names_of(sorted({u for u in (before, after) if u is not None}, key=str))
    return (
        AuditValueRow(
            field="user_id",
            item_label=item,
            before=names.get(before) if before is not None else None,
            after=names.get(after) if after is not None else None,
            classification="confidential",
        ),
    )


async def _resolve(
    viewer: AuthContext, event: AuditEventRef, version_id: UUID | None, reveal_id: UUID | None
) -> AuditValues:
    async with tenant_session(viewer.tenant) as session:
        reveal: RowMapping | None = None
        if reveal_id is not None:
            reveal = (await session.execute(_REVEAL, {"id": reveal_id})).mappings().first()
            if reveal is None:
                return UNAVAILABLE
            found = _uuid(reveal["evidence_version_id"])
            if version_id is not None and found != version_id:
                return UNAVAILABLE  # the event's reveal is not of its target version
            version_id = found
        if version_id is None:
            return UNAVAILABLE
        version = (await session.execute(_VERSION, {"id": version_id})).mappings().first()
    if version is None:
        return UNAVAILABLE
    if event.engagement_id is not None:
        if version["engagement_id"] != event.engagement_id:
            return UNAVAILABLE
    elif not await _may_read(viewer, version["engagement_id"]):
        return UNAVAILABLE  # an unscoped event on this version: its engagement's read decides
    item = str(version["title"])
    if reveal is not None:
        kind = str(reveal["kind"])
        last4 = reveal["last4"]
        return AuditValues(
            "resolved",
            rows=(
                AuditValueRow(
                    field=kind,
                    item_label=item,
                    before=None,
                    after=mask_token(kind, str(last4) if last4 is not None else None),
                    masked=True,
                    classification="restricted",
                ),
            ),
        )
    rows = await _person_rows(event, item)
    return AuditValues("resolved", rows=rows) if rows else UNAVAILABLE


async def evidence_version_values(viewer: AuthContext, event: AuditEventRef) -> AuditValues:
    """`evidence_version` targets: a reveal's masked value, or a review assignment's people."""
    version_id = _uuid(event.target_id)
    if version_id is None:
        return UNAVAILABLE
    reveal_id = (
        _uuid((event.after_ref or {}).get("reveal_id")) if event.action == "pii.revealed" else None
    )
    if event.action == "pii.revealed" and reveal_id is None:
        return UNAVAILABLE
    return await _resolve(viewer, event, version_id, reveal_id)


async def pii_reveal_values(viewer: AuthContext, event: AuditEventRef) -> AuditValues:
    """`pii_reveal` targets: the reveal itself, masked."""
    reveal_id = _uuid(event.target_id)
    if reveal_id is None:
        return UNAVAILABLE
    return await _resolve(viewer, event, None, reveal_id)


__all__ = ["evidence_version_values", "pii_reveal_values"]
