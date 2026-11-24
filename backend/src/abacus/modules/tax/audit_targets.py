"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121), for the tax
module's kinds. A `tax_return` target is its work item (T-02-T07 records status moves on it), as
is a `work_item` target (the pinned due dates); the engagement module answers which engagement
holds the work item, so the explorer shows the event to whoever may see that engagement. A tax
profile's authorization, file and transcript belong to a client entity (0550). Unknown ids are
left out (fail closed)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.api import work_item_engagement

# T-04-T15: a worksheet is its own row, owned by its engagement. T-04-T36: a K-1 activity and
# its treatments too (audited as `pass_through_*`: audit names hold no digits).
_ROWS = {
    # T-08-T19 (DEC-5916): a planning opportunity belongs to its engagement.
    "planning_opportunity": text(
        "SELECT id, engagement_id FROM planning_opportunities WHERE id = ANY(:ids)"
    ),
    "return_worksheet": text(
        "SELECT id, engagement_id FROM return_worksheets WHERE id = ANY(:ids)"
    ),
    "pass_through_activity": text(
        "SELECT id, engagement_id FROM k1_activities WHERE id = ANY(:ids)"
    ),
    "pass_through_treatment": text(
        "SELECT id, engagement_id FROM k1_treatments WHERE id = ANY(:ids)"
    ),
    # T-05-T22 / T-04-T39 (S38): an entity return's partner (its TIN seal and reveals) and a
    # return's residency determination, each owned by its engagement.
    "partner": text("SELECT id, engagement_id FROM partners WHERE id = ANY(:ids)"),
    # S46: T-07-T16 fiduciary lines and T-07-T22 estate workpapers, each its return's.
    "fai_line": text("SELECT id, engagement_id FROM fai_lines WHERE id = ANY(:ids)"),
    "trust_expense": text("SELECT id, engagement_id FROM trust_expenses WHERE id = ANY(:ids)"),
    "trust_distribution": text(
        "SELECT id, engagement_id FROM trust_distributions WHERE id = ANY(:ids)"
    ),
    "estate_asset": text(
        "SELECT id, engagement_id FROM estate_inventory_items WHERE id = ANY(:ids)"
    ),
    "estate_deduction": text(
        "SELECT id, engagement_id FROM estate_deductions WHERE id = ANY(:ids)"
    ),
    "residency_determination": text(
        "SELECT id, engagement_id FROM residency_determinations WHERE id = ANY(:ids)"
    ),
    # T-05-T41 (DEC-4701): an allocation structure version, owned by its engagement.
    # T-05-T42 (DEC-4705): a workbook section (its sign-offs and acknowledged tie-outs).
    "tax_workbook_section": text(
        "SELECT id, engagement_id FROM tax_workbook_sections WHERE id = ANY(:ids)"
    ),
    "allocation_structure": text(
        "SELECT id, engagement_id FROM allocation_structures WHERE id = ANY(:ids)"
    ),
    # T-05-T48 (DEC-4708): a return's preparer memo, owned by its engagement.
    "preparer_memo": text("SELECT id, engagement_id FROM preparer_memos WHERE id = ANY(:ids)"),
    # T-05-T51 (S42): an issue's sealed resolution note; the event names the issue, the note row
    # carries the engagement.
    "issue": text(
        "SELECT issue_id, engagement_id FROM tax_issue_resolution_notes WHERE issue_id = ANY(:ids)"
    ),
    # T-07-T12 (S45): a return's instrument interpretation and its determinations.
    "instrument_interpretation": text(
        "SELECT id, engagement_id FROM instrument_interpretations WHERE id = ANY(:ids)"
    ),
    # S52 end pass: T-06-T36's PTET election and T-08-T14's check results, each its return's.
    "ptet_election": text("SELECT id, engagement_id FROM ptet_elections WHERE id = ANY(:ids)"),
    "standards_check_result": text(
        "SELECT c.id, i.engagement_id FROM standards_check_results c "
        "JOIN standards_run_items i ON i.id = c.run_item_id WHERE c.id = ANY(:ids)"
    ),
    "instrument_determination": text(
        "SELECT d.id, i.engagement_id FROM instrument_determinations d "
        "JOIN instrument_interpretations i ON i.id = d.interpretation_id WHERE d.id = ANY(:ids)"
    ),
}
# T-05-T35 (DEC-4620): the entity workbook's events (`workbook.step_written`,
# `workbook.cell_edited`) target the return's work item, like `tax_return`.
AUDIT_KINDS = frozenset({"tax_return", "work_item", "tax_workbook"}) | frozenset(_ROWS)
_ENTITIES = {
    "tax_authorization": text(
        "SELECT id, client_entity_id FROM tax_authorizations WHERE id = ANY(:ids)"
    ),
    "tax_profile_file": text(
        "SELECT id, client_entity_id FROM tax_profile_files WHERE id = ANY(:ids)"
    ),
    "transcript": text("SELECT id, client_entity_id FROM transcripts WHERE id = ANY(:ids)"),
    "estimate_schedule": text(
        "SELECT id, client_entity_id FROM estimate_schedules WHERE id = ANY(:ids)"
    ),
    # T-07-T12 (S45): a trust's governing instrument and its clauses belong to the client entity.
    "governing_instrument": text(
        "SELECT id, client_entity_id FROM governing_instruments WHERE id = ANY(:ids)"
    ),
    "instrument_clause": text(
        "SELECT c.id, g.client_entity_id FROM instrument_clauses c "
        "JOIN instrument_segmentations s ON s.id = c.segmentation_id "
        "JOIN governing_instruments g ON g.id = s.instrument_id WHERE c.id = ANY(:ids)"
    ),
    # T-07-T24 (S47): a trust's 65-day election belongs to the client entity.
    "sixty_five_day_election": text(
        "SELECT id, client_entity_id FROM sixty_five_day_elections WHERE id = ANY(:ids)"
    ),
}
ENTITY_KINDS = frozenset(_ENTITIES)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `tax_return` and `work_item` rows: their work item id -> its engagement."""
    if kind in _ROWS:
        async with tenant_session(tenant) as session:
            found = await session.execute(_ROWS[kind], {"ids": list(ids)})
            return {row[0]: row[1] for row in found}
    owned: dict[UUID, UUID] = {}
    for work_item_id in ids:
        engagement = await work_item_engagement(tenant, work_item_id)
        if engagement is not None:
            owned[work_item_id] = engagement
    return owned


async def audit_entities(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """For a tax profile's rows named by an audit event: their id -> the owning client entity."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_ENTITIES[kind], {"ids": list(ids)})
        return dict(rows.tuples().all())
