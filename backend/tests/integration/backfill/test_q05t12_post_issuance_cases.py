"""Q-05-T12's case service (S51 partials, TASK-8730; DEC-5724; SPEC-711 AC-15 to AC-17; AUD-30).

Boundary: `create_app()` over HTTP on the migrated test database, `audit.post_issuance` on. A case
opens only on an archived audit, under the `post_issuance` kind (nothing else in the locked work
item is writable); with no certified line to match the comparison is unavailable, analysis and
the decision are refused; the agent never opens a case.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    await found.seed.run(
        "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
        "VALUES ($1, 'assurance_completion', '2000-01-01', 'test-seed') ON CONFLICT DO NOTHING",
        found.tenant_id,
    )
    await found.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'audit.post_issuance', 'true', 'test-seed', 'TASK-8730')",
        found.tenant_id,
    )
    return found


def _keyed() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


def _cases(world: Books) -> str:
    return f"/v1/audits/{world.work_item_id}/post-issuance/cases"


_BODY = {
    "type": "subsequently_discovered_facts",
    "source_kind": "other",
    "description": "Corrected certification: Stable Value Fund 1,151,230.",
}


async def _lock(world: Books) -> None:
    await world.seed.run(
        "INSERT INTO archives (tenant_id, engagement_id, seal, leaf_count, manifest, locked_by, "
        "actor_kind) VALUES ($1, $2, $3, 1, '{}'::jsonb, $4, 'human')",
        world.tenant_id,
        world.site.engagement_id,
        "a" * 64,
        world.partner.user_id,
    )


async def test_ac_a_case_opens_only_on_an_archived_audit(world: Books) -> None:
    early = await world.call("POST", _cases(world), world.manager, _BODY, headers=_keyed())
    assert early.status_code == 409, early.text
    assert cast(Json, early.json())["detail"] == "not_archived"

    await _lock(world)
    opened = await world.call("POST", _cases(world), world.manager, _BODY, headers=_keyed())
    assert opened.status_code == 201, opened.text
    case = cast(Json, opened.json())
    assert (case["ref"], case["type"], case["standard"], case["status"]) == (
        "PI-01",
        "subsequently_discovered_facts",
        "au_c_560",
        "under_evaluation",
    )
    assert case["description"] == _BODY["description"]
    told = await world.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'post_issuance.case_opened'",
        world.tenant_id,
    )
    assert told == 1

    listed = await world.call("GET", _cases(world), world.senior)
    assert listed.status_code == 200, listed.text
    body = cast(Json, listed.json())
    assert [cast(Json, i)["ref"] for i in cast(list[Json], body["items"])] == ["PI-01"]
    assert body["archive_locked_at"] is not None


async def test_ac_no_matching_line_no_comparison_no_analysis_no_decision(world: Books) -> None:
    await _lock(world)
    opened = await world.call("POST", _cases(world), world.partner, _BODY, headers=_keyed())
    assert opened.status_code == 201, opened.text
    one = f"{_cases(world)}/{cast(Json, opened.json())['case_id']}"

    compared = await world.call(
        "POST",
        f"{one}/comparison",
        world.partner,
        {"corrected": {"stable_value_fund": "1151230.00"}},
        headers=_keyed(),
    )
    assert compared.status_code == 409, compared.text
    assert cast(Json, compared.json())["detail"] == "comparison_unavailable"
    analysed = await world.call("POST", f"{one}/analysis", world.partner, headers=_keyed())
    assert analysed.status_code == 409, analysed.text
    decided = await world.call(
        "POST",
        f"{one}/decision",
        world.partner,
        {"decision": "no_action", "rationale": "Below clearly trivial."},
        headers=_keyed(),
    )
    assert decided.status_code == 409, decided.text

    # Nothing else in the locked work item is writable.
    with pytest.raises(Exception, match="archived"):
        await world.seed.run(
            "UPDATE post_issuance_events SET status = 'analysing' WHERE work_item_id = $1",
            world.work_item_id,
        )
