# ac-test-author: ayushkbhatia
"""SPEC-020 AC-2 to AC-6 (TASK-036) and SPEC-028 AC-3 to AC-8 (TASK-052): a client admin connects
the engagement's entity through the connector contract, both sides see its health and access
log, a revoke stops it at once; and a client (or the firm on its behalf) uploads an exported
trial balance instead of connecting.

HTTP through `create_app()` against the migrated Postgres and the compose S3, with the demo
ledger (`fake`) available as in local and test (SPEC-020 Q1). Every connector the product builds
is wrapped in a recording spy at the public registry (`connections.api.CONNECTORS`), so each test
proves CONN-001 (connectors only read; ADR-037, ADR-040): no connector has a write-shaped method,
and every call made is one of the contract's reads. After a revoke the spy proves no further call.

Later decisions the tests follow instead of the spec's wording:
- TASK-036 D1: the provider returns to the SPA, which completes with `POST /v1/connections/
  complete` and the user's own token (SPEC-020 §8's unauthenticated callback is gone).
- TASK-036 D3/D4: `connection.create` needs a fresh second factor; `connection.check` is held
  by the client admin, partner and manager; the connection and its log read with
  `connection.read_log`.
- TASK-036 D5: the partner and managers are notified of a revoke; client users are not.
- TASK-052 §9 / TASK-053: the import routes are `…/connection/import[/formats]` and take no
  period (the engagement's fiscal year is the period), not SPEC-028 §8's `…/ledger-import`.
- SPEC-028 Q4 (TASK-052 §10): the partner, manager and senior may upload on the client's behalf.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, Final, cast
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from openpyxl import Workbook
from sqlalchemy import text
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.connections import api as connections
from abacus.modules.connections.connector import Credentials
from abacus.modules.evidence import storage
from abacus.modules.identity.api import AuthContext
from abacus.modules.notifications import api as notifications

from .support import Json, Net, Person, Seeder, Site

BUCKET: Final = "backfill-q03t022"
MASTER: Final = b"backfill-q03t022-master-key-0123456789"
# The connector contract (ADR-037): every method a connector may have is a read or the read-only
# grant's handshake. Anything else would be a way to write to a client's system (CONN-001).
READS: Final = frozenset(
    {
        "capabilities",
        "authorise_url",
        "exchange_code",
        "refresh",
        "pull",
        "changes_since",
        "fetch_attachment",
        "health",
    }
)
WRITE_SHAPED: Final = (
    "create",
    "update",
    "delete",
    "remove",
    "post",
    "put",
    "patch",
    "write",
    "send",
    "push",
    "upload",
    "insert",
    "save",
    "void",
)
EICAR: Final = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
QBO: Final = "QuickBooks Online"  # the system; its format id comes from the formats route
COUNTS: Final = {
    "connections": "SELECT count(*) FROM connections WHERE tenant_id = $1",
    "connection_states": "SELECT count(*) FROM connection_states WHERE tenant_id = $1",
    "sync_runs": "SELECT count(*) FROM sync_runs WHERE tenant_id = $1",
    "ledger_imports": "SELECT count(*) FROM ledger_imports WHERE tenant_id = $1",
    "ledger_snapshots": "SELECT count(*) FROM ledger_snapshots WHERE tenant_id = $1",
    "fulfilments": "SELECT count(*) FROM fulfilments WHERE tenant_id = $1",
}


# --- the connector spy (CONN-001) --------------------------------------------------------------


@dataclass
class Calls:
    """Every connector call the product makes in a test: (connection id, method)."""

    made: list[tuple[object, str]] = field(default_factory=list[tuple[object, str]])
    unhealthy: bool = False

    def of(self, connection_id: object) -> list[str]:
        return [m for c, m in self.made if str(c) == str(connection_id)]


def _public(kind: type) -> set[str]:
    return {n for n in dir(kind) if not n.startswith("_") and callable(getattr(kind, n, None))}


def _spy(inner: connections.Connector, connection: object, calls: Calls) -> connections.Connector:
    """A connector that records each call, then hands it to the product's own connector."""
    ident = getattr(connection, "id", None)

    class Spy(connections.Connector):
        provider: ClassVar[str] = inner.provider

        def _note(self, name: str) -> None:
            calls.made.append((ident, name))

        def capabilities(self) -> connections.Capabilities:
            self._note("capabilities")
            return inner.capabilities()

        async def authorise_url(self, state: str, redirect_uri: str) -> str:
            self._note("authorise_url")
            return await inner.authorise_url(state, redirect_uri)

        async def exchange_code(self, code: str, redirect_uri: str) -> Credentials | None:
            self._note("exchange_code")
            return await inner.exchange_code(code, redirect_uri)

        async def refresh(self) -> None:
            self._note("refresh")
            await inner.refresh()

        async def pull(
            self,
            dataset: connections.Dataset,
            period: connections.Period,
            cursor: str | None,
        ) -> connections.RawPayload:
            self._note("pull")
            return await inner.pull(dataset, period, cursor)

        async def changes_since(self, since: datetime) -> Sequence[str]:
            self._note("changes_since")
            return await inner.changes_since(since)

        async def fetch_attachment(self, ref: str) -> connections.RawPayload:
            self._note("fetch_attachment")
            return await inner.fetch_attachment(ref)

        async def health(self) -> bool:
            self._note("health")
            return False if calls.unhealthy else await inner.health()

    return Spy()


