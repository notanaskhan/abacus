"""A-06-T16 seam (DEC-2952) against Postgres: the agent's proposed severity lands on a proposed
deficiency as the agent's (a person's proposal never touched), and adopting it makes it the
person's. Nothing here concludes: `severity_concluded` stays null (FINDING-001)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import cast

import pytest

import abacus.api as app_package  # loading it loads every module
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.api import AdoptedValue
from abacus.modules.assurance import severity_suggestions as seam

from .support import Firm, Seeder, make_firm

pytestmark = pytest.mark.asyncio


async def _deficiency(seed: Seeder, firm: Firm, *, proposed_by: str | None = None) -> uuid.UUID:
    work_item = await seed.id(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
        "SELECT $1, $2, client_id, 'notice', 'Audit', $3 FROM engagements WHERE id = $2 "
        "RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        firm.user_id,
    )
    issue = await seed.id(
        "INSERT INTO issues (tenant_id, engagement_id, record_ref, kind, title_sealed) "
        "VALUES ($1, $2, '{}'::jsonb, 'exception', '\\x01'::bytea) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
    )
    finding = await seed.id(
        "INSERT INTO audit_findings (tenant_id, engagement_id, work_item_id, issue_id, ref, kind, "
        "title, created_by_kind) VALUES ($1, $2, $3, $4, 'F-01', 'control_deficiency', "
        "'Opt-out elections missing', 'human') RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        work_item,
        issue,
    )
    return await seed.id(
        "INSERT INTO deficiencies (tenant_id, engagement_id, work_item_id, finding_id, status, "
        "severity_proposed, severity_proposed_by_kind) "
        "VALUES ($1, $2, $3, $4, 'proposed', $5, $6) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        work_item,
        finding,
        None if proposed_by is None else "deficiency",
        proposed_by,
    )


def _event(firm: Firm, suggestion: uuid.UUID) -> OutboxEvent:
    payload = {"target_type": seam.SEVERITY_SUGGESTION_TARGET, "suggestion_id": str(suggestion)}
    return cast(OutboxEvent, SimpleNamespace(tenant_id=firm.tenant_id, payload=payload))


def _pending(deficiency: uuid.UUID, suggestion: uuid.UUID, value: str) -> object:
    return SimpleNamespace(
        suggestion_id=suggestion,
        engagement_id=uuid.uuid4(),
        target_type=seam.SEVERITY_SUGGESTION_TARGET,
        target_id=deficiency,
        field_key=seam.FIELD,
        proposed_value={"t": "code", "v": value},
    )


async def _row(seed: Seeder, deficiency: uuid.UUID) -> tuple[object, object, object, object]:
    rows = await seed.rows(
        "SELECT severity_proposed, severity_proposed_by_kind, severity_suggestion_id, "
        "severity_concluded FROM deficiencies WHERE id = $1",
        deficiency,
    )
    r = rows[0]
    return (r[0], r[1], r[2], r[3])


async def test_ac_the_agents_severity_lands_as_its_proposal_and_a_person_adopts_it(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert app_package.create_app
    firm = await make_firm(seed)
    deficiency = await _deficiency(seed, firm)
    suggestion = uuid.uuid4()

    async def pending(*_a: object) -> object:
        return _pending(deficiency, suggestion, "material_weakness")

    monkeypatch.setattr(seam, "pending_suggestion", pending)
    await seam.on_suggestion_created(_event(firm, suggestion))
    assert await _row(seed, deficiency) == ("material_weakness", "agent", suggestion, None)

    person = firm.person()
    adopted = AdoptedValue(
        engagement_id=firm.engagement_id,
        target_type=seam.SEVERITY_SUGGESTION_TARGET,
        target_id=deficiency,
        field_key=seam.FIELD,
        value={"t": "code", "v": "material_weakness"},
        value_source="agent_suggested",
        cause="suggestion_adopted",
        suggestion_id=suggestion,
        citation_ids=(),
        citation_note=None,
        checkpoint_id=None,
        proposal_id=None,
    )
    async with uow(person.tenant) as tx:
        await seam.apply_severity_suggestion(tx, person, adopted)
    assert await _row(seed, deficiency) == ("material_weakness", "human", suggestion, None)


async def test_ac_a_persons_proposal_is_never_overwritten_by_the_agent(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    firm = await make_firm(seed)
    deficiency = await _deficiency(seed, firm, proposed_by="human")
    suggestion = uuid.uuid4()

    async def pending(*_a: object) -> object:
        return _pending(deficiency, suggestion, "material_weakness")

    monkeypatch.setattr(seam, "pending_suggestion", pending)
    await seam.on_suggestion_created(_event(firm, suggestion))
    assert await _row(seed, deficiency) == ("deficiency", "human", None, None)


async def test_ac_an_unknown_severity_is_ignored(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    firm = await make_firm(seed)
    deficiency = await _deficiency(seed, firm)

    async def pending(*_a: object) -> object:
        return _pending(deficiency, uuid.uuid4(), "catastrophic")

    monkeypatch.setattr(seam, "pending_suggestion", pending)
    await seam.on_suggestion_created(_event(firm, uuid.uuid4()))
    assert await _row(seed, deficiency) == (None, None, None, None)
