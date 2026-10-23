"""Q-01-T48 against Postgres: the browser error tunnel forwards only an allowlisted rebuild of the
event. A seeded SSN, TIN or email never reaches the forwarded payload. Support-session and
unauthenticated calls are refused; the envelope is capped at 64 KB and 30 per minute per person."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Protocol, cast

import asyncpg
import httpx
import pytest

import abacus.modules.platform.telemetry as telemetry
from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.error_tracking import forward_event
from abacus.modules.identity.api import configure_verifier, reset_verifier
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

SSN, TIN, EMAIL = "900-45-6789", "900456789", "claire.feld@example.test"


class Migrated(Protocol):
    app_url: str
    identity_url: str
    superuser_dsn: str


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
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    captured: list[dict[str, object]] = []

    def capture(event: dict[str, object]) -> bool:
        captured.append(event)
        return True

    monkeypatch.setattr(telemetry, "forward_event", capture)
    monkeypatch.setattr(telemetry, "_recent", {})
    return captured


@pytest.fixture
async def http(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _member(migrated_db: Migrated) -> tuple[uuid.UUID, str]:
    dsn = migrated_db.superuser_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    tenant, subject = uuid.uuid4(), f"sub-{uuid.uuid4().hex}"
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Firm')", tenant)
        user = await conn.fetchval(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, 'Staff') RETURNING id",
            ISSUER,
            subject,
            f"{subject}@example.test",
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, NULL, 'active')",
            tenant,
            user,
        )
    finally:
        await conn.close()
    return tenant, subject


def _envelope(error_type: str = "TypeError", route: str = "/engagements/$engagementId") -> bytes:
    event: dict[str, object] = {
        "event_id": uuid.uuid4().hex,
        "message": f"failed for {SSN} {EMAIL}",
        "exception": {"values": [{"type": error_type, "value": f"TIN {TIN} at {EMAIL}"}]},
        "tags": {"route": route, "email": EMAIL},
        "user": {"email": EMAIL, "id": SSN},
        "breadcrumbs": [{"message": SSN}],
        "request": {"url": f"https://app.test/x?ssn={SSN}"},
        "release": f"web@{SSN}",
        "environment": EMAIL,
    }
    lines: list[dict[str, object]] = [{"event_id": event["event_id"]}, {"type": "event"}, event]
    return "\n".join(json.dumps(line) for line in lines).encode() + b"\n"


async def _post(
    http: httpx.AsyncClient, idp: FakeIdentityProvider, subject: str, body: bytes
) -> httpx.Response:
    return await http.post(
        "/v1/telemetry/errors",
        content=body,
        headers={
            "Authorization": f"Bearer {idp.token(subject)}",
            "Content-Type": "application/x-sentry-envelope",
        },
    )


async def test_q01t48_only_the_allowlisted_rebuild_is_forwarded(
    migrated_db: Migrated,
    http: httpx.AsyncClient,
    idp: FakeIdentityProvider,
    sent: list[dict[str, object]],
) -> None:
    tenant, subject = await _member(migrated_db)
    response = await _post(http, idp, subject, _envelope())
    assert (response.status_code, response.json()) == (200, {"forwarded": True})
    [event] = sent
    dumped = json.dumps(event)
    for secret in (SSN, TIN, EMAIL, "claire"):
        assert secret not in dumped
    assert event["exception"] == {"values": [{"type": "TypeError"}]}
    assert event["tags"] == {
        "tenant_id": str(tenant),
        "error_type": "TypeError",
        "route": "/engagements/$engagementId",
    }
    assert event["environment"] == settings().environment
    assert event["release"] == settings().release
    assert set(event) == {
        "event_id",
        "level",
        "platform",
        "environment",
        "release",
        "server_name",
        "exception",
        "tags",
    }


@pytest.mark.parametrize(
    ("error_type", "route"),
    [
        (f"Error{TIN}", "/engagements"),  # digits are never part of a type name
        (EMAIL, "/engagements"),
        ("TypeError", f"/clients/{SSN}"),  # nor of a route template
        ("TypeError", f"/people/{EMAIL}"),
    ],
)
async def test_q01t48_a_type_or_route_carrying_data_is_dropped(
    migrated_db: Migrated,
    http: httpx.AsyncClient,
    idp: FakeIdentityProvider,
    sent: list[dict[str, object]],
    error_type: str,
    route: str,
) -> None:
    _, subject = await _member(migrated_db)
    await _post(http, idp, subject, _envelope(error_type, route))
    for event in sent:
        dumped = json.dumps(event)
        assert SSN not in dumped and TIN not in dumped and EMAIL not in dumped


async def test_q01t48_unauthenticated_and_support_calls_are_refused(
    migrated_db: Migrated,
    http: httpx.AsyncClient,
    idp: FakeIdentityProvider,
    sent: list[dict[str, object]],
) -> None:
    _, subject = await _member(migrated_db)
    anonymous = await http.post("/v1/telemetry/errors", content=_envelope())
    assert anonymous.status_code == 401
    support = await http.post(
        "/v1/telemetry/errors",
        content=_envelope(),
        headers={
            "Authorization": f"Bearer {idp.token(subject)}",
            "X-Support-Session": str(uuid.uuid4()),
        },
    )
    assert support.status_code in (401, 403)
    assert sent == []


async def test_q01t48_the_size_and_rate_limits_hold(
    migrated_db: Migrated,
    http: httpx.AsyncClient,
    idp: FakeIdentityProvider,
    sent: list[dict[str, object]],
) -> None:
    _, subject = await _member(migrated_db)
    huge = await _post(http, idp, subject, b"x" * (64 * 1024 + 1))
    assert huge.status_code == 413
    codes = [(await _post(http, idp, subject, _envelope())).status_code for _ in range(31)]
    assert codes.count(200) == 30 and codes[-1] == 429


def test_q01t48_nothing_is_forwarded_when_tracking_is_off() -> None:
    assert forward_event({"exception": {"values": [{"type": "TypeError"}]}}) is False


def test_q01t48_the_rebuild_never_takes_the_clients_release_or_environment() -> None:
    event = cast(dict[str, object], telemetry.rebuild(_envelope(), uuid.uuid4()))
    assert SSN not in json.dumps(event) and EMAIL not in json.dumps(event)