def _wrapping[C, K](
    factory: Callable[[C, K], connections.Connector], recorded: Calls
) -> Callable[[C, K], connections.Connector]:
    def wrapped(connection: C, credentials: K) -> connections.Connector:
        inner = factory(connection, credentials)
        assert _public(type(inner)) <= READS, f"{inner.provider}: a write-shaped method"
        return _spy(inner, connection, recorded)

    return wrapped


@pytest.fixture(autouse=True)
def calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[Calls]:
    """Wrap every registered connector; after the test, every call made was a read (CONN-001)."""
    recorded = Calls()
    for provider, factory in list(connections.CONNECTORS.items()):
        monkeypatch.setitem(connections.CONNECTORS, provider, _wrapping(factory, recorded))
    yield recorded
    assert {m for _, m in recorded.made} <= READS


@pytest.fixture(autouse=True)
def demo_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The demo ledger is a provider where the fake connector may run (SPEC-020 Q1)."""
    monkeypatch.setenv("ABACUS_FAKE_CONNECTOR_DIR", str(tmp_path))
    settings.cache_clear()
    forget_flags()
    yield
    forget_flags()
    settings.cache_clear()


@pytest.fixture(scope="module")
def bucket(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def evidence_store(bucket: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


# --- the world ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class World:
    net: Net
    tenant: uuid.UUID
    site: Site
    other: Site  # another engagement of the same firm, another client
    admin: Person  # firm admin
    owner: Person  # client admin of the site's engagement
    contributor: Person
    partner: Person
    manager: Person
    senior: Person
    staff: Person

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}/connection"

    async def call(
        self, method: str, tail: str, who: Person, *, body: Json | None = None, mfa: bool = True
    ) -> httpx.Response:
        return await self.net.call(method, self.base + tail, who, body=body, mfa=mfa)

    async def count(self, table: str) -> int:
        found = await self.seed.value(COUNTS[table], self.tenant)
        return cast(int, found)

    async def started(self, who: Person | None = None) -> dict[str, str]:
        """Start connecting the demo ledger; the provider's URL carries the state and code."""
        response = await self.call("POST", "/start", who or self.owner, body={"provider": "fake"})
        assert response.status_code == 200, response.text
        url = str(response.json()["authorise_url"])
        query = parse_qs(urlsplit(url).query)
        return {"state": query["state"][0], "code": query["code"][0]}

    async def complete(self, handed: dict[str, str], who: Person | None = None) -> httpx.Response:
        return await self.net.call(
            "POST", "/v1/connections/complete", who or self.owner, body=dict(handed)
        )

    async def connected(self) -> Json:
        response = await self.complete(await self.started())
        assert response.status_code == 201, response.text
        view = await self.call("GET", "", self.owner)
        assert view.status_code == 200, view.text
        return cast(Json, view.json())

    async def flag(self, name: str, on: bool = True) -> None:
        await self.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, $3, 'test-seed', 'Q-03-T022 tests')",
            self.tenant,
            name,
            "true" if on else "false",
        )
        forget_flags()

    async def audited(self, prefix: str) -> list[str]:
        return [a for a in await self.seed.actions(self.tenant) if a.startswith(prefix)]


async def _world(net: Net) -> World:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "q03t022")
    other = await seed.site(tenant, admin.user_id, "q03t022-other")
    team: dict[str, Person] = {}
    for role in ("engagement_partner", "manager", "senior", "staff"):
        who = await seed.person(tenant)
        await seed.member(site, who, role)
        team[role] = who
    owner = await seed.client_contact(site)
    contributor = await seed.client_contact(site, "client_contributor")
    return World(
        net,
        tenant,
        site,
        other,
        admin,
        owner,
        contributor,
        team["engagement_partner"],
        team["manager"],
        team["senior"],
        team["staff"],
    )


@pytest.fixture
async def world(net: Net) -> World:
    return await _world(net)


# ================================================================================================
# TASK-036 (SPEC-020): connecting, health, the access log and revoke
# ================================================================================================


