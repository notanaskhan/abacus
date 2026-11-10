"""A-02-T33 (TASK-6902; DEC-3902): the provider returns every firm's flow to one fixed host,
`connect.<domain>`, which hands the browser back to the host the flow began on. Over HTTP,
through `create_app()`, the real `authorise`, row-level security and the migrated test database,
with the demo ledger (`fake`) as the system.

- Start keeps the request's `Host` (after `TrustedHosts`), never a query parameter.
- `POST /v1/connections/handoff` answers that stored host and nothing else: no tenant, no firm,
  no engagement. A tampered query or body can't point it anywhere else (no open redirect).
- An unknown, expired or used state, or a stored host that is not the app host or an active portal
  host of the state's own firm, gets one neutral 404.
- The hand-off never spends the state: completion stays single use, the person's own, with its
  sealed PKCE verifier (DEC-515 L6).
- The whole path works for a client admin signed in to the firm app (the app host, the firm
  sign-in) and for one with a portal session pinned to the firm's portal host (ADR-168).
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import uow
from abacus.modules.identity.api import issue_sign_in_code, totp_at
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp
from abacus.modules.integrations.api import register_adapter, unregister_adapter
from abacus.modules.portal.api import activate_portal_host, add_portal_host

from .support import Json, Net, Person, Site

MASTER: Final = b"a02t33-master-key-0123456789abcdef"
LEDGER: Final = "probe_t16_demo_ledger"  # shared: one `fake` provider row per database
APP_HOST: Final = "localhost"  # `app_base_url`'s host on a local stack and in tests
CONNECT_HOST: Final = "connect.portal-example.test"
HANDOFF: Final = "/v1/connections/handoff"
FLAGS: Final = ("connections.portal_v2", "portal.sign_in_v2")


def _row() -> dict[str, object]:
    return {
        "key": LEDGER,
        "name": "Demo ledger",
        "category": "ledger",
        "ownership_mode": "client_authorised",
        "surfaces": ["portal"],
        "connector_provider": "fake",
        "adapter_key": "fake",
        "listing_status": "available",
        "consent_copy": {
            "title": "Connect Demo ledger",
            "will": ["Read your chart of accounts and trial balance"],
            "wont": ["Change, post or delete anything in your ledger"],
            "authorization": "I authorize the firm to read this account",
            "continue_label": "Continue to Demo ledger",
        },
        "consent_version": 1,
        "scopes": {"read": [{"code": "ledger.read", "label": "Read ledger"}]},
        "icon": "book-open",
        "tone": "olive",
        "sort_order": 10,
    }


class DemoAdapter:
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
    configure_portal_idp(InMemoryPortalIdp())
    yield
    configure_portal_idp(None)
    unregister_adapter(DemoAdapter.key)
    reset_key_service()
    forget_flags()
    settings.cache_clear()


@dataclass(frozen=True)
class World:
    net: Net
    site: Site
    tess: Person  # the client Owner of the site's entity
    portal_host: str
    other_portal_host: str  # another firm's active portal host

    @property
    def tenant(self) -> uuid.UUID:
        return self.site.tenant_id

    @property
    def http(self) -> httpx.AsyncClient:
        return self.net.http

    @property
    def start_path(self) -> str:
        return f"/v1/portal/entities/{self.site.entity_id}/connections/{LEDGER}/start"

    def firm_headers(self, host: str = APP_HOST) -> dict[str, str]:
        """Tess signed in to the firm app (the firm sign-in, not a portal session)."""
        return {**self.net.headers(self.tess), "host": host}

    async def start(self, headers: dict[str, str], *, query: str = "") -> dict[str, str]:
        self.http.cookies.clear()
        started = await self.http.post(
            f"{self.start_path}{query}",
            json={"consent_version": 1, "authorized": True},
            headers={**headers, "Idempotency-Key": f"a02t33-{uuid.uuid4().hex}"},
        )
        assert started.status_code == 201, started.text
        sent = parse_qs(urlsplit(str(started.json()["authorise_url"])).query)
        return {"state": sent["state"][0], "code": sent["code"][0]}

    async def handoff(
        self, body: Json, *, host: str = CONNECT_HOST, query: str = ""
    ) -> httpx.Response:
        self.http.cookies.clear()
        return await self.http.post(f"{HANDOFF}{query}", json=body, headers={"host": host})

    async def complete(self, handed: dict[str, str], headers: dict[str, str]) -> httpx.Response:
        self.http.cookies.clear()
        return await self.http.post(
            "/v1/connections/complete",
            json=dict(handed),
            headers={**headers, "Idempotency-Key": f"a02t33-{uuid.uuid4().hex}"},
        )

    async def stored_origin(self) -> list[str | None]:
        rows = await self.net.seed.rows(
            "SELECT origin_host FROM connection_states WHERE tenant_id = $1 ORDER BY created_at",
            self.tenant,
        )
        return [cast(str | None, r["origin_host"]) for r in rows]

    async def portal_headers(self) -> dict[str, str]:
        """A portal session for Tess, minted on the firm's portal host (ADR-168)."""
        sql = "SELECT email FROM users WHERE id = $1"
        found = await self.net.seed.value(sql, self.tess.user_id)
        email = cast(str, found)
        http, host = self.http, {"host": self.portal_host}
        http.cookies.clear()
        start = await http.post("/v1/portal/auth/start", json={"email": email}, headers=host)
        challenge = cast(str, start.json()["challenge_id"])
        issued = await issue_sign_in_code(uuid.UUID(challenge))
        assert issued is not None
        verified = await http.post(
            "/v1/portal/auth/verify",
            json={"challenge_id": challenge, "code": issued.code},
            headers=host,
        )
        http.cookies.clear()
        assert verified.status_code == 200, verified.text
        body = cast(Json, verified.json())
        if body["state"] == "signed_in":
            token = cast(str, body["access_token"])
        else:
            mfa = cast(str, body["mfa_token"])
            setup = await http.post(
                "/v1/portal/auth/mfa/setup", json={"mfa_token": mfa}, headers=host
            )
            done = await http.post(
                "/v1/portal/auth/mfa/setup/verify",
                json={"mfa_token": mfa, "totp": totp_at(setup.json()["manual_key"], time.time())},
                headers=host,
            )
            http.cookies.clear()
            assert done.status_code == 200, done.text
            token = cast(str, done.json()["session"]["access_token"])
        return {"host": self.portal_host, "authorization": f"Bearer {token}"}


