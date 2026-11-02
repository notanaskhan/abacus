"""A-04-T18 (TASK-3006; A-04 §3.4 AC4.3, AC4.4; SPEC-620; DEC-2056).

Row acceptance: "After Margaret decides at 4:40 PM R3 reads Approved, R5 Rebuttal approved and
every row EP approved, Northwind's G4 is met, and a later edit to R4 reopens G4 with a blocker."

Boundary: `create_app()` over HTTP on the migrated test database, on A-04-T13's Northwind world
(the ten AUD-08 risks, R3 proposed significant, R5's rebuttal proposed). The partner decides the
`significant_risk` card through C3. Materiality is A-04-T12's, so G4's other part is read as its
own blocker here: after the approval only `materiality_not_decided` remains, and an edit to R4
adds `register_changed_after_approval`.
"""

from __future__ import annotations

from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance.api import g4_facts

from . import test_a04t13_risk_register as register
from .tb_support import Books, Json
from .test_a04t13_risk_register import world

# The register suite's request helpers, shared (private to that module by name only).
_keyed = register._keyed  # pyright: ignore[reportPrivateUsage] -- shared test helper
_northwind = register._northwind  # pyright: ignore[reportPrivateUsage] -- shared test helper
_patch = register._patch  # pyright: ignore[reportPrivateUsage] -- shared test helper
_path = register._path  # pyright: ignore[reportPrivateUsage] -- shared test helper

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _decision_cards(world: Books) -> None:
    """The card is C3's: its routes stand behind `review.grammar_api` (off in E0)."""
    await world.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'review.grammar_api', 'true', 'test-seed', 'A-04-T18') "
        "ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()


__all__ = ("world",)  # the fixture, imported for this module


async def _propose(world: Books) -> dict[str, Json]:
    made = await _northwind(world)
    status, body = await _patch(world, made["R3"], {"significance": "proposed"})
    assert status == 200, body
    made["R3"] = cast(Json, body["risk"])
    status, body = await _patch(world, made["R5"], {"fraud": "rebuttal_proposed"})
    assert status == 200, body
    made["R5"] = cast(Json, body["risk"])
    return made


async def _register(world: Books) -> dict[str, Json]:
    response = await world.call("GET", _path(world, "/register"), world.senior)
    assert response.status_code == 200, response.text
    rows = cast(list[Json], cast(Json, response.json())["risks"])
    return {cast(str, r["code"]): r for r in rows}


async def test_ac4_3_one_card_over_every_pending_proposal(world: Books) -> None:
    await _propose(world)
    response = await world.call(
        "POST", _path(world, "/approval-requests"), world.senior, headers=_keyed()
    )
    assert response.status_code == 201, response.text
    body = cast(Json, response.json())
    assert body["subject_codes"] == ["R3", "R5"]


async def test_ac4_3_nothing_pending_answers_409(world: Books) -> None:
    await _northwind(world)
    response = await world.call(
        "POST", _path(world, "/approval-requests"), world.senior, headers=_keyed()
    )
    assert response.status_code == 409
    assert cast(Json, response.json())["detail"] == "nothing_pending"


async def test_ac4_4_the_partner_approves_and_g4_reopens_after_an_edit(world: Books) -> None:
    made = await _propose(world)
    raised = await world.call(
        "POST", _path(world, "/approval-requests"), world.senior, headers=_keyed()
    )
    assert raised.status_code == 201, raised.text
    card = cast(Json, raised.json())["decision_card_id"]
    decide = f"/v1/decision-cards/{card}/decide"
    body: Json = {
        "option_key": "approve",
        "factors": [],
        "rationale": "R3 is significant; R5's rebuttal holds for certified investment income.",
        "seen_version": 1,
    }
    refused = await world.call("POST", decide, world.senior, body)
    assert refused.status_code == 403, refused.text
    decided = await world.call("POST", decide, world.partner, body)
    assert decided.status_code == 200, decided.text

    rows = await _register(world)
    assert rows["R3"]["significance"] == "approved"
    assert rows["R5"]["fraud"] == "rebuttal_approved"
    assert {r["status"] for r in rows.values()} == {"ep_approved"}
    tenant = TenantContext(world.tenant_id, "system", "a04t18")
    facts = await g4_facts(tenant, world.site.engagement_id)
    assert facts.blockers == ("materiality_not_decided",)

    status, edited = await _patch(world, rows["R4"], {"inherent_risk": "moderate"})
    assert status == 200, edited
    facts = await g4_facts(tenant, world.site.engagement_id)
    assert "register_changed_after_approval" in facts.blockers
    assert not facts.met
    del made
