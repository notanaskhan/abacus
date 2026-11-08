"""A-04-T19's Remind against Postgres (TASK-5019; DEC-2483): the `reminded` event is stored in the
flag's insert-only history under the session's actor kind, the flag's own row is untouched, a flag
converted already answers 409, and a flag of another paper is 404. C5's drafting is stubbed: it has
its own tests (P-06-T14)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from abacus.kernel.errors import NotFound
from abacus.modules.workpapers import flags

from .support import Seeder, make_firm


@pytest.fixture
async def world(seed: Seeder, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    firm = await make_firm(seed)
    client_id = await seed.id(
        "SELECT client_id FROM engagements WHERE id = $1", firm.engagement_id
    )
    work_item = await seed.id(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, period_start, "
        "period_end, created_by) VALUES ($1, $2, $3, 'tax_return', 'Plan audit', '2025-01-01', "
        "'2025-12-31', $4) RETURNING id",
        firm.tenant_id,
        firm.engagement_id,
        client_id,
        firm.user_id,
    )
    paper = uuid.uuid4()
    await seed.run(
        "INSERT INTO workpapers (id, tenant_id, engagement_id, work_item_id, code, title, "
        "created_by) VALUES ($1, $2, $3, $4, 'AUD-05', 'Risk Assessment', $5)",
        paper,
        firm.tenant_id,
        firm.engagement_id,
        work_item,
        firm.user_id,
    )
    flag = await seed.id(
        "INSERT INTO attention_flags (tenant_id, workpaper_id, section_key, kind, text, "
        "created_by, created_by_kind) VALUES ($1, $2, 'menu_1', 'pbc_gap', "
        "'The trust agreement is missing', $3, 'human') "
        "RETURNING id",
        firm.tenant_id,
        paper,
        firm.user_id,
    )
    item_id = uuid.uuid4()
    follow_up = uuid.uuid4()

    async def items(*_a: object) -> list[object]:
        return [SimpleNamespace(id=item_id, status="requested")]

    async def draft(*_a: object) -> list[object]:
        return [SimpleNamespace(id=follow_up)]

    monkeypatch.setattr(flags, "request_items_for", items)
    monkeypatch.setattr(flags, "draft_follow_ups", draft)
    return SimpleNamespace(firm=firm, seed=seed, paper=paper, flag=flag, follow_up=follow_up)


@pytest.mark.asyncio
async def test_ac2_3_the_history_records_the_reminder_and_the_flag_stays_open(
    world: SimpleNamespace,
) -> None:
    found = await flags.remind(
        world.firm.person(), world.firm.engagement_id, world.paper, world.flag
    )
    assert found.draft_id == world.follow_up
    state = await world.seed.value("SELECT state FROM attention_flags WHERE id = $1", world.flag)
    assert state == "open"
    events = await world.seed.rows(
        "SELECT event, actor_kind, actor_user_id, ref->'ids'->>0 AS first_id "
        "FROM attention_flag_events WHERE flag_id = $1 AND event <> 'raised'",
        world.flag,
    )
    assert [tuple(e) for e in events] == [
        ("reminded", "human", world.firm.user_id, str(world.follow_up))
    ]


@pytest.mark.asyncio
async def test_a_flag_converted_already_answers_409(world: SimpleNamespace) -> None:
    await world.seed.run(
        "UPDATE attention_flags SET state = 'converted', converted_to_kind = 'request_item', "
        "converted_to_id = gen_random_uuid() WHERE id = $1",
        world.flag,
    )
    with pytest.raises(flags.FlagNotOpen):
        await flags.remind(world.firm.person(), world.firm.engagement_id, world.paper, world.flag)


@pytest.mark.asyncio
async def test_another_papers_flag_is_not_found(world: SimpleNamespace) -> None:
    with pytest.raises(NotFound):
        await flags.remind(world.firm.person(), world.firm.engagement_id, uuid.uuid4(), world.flag)
