"""Q-01-T59: independent acceptance tests (ADR-078) for the browser error tunnel
`POST /v1/telemetry/errors` (Q-01-T48), against Postgres.

Written from the plan, not from the code: Q-01 §3 F6 (the browser bullet) and §4 (the route row).
- The server re-scrubs by allowlist and forwards only the route template, the error type, the
  release, the environment and the tenant UUID. A seeded SSN, TIN or email never reaches Sentry.
- Agent principals, system contexts, support sessions and unauthenticated callers are refused;
  every human principal (firm staff and client users) may report.
- At most 64 KB per envelope; 30 per minute per session.

"Reaches Sentry" is observed at the wire: the real Sentry SDK is started through
`configure_error_tracking` with a transport that keeps the serialised envelopes it would send.
Nothing here leaves the process. Every seeded value is synthetic.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, cast

import httpx
import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.error_tracking import configure_error_tracking
from abacus.modules.identity.api import (
    AuthContext,
    agent_context_for_run,
    configure_verifier,
    current_context,
    reset_verifier,
    system_context_for_run,
)
from abacus_tools.fakes.identity import FakeIdentityProvider

from .agent_tests.support import Migrated, Person, Seeder

PATH = "/v1/telemetry/errors"
LIMIT_BYTES = 64 * 1024
PER_MINUTE = 30
# Synthetic, obviously fake values of the three shapes the AC names.
SSN = "900-12-3456"
TIN = "07-1234567"
TIN_BARE = "900123456"
EMAIL = "seeded.person@example.test"
MARKER = "HOSTILE-MARKER-5591"  # in every browser field the allowlist does not name
SEEDED = (SSN, TIN, TIN_BARE, EMAIL, MARKER)
SERVER_RELEASE = "abacus-web@tunnel-acceptance"
DSN = "https://public@example.invalid/1"
ROUTE = "/engagements/$engagementId/requests"
PROBE = "TunnelProbeError"  # a browser error type no server fault carries
Json = dict[str, object]


# --- the Sentry wire -----------------------------------------------------------------------------


class Wire(Transport):
    """A Sentry transport that keeps every envelope it is handed, serialised, and sends nothing."""

    sent: ClassVar[list[bytes]] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        Wire.sent.append(envelope.serialize())


def _events(raw: list[bytes]) -> list[Json]:
    """The event items of the serialised envelopes."""
    events: list[Json] = []
    for envelope in raw:
        lines = envelope.split(b"\n")
        for i, line in enumerate(lines[:-1]):
            try:
                header = cast(object, json.loads(line))
            except ValueError:
                continue
            if isinstance(header, dict) and cast(Json, header).get("type") == "event":
                events.append(cast(Json, json.loads(lines[i + 1])))
    return events


@dataclass
class Sentry:
    def flush(self) -> None:
        sentry_sdk.flush(2.0)

    @property
    def wire(self) -> bytes:
        self.flush()
        return b"\n".join(Wire.sent)

    @property
    def events(self) -> list[Json]:
        self.flush()
        return _events(Wire.sent)


@pytest.fixture
def sentry(monkeypatch: pytest.MonkeyPatch) -> Iterator[Sentry]:
    """Error tracking switched on as a deployment would (a DSN and a release), with the wire
    captured."""
    monkeypatch.setenv("ABACUS_SENTRY_DSN", DSN)
    monkeypatch.setenv("ABACUS_RELEASE", SERVER_RELEASE)
    settings.cache_clear()
    monkeypatch.setattr("abacus.kernel.error_tracking._configured", False)
    real = sentry_sdk.init

    def init(**options: object) -> None:
        real(**options, transport=Wire)  # pyright: ignore[reportArgumentType] -- untyped **options

    monkeypatch.setattr(sentry_sdk, "init", init)
    Wire.sent = []
    assert configure_error_tracking("abacus-api") is True
    yield Sentry()
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)
    Wire.sent = []


# --- the app, a signed-in person ----------------------------------------------------------------


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


@pytest.fixture
async def http(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@dataclass(frozen=True)
class Signed:
    person: Person
    subject: str


async def _signed(seed: Seeder, *, firm_role: str | None = None) -> Signed:
    tenant_id = await seed.firm()
    who = await _signed_in(seed, tenant_id)
    if firm_role is not None:
        await seed.run(
            "UPDATE memberships SET firm_role = $1 WHERE tenant_id = $2 AND user_id = $3",
            firm_role,
            tenant_id,
            who.person.user_id,
        )
    return who


async def _client_user(seed: Seeder) -> Signed:
    """A portal user: a client membership, an `owner` grant on one engagement."""
    staff = await _signed(seed, firm_role="firm_admin")
    tenant_id = staff.person.tenant_id
    client = await _signed_in(seed, tenant_id)
    entity_id = await seed.entity(tenant_id)
    engagement_id = await seed.engagement(tenant_id, entity_id, staff.person.user_id)
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        tenant_id,
        client.person.user_id,
    )
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'engagement', $3)",
        tenant_id,
        client.person.user_id,
        engagement_id,
    )
    return client


async def _signed_in(seed: Seeder, tenant_id: uuid.UUID) -> Signed:
    person = await seed.person(tenant_id)
    subject = str(await seed.value("SELECT idp_subject FROM users WHERE id = $1", person.user_id))
    return Signed(person, subject)


# --- envelopes -----------------------------------------------------------------------------------


def _event(
    error_type: str = "TypeError", route: str = ROUTE, **extra_tags: str
) -> dict[str, object]:
    """A browser event as `@sentry/browser` would build it, with the seeded values in every field
    the allowlist does not name, and in the ones it does where they could ride along."""
    return {
        "event_id": uuid.uuid4().hex,
        "timestamp": 1_792_000_000.0,
        "platform": "javascript",
        "level": "fatal",
        "message": f"failed for {SSN} ({EMAIL})",
        "logentry": {"message": f"TIN {TIN}", "params": [TIN_BARE]},
        "exception": {
            "values": [
                {
                    "type": error_type,
                    "value": f"Cannot read {SSN} of {EMAIL}",
                    "module": MARKER,
                    "mechanism": {"type": "onerror", "data": {"ssn": SSN}},
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": f"https://app.example.test/{EMAIL}.js",
                                "function": MARKER,
                                "lineno": 1,
                                "vars": {"tin": TIN},
                                "context_line": f"const tin = '{TIN_BARE}'",
                            }
                        ]
                    },
                }
            ]
        },
        "tags": {"route": route, "email": EMAIL, "ssn": SSN, **extra_tags},
        "user": {"id": SSN, "email": EMAIL, "ip_address": "{{auto}}"},
        "request": {
            "url": f"https://app.example.test/clients?tin={TIN}",
            "headers": {"Referer": EMAIL, "Cookie": MARKER},
            "query_string": f"ssn={SSN}",
        },
        "breadcrumbs": {"values": [{"message": f"typed {SSN}", "category": "ui.input"}]},
        "contexts": {"trace": {"trace_id": MARKER}, "browser": {"name": MARKER}},
        "extra": {"tin": TIN_BARE, "email": EMAIL},
        "fingerprint": [SSN],
        "transaction": f"/clients/{TIN_BARE}",
        "server_name": MARKER,
        "dist": MARKER,
        "modules": {MARKER: "1"},
        "sdk": {"name": MARKER, "version": "8.0.0"},
        "release": f"web@{SSN}",
        "environment": EMAIL,
    }


def _envelope(*items: tuple[str, dict[str, object]]) -> bytes:
    header: dict[str, object] = {
        "event_id": uuid.uuid4().hex,
        "dsn": f"https://{MARKER}@example.invalid/1",
        "sdk": {"name": MARKER},
        "trace": {"user_id": EMAIL},
    }
    lines: list[dict[str, object]] = [header]
    for kind, body in items:
        lines.extend([{"type": kind}, body])
    return "\n".join(json.dumps(line) for line in lines).encode() + b"\n"


def _error(error_type: str = "TypeError", route: str = ROUTE, **extra_tags: str) -> bytes:
    return _envelope(("event", _event(error_type, route, **extra_tags)))


def _sized(size: int) -> bytes:
    """A valid error envelope padded (inside a dropped field) to exactly `size` bytes."""
    event = _event()
    event["extra"] = {"pad": ""}
    base = len(_envelope(("event", event)))
    event["extra"] = {"pad": "x" * (size - base)}
    body = _envelope(("event", event))
    assert len(body) == size
    return body


async def _post(
    http: httpx.AsyncClient, idp: FakeIdentityProvider, who: Signed, body: bytes
) -> httpx.Response:
    return await http.post(
        PATH,
        content=body,
        headers={
            "Authorization": f"Bearer {idp.token(who.subject)}",
            "Content-Type": "application/x-sentry-envelope",
        },
    )


def _assert_not_forwarded(sentry: Sentry) -> None:
    """The browser's event did not reach Sentry. (The server may still report its own fault.)"""
    _assert_nothing_seeded(sentry.wire)
    for event in sentry.events:
        assert PROBE.encode() not in json.dumps(event).encode(), event


