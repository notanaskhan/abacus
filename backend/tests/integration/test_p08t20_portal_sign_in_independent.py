"""P-08-T20: independent acceptance tests for the portal sign-in (ADR-078; P-08-T05, T06, T10).

Written from SPEC-320 (AC-6, AC-7, AC-9), the epic's Stories 2.1 and 2.2 and
`docs/contracts/portal-identity.md` §2.2, §6 and §7, against the HTTP surface and the published
service entry points only, not from the implementing suite (`test_portal_sign_in.py`):

- enumeration: an unknown email, a staff member, another firm's client, a locked email and a
  valid client get the same status, body shape and (within a fixed tolerance) the same time;
- the 10-minute code, the lock after the third wrong code for 15 minutes, the 60-second resend
  that voids the old code and keeps the tries;
- the `__Host-` cookie's flags, the CSRF header and Origin on refresh, refresh reuse, sign-out;
- branding: Public fields only, the same shape for an unknown host;
- the identity provider adapter and the WorkOS fake answer the port the same way;
- no email address, IP or code in what the process logs.

Security windows run on real time (`kernel.clock.system_now`, which a demo clock never moves), so
"ten minutes later" is staged by moving the stored sign-in timestamps back (`_age`); nothing else
reaches past the API.
"""

from __future__ import annotations

import logging
import re
import statistics
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.identity import portal_session
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, PortalIdp, totp_at
from abacus.modules.identity.portal_session import issue_sign_in_code
from abacus.modules.portal.branding import activate_portal_host, add_portal_host
from abacus_tools.fakes.workos import FakeWorkOsPortalIdp

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

COOKIE = "__Host-abacus-portal"
START_SHAPE = {"challenge_id", "code_expires_at", "resend_available_at"}
# The floor every pre-session answer waits for (SPEC-320 AC-6 "padded timing") and the spread the
# suite allows between kinds of email, on a shared CI machine.
FLOOR = 0.45
SPREAD = 0.35
UUID_SHAPED = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(portal_session, "flag_enabled", on)  # the firm has portal.sign_in_v2 on
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


ADDRESS = "203.0.113.77"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), client=(ADDRESS, 51000))
    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as http:
        yield http


async def _firm(seed: Seeder) -> tuple[uuid.UUID, str]:
    tenant = await seed.firm()
    host = f"t20-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    return tenant, host


async def _client_person(seed: Seeder, tenant: uuid.UUID) -> str:
    """A client of the firm with an active `contributor` grant (no MFA floor): their email."""
    partner = await seed.person(tenant)
    engagement = await seed.engagement(tenant, await seed.entity(tenant), partner.user_id)
    person = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        person.user_id,
    )
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'contributor', 'engagement', $3)",
        tenant,
        person.user_id,
        engagement,
    )
    return cast(str, await seed.value("SELECT email FROM users WHERE id = $1", person.user_id))


async def _age(seed: Seeder, host: str, seconds: int) -> None:
    """Stage `seconds` passing for this host's sign-in: every stored time moves back."""
    gap = timedelta(seconds=seconds)
    await seed.run(
        "UPDATE sign_in_challenges SET created_at = created_at - $2::interval, "
        "code_expires_at = code_expires_at - $2::interval, "
        "resend_available_at = resend_available_at - $2::interval "
        "WHERE host = $1",
        host,
        gap,
    )
    await seed.run(
        "UPDATE sign_in_locks l SET locked_until = l.locked_until - $2::interval, "
        "window_until = l.window_until - $2::interval FROM sign_in_challenges c "
        "WHERE c.host = $1 AND l.host_tenant_id = c.host_tenant_id "
        "AND l.email_sha256 = c.email_sha256",
        host,
        gap,
    )


async def _start(client: httpx.AsyncClient, host: str, email: str) -> httpx.Response:
    return await client.post(
        "/v1/portal/auth/start", json={"email": email}, headers={"host": host}
    )


async def _verify(
    client: httpx.AsyncClient, host: str, challenge: str, code: str
) -> httpx.Response:
    return await client.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": challenge, "code": code},
        headers={"host": host},
    )


async def _code(challenge: str) -> str:
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    return issued.code


def _wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


async def _signed_in(client: httpx.AsyncClient, host: str, email: str) -> httpx.Response:
    challenge = (await _start(client, host, email)).json()["challenge_id"]
    response = await _verify(client, host, challenge, await _code(challenge))
    assert response.status_code == 200 and response.json()["state"] == "signed_in"
    return response


def _cookie_of(response: httpx.Response) -> str:
    jar = SimpleCookie()
    jar.load(response.headers["set-cookie"])
    return jar[COOKIE].value


