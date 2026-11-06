"""A-04-T24's response (TASK-5020; A-04 §3.4 AC4.6, AC4.7; DEC-2382): "R8's drafted rationale and
EBP-03 response arrive as pending suggestions", and adopting one writes the `risk_linkages` row.
Against Postgres: the pending suggestion is drawn as a `suggested` cell with no row written, the
adopting unit of work writes the live link naming it, and nothing else reaches the table."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from asyncpg import Record

import abacus.api as app_package  # loading it loads every module
from abacus.kernel.uow import Target, uow
from abacus.modules.agents.api import AdoptedValue, PendingSuggestion, pending_suggestions
from abacus.modules.assurance import risks

from .support import Seeder, make_firm

pytestmark = pytest.mark.asyncio
assert app_package is not None


def _adopted(risk_id: uuid.UUID, value: str, suggestion: uuid.UUID | None) -> AdoptedValue:
    return AdoptedValue(
        engagement_id=None,
        target_type=risks.TARGET,
        target_id=risk_id,
        field_key=risks.RESPONSE_FIELD,
        value={"t": "text", "v": value},
        value_source="agent_suggested",
        cause="suggestion_adopted",
        suggestion_id=suggestion,
        citation_ids=(),
        citation_note=None,
        checkpoint_id=None,
        proposal_id=None,
    )


@pytest.fixture
async def world(seed: Seeder, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    firm = await make_firm(seed)
    work_item = await seed.id(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
        "SELECT $1, $2, client_id, 'notice', 'Audit', $3 FROM engagements WHERE id = $2 "
        "RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        firm.user_id,
    )
    risk = await seed.id(
        "INSERT INTO risk_register_rows (tenant_id, engagement_id, work_item_id, code, level, "
        "area_key, area_label, inherent_risk, control_risk, rmm, fraud, content_hash) VALUES "
        "($1, $2, $3, 'R8', 'financial_statement', 'participant_accounts', "
        "'Participant accounts', 'high', 'max', 'high', 'none', $4) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        work_item,
        "a" * 64,
    )
    actions: list[str] = []

    async def authorise(_ctx: object, action: str, _resource: object) -> None:
        actions.append(action)

    async def work_item_of(*_a: object) -> uuid.UUID:
        return work_item

    async def allowed(_ctx: object, _resource: object, asked: tuple[str, ...]) -> list[str]:
        return list(asked)

    monkeypatch.setattr(risks, "allowed_actions", allowed)
    monkeypatch.setattr(risks, "authorise", authorise)
    monkeypatch.setattr(risks, "_work_item", work_item_of)
    return SimpleNamespace(firm=firm, seed=seed, risk=risk, work_item=work_item, actions=actions)


def _pending(world: SimpleNamespace, value: str, suggestion: uuid.UUID) -> object:
    async def pending(*_a: object) -> list[PendingSuggestion]:
        return [PendingSuggestion(suggestion, world.risk, value, (uuid.uuid4(),), 1)]

    return pending


async def _rows(world: SimpleNamespace) -> list[Record]:
    return await world.seed.rows(
        "SELECT target_kind, target_ref, state, suggestion_id FROM risk_linkages "
        "WHERE risk_id = $1",
        world.risk,
    )


async def test_ac4_6_a_pending_response_is_drawn_suggested_and_writes_no_row(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    suggestion = uuid.uuid4()
    monkeypatch.setattr(risks, "pending_suggestions", _pending(world, "EBP-03", suggestion))
    found = await risks.linkage(world.firm.person(), world.firm.engagement_id)
    assert found.cells == [("R8", "EBP-03", "suggested")]
    assert found.suggestions == {("R8", "EBP-03"): suggestion}
    assert [t.ref for t in found.targets] == ["EBP-03"]
    assert await _rows(world) == []
    assert await risks.linked_ids(world.firm.person().tenant, world.work_item) == []


async def test_without_proposal_read_no_pending_response_is_read(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`specialist` and `quality_partner` hold `risk.read` but not `proposal.read`."""

    async def only_risk_read(*_a: object) -> list[str]:
        return []

    monkeypatch.setattr(risks, "allowed_actions", only_risk_read)
    monkeypatch.setattr(risks, "pending_suggestions", _pending(world, "EBP-03", uuid.uuid4()))
    found = await risks.linkage(world.firm.person(), world.firm.engagement_id)
    assert (found.cells, found.suggestions) == ([], {})