async def test_ac2_a_client_admin_connects_and_the_connection_is_active(
    world: World, calls: Calls
) -> None:
    providers = await world.call("GET", "/providers", world.owner)
    assert providers.status_code == 200, providers.text
    assert "fake" in [p["provider"] for p in providers.json()]
    before = await world.call("GET", "", world.owner)
    assert before.status_code == 200 and before.json() is None  # nothing connected yet
    handed = await world.started()
    assert handed["state"] and handed["code"]
    done = await world.complete(handed)
    assert done.status_code == 201, done.text
    assert done.json() == {"engagement_id": str(world.site.engagement_id)}
    view = (await world.call("GET", "", world.owner)).json()
    assert view["provider"] == "fake" and view["status"] == "active"
    assert "token" not in str(view).lower()  # SPEC-020 §13: tokens are never returned
    trail = await world.audited("connection.")
    assert trail[0] == "connection.started" and trail[-1] == "connection.created"
    assert "exchange_code" in [m for _, m in calls.made]  # through the connector contract


async def test_ac2_a_used_state_is_refused_and_nothing_more_is_created(world: World) -> None:
    handed = await world.started()
    assert (await world.complete(handed)).status_code == 201
    before = await world.count("connections")
    again = await world.complete(handed)
    assert again.status_code == 409 and again.json()["detail"] == "invalid_state"
    assert await world.count("connections") == before


async def test_ac2_an_expired_state_is_refused_and_nothing_is_created(world: World) -> None:
    handed = await world.started()
    await world.seed.run(
        "UPDATE connection_states SET created_at = now() - interval '20 minutes', "
        "expires_at = now() - interval '10 minutes' "
        "WHERE tenant_id = $1",
        world.tenant,
    )
    refused = await world.complete(handed)
    assert refused.status_code == 409 and refused.json()["detail"] == "invalid_state"
    assert await world.count("connections") == 0


async def test_ac2_a_state_that_is_not_the_users_own_or_unknown_is_refused(world: World) -> None:
    second = await world.seed.client_contact(world.site)  # another client admin, same engagement
    handed = await world.started()
    stolen = await world.complete(handed, second)
    assert stolen.status_code == 409 and stolen.json()["detail"] == "invalid_state"
    forged = await world.complete({"state": "not-a-real-state", "code": handed["code"]})
    assert forged.status_code == 409 and forged.json()["detail"] == "invalid_state"
    assert await world.count("connections") == 0


@pytest.mark.parametrize("role", ["partner", "manager", "senior", "staff", "contributor", "admin"])
async def test_ac3_only_a_client_admin_starts_a_connection(world: World, role: str) -> None:
    who = cast(Person, getattr(world, role))
    refused = await world.call("POST", "/start", who, body={"provider": "fake"})
    assert refused.status_code == 403, refused.text
    assert await world.count("connection_states") == 0


async def test_ac3_starting_needs_a_fresh_second_factor(world: World) -> None:
    stale = await world.call("POST", "/start", world.owner, body={"provider": "fake"}, mfa=False)
    assert stale.status_code == 403, stale.text
    assert await world.count("connection_states") == 0


async def test_ac3_a_client_admin_of_another_engagement_cannot_start_here(world: World) -> None:
    elsewhere = await world.seed.client_contact(world.other)
    refused = await world.call("POST", "/start", elsewhere, body={"provider": "fake"})
    assert refused.status_code in (403, 404), refused.text
    assert await world.count("connection_states") == 0


async def test_ac3_another_firm_sees_no_such_engagement(world: World) -> None:
    stranger_firm = await world.seed.firm()
    stranger = await world.seed.person(stranger_firm, "firm_admin")
    for method, tail in (("POST", "/start"), ("GET", ""), ("GET", "/log"), ("POST", "/revoke")):
        body: Json | None = {"provider": "fake"} if tail == "/start" else None
        response = await world.call(method, tail, stranger, body=body)
        assert response.status_code == 404, (tail, response.text)


@pytest.mark.parametrize("role", ["owner", "partner", "manager"])
async def test_ac4_the_admin_partner_and_manager_see_health_and_check_it(
    world: World, role: str, calls: Calls
) -> None:
    made = await world.connected()
    who = cast(Person, getattr(world, role))
    seen = await world.call("GET", "", who)
    assert seen.status_code == 200, seen.text
    assert seen.json()["id"] == made["id"] and "last_pull_at" in seen.json()
    checked = await world.call("POST", "/check", who)
    assert checked.status_code == 200, checked.text
    assert checked.json()["status"] == "active" and checked.json()["last_check_ok"] is True
    assert checked.json()["last_checked_at"] is not None
    assert "health" in calls.of(made["id"])
    assert "connection.checked" in await world.audited("connection.")


