"""TASK-6960 (DEC-3960): a portal session carries the time its own second step verified, so the
matrix's `mfa_recent` reads a portal person the way it reads staff: the second factor within
`MFA_RECENT` (15 minutes) of the request. Over HTTP, through `create_app()`, the real `authorise`,
row-level security and the migrated test database, with the demo ledger (`fake`) as the system.

- A portal session whose second step (the WorkOS TOTP, ADR-168) verified moments ago starts,
  completes and disconnects a POR-16 connection on the firm's portal host.
- The same session past the window is refused at start, at completion and at disconnect (403,
  authenticated then forbidden), and nothing is created.
- A session that started on a trusted device passed the floor (DEC-1283's `portal_second_step`)
  but no second factor ran in it: it reads, and is refused every `mfa_recent` action.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import uow
from abacus.modules.identity import portal_mfa, portal_session
from abacus.modules.identity.api import issue_sign_in_code, totp_at
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp
from abacus.modules.integrations.api import register_adapter, unregister_adapter
from abacus.modules.portal.api import activate_portal_host, add_portal_host

from .support import Json, Net, Person, Site

Card = dict[str, Any]  # Any: JSON as the API answers it
MASTER: Final = b"t6960-master-key-0123456789abcdef!"
# The catalogue holds one row per connector provider, and backfill files share a worker's
# database: this is A-02-T16's demo-ledger row, byte for byte, so either file's load is a no-op.
LEDGER: Final = "probe_t16_demo_ledger"
AUTHORIZATION: Final = (
    "I authorize Brightwater Hale LLP to read this account for the services in our engagement "
    "letter"
)
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
    monkeypatch.setattr(portal_session, "FLOOR_SECONDS", 0.0)
    monkeypatch.setattr(portal_mfa, "FLOOR_SECONDS", 0.0)
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

    @property
    def tenant(self) -> uuid.UUID:
        return self.site.tenant_id

    @property
    def http(self) -> httpx.AsyncClient:
        return self.net.http

    @property
    def cards_path(self) -> str:
        return f"/v1/portal/entities/{self.site.entity_id}/connections"

    def firm_headers(self) -> dict[str, str]:
        """Tess's firm sign-in (the IdP's fresh MFA) on the portal host: the control."""
        return {**self.net.headers(self.tess), "host": self.portal_host}

    async def post(self, path: str, body: Json, headers: dict[str, str]) -> httpx.Response:
        self.http.cookies.clear()
        return await self.http.post(
            path, json=body, headers={**headers, "Idempotency-Key": f"t6960-{uuid.uuid4().hex}"}
        )

    async def start(self, headers: dict[str, str]) -> httpx.Response:
        return await self.post(
            f"{self.cards_path}/{LEDGER}/start",
            {"consent_version": 1, "authorized": True},
            headers,
        )

    async def handed(self, headers: dict[str, str]) -> dict[str, str]:
        started = await self.start(headers)
        assert started.status_code == 201, started.text
        sent = parse_qs(urlsplit(str(started.json()["authorise_url"])).query)
        return {"state": sent["state"][0], "code": sent["code"][0]}

    async def complete(self, handed: dict[str, str], headers: dict[str, str]) -> httpx.Response:
        return await self.post("/v1/connections/complete", dict(handed), headers)

    async def card(self, headers: dict[str, str]) -> Card:
        self.http.cookies.clear()
        listed = await self.http.get(self.cards_path, headers=headers)
        assert listed.status_code == 200, listed.text
        items = cast(list[Card], listed.json()["items"])
        return next(c for c in items if c["catalog_key"] == LEDGER)

    async def disconnect(self, card: Card, headers: dict[str, str]) -> httpx.Response:
        return await self.post(
            f"/v1/portal/connections/{card['connection_id']}/disconnect",
            {"seen_version": card["version"]},
            headers,
        )

    async def count(self, table: str) -> int:
        sql = f"SELECT count(*) FROM {table} WHERE tenant_id = $1"  # noqa: S608 - fixed names
        return cast(int, await self.net.seed.value(sql, self.tenant))

    async def portal_headers(self) -> dict[str, str]:
        """A portal session for Tess on the firm's portal host after the second step: the firm
        requires it of every client user, so the email code is followed by the TOTP (ADR-168)."""
        sql = "SELECT email FROM users WHERE id = $1"
        found = await self.net.seed.value(sql, self.tess.user_id)
        http, host = self.http, {"host": self.portal_host}
        http.cookies.clear()
        start = await http.post("/v1/portal/auth/start", json={"email": found}, headers=host)
        challenge = cast(str, start.json()["challenge_id"])
        issued = await issue_sign_in_code(uuid.UUID(challenge))
        assert issued is not None
        verified = await http.post(
            "/v1/portal/auth/verify",
            json={"challenge_id": challenge, "code": issued.code},
            headers=host,
        )
        assert verified.status_code == 200, verified.text
        body = cast(Json, verified.json())
        assert body["state"] == "mfa_setup_required", body  # the firm's policy: every client user
        mfa = cast(str, body["mfa_token"])
        setup = await http.post("/v1/portal/auth/mfa/setup", json={"mfa_token": mfa}, headers=host)
        done = await http.post(
            "/v1/portal/auth/mfa/setup/verify",
            json={"mfa_token": mfa, "totp": totp_at(setup.json()["manual_key"], time.time())},
            headers=host,
        )
        http.cookies.clear()
        assert done.status_code == 200, done.text
        token = cast(str, done.json()["session"]["access_token"])
        return {"host": self.portal_host, "authorization": f"Bearer {token}"}

    async def second_step_was(self, minutes: int) -> None:
        """Move Tess's live portal sessions' second step back by `minutes`."""
        await self.net.seed.run(
            "UPDATE auth_sessions SET mfa_at = now() - $2::interval "
            "WHERE user_id = $1 AND surface = 'portal' AND ended_at IS NULL",
            self.tess.user_id,
            timedelta(minutes=minutes),
        )

    async def trusted_device_only(self) -> None:
        """Tess's live portal sessions as if started on a trusted device: the floor was met, no
        second factor ran in them (`portal_context`'s `device_trusted_at` branch)."""
        await self.net.seed.run(
            "UPDATE auth_sessions SET mfa_at = NULL, device_trusted_at = now() "
            "WHERE user_id = $1 AND surface = 'portal' AND ended_at IS NULL",
            self.tess.user_id,
        )


async def _portal_host(tenant: uuid.UUID) -> str:
    host = f"t6960-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    return host


@pytest.fixture
async def world(net: Net) -> World:
    seed = net.seed
    await seed.value(
        "SELECT count(*) FROM integration_catalog_load($1::jsonb, 't6960-test')",
        json.dumps([_row()]),
    )
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "t6960")
    tess = await seed.client_contact(site)
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-6960')",
            tenant,
            flag,
        )
    await seed.run(
        "INSERT INTO portal_security_policies (tenant_id, mfa_for_all_client_users) "
        "VALUES ($1, true)",
        tenant,
    )
    forget_flags()
    return World(net, site, tess, await _portal_host(tenant))


