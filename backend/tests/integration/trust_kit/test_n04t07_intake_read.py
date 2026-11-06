"""N-04-T07 (N-04 US-2.2, US-2.3; DEC-2326): the read `NoticeIntakeWorkflow` runs, against the real
schema as the app role. Row acceptance: the Santos CP14 yields eight fields, a 0.71 respond-by
stays low confidence for a person, the client and authorization are looked up, a repeat is flagged.
"""

from __future__ import annotations

import uuid

import pytest

import abacus.api as app_package  # loading it loads every module
from abacus.modules.notices.intake_read import mark_failed, read_if_ready, read_intake

from .support import Firm, Seeder, make_firm

pytestmark = pytest.mark.asyncio
LAST4 = "2208"
CP14 = (
    ("notice.number", "CP14", "0.990", False),
    ("notice.tax_year", "2024", "0.980", False),
    ("notice.date", "2026-09-01", "0.970", False),
    ("notice.respond_by", "2026-09-21", "0.710", True),
    ("notice.amount_due", "1,204.18", "0.990", False),
    ("notice.taxpayer_last4", LAST4, "0.960", False),
    ("notice.tax_due", "1,100.00", "0.980", False),
    ("notice.penalties", "104.18", "0.970", False),
)


async def _intake(
    firm: Firm, version: uuid.UUID | None, inbox: uuid.UUID | None = None
) -> uuid.UUID:
    return await firm.seed.id(
        "INSERT INTO notice_intakes (tenant_id, source, evidence_version_id, inbox_item_id, "
        "status, extraction_mode, created_by) VALUES ($1, 'upload', $2, $3, 'extracting', "
        "'code_map', $4) RETURNING id",
        firm.tenant_id,
        version,
        inbox,
        firm.user_id,
    )


async def _read_fields(firm: Firm, version: uuid.UUID) -> None:
    for key, value, confidence, low in CP14:
        await firm.seed.run(
            "INSERT INTO extracted_fields (tenant_id, evidence_version_id, form_type, tax_year, "
            "form_map_version, field_key, label, value_type, value_text, page_no, bbox, "
            "confidence, low_confidence, extractor_kind, extractor_version, match_id) VALUES "
            "($1, $2, 'cp14', 2024, 'cp14-2024-v2', $3, $3, 'code', $4, 1, "
            "ARRAY[1,1,2,2]::numeric(10,2)[], $5::numeric, $6, 'form_map', 'form-map-1', $7)",
            firm.tenant_id,
            version,
            key,
            value,
            confidence,
            low,
            f"ev:{version}#field:{key}",
        )


async def _entity_with_last4(firm: Firm, last4: str = LAST4) -> uuid.UUID:
    client = await firm.seed.value(
        "SELECT client_id FROM client_entities WHERE tenant_id = $1 LIMIT 1", firm.tenant_id
    )
    return await firm.seed.id(
        "INSERT INTO client_entities (tenant_id, client_id, name, tin_last4, tin_sealed, "
        "tin_kind, tin_fingerprint, tin_status) VALUES ($1, $2, 'Maria Santos', $3, $4, 'ssn', "
        "$5, 'on_file') RETURNING id",
        firm.tenant_id,
        client,
        last4,
        b"sealed",
        uuid.uuid4().bytes,
    )


async def test_ac_the_santos_cp14_reads_eight_fields_and_matches_the_client(seed: Seeder) -> None:
    assert app_package.create_app
    firm = await make_firm(seed)
    version = await firm.version(b"%PDF-1.4 santos cp14")
    await _read_fields(firm, version)
    entity = await _entity_with_last4(firm)
    intake = await _intake(firm, version)

    assert await read_if_ready(firm.tenant_id, intake) == "ready"

    rows = await seed.rows(
        "SELECT field_key, value_text, last4, value_sealed IS NOT NULL AS sealed, confidence, "
        "low_confidence, origin FROM notice_field_values WHERE owner_id = $1 ORDER BY field_key",
        intake,
    )
    by_key = {r["field_key"]: r for r in rows}
    assert len(rows) == 8
    assert by_key["notice.respond_by"]["low_confidence"] is True
    assert str(by_key["notice.respond_by"]["confidence"]) == "0.710"
    assert by_key["notice.code"]["value_text"] == "CP14"
    assert by_key["notice.amount_total"]["value_text"] == "1,204.18"
    tin = by_key["taxpayer.tin"]
    assert (tin["value_text"], tin["last4"], tin["sealed"]) == (None, LAST4, True)
    assert {r["origin"] for r in rows} == {"code_map"}

    state = (
        await seed.rows(
            "SELECT status, match->>'client_entity_id' AS entity, match->>'method' AS method, "
            "authorization_facts->>'kind' AS kind, duplicate_of_work_item_id AS dup "
            "FROM notice_intakes WHERE id = $1",
            intake,
        )
    )[0]
    assert (state["status"], state["entity"], state["method"]) == ("ready", str(entity), "tin")
    assert (state["kind"], state["dup"]) == ("none", None)


