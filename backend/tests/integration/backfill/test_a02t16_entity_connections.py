"""A-02-T16 (TASK-1416; SPEC-333 AC-35 to AC-42; A-02 AC-9.1 to AC-9.8; C20 v1): POR-16's
entity-scoped connection service over HTTP, through `create_app()`, the real `authorise`, walls,
row-level security and the migrated test database, with the demo ledger (`fake`) as the system.

The row's acceptance: starting without the authorization is refused `authorization_required`, a
reused OAuth state is refused, and the activity renders "Connected by Tess Moreno (client)".
Around it: fresh MFA and the client Owner only; another client's entity is 404 (INV-4); the
consent is recorded once as shown; the catalogue's honesty (an unregistered adapter offers only
*Export instead* on a ledger); one live ledger per entity; reconnect in place; Try again runs one
retry and a second click answers the same run; disconnect erases the secret and keeps what was
received; the legacy engagement routes read the same connection.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.egress import EgressRefused
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.connections import retrievals
from abacus.modules.connections.api import FakeConnector, Unavailable, revoke_retired
from abacus.modules.integrations.api import register_adapter, unregister_adapter

from .support import Json, Net, Person, Site

Card = dict[str, Any]  # Any: JSON as the API answers it
COUNTS: Final = {
    "connections": "SELECT count(*) FROM connections WHERE tenant_id = $1",
    "connection_states": "SELECT count(*) FROM connection_states WHERE tenant_id = $1",
    "connection_consents": "SELECT count(*) FROM connection_consents WHERE tenant_id = $1",
    "connection_consent_links": (
        "SELECT count(*) FROM connection_consent_links WHERE tenant_id = $1"
    ),
    "connection_secrets": "SELECT count(*) FROM connection_secrets WHERE tenant_id = $1",
    "sync_runs": "SELECT count(*) FROM sync_runs WHERE tenant_id = $1",
    "connection_grant_revocations": (
        "SELECT count(*) FROM connection_grant_revocations WHERE tenant_id = $1"
    ),
}
MASTER: Final = b"a02t16-master-key-0123456789abcdef"
LEDGER: Final = "probe_t16_demo_ledger"  # the catalogue row whose system is the demo ledger
UNBUILT: Final = "probe_t16_unbuilt_ledger"  # a ledger with no adapter here
AUTHORIZATION: Final = (
    "I authorize Brightwater Hale LLP to read this account for the services in our engagement "
    "letter"
)


def _row(key: str, provider: str, **over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "key": key,
        "name": "Demo ledger" if key == LEDGER else "Unbuilt ledger",
        "category": "ledger",
        "ownership_mode": "client_authorised",
        "surfaces": ["portal"],
        "connector_provider": provider,
        "adapter_key": provider if key == LEDGER else f"{provider}_adapter",
        "listing_status": "available",
        "consent_copy": {
            "title": "Connect Demo ledger",
            "will": ["Read your chart of accounts and trial balance"],
            "wont": ["Change, post or delete anything in your ledger", "See your password"],
            "authorization": AUTHORIZATION,
            "continue_label": "Continue to Demo ledger",
        },
        "consent_version": 1,
        "scopes": {"read": [{"code": "ledger.read", "label": "Read ledger"}]},
        "icon": "book-open",
        "tone": "olive",
        "sort_order": 10,
    }
    row.update(over)
    return row


class DemoAdapter:
    """The demo ledger's read-only adapter, registered for the test (catalogue honesty)."""

    key = "fake"
    category = "ledger"
    connector_provider = "fake"

    def read_scopes(self) -> tuple[str, ...]:
        return ("ledger.read",)

    def egress_hosts(self) -> tuple[str, ...]:
        return ("demo.ledger.example",)


@pytest.fixture(autouse=True)
def demo_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_FAKE_CONNECTOR_DIR", str(tmp_path))
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    register_adapter(DemoAdapter())
    yield
    unregister_adapter(DemoAdapter.key)
    reset_key_service()
    forget_flags()
    settings.cache_clear()


@pytest.fixture(autouse=True)
def no_temporal(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[uuid.UUID]]:
    """Retries record their run; the workflow start is noted, not dispatched."""
    started: list[uuid.UUID] = []

    async def note(_tenant_id: uuid.UUID, run_id: uuid.UUID) -> None:
        started.append(run_id)

    monkeypatch.setattr(retrievals, "_start", note)
    yield started