@pytest.mark.parametrize("role", ["senior", "staff", "contributor", "admin"])
async def test_ac4_others_neither_see_nor_check_the_connection(world: World, role: str) -> None:
    await world.connected()
    who = cast(Person, getattr(world, role))
    assert (await world.call("GET", "", who)).status_code == 403
    assert (await world.call("POST", "/check", who)).status_code == 403


async def test_ac4_a_failed_check_shows_needs_attention_and_a_good_one_clears_it(
    world: World, calls: Calls
) -> None:
    await world.connected()
    calls.unhealthy = True
    failed = await world.call("POST", "/check", world.manager)
    assert failed.status_code == 200, failed.text
    assert failed.json()["status"] == "needs_attention"
    assert failed.json()["last_check_ok"] is False
    calls.unhealthy = False
    healed = await world.call("POST", "/check", world.manager)
    assert healed.json()["status"] == "active" and healed.json()["last_check_ok"] is True


async def test_ac4_the_last_successful_pull_is_shown(world: World) -> None:
    made = await world.connected()
    await _run(world, made, "succeeded", datetime(2026, 1, 15, 10, tzinfo=UTC))
    await _run(
        world, made, "failed", datetime(2026, 1, 16, 10, tzinfo=UTC)
    )  # a later failure isn't a pull
    view = (await world.call("GET", "", world.partner)).json()
    assert view["last_pull_at"] is not None and view["last_pull_at"].startswith("2026-01-15")


async def _run(world: World, made: Json, status: str, at: datetime) -> uuid.UUID:
    """A finished sync run of the connection (the pipeline's record; seeded as the superuser). A
    succeeded run has its snapshot and evidence version, as the pipeline leaves them."""
    succeeded = status == "succeeded"
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest() if succeeded else None
    snapshot = None
    if succeeded:
        snapshot = await world.seed.value(
            "INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, period_end, "
            "pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit) VALUES "
            "($1, $2, '2025-01-01', '2025-12-31', $3, 'fake', $4, 2, 10, 10) RETURNING id",
            world.tenant,
            world.site.entity_id,
            at,
            fingerprint,
        )
    return cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO sync_runs (tenant_id, client_entity_id, connection_id, engagement_id, "
            "request_item_id, dataset, period_start, period_end, status, started_by, started_at, "
            "finished_at, raw_fingerprint, raw_size_bytes, source, failure_code, snapshot_id, "
            "evidence_version_id) VALUES ($1, $2, $3, $4, $5, 'trial_balance', '2025-01-01', "
            "'2025-12-31', $6, $7, $8::timestamptz, $8::timestamptz + interval '1 minute', "
            "$9, $10, $11, $12, $13, $14) "
            "RETURNING id",
            world.tenant,
            world.site.entity_id,
            _cid(made),
            world.site.engagement_id,
            world.site.item_id,
            status,
            str(world.manager.user_id),
            at,
            fingerprint,
            100 if succeeded else None,
            "fake" if succeeded else None,
            None if succeeded else "unavailable",
            snapshot,
            world.site.version_id if succeeded else None,
        ),
    )


@pytest.mark.parametrize("role", ["owner", "partner", "manager"])
async def test_ac5_the_access_log_lists_every_run_newest_first(world: World, role: str) -> None:
    made = await world.connected()
    first = await _run(world, made, "succeeded", datetime(2026, 1, 10, 9, tzinfo=UTC))
    second = await _run(world, made, "failed", datetime(2026, 1, 11, 9, tzinfo=UTC))
    log = await world.call("GET", "/log", cast(Person, getattr(world, role)))
    assert log.status_code == 200, log.text
    entries = cast(list[Json], log.json())
    assert [e["id"] for e in entries] == [str(second), str(first)]
    newest = entries[0]
    assert newest["dataset"] == "trial_balance" and newest["status"] == "failed"
    assert (newest["period_start"], newest["period_end"]) == ("2025-01-01", "2025-12-31")
    assert newest["started_at"] and newest["started_by"]


@pytest.mark.parametrize("role", ["senior", "staff", "contributor", "admin"])
async def test_ac5_only_the_admin_partner_and_manager_read_the_log(
    world: World, role: str
) -> None:
    made = await world.connected()
    await _run(world, made, "succeeded", datetime(2026, 1, 10, 9, tzinfo=UTC))
    refused = await world.call("GET", "/log", cast(Person, getattr(world, role)))
    assert refused.status_code == 403, refused.text


async def test_ac5_a_log_shows_nothing_of_another_engagement(world: World) -> None:
    await world.connected()
    elsewhere = await world.seed.client_contact(world.other)
    other_base = f"/v1/engagements/{world.other.engagement_id}/connection"
    log = await world.net.call("GET", f"{other_base}/log", elsewhere)
    assert log.status_code == 200 and log.json() == []


