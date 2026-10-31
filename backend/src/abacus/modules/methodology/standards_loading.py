"""Loading a firm's standards the way the import endpoints do (K-02-T18; K-02 §3 F5; DEC-1472).

The scenario loader (and a firm's onboarding script) may only use `methodology.api`, so the
import endpoint's path is exposed here as calls: create a standard, read a workbook in the
isolated child exactly as `POST /v1/standards/{id}/imports` does and draft its payload, and
publish a numbered draft as its owner. Nothing here bypasses a check: each call is the service
function the route calls, with the caller's own authority (ADR-052, INV-1).
"""

from __future__ import annotations

import asyncio
from datetime import date
from uuid import UUID

from abacus.kernel.errors import NotFound
from abacus.kernel.isolation import run_isolated
from abacus.modules.identity.api import AuthContext
from abacus.modules.methodology import standards, standards_import
from abacus.modules.methodology.standards_contract import (
    StandardCreateIn,
    StandardOut,
    StandardPublishIn,
    StandardVersionOut,
    StandardVersionSummaryOut,
)


async def create_standard(
    ctx: AuthContext, *, key: str, name: str, kind: str, owner_id: UUID
) -> StandardOut:
    return await standards.create_standard(
        ctx,
        StandardCreateIn.model_validate(
            {"key": key, "name": name, "kind": kind, "owner_id": owner_id}
        ),
    )


async def standard_by_key(ctx: AuthContext, key: str) -> StandardOut:
    found = next((s for s in await standards.list_standards(ctx, None) if s.key == key), None)
    if found is None:
        raise NotFound("firm_standard")
    return found


def standard_workbook(kind: str, title: str, payload: dict[str, object]) -> bytes:
    """A payload in the import format (the export's bytes)."""
    return standards_import.export_workbook(kind, title, payload)


async def import_standard_workbook(
    ctx: AuthContext, standard_id: UUID, data: bytes
) -> StandardVersionSummaryOut:
    """The import endpoint's path: the workbook read in the isolated child, then a draft."""
    kind = (await standards.standard_detail(ctx, standard_id, None)).standard.kind
    payload, problems = await asyncio.to_thread(
        run_isolated, standards_import.read_payload_isolated, kind, data, False
    )
    if payload is None:
        raise standards_import.ImportInvalid(problems)
    return await standards.import_draft(ctx, standard_id, payload)


async def publish_standard(
    ctx: AuthContext, standard_id: UUID, *, effective_from: date, change_summary: str
) -> StandardVersionOut:
    """Publish the standard's draft as its owner, at the draft's row version."""
    detail = await standards.standard_detail(ctx, standard_id, None)
    draft = detail.standard.draft_version
    if draft is None:
        raise NotFound("firm_standard_version")
    version = await standards.version_detail(ctx, standard_id, draft.id)
    return await standards.publish_version(
        ctx,
        standard_id,
        draft.id,
        StandardPublishIn(effective_from=effective_from, change_summary=change_summary),
        version.row_version,
    )


__all__ = [
    "create_standard",
    "import_standard_workbook",
    "publish_standard",
    "standard_by_key",
    "standard_workbook",
]