@dataclass(frozen=True)
class World:
    net: Net
    site: Site
    other: Site
    tess: Person  # Owner of the site's entity (an engagement grant)
    contributor: Person
    partner: Person
    manager: Person
    stranger_owner: Person  # Owner on another client's entity

    @property
    def tenant(self) -> uuid.UUID:
        return self.site.tenant_id

    @property
    def cards_path(self) -> str:
        return f"/v1/portal/entities/{self.site.entity_id}/connections"

    async def call(
        self, method: str, path: str, who: Person, body: Json | None = None, *, mfa: bool = True
    ) -> httpx.Response:
        headers = self.net.headers(who, mfa=mfa)
        if method == "POST":
            headers["Idempotency-Key"] = f"a02t16-{uuid.uuid4().hex}"
        return await self.net.http.request(method, path, json=body, headers=headers)

    async def cards(self, who: Person | None = None) -> list[Card]:
        response = await self.call("GET", self.cards_path, who or self.tess)
        assert response.status_code == 200, response.text
        return cast(list[Card], response.json()["items"])

    async def card(self, key: str = LEDGER) -> Card:
        return next(c for c in await self.cards() if c["catalog_key"] == key)

    async def start(
        self, who: Person | None = None, *, authorized: bool = True, version: int = 1
    ) -> httpx.Response:
        return await self.call(
            "POST",
            f"{self.cards_path}/{LEDGER}/start",
            who or self.tess,
            {"consent_version": version, "authorized": authorized},
        )

    async def handed(self) -> dict[str, str]:
        started = await self.start()
        assert started.status_code == 201, started.text
        query = parse_qs(urlsplit(str(started.json()["authorise_url"])).query)
        return {"state": query["state"][0], "code": query["code"][0]}

    async def complete(self, handed: dict[str, str], who: Person | None = None) -> httpx.Response:
        return await self.call("POST", "/v1/connections/complete", who or self.tess, dict(handed))

    async def connected(self) -> Card:
        """Connect (or reconnect) the demo ledger; its card, as the portal reads it after."""
        done = await self.complete(await self.handed())
        assert done.status_code == 201, done.text
        body = done.json()
        assert body["engagement_id"] == str(self.site.engagement_id)
        # A-02-T28 (additive): the entity, so the portal returns to POR-16.
        assert body["client_entity_id"] == str(self.site.entity_id)
        return await self.card()

    async def count(self, table: str) -> int:
        return cast(int, await self.net.seed.value(COUNTS[table], self.tenant))

    async def actions(self, prefix: str) -> list[str]:
        return [a for a in await self.net.seed.actions(self.tenant) if a.startswith(prefix)]


async def _load_catalogue(net: Net) -> None:
    rows = [_row(LEDGER, "fake"), _row(UNBUILT, "probe_t16_unbuilt")]
    await net.seed.value(
        "SELECT count(*) FROM integration_catalog_load($1::jsonb, 'a02t16-test')", json.dumps(rows)
    )


@pytest.fixture
async def world(net: Net) -> AsyncIterator[World]:
    seed = net.seed
    await _load_catalogue(net)
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "a02t16")
    other = await seed.site(tenant, admin.user_id, "a02t16-other")
    team: dict[str, Person] = {}
    for role in ("engagement_partner", "manager"):
        who = await seed.person(tenant)
        await seed.member(site, who, role)
        team[role] = who
    tess = await seed.client_contact(site)
    await seed.run("UPDATE users SET display_name = 'Tess Moreno' WHERE id = $1", tess.user_id)
    contributor = await seed.client_contact(site, "client_contributor")
    stranger = await seed.client_contact(other)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'connections.portal_v2', 'true', 'test-seed', 'A-02-T16')",
        tenant,
    )
    forget_flags()
    yield World(
        net,
        site,
        other,
        tess,
        contributor,
        team["engagement_partner"],
        team["manager"],
        stranger,
    )


# --- start: the authorization, fresh MFA, who may start ------------------------------------------


async def test_ac36_starting_without_the_authorization_is_refused(world: World) -> None:
    refused = await world.start(authorized=False)
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"] == "authorization_required"
    assert await world.count("connection_consents") == 0
    assert await world.count("connection_states") == 0