async def test_ac6_a_revoke_stops_the_connection_at_once_and_destroys_its_tokens(
    world: World, calls: Calls
) -> None:
    made = await world.connected()
    secrets_before = await world.seed.value(
        "SELECT count(*) FROM connection_secrets WHERE connection_id = $1", _cid(made)
    )
    assert secrets_before == 1  # the demo sign-in hands back credentials (TASK-036 D2)
    revoked = await world.call("POST", "/revoke", world.owner)
    assert revoked.status_code == 200, revoked.text
    status = await world.seed.value("SELECT status FROM connections WHERE id = $1", _cid(made))
    assert status == "revoked"
    assert (
        await world.seed.value(
            "SELECT count(*) FROM connection_secrets WHERE connection_id = $1",
            _cid(made),
        )
        == 0
    )
    assert "connection.revoked" in await world.audited("connection.")
    assert (await world.call("GET", "", world.owner)).json() is None
    # A new retrieval fails `no_connection`, and the connector is never asked again.
    calls_before = len(calls.of(made["id"]))
    runs_before = await world.count("sync_runs")
    retrieval = await world.net.call(
        "POST",
        f"/v1/engagements/{world.site.engagement_id}/retrievals",
        world.manager,
        body={
            "request_item_id": str(world.site.item_id),
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
        },
    )
    assert retrieval.status_code == 409 and retrieval.json()["detail"] == "no_connection"
    check = await world.call("POST", "/check", world.manager)
    assert check.status_code == 409, check.text
    assert await world.count("sync_runs") == runs_before
    assert len(calls.of(made["id"])) == calls_before


async def test_ac6_the_partner_and_manager_are_told_of_a_clients_revoke(world: World) -> None:
    made = await world.connected()
    await world.flag("notifications.v2")
    assert (await world.call("POST", "/revoke", world.owner)).status_code == 200
    rows = await world.seed.rows(
        "SELECT id, tenant_id, event_type, payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'connection.revoked'",
        world.tenant,
    )
    assert len(rows) == 1 and str(made["id"]) in str(rows[0]["payload"])
    event = OutboxEvent(
        event_id=cast(uuid.UUID, rows[0]["id"]),
        tenant_id=world.tenant,
        event_type="connection.revoked",
        payload=_json(rows[0]["payload"]),
    )
    await notifications.SUBSCRIPTIONS["connection.revoked"](event)
    told = await world.seed.rows(
        "SELECT recipient_user_id FROM notifications WHERE tenant_id = $1 "
        "AND kind = 'connection.revoked'",
        world.tenant,
    )
    recipients = {cast(uuid.UUID, r["recipient_user_id"]) for r in told}
    assert {world.partner.user_id, world.manager.user_id} <= recipients
    assert world.owner.user_id not in recipients and world.senior.user_id not in recipients


def _cid(made: Json) -> uuid.UUID:
    return uuid.UUID(str(made["id"]))


def _json(value: object) -> Json:
    return cast(Json, json.loads(value) if isinstance(value, str) else value)


@pytest.mark.parametrize("role", ["senior", "staff", "contributor"])
async def test_ac6_only_the_admin_partner_and_manager_revoke(world: World, role: str) -> None:
    made = await world.connected()
    refused = await world.call("POST", "/revoke", cast(Person, getattr(world, role)))
    assert refused.status_code == 403, refused.text
    status = await world.seed.value("SELECT status FROM connections WHERE id = $1", _cid(made))
    assert status == "active"


async def test_q3_connecting_again_revokes_the_old_connection(world: World, calls: Calls) -> None:
    old = await world.connected()
    new = await world.connected()
    assert new["id"] != old["id"]
    statuses = await world.seed.rows(
        "SELECT id, status FROM connections WHERE tenant_id = $1", world.tenant
    )
    assert {str(r["id"]): r["status"] for r in statuses} == {
        old["id"]: "revoked",
        new["id"]: "active",
    }
    before = len(calls.of(old["id"]))
    await world.call("POST", "/check", world.manager)
    assert len(calls.of(old["id"])) == before  # the replaced connection is never called again


def test_conn001_the_connector_contract_has_no_write_shaped_method() -> None:
    contract = _public(connections.Connector)
    assert contract == READS
    assert not [m for m in contract if m.startswith(WRITE_SHAPED)]


# ================================================================================================
# TASK-052 (SPEC-028): an exported trial balance instead of a connection
# ================================================================================================