def _assert_nothing_seeded(wire: bytes) -> None:
    for value in SEEDED:
        assert value.encode() not in wire, value


# --- the allowlist ------------------------------------------------------------------------------


async def test_q01_t59_an_error_reaches_sentry_with_only_the_allowlisted_fields(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _signed(seed)
    response = await _post(http, idp, who, _error())
    assert response.status_code == 200, response.text
    [event] = sentry.events
    _assert_nothing_seeded(sentry.wire)
    tags = cast(Json, event["tags"])
    assert tags.get("route") == ROUTE
    assert tags.get("tenant_id") == str(who.person.tenant_id)
    exception = cast(Json, event["exception"])
    values = cast(list[Json], exception["values"])
    assert [v["type"] for v in values] == ["TypeError"]
    assert event["release"] == SERVER_RELEASE
    assert event["environment"] == settings().environment
    for dropped in ("user", "request", "breadcrumbs", "extra", "message", "logentry", "modules"):
        assert dropped not in event, dropped
    # Every tag is one of the AC's fields (the error type may also ride as a tag).
    assert set(tags) <= {"route", "tenant_id", "error_type"}
    assert tags.get("error_type", "TypeError") == "TypeError"


async def test_q01_t59_release_environment_and_tenant_come_from_the_server_not_the_browser(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _signed(seed)
    claimed = str(uuid.uuid4())
    await _post(http, idp, who, _error(tenant_id=claimed))
    [event] = sentry.events
    assert claimed.encode() not in sentry.wire
    assert cast(Json, event["tags"])["tenant_id"] == str(who.person.tenant_id)
    assert event["release"] == SERVER_RELEASE
    assert event["environment"] == settings().environment


@pytest.mark.parametrize(
    ("error_type", "route"),
    [
        (f"TypeError {SSN}", ROUTE),
        (EMAIL, ROUTE),
        (f"Error{TIN_BARE}", ROUTE),
        (f"TIN {TIN}", ROUTE),
        ("TypeError", f"/clients/{SSN}"),
        ("TypeError", f"/clients/{TIN}"),
        ("TypeError", f"/returns/{TIN_BARE}"),
        ("TypeError", f"/people/{EMAIL}"),
        ("TypeError", f"/engagements/$engagementId?ssn={SSN}"),
        ("TypeError", f"https://app.example.test/people/{EMAIL}"),
        ("TypeError", f"{ROUTE}#{TIN}"),
    ],
)
async def test_q01_t59_seeded_values_in_the_type_or_route_never_reach_sentry(
    seed: Seeder,
    http: httpx.AsyncClient,
    idp: FakeIdentityProvider,
    sentry: Sentry,
    error_type: str,
    route: str,
) -> None:
    who = await _signed(seed)
    response = await _post(http, idp, who, _error(error_type, route))
    assert response.status_code < 500, response.text
    _assert_nothing_seeded(sentry.wire)


async def test_q01_t59_items_other_than_an_error_event_are_not_forwarded(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _signed(seed)
    hostile = {"message": SSN, "user": {"email": EMAIL}, "extra": {"tin": TIN}}
    body = _envelope(
        ("session", {"sid": MARKER, "did": EMAIL, "attrs": {"release": SSN}}),
        ("transaction", {**hostile, "transaction": f"/clients/{TIN_BARE}"}),
        ("attachment", {"data": TIN}),
        ("client_report", {"discarded_events": [{"reason": EMAIL}]}),
    )
    response = await _post(http, idp, who, body)
    assert response.status_code < 500, response.text
    assert sentry.events == []
    _assert_nothing_seeded(sentry.wire)


async def test_q01_t59_an_event_without_an_error_is_not_forwarded(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    """A message-only event (`captureMessage`) has no error type: nothing on the allowlist."""
    who = await _signed(seed)
    event = _event()
    del event["exception"]
    response = await _post(http, idp, who, _envelope(("event", event)))
    assert response.status_code < 500, response.text
    _assert_nothing_seeded(sentry.wire)


# --- who may report ------------------------------------------------------------------------------


@pytest.mark.parametrize("firm_role", [None, "firm_admin", "practice_leader", "security_admin"])
async def test_q01_t59_firm_staff_may_report(
    seed: Seeder,
    http: httpx.AsyncClient,
    idp: FakeIdentityProvider,
    sentry: Sentry,
    firm_role: str | None,
) -> None:
    who = await _signed(seed, firm_role=firm_role)
    response = await _post(http, idp, who, _error())
    assert response.status_code == 200, response.text
    assert len(sentry.events) == 1


async def test_q01_t59_a_client_user_may_report(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _client_user(seed)
    response = await _post(http, idp, who, _error())
    assert response.status_code == 200, response.text
    [event] = sentry.events
    assert cast(Json, event["tags"])["tenant_id"] == str(who.person.tenant_id)


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer not-a-token", "Basic dXNlcjpwYXNz", ""],
)
async def test_q01_t59_unauthenticated_callers_are_refused(
    http: httpx.AsyncClient, sentry: Sentry, authorization: str | None
) -> None:
    headers = {"Content-Type": "application/x-sentry-envelope"}
    if authorization is not None:
        headers["Authorization"] = authorization
    response = await http.post(PATH, content=_error(), headers=headers)
    assert response.status_code == 401, response.text
    assert sentry.wire == b""


async def test_q01_t59_a_token_for_someone_with_no_membership_is_refused(
    http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    stranger = Signed(Person(uuid.uuid4(), uuid.uuid4()), f"sub-{uuid.uuid4().hex}")
    response = await _post(http, idp, stranger, _error())
    assert response.status_code in (401, 403), response.text
    assert sentry.wire == b""


async def test_q01_t59_a_revoked_member_is_refused(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _signed(seed)
    await seed.revoke(who.person)
    response = await _post(http, idp, who, _error())
    assert response.status_code in (401, 403), response.text
    assert sentry.wire == b""


async def test_q01_t59_a_support_session_header_is_refused(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _signed(seed)
    response = await http.post(
        PATH,
        content=_error(),
        headers={
            "Authorization": f"Bearer {idp.token(who.subject)}",
            "X-Abacus-Tenant": str(who.person.tenant_id),
            "X-Support-Session": str(uuid.uuid4()),
        },
    )
    assert response.status_code in (401, 403), response.text
    assert sentry.wire == b""


def _assert_refused(response: httpx.Response) -> None:
    """Refused: no success, so nothing accepted. The route is `OWN` (TASK-922), not the plan's
    `telemetry.error.report` matrix action, so a non-human principal that reaches it is not
    refused by `authorise` with a 403; today it fails as a 500 (reported in Q-01-T59's task file).
    The AC's outcome, refused and nothing forwarded, is what this asserts."""
    assert response.status_code >= 400, response.text
    assert response.status_code != 413 and response.status_code != 429, response.text


@pytest.fixture
def as_principal() -> Iterator[Callable[[object], httpx.AsyncClient]]:
    """The app with its sign-in dependency answering as a given principal, the way
    tests/security/test_agent_principal.py puts the agent at the HTTP edge."""
    clients: list[httpx.AsyncClient] = []

    def make(principal: object) -> httpx.AsyncClient:
        app = create_app()
        app.dependency_overrides[current_context] = lambda: principal
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        client = httpx.AsyncClient(transport=transport, base_url="http://test")
        clients.append(client)
        return client

    yield make


async def test_q01_t59_a_support_session_principal_is_refused(
    seed: Seeder, sentry: Sentry, as_principal: Callable[[object], httpx.AsyncClient]
) -> None:
    """A live break-glass context as `identity.support` builds it (actor kind `support`)."""
    tenant_id = await seed.firm()
    session_id = uuid.uuid4()
    support = AuthContext(
        tenant=TenantContext(tenant_id, "support", f"support:{session_id}"),
        user_id=uuid.uuid4(),
        membership_id=session_id,
        firm_role="platform_support",
        mfa_at=datetime.now(UTC),
    )
    async with as_principal(support) as client:
        response = await client.post(PATH, content=_error())
    assert response.status_code == 403, response.text
    assert sentry.wire == b""


async def test_q01_t59_an_agent_principal_is_refused(
    seed: Seeder, sentry: Sentry, as_principal: Callable[[object], httpx.AsyncClient]
) -> None:
    """INV-1: the agent principal holds no telemetry action, whoever it acts for."""
    initiator = await _signed(seed, firm_role="firm_admin")
    agent = await agent_context_for_run(
        tenant_id=initiator.person.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="evidence.screener",
        engagement_id=None,
        task_scope=frozenset({"telemetry.error.report"}),
        initiator_user_id=initiator.person.user_id,
    )
    async with as_principal(agent) as client:
        response = await client.post(PATH, content=_error(PROBE))
    _assert_refused(response)
    _assert_not_forwarded(sentry)


async def test_q01_t59_a_system_context_is_refused(
    seed: Seeder, sentry: Sentry, as_principal: Callable[[object], httpx.AsyncClient]
) -> None:
    """§4: refused to system contexts."""
    initiator = await _signed(seed)
    system = system_context_for_run(
        tenant_id=initiator.person.tenant_id,
        run_id=uuid.uuid4(),
        engagement_id=uuid.uuid4(),
        on_behalf_of=initiator.person.user_id,
    )
    async with as_principal(system) as client:
        response = await client.post(PATH, content=_error(PROBE))
    _assert_refused(response)
    _assert_not_forwarded(sentry)


# --- limits --------------------------------------------------------------------------------------


async def test_q01_t59_an_envelope_of_exactly_64_kb_is_accepted(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _signed(seed)
    response = await _post(http, idp, who, _sized(LIMIT_BYTES))
    assert response.status_code == 200, response.text
    assert len(sentry.events) == 1
    _assert_nothing_seeded(sentry.wire)


async def test_q01_t59_an_envelope_over_64_kb_is_refused(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _signed(seed)
    response = await _post(http, idp, who, _sized(LIMIT_BYTES + 1))
    assert response.status_code == 413, response.text
    assert sentry.wire == b""


async def test_q01_t59_an_oversized_envelope_without_a_length_is_refused(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    """Streamed (chunked, no Content-Length): the cap holds on the bytes, not the header."""
    who = await _signed(seed)
    body = _sized(LIMIT_BYTES + 4096)

    async def chunks() -> AsyncIterator[bytes]:
        for start in range(0, len(body), 8192):
            yield body[start : start + 8192]

    response = await http.post(
        PATH,
        content=chunks(),
        headers={
            "Authorization": f"Bearer {idp.token(who.subject)}",
            "Content-Type": "application/x-sentry-envelope",
        },
    )
    assert response.status_code == 413, response.text
    assert sentry.wire == b""


async def test_q01_t59_an_understated_length_does_not_lift_the_cap(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _signed(seed)
    body = _sized(LIMIT_BYTES + 1024)

    async def chunks() -> AsyncIterator[bytes]:
        yield body

    response = await http.post(
        PATH,
        content=chunks(),
        headers={
            "Authorization": f"Bearer {idp.token(who.subject)}",
            "Content-Type": "application/x-sentry-envelope",
            "Content-Length": "100",
        },
    )
    assert response.status_code in (400, 413), response.text
    assert sentry.wire == b""


async def test_q01_t59_thirty_per_minute_then_refused(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    who = await _signed(seed)
    codes = [(await _post(http, idp, who, _error())).status_code for _ in range(PER_MINUTE)]
    assert codes == [200] * PER_MINUTE
    over = await _post(http, idp, who, _error())
    assert over.status_code == 429, over.text
    assert len(sentry.events) == PER_MINUTE


async def test_q01_t59_one_sessions_limit_does_not_spend_anothers(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, sentry: Sentry
) -> None:
    first, second = await _signed(seed), await _signed(seed)
    for _ in range(PER_MINUTE):
        await _post(http, idp, first, _error())
    assert (await _post(http, idp, first, _error())).status_code == 429
    response = await _post(http, idp, second, _error())
    assert response.status_code == 200, response.text