async def test_ac36_starting_needs_a_fresh_second_factor(world: World) -> None:
    stale = await world.call(
        "POST",
        f"{world.cards_path}/{LEDGER}/start",
        world.tess,
        {"consent_version": 1, "authorized": True},
        mfa=False,
    )
    assert stale.status_code == 403, stale.text
    assert await world.count("connection_consents") == 0


@pytest.mark.parametrize("who", ["partner", "manager", "contributor"])
async def test_ac41_firm_staff_and_contributors_cannot_start(world: World, who: str) -> None:
    refused = await world.start(cast(Person, getattr(world, who)))
    assert refused.status_code == 403, refused.text
    assert await world.count("connection_states") == 0


async def test_ac41_another_clients_owner_and_another_firm_get_404(world: World) -> None:
    for path in (world.cards_path, f"{world.cards_path}/{LEDGER}/start"):
        method = "POST" if path.endswith("/start") else "GET"
        body: Json | None = (
            {"consent_version": 1, "authorized": True} if method == "POST" else None
        )
        response = await world.call(method, path, world.stranger_owner, body)
        assert response.status_code == 404, response.text
        assert world.site.marker not in response.text
    stranger_firm = await world.net.seed.firm()
    outsider = await world.net.seed.person(stranger_firm, "firm_admin")
    assert (await world.call("GET", world.cards_path, outsider)).status_code == 404


async def test_ac37_the_consent_is_recorded_once_as_shown(world: World) -> None:
    started = await world.start()
    assert started.status_code == 201, started.text
    body = started.json()
    assert "authorise_url" in body and body["consent_id"]
    rows = await world.net.seed.rows(
        "SELECT * FROM connection_consents WHERE tenant_id = $1", world.tenant
    )
    assert len(rows) == 1
    consent = rows[0]
    assert consent["catalog_key"] == LEDGER and consent["consent_version"] == 1
    assert list(consent["will"]) == ["Read your chart of accounts and trial balance"]
    assert next(iter(consent["wont"])) == "Change, post or delete anything in your ledger"
    assert consent["authorization_text"] == AUTHORIZATION
    assert consent["authorised_by_user_id"] == world.tess.user_id
    assert len(consent["ip_sha256"]) == 64
    state = await world.net.seed.rows(
        "SELECT consent_id, client_entity_id, user_id, category FROM connection_states "
        "WHERE tenant_id = $1",
        world.tenant,
    )
    assert state[0]["consent_id"] == consent["id"]
    assert (state[0]["client_entity_id"], state[0]["user_id"]) == (
        world.site.entity_id,
        world.tess.user_id,
    )
    assert await world.actions("connection.") == [
        "connection.consent_recorded",
        "connection.started",
    ]


async def test_an_old_consent_copy_and_an_unbuilt_system_are_refused(world: World) -> None:
    stale = await world.start(version=2)
    assert stale.status_code == 409 and stale.json()["detail"] == "consent_version_stale"
    unbuilt = await world.call(
        "POST",
        f"{world.cards_path}/{UNBUILT}/start",
        world.tess,
        {"consent_version": 1, "authorized": True},
    )
    assert unbuilt.status_code == 409 and unbuilt.json()["detail"] == "connector_not_available"
    assert await world.count("connection_consents") == 0


# --- complete: single-use state, the activity grammar --------------------------------------------


async def test_ac36_a_reused_oauth_state_is_refused_and_nothing_more_is_created(
    world: World,
) -> None:
    handed = await world.handed()
    first = await world.complete(handed)
    assert first.status_code == 201, first.text
    assert (await world.card())["reconnected"] is False
    before = await world.count("connections")
    again = await world.complete(handed)
    assert again.status_code == 409 and again.json()["detail"] == "invalid_state"
    assert await world.count("connections") == before == 1


async def test_a_state_is_bound_to_the_person_who_started_it(world: World) -> None:
    other_owner = await world.net.seed.client_contact(world.site)  # same entity, another Owner
    stolen = await world.complete(await world.handed(), other_owner)
    assert stolen.status_code == 409 and stolen.json()["detail"] == "invalid_state"
    assert await world.count("connections") == 0


