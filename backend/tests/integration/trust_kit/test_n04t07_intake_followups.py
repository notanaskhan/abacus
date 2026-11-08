"""N-04-T07 follow-ups (DEC-2953) against Postgres: Create anyway past a duplicate needs a reason
and records it; Attach files the document on the chosen notice (same bytes, a new item); a file
whose text was ready before its intake is read at once instead of waiting ten minutes."""

from __future__ import annotations

import uuid

import pytest

import abacus.api as app_package  # loading it loads every module
from abacus.modules.notices import intake as intake_module
from abacus.modules.notices.intake_read import read_if_ready

from .support import Firm, Seeder, make_firm

pytestmark = pytest.mark.asyncio


async def _notice(seed: Seeder, firm: Firm) -> uuid.UUID:
    work_item = await seed.id(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
        "SELECT $1, $2, client_id, 'notice', 'CP14', $3 FROM engagements WHERE id = $2 "
        "RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        firm.user_id,
    )
    await seed.run(
        "INSERT INTO notices (tenant_id, work_item_id, engagement_id, notice_code, received_on) "
        "VALUES ($1, $2, $3, 'CP14', '2026-09-10')",
        firm.tenant_id,
        work_item,
        firm.engagement_id,
    )
    return work_item


async def _intake(seed: Seeder, firm: Firm, version: uuid.UUID, status: str) -> uuid.UUID:
    return await seed.id(
        "INSERT INTO notice_intakes (tenant_id, source, evidence_version_id, status, "
        "extraction_mode, created_by) VALUES ($1, 'upload', $2, $3, 'manual', $4) RETURNING id",
        firm.tenant_id,
        version,
        status,
        firm.user_id,
    )


async def test_ac_create_anyway_without_a_reason_is_refused(seed: Seeder) -> None:
    assert app_package.create_app
    firm = await make_firm(seed)
    duplicate = await _notice(seed, firm)
    made = await _intake(seed, firm, await firm.version(b"%PDF-1.4 again"), "manual_entry")
    await seed.run(
        "UPDATE notice_intakes SET duplicate_of_work_item_id = $1 WHERE id = $2", duplicate, made
    )
    entity = await seed.value(
        "SELECT id FROM client_entities WHERE tenant_id = $1 LIMIT 1", firm.tenant_id
    )
    with pytest.raises(intake_module.CreateAnywayReasonRequired):
        await intake_module.create_notice(
            firm.person(),
            made,
            client_entity_id=uuid.UUID(str(entity)),
            assignee_id=firm.user_id,
            engagement_id=firm.engagement_id,
            related_return_id=None,
            create_anyway=True,
        )


async def test_ac_attach_files_the_document_on_the_chosen_notice(seed: Seeder) -> None:
    firm = await make_firm(seed)
    notice = await _notice(seed, firm)
    version = await firm.version(b"%PDF-1.4 supporting 1099")
    made = await _intake(seed, firm, version, "manual_entry")

    found = await intake_module.attach(firm.person(), made, notice)

    assert (found.status, found.created_work_item_id) == ("created", notice)
    rows = await seed.rows(
        "SELECT v.fingerprint = s.fingerprint AS same, i.work_item_id FROM evidence_versions v "
        "JOIN evidence_items i ON i.id = v.evidence_item_id, evidence_versions s "
        "WHERE s.id = $1 AND v.id <> s.id AND i.work_item_id = $2",
        version,
        notice,
    )
    assert [(r["same"], r["work_item_id"]) for r in rows] == [(True, notice)]


async def test_ac_a_file_with_text_already_is_read_at_once(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(b"%PDF-1.4 a state letter with a text layer")
    await seed.run(
        "INSERT INTO evidence_pages (tenant_id, evidence_version_id, page_no, width_pt, "
        "height_pt, has_text_layer) VALUES ($1, $2, 1, 612, 792, true)",
        firm.tenant_id,
        version,
    )
    made = await _intake(seed, firm, version, "extracting")
    # No map covers it: it opens for entry now, not after ten minutes.
    assert await read_if_ready(firm.tenant_id, made) == "manual_entry"