# --- within the window ---------------------------------------------------------------------------


async def test_a_portal_session_after_its_second_step_starts_completes_and_disconnects(
    world: World,
) -> None:
    portal = await world.portal_headers()
    handed = await world.handed(portal)
    done = await world.complete(handed, portal)
    assert done.status_code == 201, done.text
    assert done.json()["client_entity_id"] == str(world.site.entity_id)
    card = await world.card(portal)
    assert card["status"] == "connected", card
    gone = await world.disconnect(card, portal)
    assert gone.status_code == 200, gone.text
    assert gone.json()["status"] == "disconnected"
    assert await world.count("connection_secrets") == 0


async def test_fourteen_minutes_after_the_second_step_is_still_recent(world: World) -> None:
    portal = await world.portal_headers()
    await world.second_step_was(14)
    started = await world.start(portal)
    assert started.status_code == 201, started.text


# --- past the window -----------------------------------------------------------------------------


async def test_past_the_window_a_portal_session_cannot_start(world: World) -> None:
    portal = await world.portal_headers()
    await world.second_step_was(16)
    refused = await world.start(portal)
    assert refused.status_code == 403, refused.text
    assert await world.count("connection_consents") == 0
    assert await world.count("connection_states") == 0
    assert (await world.card(portal))["status"] != "connected"  # reads still answer


async def test_past_the_window_a_portal_session_cannot_complete(world: World) -> None:
    portal = await world.portal_headers()
    handed = await world.handed(world.firm_headers())  # the state is Tess's own
    await world.second_step_was(16)
    refused = await world.complete(handed, portal)
    assert refused.status_code == 403, refused.text
    assert await world.count("connection_secrets") == 0
    # Completion spends the state first (single use, by design): the person starts again.
    again = await world.complete(handed, world.firm_headers())
    assert again.status_code == 409 and again.json()["detail"] == "invalid_state"


async def test_past_the_window_a_portal_session_cannot_disconnect(world: World) -> None:
    portal = await world.portal_headers()
    done = await world.complete(await world.handed(portal), portal)
    assert done.status_code == 201, done.text
    await world.second_step_was(16)
    card = await world.card(portal)
    refused = await world.disconnect(card, portal)
    assert refused.status_code == 403, refused.text
    assert await world.count("connection_secrets") == 1
    assert (await world.card(portal))["status"] == "connected"


# --- a trusted device is the floor, not a recent second factor ----------------------------------


async def test_a_trusted_device_session_reads_and_is_refused_every_mfa_recent_action(
    world: World,
) -> None:
    portal = await world.portal_headers()
    done = await world.complete(await world.handed(portal), portal)
    assert done.status_code == 201, done.text
    await world.trusted_device_only()
    card = await world.card(portal)  # the floor is met: the session reads
    assert (await world.start(portal)).status_code == 403
    assert (await world.disconnect(card, portal)).status_code == 403
    assert await world.count("connection_secrets") == 1