async def test_ac42_the_activity_reads_connected_by_tess_moreno_client(world: World) -> None:
    done = await world.connected()
    detail = await world.call("GET", f"/v1/portal/connections/{done['connection_id']}", world.tess)
    assert detail.status_code == 200, detail.text
    lines = [a["text"] for a in detail.json()["activity"]]
    assert lines == ["Connected by Tess Moreno (client)"]
    card = detail.json()["card"]
    assert card["connected_by"] == {
        "user_id": str(world.tess.user_id),
        "display_name": "Tess Moreno",
        "kind": "client",
    }
    # The firm reads the same activity (connection.read on the entity's engagement).
    firm = await world.call(
        "GET", f"/v1/portal/connections/{done['connection_id']}", world.manager
    )
    assert firm.status_code == 200
    assert [a["text"] for a in firm.json()["activity"]] == lines


# --- cards: honest catalogue, status words, Export instead ---------------------------------------


async def test_ac35_cards_show_status_words_and_export_instead_beside_every_ledger(
    world: World,
) -> None:
    before = await world.card()
    assert before["status"] == "available"
    assert before["allowed_actions"] == ["connect", "export_instead"]
    assert [s["code"] for s in before["scopes"]] == ["ledger.read"]  # read scopes only (DF-19)
    unbuilt = await world.card(UNBUILT)
    assert unbuilt["status"] == "coming_soon"
    assert unbuilt["allowed_actions"] == ["export_instead"]  # ADR-108: only Export instead
    await world.connected()
    after = await world.card()
    assert after["status"] == "connected" and after["connection_id"]
    assert after["allowed_actions"] == ["details", "disconnect", "export_instead"]
    assert after["export_instead"] == {"request_item_id": None, "binder_id": None}
    firm = next(c for c in await world.cards(world.manager) if c["catalog_key"] == LEDGER)
    assert "disconnect" not in firm["allowed_actions"] and "connect" not in firm["allowed_actions"]


async def test_a_second_live_ledger_for_the_entity_is_refused(world: World) -> None:
    await world.connected()
    second = await world.start()
    assert second.status_code == 409 and second.json()["detail"] == "ledger_already_connected"


async def test_the_legacy_engagement_route_reads_the_same_ledger(world: World) -> None:
    done = await world.connected()
    legacy = await world.call(
        "GET", f"/v1/engagements/{world.site.engagement_id}/connection", world.tess
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["id"] == done["connection_id"]


async def test_flag_off_is_404_after_authorisation(world: World) -> None:
    await world.net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 "
        "AND flag = 'connections.portal_v2'",
        world.tenant,
    )
    forget_flags()
    assert (await world.call("GET", world.cards_path, world.tess)).status_code == 404


# --- reconnect, retry, disconnect ----------------------------------------------------------------


async def _needs(world: World, connection_id: object, reason: str) -> None:
    await world.net.seed.run(
        "UPDATE connections SET status = 'needs_attention', status_reason_code = $2 WHERE id = $1",
        uuid.UUID(str(connection_id)),
        reason,
    )


async def test_ac9_3_a_reconnect_reauthorises_the_same_connection(world: World) -> None:
    done = await world.connected()
    await _needs(world, done["connection_id"], "token_expired")
    await world.net.seed.run(
        "INSERT INTO reconnect_requests (tenant_id, connection_id, requested_by_user_id, "
        "engagement_id) VALUES ($1, $2, $3, $4)",
        world.tenant,
        uuid.UUID(str(done["connection_id"])),
        world.manager.user_id,
        world.site.engagement_id,
    )
    reauth = await world.card()
    assert reauth["status"] == "needs_reauth" and reauth["reauth_requested_at"]
    assert reauth["allowed_actions"] == ["reconnect", "details", "export_instead"]
    again = await world.connected()
    assert again["connection_id"] == done["connection_id"] and again["reconnected"] is True
    card = await world.card()
    assert card["status"] == "connected" and card["reconnected"] is True
    assert card["reauth_requested_at"] is None  # the request was fulfilled
    detail = await world.call("GET", f"/v1/portal/connections/{done['connection_id']}", world.tess)
    texts = [a["text"] for a in detail.json()["activity"]]
    assert texts == ["Reconnected by Tess Moreno (client)", "Connected by Tess Moreno (client)"]
    links = await world.count("connection_consent_links")
    assert links == 2  # each consent linked once, to the same connection