async def _lock(client: httpx.AsyncClient, host: str, email: str) -> httpx.Response:
    challenge = (await _start(client, host, email)).json()["challenge_id"]
    last = None
    for _ in range(3):
        last = await _verify(client, host, challenge, "000000")
    assert last is not None
    return last


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _code_requests(seed: Seeder, tenant: uuid.UUID) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
            "AND event_type = 'portal.sign_in_code_requested'",
            tenant,
        ),
    )


# --- AC-6: no enumeration ----------------------------------------------------------------------


async def test_ac6_every_kind_of_email_gets_one_status_body_shape_and_time(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    valid = await _client_person(seed, tenant)
    staff = await seed.person(tenant)
    staff_email = cast(
        str, await seed.value("SELECT email FROM users WHERE id = $1", staff.user_id)
    )
    other_tenant, _ = await _firm(seed)
    elsewhere = await _client_person(seed, other_tenant)
    locked = await _client_person(seed, tenant)
    assert (await _lock(client, host, locked)).status_code == 423
    sent_before = await _code_requests(seed, tenant)  # the locked person's own sign-in
    kinds = {
        "valid": valid,
        "unknown": f"nobody-{uuid.uuid4().hex[:6]}@example.test",
        "staff": staff_email,
        "another firm's client": elsewhere,
        "locked": locked,
    }
    times: dict[str, list[float]] = {k: [] for k in kinds}
    for _ in range(3):
        for kind, email in kinds.items():
            began = time.perf_counter()
            response = await _start(client, host, email)
            times[kind].append(time.perf_counter() - began)
            assert response.status_code == 202, kind
            body = cast(dict[str, object], response.json())
            assert set(body) == START_SHAPE, kind
            assert UUID_SHAPED.fullmatch(str(body["challenge_id"])), kind
            assert _at(str(body["code_expires_at"])) > datetime.now(UTC), kind
            assert response.headers["cache-control"] == "no-store", kind
    medians = {k: statistics.median(v) for k, v in times.items()}
    assert min(medians.values()) >= FLOOR, medians
    assert max(medians.values()) - min(medians.values()) <= SPREAD, medians
    # Only the valid client is sent a code (the first start; the 60 s rule holds the rest).
    assert await _code_requests(seed, tenant) == sent_before + 1
    assert await _code_requests(seed, other_tenant) == 0


async def test_ac6_an_unknown_email_writes_no_audit_event_in_the_firm(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    before = await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", tenant)
    unknown = f"nobody-{uuid.uuid4().hex[:6]}@example.test"
    challenge = (await _start(client, host, unknown)).json()["challenge_id"]
    for _ in range(3):
        await _verify(client, host, challenge, "000000")
    after = await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", tenant)
    assert after == before


async def test_ac7_an_email_that_matches_no_one_locks_the_same_way(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    _, host = await _firm(seed)
    unknown = f"nobody-{uuid.uuid4().hex[:6]}@example.test"
    challenge = (await _start(client, host, unknown)).json()["challenge_id"]
    first = await _verify(client, host, challenge, "000000")
    assert first.status_code == 401
    assert first.json() == {"detail": "code_mismatch", "facts": {"tries_left": 2}}
    await _verify(client, host, challenge, "000000")
    third = await _verify(client, host, challenge, "000000")
    assert third.status_code == 423 and third.json()["detail"] == "sign_in_locked"


# --- AC-7: the code, the lock and the resend -----------------------------------------------------


async def test_ac7_a_code_older_than_10_minutes_answers_410(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    email = await _client_person(seed, tenant)
    started = (await _start(client, host, email)).json()
    assert _at(started["code_expires_at"]) - datetime.now(UTC) <= timedelta(minutes=10)
    assert _at(started["code_expires_at"]) - datetime.now(UTC) > timedelta(minutes=9)
    code = await _code(started["challenge_id"])
    await _age(seed, host, 10 * 60 + 1)
    late = await _verify(client, host, started["challenge_id"], code)
    assert late.status_code == 410 and late.json() == {"detail": "code_expired"}

    fresh = (await _start(client, host, email)).json()
    fresh_code = await _code(fresh["challenge_id"])
    await _age(seed, host, 9 * 60 + 30)  # still inside the ten minutes
    assert (await _verify(client, host, fresh["challenge_id"], fresh_code)).status_code == 200


async def test_ac7_the_third_wrong_code_locks_for_15_minutes_then_sign_in_works(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    email = await _client_person(seed, tenant)
    started = (await _start(client, host, email)).json()
    code = await _code(started["challenge_id"])
    tries = [await _verify(client, host, started["challenge_id"], _wrong(code)) for _ in range(2)]
    assert [t.json()["facts"]["tries_left"] for t in tries] == [2, 1]
    locked = await _verify(client, host, started["challenge_id"], _wrong(code))
    assert locked.status_code == 423
    until = _at(locked.json()["facts"]["locked_until"])
    assert timedelta(minutes=14) < until - datetime.now(UTC) <= timedelta(minutes=15, seconds=5)
    # The right code during the lock, on a fresh challenge too, is refused the same way.
    again = (await _start(client, host, email)).json()
    assert (await _verify(client, host, again["challenge_id"], "123456")).status_code == 423
    await _age(seed, host, 15 * 60 + 1)
    after = (await _start(client, host, email)).json()
    signed = await _verify(client, host, after["challenge_id"], await _code(after["challenge_id"]))
    assert signed.status_code == 200 and signed.json()["state"] == "signed_in"


async def test_ac7_resend_waits_60_seconds_voids_the_old_code_and_keeps_the_tries(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    email = await _client_person(seed, tenant)
    started = (await _start(client, host, email)).json()
    challenge = started["challenge_id"]
    old = await _code(challenge)
    missed = await _verify(client, host, challenge, _wrong(old))
    assert missed.json()["facts"]["tries_left"] == 2
    soon = await client.post(
        "/v1/portal/auth/resend", json={"challenge_id": challenge}, headers={"host": host}
    )
    assert soon.status_code == 429 and soon.json()["detail"] == "resend_too_soon"
    assert _at(soon.json()["facts"]["resend_available_at"]) == _at(started["resend_available_at"])
    assert timedelta(seconds=50) < _at(started["resend_available_at"]) - datetime.now(UTC)
    await _age(seed, host, 61)
    resent = await client.post(
        "/v1/portal/auth/resend", json={"challenge_id": challenge}, headers={"host": host}
    )
    assert resent.status_code == 202 and set(resent.json()) == START_SHAPE
    await _code(challenge)
    stale = await _verify(client, host, challenge, old)  # the old code no longer works
    assert stale.status_code == 401 and stale.json()["facts"]["tries_left"] == 1  # not reset
    assert (await _verify(client, host, challenge, old)).status_code == 423


# --- AC-9 and ADR-168: the cookie, CSRF, refresh reuse, sign-out ---------------------------------


async def test_the_session_cookie_is_host_only_secure_httponly_and_strict(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    response = await _signed_in(client, host, await _client_person(seed, tenant))
    jar = SimpleCookie()
    jar.load(response.headers["set-cookie"])
    morsel = jar[COOKIE]
    assert morsel["secure"] and morsel["httponly"]
    assert str(morsel["samesite"]).lower() == "strict"
    assert morsel["path"] == "/" and not morsel["domain"]  # `__Host-`: this host only
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["access_token"] != morsel.value and isinstance(body["expires_in"], int)


async def test_refresh_needs_the_csrf_header_and_this_hosts_origin(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    cookie = _cookie_of(await _signed_in(client, host, await _client_person(seed, tenant)))
    for headers in (
        {"host": host, "origin": f"https://{host}"},  # no CSRF header
        {"host": host, "x-abacus-csrf": "1"},  # no Origin
        {"host": host, "origin": "https://elsewhere.example.test", "x-abacus-csrf": "1"},
        {"host": host, "origin": f"https://{host}", "x-abacus-csrf": "0"},
    ):
        client.cookies.clear()
        client.cookies.set(COOKIE, cookie)
        refused = await client.post("/v1/portal/auth/refresh", headers=headers)
        assert refused.status_code == 403, headers
    client.cookies.clear()
    client.cookies.set(COOKIE, cookie)
    ok = await client.post(
        "/v1/portal/auth/refresh",
        headers={"host": host, "origin": f"https://{host}", "x-abacus-csrf": "1"},
    )
    assert ok.status_code == 200 and ok.json()["state"] == "signed_in"
    assert _cookie_of(ok) != cookie  # rotated


async def test_a_reused_refresh_cookie_ends_the_session(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    first = _cookie_of(await _signed_in(client, host, await _client_person(seed, tenant)))
    headers = {"host": host, "origin": f"https://{host}", "x-abacus-csrf": "1"}

    async def refresh(cookie: str) -> httpx.Response:
        client.cookies.clear()
        client.cookies.set(COOKIE, cookie)
        return await client.post("/v1/portal/auth/refresh", headers=headers)

    rotated = await refresh(first)
    assert rotated.status_code == 200
    second = _cookie_of(rotated)
    reused = await refresh(first)
    assert reused.status_code == 401
    assert (await refresh(second)).status_code == 401  # the whole session ended


async def test_sign_out_ends_the_token_and_the_cookie(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    signed = await _signed_in(client, host, await _client_person(seed, tenant))
    token, cookie = signed.json()["access_token"], _cookie_of(signed)
    client.cookies.clear()
    client.cookies.set(COOKIE, cookie)
    out = await client.post(
        "/v1/portal/auth/sign-out", headers={"host": host, "authorization": f"Bearer {token}"}
    )
    assert out.status_code == 200
    again = await client.post(
        "/v1/portal/auth/sign-out", headers={"host": host, "authorization": f"Bearer {token}"}
    )
    assert again.status_code == 401
    client.cookies.clear()
    client.cookies.set(COOKIE, cookie)
    refreshed = await client.post(
        "/v1/portal/auth/refresh",
        headers={"host": host, "origin": f"https://{host}", "x-abacus-csrf": "1"},
    )
    assert refreshed.status_code == 401


# --- P-08-T05: branding --------------------------------------------------------------------------


async def test_branding_is_public_only_and_an_unknown_host_gets_the_same_shape(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host = await _firm(seed)
    known = await client.get("/v1/portal/branding", headers={"host": host})
    unknown = await client.get(
        "/v1/portal/branding", headers={"host": f"nobody-{uuid.uuid4().hex[:6]}.example.test"}
    )
    assert (known.status_code, unknown.status_code) == (200, 200)
    assert set(known.json()) == set(unknown.json())
    neutral = unknown.json()
    assert neutral["firm_name"] is None and neutral["logo_url"] is None
    for body in (known.text, unknown.text):
        assert str(tenant) not in body
        assert not UUID_SHAPED.search(body)  # no tenant or record identifier of any kind
        assert "accrued" not in body.casefold()
    logo = await client.get(
        "/v1/portal/branding/logo", headers={"host": f"nobody-{uuid.uuid4().hex[:6]}.example.test"}
    )
    assert logo.status_code == 404


# --- P-08-T06: the adapter and the fake ----------------------------------------------------------


async def _port_outcomes(idp: PortalIdp, now: float) -> tuple[object, ...]:
    """The port's observable answers, in one sequence both providers must agree on."""
    email = f"Parity.{uuid.uuid4().hex[:6]}@Sink.Example.Test"
    user = await idp.upsert_user(email)
    same = await idp.upsert_user(email.lower()) == user
    try:
        await idp.enrol_totp(user, issuer="Accrued", account=email)
        branded = "accepted"
    except ValueError:
        branded = "refused"
    enrolment = await idp.enrol_totp(user, issuer="Brightwater Hale", account=email)
    uri_ok = enrolment.otpauth_uri.startswith("otpauth://totp/") and (
        "Brightwater" in enrolment.otpauth_uri
    )
    challenge = await idp.challenge(enrolment.factor_id)
    right = await idp.verify(challenge, totp_at(enrolment.secret, now))
    replay = await idp.verify(challenge, totp_at(enrolment.secret, now))
    wrong = await idp.verify(await idp.challenge(enrolment.factor_id), "12345x")
    await idp.remove_factor(enrolment.factor_id)
    await idp.remove_factor(enrolment.factor_id)  # gone either way
    return (same, branded, uri_ok, right, replay, wrong)


async def test_the_in_memory_adapter_and_the_workos_fake_answer_the_port_alike() -> None:
    now = time.time()
    memory = await _port_outcomes(InMemoryPortalIdp(), now)
    fake = await _port_outcomes(FakeWorkOsPortalIdp(now=now), now)
    assert memory == fake == (True, "refused", True, True, False, False)


# --- SPEC-320 §15: nothing personal or secret in the logs ---------------------------------------


async def test_no_email_ip_or_code_reaches_the_logs(
    seed: Seeder,
    client: httpx.AsyncClient,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    tenant, host = await _firm(seed)
    email = await _client_person(seed, tenant)
    caplog.set_level(logging.DEBUG)
    capsys.readouterr()
    started = (await _start(client, host, email)).json()
    code = await _code(started["challenge_id"])
    await _verify(client, host, started["challenge_id"], _wrong(code))
    signed = await _verify(client, host, started["challenge_id"], code)
    assert signed.status_code == 200
    token = signed.json()["access_token"]
    await _start(client, host, f"nobody-{uuid.uuid4().hex[:6]}@example.test")
    captured = capsys.readouterr()
    logged = captured.out + captured.err + "\n".join(r.getMessage() for r in caplog.records)
    logged += "\n".join(str(r.__dict__) for r in caplog.records)
    for secret in (email, email.split("@")[0], code, ADDRESS, token, _cookie_of(signed)):
        assert secret not in logged, secret[:4]
