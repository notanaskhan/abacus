"""A-02-T29 (TASK-1615; ADR-078 independent AC tests; SPEC-333 AC-35..AC-44; A-02 §3.9-§3.11;
C20 v1): entity-scoped connections, reconnect requests and health, written from the spec and the
contract rather than from the code, over HTTP through `create_app()`, the real `authorise`, walls
and row-level security, on A-02-T16's world.

Each test seeds the violation it guards against and expects the refusal: starting without the
authorization or a fresh second factor; a spent or someone else's OAuth state; a second live
ledger (by the API and by the database); a second card feed of a different account is allowed
(many feeds); disconnect keeps what was received; `token_expired` reads Needs reauth while an
outage reads Needs attention; Tess Moreno cannot read another client's connection (INV-4); the
agent and the system hold no connection-making action; a portal person cannot ask the firm's
reconnect question.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from abacus.modules.identity.authz.matrix import RULES

from . import test_a02t16_entity_connections as t16

World = t16.World
demo_ledger = t16.demo_ledger
no_temporal = t16.no_temporal
world = t16.world
LEDGER = t16.LEDGER


async def test_ac36_no_authorization_no_state_no_consent(world: World) -> None:
    refused = await world.start(authorized=False)
    assert refused.status_code == 422
    assert (await world.count("connection_states"), await world.count("connection_consents")) == (
        0,
        0,
    )


async def test_ac36_a_stale_second_factor_cannot_start(world: World) -> None:
    stale = await world.call(
        "POST",
        f"{world.cards_path}/{LEDGER}/start",
        world.tess,
        {"consent_version": 1, "authorized": True},
        mfa=False,
    )
    assert stale.status_code == 403
    assert await world.count("connection_states") == 0


async def test_ac36_a_state_completes_once_and_only_for_its_starter(world: World) -> None:
    # Presented by anyone else, the state is spent and refused (A-02-T16: fail closed).
    handed = await world.handed()
    stolen = await world.complete(handed, world.contributor)
    assert stolen.status_code == 409
    assert (await world.complete(handed)).status_code == 409
    assert await world.count("connections") == 0
    # The starter's own state completes once; a replay is refused.
    fresh = await world.handed()
    first = await world.complete(fresh)
    assert first.status_code == 201
    replay = await world.complete(fresh)
    assert replay.status_code == 409 and replay.json()["detail"] == "invalid_state"
    assert await world.count("connections") == 1


async def test_one_live_ledger_per_entity_by_the_api_and_the_database(world: World) -> None:
    done = await world.connected()
    again = await world.start()
    assert again.status_code == 409
    with pytest.raises(asyncpg.UniqueViolationError):
        await world.net.seed.run(
            "INSERT INTO connections (tenant_id, client_entity_id, provider, scopes, created_by, "
            "category, status) VALUES ($1, $2, 'fake', '{}', 'seed', 'ledger', 'active')",
            world.tenant,
            world.site.entity_id,
        )
    assert done["connection_id"]


async def test_many_feeds_of_different_accounts_may_be_live(world: World) -> None:
    for account in ("acct-1009", "acct-2210"):
        await world.net.seed.run(
            "INSERT INTO connections (tenant_id, client_entity_id, provider, scopes, created_by, "
            "category, status, external_account_ref) "
            "VALUES ($1, $2, 'fake_card_feed', '{}', 'seed', 'card_feed', 'active', $3)",
            world.tenant,
            world.site.entity_id,
            account,
        )
    rows = await world.net.seed.rows(
        "SELECT count(*) AS n FROM connections WHERE tenant_id = $1 AND category = 'card_feed' "
        "AND status = 'active'",
        world.tenant,
    )
    assert rows[0]["n"] == 2


async def test_ac39_disconnect_keeps_what_was_received(world: World) -> None:
    done = await world.connected()
    cid = done["connection_id"]
    version = (await world.card())["version"]
    gone = await world.call(
        "POST", f"/v1/portal/connections/{cid}/disconnect", world.tess, {"seen_version": version}
    )
    assert gone.status_code == 200
    assert await world.count("connection_secrets") == 0
    assert await world.count("connections") == 1


@pytest.mark.parametrize(
    ("reason", "word"),
    [
        ("token_expired", "needs_reauth"),
        ("invalid_grant", "needs_reauth"),
        ("provider_unavailable", "needs_attention"),
    ],
)
async def test_ac_needs_reauth_is_split_from_needs_attention_by_code(
    world: World, reason: str, word: str
) -> None:
    done = await world.connected()
    await world.net.seed.run(
        "UPDATE connections SET status = 'needs_attention', status_reason_code = $2 WHERE id = $1",
        uuid.UUID(str(done["connection_id"])),
        reason,
    )
    assert (await world.card())["status"] == word


async def test_inv4_tess_moreno_cannot_read_another_clients_connection(world: World) -> None:
    done = await world.connected()
    cid = done["connection_id"]
    theirs = await world.call("GET", f"/v1/portal/connections/{cid}", world.stranger_owner)
    assert theirs.status_code == 404
    other_cards = await world.call(
        "GET", f"/v1/portal/entities/{world.other.entity_id}/connections", world.tess
    )
    assert other_cards.status_code == 404


@pytest.mark.parametrize(
    "action",
    [
        "connection.create",
        "connection.revoke",
        "connection.retry",
        "connection.disconnect",
        "connection.reconnect_request",
    ],
)
def test_the_agent_and_the_system_cannot_make_or_end_a_connection(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") in (None, "deny")
    assert rule.decisions.get("system") in (None, "deny")


async def test_a_portal_person_cannot_ask_the_firms_reconnect_question(world: World) -> None:
    done = await world.connected()
    cid = done["connection_id"]
    await world.net.seed.run(
        "UPDATE connections SET status = 'needs_attention', status_reason_code = 'token_expired' "
        "WHERE id = $1",
        uuid.UUID(str(cid)),
    )
    headers = world.net.headers(world.tess)
    headers["Idempotency-Key"] = f"a02t29-{uuid.uuid4().hex}"
    asked = await world.net.http.post(f"/v1/connections/{cid}/reconnect-requests", headers=headers)
    assert asked.status_code in (403, 404)