async def test_ac40_retry_needs_reauth_first_then_runs_once(
    world: World, no_temporal: list[uuid.UUID]
) -> None:
    done = await world.connected()
    cid = uuid.UUID(str(done["connection_id"]))
    retry = f"/v1/portal/connections/{cid}/retry"
    await _needs(world, cid, "token_expired")
    refused = await world.call("POST", retry, world.tess)
    assert refused.status_code == 409 and refused.json()["detail"] == "connection_needs_reauth"
    await _needs(world, cid, "sync_failed")
    nothing = await world.call("POST", retry, world.tess)
    assert nothing.status_code == 409 and nothing.json()["detail"] == "no_failed_sync"
    await world.net.seed.run(
        "INSERT INTO sync_runs (id, tenant_id, client_entity_id, connection_id, engagement_id, "
        "request_item_id, dataset, period_start, period_end, started_by, status, failure_code, "
        "finished_at) VALUES ($1, $2, $3, $4, $5, $6, 'trial_balance', '2025-01-01', "
        "'2025-12-31', $7, 'failed', 'provider_unavailable', clock_timestamp())",
        uuid.uuid4(),
        world.tenant,
        world.site.entity_id,
        cid,
        world.site.engagement_id,
        world.site.item_id,
        str(world.tess.user_id),
    )
    card = await world.card()
    assert card["status"] == "needs_attention" and card["last_failed_at"]
    assert card["allowed_actions"][0] == "retry"
    first = await world.call("POST", retry, world.tess)
    assert first.status_code == 202, first.text
    second = await world.call("POST", retry, world.tess)
    assert second.status_code == 202 and second.json() == first.json()
    # One run; its workflow is ensured on each click (the start attaches to a running one).
    assert set(no_temporal) == {uuid.UUID(first.json()["sync_run_id"])}
    assert await world.count("sync_runs") == 2
    assert (await world.actions("connection.retry_requested")) == [
        "connection.retry_requested"
    ] * 2


async def test_ac39_disconnect_erases_the_secret_and_keeps_what_was_received(
    world: World,
) -> None:
    done = await world.connected()
    cid = done["connection_id"]
    assert await world.count("connection_secrets") == 1
    path = f"/v1/portal/connections/{cid}/disconnect"
    stale = await world.call("POST", path, world.tess, {"seen_version": 99})
    assert stale.status_code == 409 and stale.json()["detail"] == "stale_version"
    manager = await world.call("POST", path, world.manager, {"seen_version": 1})
    assert manager.status_code == 403  # the client's Owner disconnects, not the firm
    no_mfa = await world.call("POST", path, world.tess, {"seen_version": 1}, mfa=False)
    assert no_mfa.status_code == 403
    version = (await world.card())["version"]
    gone = await world.call("POST", path, world.tess, {"seen_version": version})
    assert gone.status_code == 200, gone.text
    assert gone.json()["status"] == "disconnected"
    assert await world.count("connection_secrets") == 0
    assert await world.count("connections") == 1  # the row and its history stay
    detail = await world.call("GET", f"/v1/portal/connections/{cid}", world.tess)
    assert detail.json()["activity"][0]["text"] == "Disconnected by Tess Moreno (client)"
    again = await world.call("POST", path, world.tess, {"seen_version": version + 1})
    assert again.status_code == 404


# --- security review fix round (DEC-515) ---------------------------------------------------------


async def _revocation_events(world: World) -> list[OutboxEvent]:
    rows = await world.net.seed.rows(
        "SELECT id, payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'connection_grant.revocation_requested' ORDER BY seq",
        world.tenant,
    )
    return [
        OutboxEvent(
            cast(uuid.UUID, r["id"]),
            world.tenant,
            "connection_grant.revocation_requested",
            cast(
                dict[str, object],
                json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
            ),
        )
        for r in rows
    ]