async def test_ac_several_entities_with_the_last_four_are_the_persons_pick(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(b"%PDF-1.4 two candidates")
    await _read_fields(firm, version)
    first = await _entity_with_last4(firm)
    second = await _entity_with_last4(firm)
    intake = await _intake(firm, version)

    await read_intake(firm.tenant_id, intake, None)

    match = await seed.value("SELECT match::text FROM notice_intakes WHERE id = $1", intake)
    assert str(first) in str(match) and str(second) in str(match)
    assert (
        await seed.value(
            "SELECT match->>'client_entity_id' FROM notice_intakes WHERE id = $1", intake
        )
        is None
    )


async def test_ac_a_refusal_opens_manual_entry_and_names_its_reason(seed: Seeder) -> None:
    firm = await make_firm(seed)
    intake = await _intake(firm, await firm.version(b"%PDF-1.4 refused"))

    assert await read_intake(firm.tenant_id, intake, "consent_7216") == "manual_entry"

    assert (
        await seed.value(
            "SELECT match->>'manual_reason_code' FROM notice_intakes WHERE id = $1", intake
        )
        == "consent_7216"
    )
    assert (
        await seed.value("SELECT count(*) FROM notice_field_values WHERE owner_id = $1", intake)
        == 0
    )


async def test_ac_a_file_no_map_covers_opens_manual_entry(seed: Seeder) -> None:
    firm = await make_firm(seed)
    intake = await _intake(firm, await firm.version(b"%PDF-1.4 state letter"))

    assert await read_intake(firm.tenant_id, intake, None) == "manual_entry"

    assert (
        await seed.value(
            "SELECT match->>'manual_reason_code' FROM notice_intakes WHERE id = $1", intake
        )
        == "no_map"
    )


async def test_ac_nothing_read_yet_keeps_waiting_for_the_signal(seed: Seeder) -> None:
    firm = await make_firm(seed)
    intake = await _intake(firm, await firm.version(b"%PDF-1.4 still reading"))
    assert await read_if_ready(firm.tenant_id, intake) == "extracting"


async def test_ac_a_recorded_ocr_refusal_is_read_without_a_signal(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(b"%PDF-1.4 refused earlier")
    await seed.run(
        "INSERT INTO ocr_runs (tenant_id, evidence_version_id, provider, api, status, "
        "refused_reason, basis) VALUES ($1, $2, 'fake', 'detect_text', 'refused', "
        "'consent_missing', 'synthetic')",
        firm.tenant_id,
        version,
    )
    intake = await _intake(firm, version)
    assert await read_if_ready(firm.tenant_id, intake) == "manual_entry"


async def test_ac_ten_minutes_without_text_fails_to_entering_the_fields(seed: Seeder) -> None:
    firm = await make_firm(seed)
    intake = await _intake(firm, await firm.version(b"%PDF-1.4 never read"))
    assert await mark_failed(firm.tenant_id, intake) == "failed"
    assert await mark_failed(firm.tenant_id, intake) == "gone"


async def test_ac_the_read_never_overwrites_an_intake_a_person_has(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(b"%PDF-1.4 discarded")
    await _read_fields(firm, version)
    intake = await _intake(firm, version)
    await seed.run(
        "UPDATE notice_intakes SET status = 'discarded', discarded_reason_code = 'mistake' "
        "WHERE id = $1",
        intake,
    )
    assert await read_intake(firm.tenant_id, intake, None) == "discarded"
    assert (
        await seed.value("SELECT count(*) FROM notice_field_values WHERE owner_id = $1", intake)
        == 0
    )


async def test_ac_the_same_bytes_on_a_notice_are_a_possible_duplicate(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(b"%PDF-1.4 same bytes")
    work_item = await seed.id(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
        "SELECT $1, $2, client_id, 'notice', 'CP14', $3 FROM engagements WHERE id = $2 "
        "RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        firm.user_id,
    )
    await seed.run(
        "INSERT INTO notices (tenant_id, work_item_id, engagement_id, notice_code, received_on, "
        "source_evidence_version_id) VALUES ($1, $2, $3, 'CP14', '2026-09-01', $4)",
        firm.tenant_id,
        work_item,
        firm.engagement_id,
        version,
    )
    await _read_fields(firm, version)
    await _entity_with_last4(firm)
    intake = await _intake(firm, version)

    await read_intake(firm.tenant_id, intake, None)

    assert (
        await seed.value(
            "SELECT duplicate_of_work_item_id FROM notice_intakes WHERE id = $1", intake
        )
        == work_item
    )