async def _portal_host(tenant: uuid.UUID, label: str) -> str:
    host = f"{label}-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    return host


@pytest.fixture
async def world(net: Net) -> World:
    seed = net.seed
    await seed.value(
        "SELECT count(*) FROM integration_catalog_load($1::jsonb, 'a02t33-test')",
        json.dumps([_row()]),
    )
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "a02t33")
    tess = await seed.client_contact(site)
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'A-02-T33')",
            tenant,
            flag,
        )
    forget_flags()
    other_firm = await seed.firm()
    return World(
        net,
        site,
        tess,
        await _portal_host(tenant, "t33"),
        await _portal_host(other_firm, "t33-other"),
    )


def _neutral(response: httpx.Response) -> None:
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "not found"}


# --- start keeps the request's host --------------------------------------------------------------


async def test_start_keeps_the_request_host_without_its_port_never_the_query(world: World) -> None:
    await world.start(world.firm_headers(f"{APP_HOST}:5173"), query="?origin_host=evil.example")
    await world.start(world.firm_headers(world.portal_host.upper()))
    assert await world.stored_origin() == [APP_HOST, world.portal_host]


# --- the hand-off answers the stored host only ---------------------------------------------------


async def test_the_handoff_answers_only_the_stored_host_and_no_tenant(world: World) -> None:
    handed = await world.start(world.firm_headers(world.portal_host))
    answered = await world.handoff({"state": handed["state"]})
    assert answered.status_code == 200, answered.text
    assert answered.json() == {"origin_host": world.portal_host}
    site = world.site
    for secret in (world.tenant, site.entity_id, site.engagement_id, site.marker):
        assert str(secret) not in answered.text


async def test_tampered_parameters_never_change_where_the_handoff_points(world: World) -> None:
    handed = await world.start(world.firm_headers(world.portal_host))
    query = "?origin_host=evil.example&redirect_uri=https://evil.example/"
    answered = await world.handoff({"state": handed["state"]}, query=query)
    assert answered.json() == {"origin_host": world.portal_host}
    smuggled = await world.handoff({"state": handed["state"], "origin_host": "evil.example"})
    assert smuggled.status_code == 422, smuggled.text  # extra fields are refused, not followed
    assert await world.stored_origin() == [world.portal_host]