async def test_m1_disconnect_and_reconnect_revoke_the_grant_at_the_provider(world: World) -> None:
    done = await world.connected()
    cid = uuid.UUID(str(done["connection_id"]))
    await _needs(world, cid, "token_expired")
    await world.connected()  # the reconnect replaces the grant
    version = (await world.card())["version"]
    gone = await world.call(
        "POST", f"/v1/portal/connections/{cid}/disconnect", world.tess, {"seen_version": version}
    )
    assert gone.status_code == 200, gone.text
    reasons = await world.net.seed.rows(
        "SELECT reason FROM connection_grant_revocations WHERE tenant_id = $1 ORDER BY created_at",
        world.tenant,
    )
    assert [r["reason"] for r in reasons] == ["replaced", "disconnected"]
    assert await world.count("connection_secrets") == 0
    events = await _revocation_events(world)
    assert len(events) == 2
    for event in events:
        await revoke_retired(event)
        await revoke_retired(event)  # a replay finds nothing left to do
    assert await world.count("connection_grant_revocations") == 0  # crypto-erased
    revoked = await world.net.seed.rows(
        "SELECT after_ref FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'connection.grant_revoked'",
        world.tenant,
    )
    assert len(revoked) == 2
    for r in revoked:
        after = r["after_ref"]
        assert (json.loads(after) if isinstance(after, str) else after)["result"] == 0


async def test_l6_the_state_keeps_a_sealed_pkce_verifier(world: World) -> None:
    started = await world.start()
    assert started.status_code == 201, started.text
    row = await world.net.seed.rows(
        "SELECT verifier_sealed FROM connection_states WHERE tenant_id = $1", world.tenant
    )
    assert row[0]["verifier_sealed"] is not None
    assert b"demo" not in bytes(row[0]["verifier_sealed"])


async def test_m2_the_legacy_start_is_closed_once_por16_is_on(world: World) -> None:
    refused = await world.call(
        "POST",
        f"/v1/engagements/{world.site.engagement_id}/connection/start",
        world.tess,
        {"provider": "fake"},
    )
    assert refused.status_code == 409 and refused.json()["detail"] == "connection_flow_moved"


async def _flag(world: World, on: bool) -> None:
    await world.net.seed.run(
        "UPDATE feature_flag_states SET value = $2 WHERE tenant_id = $1 "
        "AND flag = 'connections.portal_v2'",
        world.tenant,
        "true" if on else "false",
    )
    forget_flags()


async def test_m2_a_legacy_flow_never_replaces_a_consented_ledger(world: World) -> None:
    done = await world.connected()
    await _flag(world, False)
    started = await world.call(
        "POST",
        f"/v1/engagements/{world.site.engagement_id}/connection/start",
        world.tess,
        {"provider": "fake"},
    )
    assert started.status_code == 200, started.text
    query = parse_qs(urlsplit(str(started.json()["authorise_url"])).query)
    refused = await world.complete({"state": query["state"][0], "code": query["code"][0]})
    assert refused.status_code == 409 and refused.json()["detail"] == "ledger_already_connected"
    # Round 2 L2: the grant the refused legacy completion obtained is queued for revocation.
    queued = await world.net.seed.rows(
        "SELECT reason FROM connection_grant_revocations WHERE tenant_id = $1", world.tenant
    )
    assert [r["reason"] for r in queued] == ["abandoned"]
    legacy = await world.call(
        "GET", f"/v1/engagements/{world.site.engagement_id}/connection", world.tess
    )
    assert legacy.json()["id"] == done["connection_id"]  # the consented ledger stays


async def test_l9_a_portal_state_does_not_complete_with_the_flag_off(world: World) -> None:
    handed = await world.handed()
    await _flag(world, False)
    off = await world.complete(handed)
    assert off.status_code == 404
    assert await world.count("connections") == 0


async def test_l5_a_completion_refused_after_the_exchange_queues_its_grant(world: World) -> None:
    handed = await world.handed()
    await world.net.seed.run(
        "INSERT INTO connections (id, tenant_id, client_entity_id, provider, status, scopes, "
        "created_by, category) VALUES ($1, $2, $3, 'import', 'active', '{}', 'seed', 'ledger')",
        uuid.uuid4(),
        world.tenant,
        world.site.entity_id,
    )
    refused = await world.complete(handed)
    assert refused.status_code == 409 and refused.json()["detail"] == "ledger_already_connected"
    assert (await world.actions("connection.failed")) == ["connection.failed"]
    queued = await world.net.seed.rows(
        "SELECT reason, state_id, connection_id FROM connection_grant_revocations "
        "WHERE tenant_id = $1",
        world.tenant,
    )
    assert len(queued) == 1 and queued[0]["reason"] == "abandoned"
    assert queued[0]["state_id"] is not None and queued[0]["connection_id"] is None
    for event in await _revocation_events(world):
        await revoke_retired(event)
    assert await world.count("connection_grant_revocations") == 0
    assert (await world.actions("connection.grant_revoked")) == ["connection.grant_revoked"]