# QuickBooks Online's trial balance export (SPEC-028 §4.3): title lines, a header row with a blank
# account column, accounts as "<number> <name>", amounts with thousands separators, a TOTAL row.
QBO_BALANCED: Final = (
    "Trial Balance\n"
    "Example Company\n"
    '"As of December 31, 2025"\n'
    "\n"
    ",Debit,Credit\n"
    '1000 Cash,"12,500.00",\n'
    '1200 Accounts Receivable,"3,250.00",\n'
    '2000 Accounts Payable,,"4,000.00"\n'
    '3000 Retained Earnings,,"6,750.00"\n'
    '4000 Revenue,,"20,000.00"\n'
    '6000 Expenses,"15,000.00",\n'
    'TOTAL,"$30,750.00","$30,750.00"\n'
)


def _qbo(
    *, total: bool = True, as_of: str = "December 31, 2025", short: Decimal = Decimal(0)
) -> bytes:
    # The "As of" line is one quoted CSV field (its date has a comma).
    lines = QBO_BALANCED.replace("As of December 31, 2025", f"As of {as_of}").splitlines()
    if not total:
        lines = [x for x in lines if not x.startswith("TOTAL")]
    if short:
        cash = Decimal("12500.00") - short
        lines = [f'1000 Cash,"{cash:,.2f}",' if x.startswith("1000 Cash") else x for x in lines]
        if total:
            lines = [
                f'TOTAL,"${Decimal("30750.00") - short:,.2f}","$30,750.00"'
                if x.startswith("TOTAL")
                else x
                for x in lines
            ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _xero(*, as_at: str = "31 December 2025") -> bytes:
    """Xero's trial balance export (SPEC-028 §4.3): title lines, a header row, accounts as
    "<name> (<code>)" under section headings, year-to-date balances as text, negatives in
    parentheses, a Total row."""
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    for row in (
        ["Trial Balance"],
        ["Example Company"],
        [f"As at {as_at}"],
        [],
        ["Account", "Debit", "Credit", "YTD Debit", "YTD Credit"],
        ["Assets", None, None, None, None],
        ["Cash (1000)", "", "", "12,500.00", ""],
        ["Accounts Receivable (1200)", "", "", "3,250.00", ""],
        ["Accounts Payable (2000)", "", "", "", "4,000.00"],
        ["Retained Earnings (3000)", "", "", "", "6,750.00"],
        ["Revenue (4000)", "", "", "", "20,000.00"],
        ["Expenses (6000)", "", "", "15,000.00", ""],
        ["Total", "", "", "30,750.00", "30,750.00"],
    ):
        sheet.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


async def _upload(
    world: World, who: Person, content: bytes, *, fmt: str | None = None, site: Site | None = None
) -> httpx.Response:
    engagement = (site or world.site).engagement_id
    return await world.net.http.post(
        f"/v1/engagements/{engagement}/connection/import?format={fmt or await _format(world)}",
        content=content,
        headers={**world.net.headers(who), "Content-Type": "text/csv"},
    )


async def _format(world: World, system: str = QBO) -> str:
    """The id of `system`'s export format, as the formats route lists it."""
    listed = await world.call("GET", "/import/formats", world.manager)
    assert listed.status_code == 200, listed.text
    [found] = [f["id"] for f in listed.json() if f["system"] == system]
    return str(found)


@pytest.fixture
async def importing(world: World) -> World:
    await world.flag("ledger.import")
    return world


async def test_ac2_the_formats_list_names_qbo_and_xero_with_numbered_steps(
    importing: World,
) -> None:
    listed = await importing.call("GET", "/import/formats", importing.owner)
    assert listed.status_code == 200, listed.text
    formats = {f["id"]: f for f in listed.json()}
    systems = {f["system"]: f for f in formats.values()}
    assert {"QuickBooks Online", "Xero"} <= set(systems)
    assert str(systems["QuickBooks Online"]["file_type"]).lower() == "csv"
    assert str(systems["Xero"]["file_type"]).lower() == "xlsx"
    assert all(f["steps"] for f in formats.values())


async def test_ac3_an_export_is_stored_write_once_with_its_fingerprint(
    importing: World, calls: Calls
) -> None:
    content = _qbo()
    done = await _upload(importing, importing.owner, content)
    assert done.status_code == 201, done.text
    body = done.json()
    assert body["status"] == "received" and body["failure_code"] is None
    assert body["on_behalf"] is False and body["duplicate"] is False
    row = await importing.seed.rows(
        "SELECT fingerprint, size_bytes, scan_status, storage_key FROM ledger_imports "
        "WHERE tenant_id = $1",
        importing.tenant,
    )
    assert len(row) == 1
    assert row[0]["fingerprint"] == hashlib.sha256(content).hexdigest()
    assert row[0]["size_bytes"] == len(content) and row[0]["scan_status"] == "clean"
    # Write-once: the app may never change or remove an import (ADR-016).
    with pytest.raises(Exception, match=r"permission denied|insert-only|immutable|not allowed"):
        await _as_app(importing, "UPDATE ledger_imports SET format = format")
    with pytest.raises(Exception, match=r"permission denied|insert-only|immutable|not allowed"):
        await _as_app(importing, "DELETE FROM ledger_imports")
    assert [m for _, m in calls.made if m not in ("capabilities", "health")] == []


async def _as_app(world: World, sql: str) -> None:
    """Run `sql` as the app role inside the firm's tenant, as the product does."""
    async with tenant_session(TenantContext(world.tenant, "system", "test")) as session:
        await session.execute(text(sql))


async def _pipeline(world: World) -> connections.RunResult | connections.RunFailed:
    """The manager retrieves the item's trial balance for the fiscal year, and the pipeline runs
    in-process to its end (the stages the retrieval workflow runs as activities)."""
    ctx = AuthContext(
        tenant=TenantContext(world.tenant, "human", str(world.manager.user_id)),
        user_id=world.manager.user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC),
    )
    started = await connections.start_retrieval(
        ctx,
        engagement_id=world.site.engagement_id,
        request_item_id=world.site.item_id,
        period=connections.Period(date(2025, 1, 1), date(2025, 12, 31)),
    )
    system = await connections.load_system_context(world.tenant, started.run_id)
    try:
        return await connections.run_pipeline(system)
    except connections.RunFailed as failed:
        return failed


