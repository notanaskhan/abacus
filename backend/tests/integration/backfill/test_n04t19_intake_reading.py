"""N-04-T19 (TASK-3345; DEC-2377): with no form map, the responder proposes over masked text.

N-04 US-2.2: each value names its run for a person to confirm; nothing proposed, or no masked text,
opens manual entry; nothing is guessed. `NoticeIntakeWorkflow` (N-04-T07) reads mapped forms.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from abacus.ai_gateway.context import DataSubject
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.agents import api as agents_api
from abacus.modules.agents.handoff import NoticeExtractOutput, NoticeProposedField
from abacus.modules.agents.notice_responder import ExtractProposal
from abacus.modules.evidence.api import NewItem, Provenance, add_version, stage_content
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import intake_read
from abacus.modules.notices.intake import create as create_intake
from abacus.modules.notices.intake import intake as intake_of
from abacus.modules.notices.intake import revise

from .tb_support import Books, books


@pytest.fixture
async def world(net: object, object_store: str) -> Books:
    # `notices.workspace` retired at N-04-T27 (DEC-2602).
    return await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net`


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


async def _in_manual_entry(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> tuple[uuid.UUID, AuthContext, list[dict[str, object]]]:
    intake, _version = await _intake(world, monkeypatch)
    await _no_map(monkeypatch)
    asked: list[dict[str, object]] = []

    async def pages(_tenant: object, **_k: object) -> dict[int, str]:
        return {1: "State notice"}

    async def refused(_tenant: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(intake_read, "masked_pages", pages)
    monkeypatch.setattr(agents_api, "extract_notice_fields", refused)
    assert await intake_read.read_intake(world.tenant_id, intake, None) == "manual_entry"

    async def propose(_tenant: object, **given: object) -> ExtractProposal:
        asked.append(given)
        return ExtractProposal(
            NoticeExtractOutput(
                fields=[
                    NoticeProposedField(
                        field_key="agency.name", value="CO DOR", confidence=0.95, citation="p1"
                    ),
                    NoticeProposedField(
                        field_key="notice.code", value="READ", confidence=0.95, citation="p1"
                    ),
                ]
            ),
            uuid.uuid4(),
        )

    monkeypatch.setattr(agents_api, "extract_notice_fields", propose)
    tenant = TenantContext(world.tenant_id, "human", str(world.senior.user_id))
    return intake, AuthContext(tenant, world.senior.user_id, uuid.uuid4(), None, None), asked


async def _emitted(world: Books, intake: uuid.UUID) -> list[object]:
    rows = await world.seed.rows(
        "SELECT payload->>'client_entity_id' AS entity FROM outbox "
        "WHERE event_type = 'notice_intake.taxpayer_named' AND payload->>'intake_id' = $1",
        str(intake),
    )
    return [r["entity"] for r in rows]


async def test_ac_naming_the_client_and_the_year_reads_again_under_the_consent_gate(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, person, asked = await _in_manual_entry(world, monkeypatch)
    entity = world.site.entity_id

    # The year alone, then the client: only the revise that leaves both names the taxpayer.
    once = await revise(person, intake, 2, fields=[("notice.code", "CP-TYPED", False)])
    assert await _emitted(world, intake) == []
    twice = await revise(
        person, intake, once.row_version, fields=[("notice.tax_year", "2024", False)]
    )
    assert await _emitted(world, intake) == []
    await revise(person, intake, twice.row_version, fields=[], client_entity_id=entity)
    assert await _emitted(world, intake) == [str(entity)]

    assert await intake_read.reread_named(world.tenant_id, intake) == "ready"
    (given,) = asked
    assert given["subjects"] == (DataSubject(entity, 2024),)
    assert "notice.code" not in cast("tuple[str, ...]", given["keys"])
    found = await intake_of(person, intake)
    assert (found.status, found.extraction_mode) == ("ready", "agent")
    values = {f.key: (f.value_text, f.origin) for f in found.fields}
    assert values["agency.name"] == ("CO DOR", "agent")
    # The responder said READ for a key the person typed: the person's value stands.
    assert values["notice.code"] == ("CP-TYPED", "human")

    # Idempotent: a second run reads nothing more.
    assert await intake_read.reread_named(world.tenant_id, intake) == "ready"
    assert len(asked) == 1


async def test_ac_a_refused_reread_leaves_manual_entry_as_the_person_has_it(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, person, _asked = await _in_manual_entry(world, monkeypatch)

    async def refused(_tenant: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(agents_api, "extract_notice_fields", refused)
    entity = world.site.entity_id
    named = await revise(
        person, intake, 2, fields=[("notice.tax_year", "2024", False)], client_entity_id=entity
    )
    assert await intake_read.reread_named(world.tenant_id, intake) == "manual_entry"
    found = await intake_of(person, intake)
    assert (found.status, found.row_version) == ("manual_entry", named.row_version)


async def test_ac_a_notice_a_form_map_read_never_reads_again(
    world: Books, monkeypatch: pytest.MonkeyPatch
) -> None:
    intake, person, asked = await _in_manual_entry(world, monkeypatch)
    await world.seed.run(
        "UPDATE notice_intakes SET match = match - 'manual_reason_code' WHERE id = $1", intake
    )
    entity = world.site.entity_id
    await revise(
        person, intake, 2, fields=[("notice.tax_year", "2024", False)], client_entity_id=entity
    )
    assert await _emitted(world, intake) == []
    assert await intake_read.reread_named(world.tenant_id, intake) == "manual_entry"
    assert asked == []
