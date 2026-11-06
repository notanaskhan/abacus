"""N-04-T19 (TASK-3345; DEC-2334): an intake leaves `extracting`, by code, the agent or a person.

N-04 US-2.2: a mapped notice's fields come from the code map; no map and no responder opens manual
entry; a refused OCR opens manual entry; nothing is guessed. Bug this pins: nothing subscribed, so
an intake at a firm with extraction on stayed `extracting` for good.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import OutboxEvent, uow
from abacus.modules.agents.handoff import NoticeExtractOutput, NoticeProposedField
from abacus.modules.agents.notice_responder import ExtractProposal
from abacus.modules.evidence.api import NewItem, Provenance, add_version, stage_content
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import intake_reading
from abacus.modules.notices.intake import create as create_intake

from .tb_support import Books, books


@pytest.fixture
async def world(net: object, object_store: str) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net`
    await found.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'notices.workspace', 'true', 'test-seed', 'N-04-T19') "
        "ON CONFLICT DO NOTHING",
        found.tenant_id,
    )
    forget_flags()
    return found


async def _intake(world: Books, monkeypatch: pytest.MonkeyPatch) -> tuple[uuid.UUID, uuid.UUID]:
    async def on(_tenant: object, _flag: object) -> str:
        return "notices"

    monkeypatch.setattr("abacus.modules.notices.intake.flag_variant", on)
    stored = await stage_content(world.tenant_id, f"notice {uuid.uuid4()}".encode())
    tenant = TenantContext(world.tenant_id, "human", str(world.senior.user_id))
    async with uow(tenant) as tx:
        version = await add_version(
            tx,
            engagement_id=world.site.engagement_id,
            item=NewItem(title="CP2000.pdf"),
            stored=stored,
            media_type="application/pdf",
            provenance=Provenance(source="firm_upload", method="uploaded"),
            requested_by=world.senior.user_id,
        )
    person = AuthContext(tenant, world.senior.user_id, uuid.uuid4(), None, None)
    made = await create_intake(
        person, source="upload", evidence_version_id=version.id, inbox_item_id=None
    )
    assert made.status == "extracting"
    return made.id, version.id


def _event(world: Books, version: uuid.UUID) -> OutboxEvent:
    return cast(
        OutboxEvent,
        SimpleNamespace(
            tenant_id=world.tenant_id,
            payload={
                "evidence_version_id": str(version),
                "engagement_id": str(world.site.engagement_id),
            },
        ),
    )


async def test_ac_a_mapped_notices_fields_come_from_code_and_it_is_ready(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, version = await _intake(world, monkeypatch)

    async def fields(_tenant: object, _version: object) -> list[dict[str, object]]:
        return [
            {
                "field_key": "notice.number",
                "value_text": "CP2000",
                "confidence": Decimal("0.98"),
                "low_confidence": False,
            },
            {
                "field_key": "notice.respond_by",
                "value_text": "2026-09-23",
                "confidence": Decimal("0.71"),
                "low_confidence": True,
            },
            {
                "field_key": "not.a_field",
                "value_text": "x",
                "confidence": Decimal(1),
                "low_confidence": False,
            },
        ]

    monkeypatch.setattr(intake_reading, "recorded_form_fields", fields)
    await intake_reading.on_fields_recorded(_event(world, version))
    (row,) = await world.seed.rows(
        "SELECT status, extraction_mode FROM notice_intakes WHERE id = $1", intake
    )
    assert tuple(row) == ("ready", "code_map")
    values = await world.seed.rows(
        "SELECT field_key, value_text, low_confidence, origin, recorded_actor_kind "
        "FROM notice_field_values WHERE owner_id = $1 ORDER BY field_key",
        intake,
    )
    assert [tuple(v) for v in values] == [
        ("notice.code", "CP2000", False, "code_map", "system"),
        ("notice.respond_by", "2026-09-23", True, "code_map", "system"),
    ]


async def test_ac_no_map_and_no_responder_opens_manual_entry(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, version = await _intake(world, monkeypatch)

    async def unknown(_tenant: object, _version: object) -> bool:
        return False

    async def no_text(_tenant: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(intake_reading, "form_is_known", unknown)
    monkeypatch.setattr(intake_reading, "masked_pages", no_text)
    await intake_reading.on_scanned(_event(world, version))
    (row,) = await world.seed.rows(
        "SELECT status, extraction_mode FROM notice_intakes WHERE id = $1", intake
    )
    assert tuple(row) == ("manual_entry", "manual")


async def test_ac_a_mapped_form_waits_for_its_own_event(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, version = await _intake(world, monkeypatch)

    async def known(_tenant: object, _version: object) -> bool:
        return True

    monkeypatch.setattr(intake_reading, "form_is_known", known)
    await intake_reading.on_scanned(_event(world, version))
    (row,) = await world.seed.rows("SELECT status FROM notice_intakes WHERE id = $1", intake)
    assert row["status"] == "extracting"


async def test_ac_a_refused_ocr_opens_manual_entry(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, version = await _intake(world, monkeypatch)
    await intake_reading.on_ocr_refused(_event(world, version))
    (row,) = await world.seed.rows("SELECT status FROM notice_intakes WHERE id = $1", intake)
    assert row["status"] == "manual_entry"


async def test_ac_with_no_map_the_responders_proposal_is_recorded_as_the_agents(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, version = await _intake(world, monkeypatch)
    run = uuid.uuid4()

    async def unknown(_tenant: object, _version: object) -> bool:
        return False

    async def pages(_tenant: object, **_k: object) -> dict[int, str]:
        return {1: "State notice"}

    async def propose(_tenant: object, **_k: object) -> ExtractProposal:
        return ExtractProposal(
            NoticeExtractOutput(
                fields=[
                    NoticeProposedField(
                        field_key="agency.name", value="CO DOR", confidence=0.72, citation="p1"
                    ),
                    NoticeProposedField(
                        field_key="not.a_field", value="x", confidence=1, citation="p1"
                    ),
                ]
            ),
            run,
        )

    monkeypatch.setattr(intake_reading, "form_is_known", unknown)
    monkeypatch.setattr(intake_reading, "masked_pages", pages)
    monkeypatch.setattr(intake_reading, "extract_notice_fields", propose)
    await intake_reading.on_scanned(_event(world, version))
    (row,) = await world.seed.rows(
        "SELECT status, extraction_mode FROM notice_intakes WHERE id = $1", intake
    )
    assert tuple(row) == ("ready", "agent")
    (value,) = await world.seed.rows(
        "SELECT field_key, low_confidence, origin, agent_run_id FROM notice_field_values "
        "WHERE owner_id = $1",
        intake,
    )
    assert tuple(value) == ("agency.name", True, "agent", run)