async def test_ac4_a_clean_import_is_snapshotted_and_fulfils_the_item_as_imported(
    importing: World, calls: Calls
) -> None:
    assert (await _upload(importing, importing.owner, _qbo())).status_code == 201
    result = await _pipeline(importing)
    assert isinstance(result, connections.RunResult), result
    method = await importing.seed.value(
        "SELECT method FROM evidence_versions WHERE id = $1", result.evidence_version_id
    )
    assert method == "imported"
    totals = await importing.seed.rows(
        "SELECT total_debit, total_credit, line_count FROM ledger_snapshots WHERE id = $1",
        result.snapshot_id,
    )
    assert [(r["total_debit"], r["total_credit"], r["line_count"]) for r in totals] == [
        (Decimal("30750.00"), Decimal("30750.00"), 6)
    ]
    fulfilled = await importing.seed.value(
        "SELECT count(*) FROM fulfilments WHERE tenant_id = $1 AND request_item_id = $2",
        importing.tenant,
        importing.site.item_id,
    )
    assert fulfilled == 1
    assert "pull" in [m for _, m in calls.made]  # the import connector read the stored export


async def test_ac3_a_file_not_scanned_clean_is_never_parsed_or_stored(importing: World) -> None:
    infected = _qbo() + b"\n" + EICAR + b"\n"
    refused = await _upload(importing, importing.owner, infected)
    assert refused.status_code == 422 and refused.json()["detail"] == "file_refused"
    assert await importing.count("ledger_imports") == 0
    assert await importing.count("ledger_snapshots") == 0


async def test_ac4_an_import_becomes_the_entitys_active_import_connection(
    importing: World,
) -> None:
    assert (await _upload(importing, importing.owner, _qbo())).status_code == 201
    rows = await importing.seed.rows(
        "SELECT provider, status FROM connections WHERE tenant_id = $1 AND client_entity_id = $2",
        importing.tenant,
        importing.site.entity_id,
    )
    assert [(r["provider"], r["status"]) for r in rows] == [("import", "active")]
    latest = await importing.call("GET", "/import", importing.partner)
    assert latest.status_code == 200 and latest.json()["status"] == "received"
    assert latest.json()["format"] == await _format(importing)
    assert latest.json()["system"] == QBO


async def test_ac5_a_total_row_gives_the_control_totals_and_without_one_the_lines_do(
    importing: World,
) -> None:
    with_total = (await _upload(importing, importing.owner, _qbo())).json()
    assert with_total["status"] == "received" and with_total["totals_from_lines"] is False
    other_owner = await importing.seed.client_contact(importing.other)
    without = await _upload(importing, other_owner, _qbo(total=False), site=importing.other)
    assert without.status_code == 201, without.text
    assert without.json()["status"] == "received" and without.json()["totals_from_lines"] is True


async def test_ac5_parenthesised_negatives_and_signed_amounts_are_read(importing: World) -> None:
    """Credits written as parenthesised or signed negative debits balance like credit columns."""
    parenthesised = (
        _qbo()
        .replace(b',,"4,000.00"', b',"(4,000.00)",')
        .replace(b',,"6,750.00"', b',"-6,750.00",')
    )
    done = await _upload(importing, importing.owner, parenthesised)
    assert done.status_code == 201, done.text
    assert done.json()["status"] == "received", done.json()
    assert Decimal(str(done.json()["difference"] or 0)) == Decimal(0)