async def test_model_text_that_names_no_section_is_never_drawn(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(risks, "pending_suggestions", _pending(world, "Do it now", uuid.uuid4()))
    found = await risks.linkage(world.firm.person(), world.firm.engagement_id)
    assert (found.cells, found.targets) == ([], [])


async def test_ac4_6_adopting_writes_the_live_link_naming_the_suggestion(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    person = world.firm.person()
    suggestion = uuid.uuid4()
    async with uow(person.tenant) as tx:
        await risks.apply_risk_suggestion(tx, person, _adopted(world.risk, "ebp-03", suggestion))
    assert world.actions == ["risk.link"]  # the link's own action, not risk.edit
    assert [tuple(r) for r in await _rows(world)] == [
        ("workpaper", "EBP-03", "linked", suggestion)
    ]
    assert await risks.linked_ids(person.tenant, world.work_item) == [world.risk]
    row = await world.seed.value(
        "SELECT version_no FROM risk_register_rows WHERE id = $1", world.risk
    )
    assert row == 1  # a link doesn't move the row's content hash or version

    # The suggestion now names a target that stands: the matrix draws the live dot only.
    monkeypatch.setattr(risks, "pending_suggestions", _pending(world, "EBP-03", suggestion))
    found = await risks.linkage(person, world.firm.engagement_id)
    assert found.cells == [("R8", "EBP-03", "linked")]


async def test_adopting_a_response_already_linked_leaves_the_link_alone(
    world: SimpleNamespace,
) -> None:
    person = world.firm.person()
    await risks.link_response(
        person, world.firm.engagement_id, world.risk, target_kind="workpaper", target_ref="EBP-03"
    )
    async with uow(person.tenant) as tx:
        await risks.apply_risk_suggestion(tx, person, _adopted(world.risk, "EBP-03", uuid.uuid4()))
        # The applier wrote nothing; the adopting caller records `suggestion.adopted` regardless.
        tx.record("suggestion.adopted", target=Target("suggestion", uuid.uuid4()))
    assert [tuple(r) for r in await _rows(world)] == [("workpaper", "EBP-03", "linked", None)]


async def test_an_edited_value_that_names_no_section_is_refused(world: SimpleNamespace) -> None:
    person = world.firm.person()
    with pytest.raises(risks.RiskInvalid):
        async with uow(person.tenant) as tx:
            await risks.apply_risk_suggestion(
                tx, person, _adopted(world.risk, "Journal entries", uuid.uuid4())
            )
    assert await _rows(world) == []


async def test_linking_by_hand_still_answers_already_linked(world: SimpleNamespace) -> None:
    person = world.firm.person()
    link = {"target_kind": "workpaper", "target_ref": "AUD-09"}
    await risks.link_response(person, world.firm.engagement_id, world.risk, **link)
    with pytest.raises(risks.AlreadyLinked):
        await risks.link_response(person, world.firm.engagement_id, world.risk, **link)


async def test_ac4_7_a_pending_response_reads_from_the_store_and_a_shadow_run_never_shows(
    world: SimpleNamespace,
) -> None:
    async def run(shadow: bool) -> uuid.UUID:
        return await world.seed.id(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope, status, shadow) VALUES ($1, "
            "'workpapers.section_drafter', 1, $2, $3, ARRAY['suggestion.create'], 'running', "
            "$4) "
            "RETURNING id",
            world.firm.tenant_id,
            world.firm.engagement_id,
            world.firm.user_id,
            shadow,
        )

    async def suggestion(run_id: uuid.UUID, value: str) -> uuid.UUID:
        return await world.seed.id(
            "INSERT INTO suggestions (tenant_id, engagement_id, target_type, target_id, "
            "field_key, proposed_value, agent_run_id) VALUES ($1, $2, 'risk', $3, 'response', "
            "jsonb_build_object('t', 'text', 'v', $4::text), $5) RETURNING id",
            world.firm.tenant_id,
            world.firm.engagement_id,
            world.risk,
            value,
            run_id,
        )

    shown = await suggestion(await run(False), "EBP-03")
    await suggestion(await run(True), "EBP-04")
    found = await pending_suggestions(
        world.firm.person().tenant, world.firm.engagement_id, risks.TARGET, risks.RESPONSE_FIELD
    )
    assert [(p.id, p.target_id, p.value) for p in found] == [(shown, world.risk, "EBP-03")]