async def _queued_revocation(world: World) -> OutboxEvent:
    done = await world.connected()
    version = (await world.card())["version"]
    gone = await world.call(
        "POST",
        f"/v1/portal/connections/{done['connection_id']}/disconnect",
        world.tess,
        {"seen_version": version},
    )
    assert gone.status_code == 200, gone.text
    (event,) = await _revocation_events(world)
    return event


async def _revoked_results(world: World) -> list[int]:
    rows = await world.net.seed.rows(
        "SELECT after_ref FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'connection.grant_revoked'",
        world.tenant,
    )
    out: list[int] = []
    for r in rows:
        after = r["after_ref"]
        out.append(cast(int, (json.loads(after) if isinstance(after, str) else after)["result"]))
    return out


async def test_m1_round2_an_unreachable_provider_is_given_up_on_the_last_attempt(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = await _queued_revocation(world)

    async def down(_self: object) -> None:
        raise Unavailable("provider_unavailable")

    monkeypatch.setattr(FakeConnector, "revoke", down)
    with pytest.raises(Unavailable):  # early: the relay retries
        await revoke_retired(event)
    assert await world.count("connection_grant_revocations") == 1
    await world.net.seed.run(
        "UPDATE connection_grant_revocations SET created_at = now() - interval '1 day' "
        "WHERE tenant_id = $1",
        world.tenant,
    )
    await revoke_retired(event)  # the last attempt: recorded and erased, never parked
    assert await world.count("connection_grant_revocations") == 0
    assert await _revoked_results(world) == [4]  # unreachable


async def test_m1_round2_an_egress_refusal_is_recorded_refused(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = await _queued_revocation(world)

    async def blocked(_self: object) -> None:
        raise EgressRefused("api.undeclared.example")

    monkeypatch.setattr(FakeConnector, "revoke", blocked)
    await revoke_retired(event)
    assert await world.count("connection_grant_revocations") == 0
    assert await _revoked_results(world) == [2]  # refused


async def test_l7_runs_of_an_engagement_the_reader_is_not_on_stay_hidden(world: World) -> None:
    done = await world.connected()
    cid = uuid.UUID(str(done["connection_id"]))
    hidden = await world.net.seed.value(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, 'Other year', "
        "'2024-01-01', '2024-12-31', $4) RETURNING id",
        world.tenant,
        world.site.client_id,
        world.site.entity_id,
        world.manager.user_id,
    )
    await world.net.seed.run(
        "INSERT INTO sync_runs (id, tenant_id, client_entity_id, connection_id, engagement_id, "
        "trigger, dataset, period_start, period_end, started_by, status, failure_code, "
        "finished_at) VALUES ($1, $2, $3, $4, $5, 'on_demand', 'trial_balance', '2024-01-01', "
        "'2024-12-31', 'seed', 'failed', 'provider_unavailable', clock_timestamp())",
        uuid.uuid4(),
        world.tenant,
        world.site.entity_id,
        cid,
        hidden,
    )
    detail = await world.call("GET", f"/v1/portal/connections/{cid}", world.manager)
    assert detail.status_code == 200, detail.text
    assert detail.json()["recent_syncs"] == []
    assert detail.json()["card"]["last_failed_at"] is None


async def test_l11_a_repeated_idempotency_key_answers_the_first_disconnect(world: World) -> None:
    done = await world.connected()
    version = (await world.card())["version"]
    path = f"/v1/portal/connections/{done['connection_id']}/disconnect"
    headers = world.net.headers(world.tess)
    headers["Idempotency-Key"] = f"a02t16-{uuid.uuid4().hex}"
    first = await world.net.http.post(path, json={"seen_version": version}, headers=headers)
    again = await world.net.http.post(path, json={"seen_version": version}, headers=headers)
    assert first.status_code == again.status_code == 200
    assert first.json() == again.json()