async def test_ac6_an_unbalanced_export_fails_with_the_difference_and_nothing_is_kept(
    importing: World,
) -> None:
    failed = await _upload(importing, importing.owner, _qbo(short=Decimal("1250.00")))
    assert failed.status_code == 201, failed.text
    body = failed.json()
    assert body["status"] == "failed" and body["failure_code"]
    assert Decimal(str(body["difference"])).copy_abs() == Decimal("1250.00")
    assert await importing.count("ledger_snapshots") == 0
    assert await importing.count("fulfilments") == 0
    seen_by_firm = (await importing.call("GET", "/import", importing.manager)).json()
    assert seen_by_firm["status"] == "failed"
    assert seen_by_firm["failure_code"] == body["failure_code"]


@pytest.mark.parametrize("system", ["QuickBooks Online", "Xero"])
async def test_ac6_an_export_of_another_period_fails_naming_the_period_it_covers(
    importing: World, system: str
) -> None:
    """SPEC-028 AC-6 and §12: an export of another period is refused (`period_mismatch`) with
    both periods in the message, and nothing is snapshotted or fulfilled, whenever the check runs:
    at upload, or when the pipeline reads the export."""
    content = _qbo(as_of="November 30, 2025") if system == QBO else _xero(as_at="30 November 2025")
    fmt = await _format(importing, system)
    uploaded = await _upload(importing, importing.owner, content, fmt=fmt)
    assert uploaded.status_code == 201, uploaded.text
    if uploaded.json()["status"] == "received":
        await _pipeline(importing)
    assert await importing.count("ledger_snapshots") == 0
    assert await importing.count("fulfilments") == 0
    seen = (await importing.call("GET", "/import", importing.owner)).json()
    assert seen["status"] == "failed", json.dumps(seen)
    assert seen["found_period_end"] == "2025-11-30"


async def test_ac4_a_clean_xero_export_is_received(importing: World) -> None:
    done = await _upload(importing, importing.owner, _xero(), fmt=await _format(importing, "Xero"))
    assert done.status_code == 201, done.text
    assert done.json()["status"] == "received", done.json()


async def test_ac8_the_same_export_twice_is_recognised_and_kept_once(importing: World) -> None:
    content = _qbo()
    first = await _upload(importing, importing.owner, content)
    assert first.status_code == 201 and first.json()["duplicate"] is False
    second = await _upload(importing, importing.owner, content)
    assert second.status_code == 201, second.text
    assert second.json()["duplicate"] is True
    assert await importing.count("ledger_imports") == 1


@pytest.mark.parametrize("role", ["partner", "manager", "senior"])
async def test_q4_the_firm_uploads_on_the_clients_behalf(importing: World, role: str) -> None:
    done = await _upload(importing, cast(Person, getattr(importing, role)), _qbo())
    assert done.status_code == 201, done.text
    assert done.json()["on_behalf"] is True


@pytest.mark.parametrize("role", ["staff", "contributor", "admin"])
async def test_q4_others_may_not_upload_an_export(importing: World, role: str) -> None:
    refused = await _upload(importing, cast(Person, getattr(importing, role)), _qbo())
    assert refused.status_code == 403, refused.text
    assert await importing.count("ledger_imports") == 0


async def test_rollout_an_upload_is_refused_while_the_firms_flag_is_off(world: World) -> None:
    refused = await _upload(world, world.owner, _qbo())
    assert refused.status_code == 409 and refused.json()["detail"] == "ledger_import_off"
    assert await world.count("ledger_imports") == 0


async def test_ac1_a_live_connection_makes_an_export_unneeded(importing: World) -> None:
    await importing.connected()
    refused = await _upload(importing, importing.owner, _qbo())
    assert refused.status_code == 409 and refused.json()["detail"] == "already_connected"
    assert await importing.count("ledger_imports") == 0


async def test_ac3_another_firm_cannot_upload_or_read_an_import(importing: World) -> None:
    assert (await _upload(importing, importing.owner, _qbo())).status_code == 201
    stranger_firm = await importing.seed.firm()
    stranger = await importing.seed.person(stranger_firm, "firm_admin")
    await importing.seed.run(  # the stranger's own firm may import: only the engagement is foreign
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'ledger.import', 'true', 'test-seed', 'Q-03-T022 tests')",
        stranger_firm,
    )
    forget_flags()
    assert (await _upload(importing, stranger, _qbo())).status_code == 404
    assert (await importing.call("GET", "/import", stranger)).status_code == 404
