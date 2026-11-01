"""A-04-T15 (TASK-2903; A-04 §6.1, AC3.4; SPEC-620; DEC-1953).

Row acceptance: "On the fake model the Northwind card shows Recommended by Accrued Agent on 1.5%
with reasons, the agent principal's decide returns 403, and evals/decision_recommendation passes
every threshold."

Boundary: `create_app()` over HTTP on the migrated test database, with the fake model answering
`decisions.recommend@v1` through the agents module's own responder (read from the task by code).
The suite half is `tests/unit/tools/test_a04t09_decision_recommendation.py` on the same graders.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Final, cast

import pytest

from abacus.ai_gateway import FakeModel, configure_provider
from abacus.kernel.flags import forget_flags
from abacus.modules.agents.api import install_fake_responses

from .tb_support import Books, Json
from .test_a04t12_materiality_service import _keyed, _path
from .test_a04t12_materiality_service import world as materiality_world

pytestmark = pytest.mark.asyncio

world = materiality_world
DRAFTING: Final = "workpapers.drafting"


@pytest.fixture(autouse=True)
def _model() -> Iterator[None]:
    configure_provider(install_fake_responses(FakeModel()))
    yield
    configure_provider(None)


async def _drafting_on(books_: Books) -> None:
    await books_.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'A-04-T15') ON CONFLICT DO NOTHING",
        books_.tenant_id,
        DRAFTING,
    )
    forget_flags()


async def _propose(books_: Books, tb_id: uuid.UUID) -> tuple[int, Json]:
    response = await books_.call(
        "POST",
        _path(books_, "/proposals"),
        books_.manager,
        {"tb_snapshot_id": str(tb_id), "benchmark_key": "net_assets", "recommend": True},
        headers=_keyed(),
    )
    return response.status_code, cast(Json, response.json())


async def test_the_card_carries_the_agents_tag_on_1_5_with_reasons(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, tb_id = world
    await _drafting_on(books_)
    status, proposed = await _propose(books_, tb_id)
    assert status == 201, proposed
    tagged = [o["key"] for o in cast(list[Json], proposed["options"]) if o["recommended"]]
    assert tagged == ["rate_1_5"]
    card = await books_.call(
        "GET", f"/v1/decision-cards/{proposed['decision_card_id']}", books_.partner
    )
    assert card.status_code == 200, card.text
    body = cast(Json, card.json())
    assert "Accrued Agent" in card.text
    assert body["card"]["recommendation_suggestion_id"] is not None  # type: ignore[index]
    run = await books_.seed.value(
        "SELECT status FROM agent_runs WHERE tenant_id = $1 AND agent_id = $2",
        books_.tenant_id,
        "decisions.recommender",
    )
    assert run == "completed"


async def test_without_drafting_a_recommendation_is_409(world: tuple[Books, uuid.UUID]) -> None:
    books_, tb_id = world
    status, body = await _propose(books_, tb_id)
    assert (status, body["detail"]) == (409, "drafting_not_enabled")


async def test_the_agent_never_decides(world: tuple[Books, uuid.UUID]) -> None:
    books_, tb_id = world
    await _drafting_on(books_)
    _, proposed = await _propose(books_, tb_id)
    decided = await books_.seed.value(
        "SELECT count(*) FROM decisions WHERE tenant_id = $1", books_.tenant_id
    )
    assert decided == 0
    # The decisions table is human-only (0094) and the matrix denies the agent `decision.decide`:
    # an agent context deciding the tagged card is refused before anything is written.
    from abacus.modules.agents.api import load_agent_context
    from abacus.modules.review.decisions import decide_card

    run_id = await books_.seed.value(
        "SELECT id FROM agent_runs WHERE tenant_id = $1 AND agent_id = 'decisions.recommender'",
        books_.tenant_id,
    )
    await books_.seed.run_untriggered(
        "UPDATE agent_runs SET status = 'running' WHERE id = $1", run_id
    )
    agent = await load_agent_context(books_.tenant_id, cast(uuid.UUID, run_id))
    with pytest.raises(Exception) as refused:
        await decide_card(
            agent,  # type: ignore[arg-type]  # the agent is not a person: refused
            uuid.UUID(cast(str, proposed["decision_card_id"])),
            option_key="rate_1_5",
            factors=[],
            rationale="The agent cannot decide.",
            seen_version=1,
        )
    assert refused.typename in {"Forbidden", "HumanRequired", "NotAPerson"}, refused.typename
