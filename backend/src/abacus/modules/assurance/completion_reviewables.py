"""AUD-17's planning and completion rows that weren't reviewables (S28, TASK-3400, DEC-2399).

The design's matrix signs Materiality, Findings and the Completion Checklist at their levels, and
none was a C3 reviewable, so none could be signed or reach the G5 gate. Each is one row per audit
work item, its content hash computed from its own records, so any change leaves its sign-offs
stale:

- `materiality`: the newest version (its number, status and figures); its preparer proposed it.
- `audit_findings`: every finding's ref, kind, route and evaluation; their raisers prepared them.
- `completion_checklist`: every item's key, status and evidence; it has no preparer of its own.

A row appears once its object exists (a materiality version, a finding, a checklist item).
"""

from __future__ import annotations

import json
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.review.api import Json, Reviewable, ReviewableFacts, content_hash

MATERIALITY: Final = "materiality"
FINDINGS: Final = "audit_findings"
CHECKLIST: Final = "completion_checklist"

# Fixed statements, bound parameters (SQL-001): one by engagement, one by work item.
_MAT = (
    "SELECT DISTINCT ON (work_item_id) work_item_id, engagement_id, version_no, status, "
    "overall, pm, ct, created_by_user_id AS created_by FROM materiality_versions "
)
_MAT_ORDER = " ORDER BY work_item_id, version_no DESC"
_FND = (
    "SELECT work_item_id, engagement_id, ref, kind, route, evaluation, version "
    "FROM audit_findings "
)
_FND_ORDER = " ORDER BY work_item_id, ref"
_CHK = "SELECT work_item_id, engagement_id, item_key, status, evidence_text FROM completion_items "
_CHK_ORDER = " ORDER BY work_item_id, position"
_STATEMENTS: Final = {
    (MATERIALITY, "engagement"): text(_MAT + "WHERE engagement_id = :v" + _MAT_ORDER),
    (MATERIALITY, "item"): text(_MAT + "WHERE work_item_id = :v" + _MAT_ORDER),
    (FINDINGS, "engagement"): text(_FND + "WHERE engagement_id = :v" + _FND_ORDER),
    (FINDINGS, "item"): text(_FND + "WHERE work_item_id = :v" + _FND_ORDER),
    (CHECKLIST, "engagement"): text(_CHK + "WHERE engagement_id = :v" + _CHK_ORDER),
    (CHECKLIST, "item"): text(_CHK + "WHERE work_item_id = :v" + _CHK_ORDER),
}


async def _rows(kind: str, by: str, value: UUID, tenant: TenantContext) -> list[dict[str, object]]:
    async with tenant_session(tenant) as session:
        found = await session.execute(_STATEMENTS[(kind, by)], {"v": value})
        return [dict(r) for r in found.mappings().all()]


def _by_item(rows: list[dict[str, object]]) -> dict[UUID, list[dict[str, object]]]:
    out: dict[UUID, list[dict[str, object]]] = {}
    for r in rows:
        out.setdefault(cast(UUID, r["work_item_id"]), []).append(r)
    return out


def _hash(value: object) -> str:
    """The rows as canonical JSON: figures and dates as their text, so the hash is stable."""
    return content_hash(cast("Json", json.loads(json.dumps(value, default=str, sort_keys=True))))


def _materiality_hash(r: dict[str, object]) -> str:
    return _hash({k: r[k] for k in ("version_no", "status", "overall", "pm", "ct")})


def _findings_hash(rows: list[dict[str, object]]) -> str:
    keys = ("ref", "kind", "route", "evaluation", "version")
    return _hash([{k: r[k] for k in keys} for r in rows])


def _checklist_hash(rows: list[dict[str, object]]) -> str:
    return _hash([{k: r[k] for k in ("item_key", "status", "evidence_text")} for r in rows])


async def materiality_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    rows = await _rows(MATERIALITY, "engagement", engagement_id, tenant)
    return [
        Reviewable(
            MATERIALITY,
            cast(UUID, r["work_item_id"]),
            "MAT",
            f"Materiality (v{r['version_no']})",
            _materiality_hash(r),
            True,
        )
        for r in rows
    ]


async def materiality_facts(tenant: TenantContext, work_item_id: UUID) -> ReviewableFacts | None:
    rows = await _rows(MATERIALITY, "item", work_item_id, tenant)
    if not rows:
        return None
    r = rows[0]
    return ReviewableFacts(
        MATERIALITY,
        work_item_id,
        cast(UUID, r["engagement_id"]),
        _materiality_hash(r),
        int(cast(int, r["version_no"])),
        frozenset({cast(UUID, r["created_by"])}) if r["created_by"] else frozenset(),
        label=f"Materiality (v{r['version_no']})",
    )


async def findings_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    by_item = _by_item(await _rows(FINDINGS, "engagement", engagement_id, tenant))
    return [
        Reviewable(FINDINGS, item, "FND", "Findings", _findings_hash(rows), True)
        for item, rows in by_item.items()
    ]


async def findings_facts(tenant: TenantContext, work_item_id: UUID) -> ReviewableFacts | None:
    rows = await _rows(FINDINGS, "item", work_item_id, tenant)
    if not rows:
        return None
    return ReviewableFacts(
        FINDINGS,
        work_item_id,
        cast(UUID, rows[0]["engagement_id"]),
        _findings_hash(rows),
        sum(int(cast(int, r["version"])) for r in rows),
        frozenset(),  # a finding's raiser is its issue's; the matrix conditions read L1 signers
        label="Findings",
    )


async def checklist_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    by_item = _by_item(await _rows(CHECKLIST, "engagement", engagement_id, tenant))
    return [
        Reviewable(
            CHECKLIST,
            item,
            "CHK",
            "Completion Checklist",
            _checklist_hash(rows),
            any(r["status"] != "open" for r in rows),
        )
        for item, rows in by_item.items()
    ]


async def checklist_facts(tenant: TenantContext, work_item_id: UUID) -> ReviewableFacts | None:
    rows = await _rows(CHECKLIST, "item", work_item_id, tenant)
    if not rows:
        return None
    return ReviewableFacts(
        CHECKLIST,
        work_item_id,
        cast(UUID, rows[0]["engagement_id"]),
        _checklist_hash(rows),
        1,
        frozenset(),
        label="Completion Checklist",
    )