async def test_an_unknown_state_is_neutral(world: World) -> None:
    _neutral(await world.handoff({"state": "x" * 43}))


async def test_an_expired_state_is_refused(world: World) -> None:
    handed = await world.start(world.firm_headers(world.portal_host))
    await world.net.seed.run(
        "UPDATE connection_states SET created_at = clock_timestamp() - interval '1 hour', "
        "expires_at = clock_timestamp() - interval '1 minute' WHERE tenant_id = $1",
        world.tenant,
    )
    _neutral(await world.handoff({"state": handed["state"]}))


async def test_a_replayed_state_is_refused_once_completion_spends_it(world: World) -> None:
    handed = await world.start(world.firm_headers())
    assert (await world.handoff({"state": handed["state"]})).status_code == 200
    done = await world.complete(handed, world.firm_headers())
    assert done.status_code == 201, done.text
    _neutral(await world.handoff({"state": handed["state"]}))
    again = await world.complete(handed, world.firm_headers())
    assert again.status_code == 409 and again.json()["detail"] == "invalid_state"


@pytest.mark.parametrize("stored", ["disabled", "another_firm", "unknown_host", "none"])
async def test_a_stored_host_that_is_not_a_live_host_of_the_firm_is_refused(
    world: World, stored: str
) -> None:
    handed = await world.start(world.firm_headers(world.portal_host))
    if stored == "disabled":
        await world.net.seed.run(
            "UPDATE portal_domains SET status = 'disabled' WHERE hostname = $1", world.portal_host
        )
    else:
        origin = {
            "another_firm": world.other_portal_host,
            "unknown_host": "evil.example",
            "none": None,
        }[stored]
        await world.net.seed.run(
            "UPDATE connection_states SET origin_host = $2 WHERE tenant_id = $1",
            world.tenant,
            origin,
        )
    _neutral(await world.handoff({"state": handed["state"]}))


async def test_the_handoff_never_spends_the_state(world: World) -> None:
    handed = await world.start(world.firm_headers())
    for _ in range(2):
        assert (await world.handoff({"state": handed["state"]})).status_code == 200
    used = await world.net.seed.value(
        "SELECT count(*) FROM connection_states WHERE tenant_id = $1 AND used_at IS NOT NULL",
        world.tenant,
    )
    assert used == 0
    sealed = await world.net.seed.value(
        "SELECT count(*) FROM connection_states WHERE tenant_id = $1 "
        "AND verifier_sealed IS NOT NULL",
        world.tenant,
    )
    assert sealed == 1


# --- the whole path: start, the connect host's hand-off, completion on the origin host -----------


async def test_the_whole_path_for_a_client_admin_signed_in_to_the_firm_app(world: World) -> None:
    signed_in = world.firm_headers()
    handed = await world.start(signed_in)
    bounced = await world.handoff({"state": handed["state"]})
    assert bounced.json() == {"origin_host": APP_HOST}
    done = await world.complete(handed, world.firm_headers(bounced.json()["origin_host"]))
    assert done.status_code == 201, done.text
    assert done.json()["client_entity_id"] == str(world.site.entity_id)


async def test_the_whole_path_for_a_client_admin_with_a_portal_session(world: World) -> None:
    """The flow begins on the firm's portal host and the hand-off sends it back there, where the
    portal session is valid and nowhere else (ADR-163 §5): the reason for the hop.

    The start uses Tess's firm sign-in on the portal host; the completion on the portal host is
    her portal session, which carries its second step's time since TASK-6960 (#1607), so
    `connection.create`'s `mfa_recent` holds and the connection is made (201)."""
    portal = await world.portal_headers()
    handed = await world.start(world.firm_headers(world.portal_host))
    bounced = await world.handoff({"state": handed["state"]})
    assert bounced.json() == {"origin_host": world.portal_host}
    elsewhere = await world.complete(handed, {**portal, "host": CONNECT_HOST})
    assert elsewhere.status_code == 401, elsewhere.text  # not valid on the connect host
    assert (await world.handoff({"state": handed["state"]})).status_code == 200  # still unspent
    on_origin = await world.complete(handed, {**portal, "host": bounced.json()["origin_host"]})
    assert on_origin.status_code == 201, on_origin.text
    assert on_origin.json()["client_entity_id"] == str(world.site.entity_id)
