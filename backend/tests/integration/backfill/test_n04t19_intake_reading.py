"""N-04-T19 (TASK-3345; DEC-2334): with no form map, the responder proposes over masked text.

N-04 US-2.2: each value names its run for a person to confirm; nothing proposed, or no masked text,
opens manual entry; nothing is guessed. `NoticeIntakeWorkflow` (N-04-T07) reads mapped forms.
"""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import uow
from abacus.modules.agents import api as agents_api
from abacus.modules.agents.handoff import NoticeExtractOutput, NoticeProposedField
from abacus.modules.agents.notice_responder import ExtractProposal
from abacus.modules.evidence.api import NewItem, Provenance, add_version, stage_content
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import intake_read
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


async def _no_map(monkeypatch: pytest.MonkeyPatch) -> None:
    async def none_read(_tenant_id: object, _version: object) -> int:
        return 0

    async def no_fields(_tenant: object, _version: object) -> tuple[()]:
        return ()

    monkeypatch.setattr(intake_read, "extract_version", none_read)
    monkeypatch.setattr(intake_read, "extracted_fields_of", no_fields)


async def test_ac_no_map_and_no_masked_text_opens_manual_entry(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, _version = await _intake(world, monkeypatch)
    await _no_map(monkeypatch)

    async def no_text(_tenant: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(intake_read, "masked_pages", no_text)
    assert await intake_read.read_intake(world.tenant_id, intake, None) == "manual_entry"
    (row,) = await world.seed.rows(
        "SELECT status, extraction_mode FROM notice_intakes WHERE id = $1", intake
    )
    assert tuple(row) == ("manual_entry", "manual")


async def test_ac_with_no_map_the_responders_proposal_is_recorded_as_the_agents(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, _version = await _intake(world, monkeypatch)
    run = uuid.uuid4()

    await _no_map(monkeypatch)

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

    monkeypatch.setattr(intake_read, "masked_pages", pages)
    monkeypatch.setattr(agents_api, "extract_notice_fields", propose)
    assert await intake_read.read_intake(world.tenant_id, intake, None) == "ready"
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
