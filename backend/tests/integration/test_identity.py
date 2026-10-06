"""AC-1, AC-2, AC-3, AC-6, AC-8, AC-20: sign-in, tenant context, `authorise` and `visible`
against a real Postgres (TASK-007 contract).

Seed rows are written as the superuser (`migrated_db.superuser_dsn`; it bypasses row-level
security) with unique names, so tests never need cleanup. HTTP goes through
`httpx.ASGITransport(app=create_app())` with a probe router appended to `abacus.api.app.ROUTERS`.
Raw connections as the three database roles check the grants directly.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, Protocol, cast

import asyncpg
import httpx
import pytest
import yaml
from alembic.operations import Operations
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import Column, MetaData, Table, Text, Uuid, column, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import abacus.api.app as app_module
from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    dispose_engine,
    identity_engine,
    tenant_session,
)
from abacus.kernel.db.migration import tenant_table
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    configure_verifier,
    current_context,
    reset_verifier,
    visible,
)
from abacus_tools.codegen import permission_matrix as pm
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

TENANT_HEADER = "X-Abacus-Tenant"


FirmRole = Literal["firm_admin", "practice_leader", "quality_partner"]


class Migrated(Protocol):
    owner_url: str
    app_url: str
    identity_url: str
    superuser_dsn: str


def _plain(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


# --- seeding (superuser) -------------------------------------------------------------------------


class Seeder:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def run(self, sql: str, *args: object) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    async def value(self, sql: str, *args: object) -> object:
        conn = await asyncpg.connect(self._dsn)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    async def rows(self, sql: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self._dsn)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    async def firm(self, name: str | None = None) -> uuid.UUID:
        tenant_id = uuid.uuid4()
        await self.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, $2)",
            tenant_id,
            name or f"Firm {tenant_id.hex[:8]}",
        )
        return tenant_id

    async def user(self, subject: str | None = None) -> tuple[uuid.UUID, str]:
        subject = subject or f"sub-{uuid.uuid4().hex}"
        user_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                ISSUER,
                subject,
                f"{subject}@example.test",
                f"User {subject[-6:]}",
            ),
        )
        return user_id, subject

    async def membership(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        firm_role: str | None = None,
        *,
        revoked: bool = False,
    ) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO memberships (tenant_id, user_id, firm_role, status, revoked_at) "
                "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                tenant_id,
                user_id,
                firm_role,
                "revoked" if revoked else "active",
                datetime.now(UTC) if revoked else None,
            ),
        )

    async def revoke(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.run(
            "UPDATE memberships SET status = 'revoked', revoked_at = now() "
            "WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            user_id,
        )

    async def reactivate(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.run(
            "UPDATE memberships SET status = 'active', revoked_at = NULL "
            "WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            user_id,
        )

    async def set_firm_role(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, firm_role: str | None
    ) -> None:
        await self.run(
            "UPDATE memberships SET firm_role = $3 WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            user_id,
            firm_role,
        )

    async def engagement_member(
        self, tenant_id: uuid.UUID, engagement_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> None:
        await self.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            tenant_id,
            engagement_id,
            user_id,
            role,
        )


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    subject: str
    tenant_id: uuid.UUID


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Each test has its own event loop: rebuild the engines for it, from the test database."""
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


# --- probe routes with a real request context ----------------------------------------------------


class Seen(BaseModel):
    tenant_id: str
    actor_kind: str
    actor_id: str
    user_id: str
    firm_role: str | None
    mfa_at: str | None


class Ok(BaseModel):
    ok: bool


probe = AbacusRouter(prefix="/probe", tags=["probe"])


@probe.get("/context", action="engagement.read_metadata", response_model=Seen)
async def _context(ctx: Annotated[AuthContext, Depends(current_context)]) -> Seen:
    visible(ctx, "engagement.read_metadata", column("engagement_id", Uuid()))
    return Seen(
        tenant_id=str(ctx.tenant.tenant_id),
        actor_kind=ctx.tenant.actor_kind,
        actor_id=ctx.tenant.actor_id,
        user_id=str(ctx.user_id),
        firm_role=ctx.firm_role,
        mfa_at=None if ctx.mfa_at is None else ctx.mfa_at.isoformat(),
    )


@probe.get("/unchecked", action="engagement.create", response_model=Ok)
async def _unchecked(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    return Ok(ok=True)


@probe.get("/create", action="engagement.create", response_model=Ok)
async def _create(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    await authorise(ctx, "engagement.create", Resource.firm(ctx.tenant_id))
    return Ok(ok=True)


@probe.get("/update", action="engagement.update", response_model=Ok)
async def _update(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    await authorise(ctx, "engagement.update", Resource.firm(ctx.tenant_id))
    return Ok(ok=True)


@pytest.fixture
async def client(
    monkeypatch: pytest.MonkeyPatch, idp: FakeIdentityProvider
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(app_module, "ROUTERS", (*app_module.ROUTERS, probe))
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _assert_forbidden(response: httpx.Response) -> None:
    """A 403 has the fixed body: no layer, no tenant, no user data."""
    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}
    assert "WWW-Authenticate" not in response.headers


def _auth(token: str, tenant_id: uuid.UUID | str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if tenant_id is not None:
        headers[TENANT_HEADER] = str(tenant_id)
    return headers


async def _single(seed: Seeder, firm_role: str | None = None) -> Person:
    tenant_id = await seed.firm()
    user_id, subject = await seed.user()
    await seed.membership(tenant_id, user_id, firm_role)
    return Person(user_id, subject, tenant_id)


# --- AC-1: one membership resolves the tenant ----------------------------------------------------


async def test_ac1_one_membership_resolves_to_that_tenant(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed)
    response = await client.get("/probe/context", headers=_auth(idp.token(who.subject)))
    assert response.status_code == 200
    seen = response.json()
    assert seen["tenant_id"] == str(who.tenant_id)
    assert seen["actor_kind"] == "human"
    assert seen["actor_id"] == str(who.user_id)
    assert seen["user_id"] == str(who.user_id)


async def test_ac1_one_membership_with_the_matching_header_also_resolves(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed)
    response = await client.get(
        "/probe/context", headers=_auth(idp.token(who.subject), who.tenant_id)
    )
    assert response.status_code == 200
    assert response.json()["tenant_id"] == str(who.tenant_id)


@pytest.mark.parametrize("firm_role", [None, "firm_admin", "practice_leader", "quality_partner"])
async def test_ac1_firm_role_comes_from_the_membership(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder, firm_role: str | None
) -> None:
    who = await _single(seed, firm_role)
    response = await client.get("/probe/context", headers=_auth(idp.token(who.subject)))
    assert response.json()["firm_role"] == firm_role


async def test_ac1_role_claims_in_the_token_never_grant_a_firm_role(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, None)
    tokens = [
        idp.token(who.subject, role="firm_admin"),
        idp.token(who.subject, roles=["firm_admin"]),
        idp.token(who.subject, org_role="firm_admin"),
    ]
    for token in tokens:
        response = await client.get("/probe/context", headers=_auth(token))
        assert response.json()["firm_role"] is None


async def test_ac1_a_token_role_does_not_override_the_membership_role(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, "quality_partner")
    token = idp.token(who.subject, role="firm_admin")
    response = await client.get("/probe/context", headers=_auth(token))
    assert response.json()["firm_role"] == "quality_partner"


async def test_ac1_mfa_time_comes_from_the_token(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed)
    plain = await client.get("/probe/context", headers=_auth(idp.token(who.subject)))
    mfa = await client.get("/probe/context", headers=_auth(idp.token(who.subject, mfa=True)))
    assert plain.json()["mfa_at"] is None
    assert mfa.json()["mfa_at"] is not None


async def test_ac1_an_authorised_route_works_end_to_end(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, "firm_admin")
    response = await client.get("/probe/create", headers=_auth(idp.token(who.subject)))
    assert response.status_code == 200
    assert response.json() == {"ok": True}


# --- several memberships: the header must name one -----------------------------------------------


async def _two_firms(seed: Seeder) -> tuple[str, uuid.UUID, uuid.UUID]:
    first, second = (
        await seed.firm("Alpha " + uuid.uuid4().hex[:6]),
        await seed.firm("Beta " + uuid.uuid4().hex[:6]),
    )
    user_id, subject = await seed.user()
    await seed.membership(first, user_id, "firm_admin")
    await seed.membership(second, user_id, None)
    return subject, first, second


async def test_ac1_several_memberships_the_header_picks_the_tenant(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    subject, first, second = await _two_firms(seed)
    token = idp.token(subject)
    for tenant_id, role in ((first, "firm_admin"), (second, None)):
        response = await client.get("/probe/context", headers=_auth(token, tenant_id))
        assert response.status_code == 200
        assert response.json()["tenant_id"] == str(tenant_id)
        assert response.json()["firm_role"] == role


async def test_ac1_several_memberships_without_the_header_is_403(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    subject, _first, _second = await _two_firms(seed)
    response = await client.get("/probe/context", headers=_auth(idp.token(subject)))
    _assert_forbidden(response)


@pytest.mark.parametrize(
    "value", ["not-a-uuid", "", " ", "12345", "00000000-0000-0000-0000-00000000000g"]
)
async def test_ac1_several_memberships_with_a_malformed_header_is_403(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder, value: str
) -> None:
    subject, _first, _second = await _two_firms(seed)
    response = await client.get("/probe/context", headers=_auth(idp.token(subject), value))
    _assert_forbidden(response)


async def test_ac1_a_header_naming_a_firm_the_user_does_not_belong_to_is_403(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    subject, _first, _second = await _two_firms(seed)
    stranger = await seed.firm()
    response = await client.get("/probe/context", headers=_auth(idp.token(subject), stranger))
    _assert_forbidden(response)


async def test_ac1_a_header_naming_a_tenant_that_does_not_exist_is_403(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    subject, _first, _second = await _two_firms(seed)
    response = await client.get("/probe/context", headers=_auth(idp.token(subject), uuid.uuid4()))
    _assert_forbidden(response)


async def test_ac1_a_header_naming_a_revoked_membership_is_403(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    tenant_a, tenant_b = await seed.firm(), await seed.firm()
    user_id, subject = await seed.user()
    await seed.membership(tenant_a, user_id)
    await seed.membership(tenant_b, user_id)
    await seed.revoke(tenant_b, user_id)
    token = idp.token(subject)
    _assert_forbidden(await client.get("/probe/context", headers=_auth(token, tenant_b)))
    assert (await client.get("/probe/context", headers=_auth(token, tenant_a))).status_code == 200


async def test_ac1_a_user_in_another_firm_cannot_borrow_this_firms_tenant_id(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    victim = await _single(seed, "firm_admin")
    other_firm = await seed.firm()
    other_user, other_subject = await seed.user()
    await seed.membership(other_firm, other_user)
    await seed.membership(await seed.firm(), other_user)
    response = await client.get(
        "/probe/context", headers=_auth(idp.token(other_subject), victim.tenant_id)
    )
    _assert_forbidden(response)


# --- AC-2: no membership, no access --------------------------------------------------------------


async def test_ac2_a_user_without_memberships_is_403_on_an_action_route(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    _user_id, subject = await seed.user()
    response = await client.get("/probe/context", headers=_auth(idp.token(subject)))
    _assert_forbidden(response)


async def test_ac2_a_user_with_only_revoked_memberships_is_403(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    tenant_id = await seed.firm()
    user_id, subject = await seed.user()
    await seed.membership(tenant_id, user_id, revoked=True)
    response = await client.get("/probe/context", headers=_auth(idp.token(subject), tenant_id))
    _assert_forbidden(response)
    response = await client.get("/probe/context", headers=_auth(idp.token(subject)))
    _assert_forbidden(response)


async def test_ac2_a_valid_token_for_an_unknown_user_is_403_not_401(
    client: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    response = await client.get(
        "/probe/context", headers=_auth(idp.token("nobody-" + uuid.uuid4().hex))
    )
    _assert_forbidden(response)
    assert "WWW-Authenticate" not in response.headers


async def test_ac2_an_unknown_user_is_403_on_me(
    client: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    response = await client.get("/v1/me", headers=_auth(idp.token("nobody-" + uuid.uuid4().hex)))
    _assert_forbidden(response)


async def test_ac2_a_user_issued_by_another_issuer_is_unknown(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed)
    other = FakeIdentityProvider(issuer="https://other-idp.example.test")
    configure_verifier(other.verifier())
    response = await client.get("/probe/context", headers=_auth(other.token(who.subject)))
    _assert_forbidden(response)


# --- AC-3: revocation applies to the next request ------------------------------------------------


async def test_ac3_revoking_a_membership_denies_the_next_request_with_the_same_token(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, "firm_admin")
    headers = _auth(idp.token(who.subject))
    assert (await client.get("/probe/context", headers=headers)).status_code == 200
    await seed.revoke(who.tenant_id, who.user_id)
    _assert_forbidden(await client.get("/probe/context", headers=headers))


async def test_ac3_nothing_is_cached_reactivation_applies_to_the_next_request(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed)
    headers = _auth(idp.token(who.subject))
    await seed.revoke(who.tenant_id, who.user_id)
    _assert_forbidden(await client.get("/probe/context", headers=headers))
    await seed.reactivate(who.tenant_id, who.user_id)
    assert (await client.get("/probe/context", headers=headers)).status_code == 200


async def test_ac1_a_changed_firm_role_applies_to_the_next_request(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, "firm_admin")
    headers = _auth(idp.token(who.subject))
    assert (await client.get("/probe/context", headers=headers)).json()[
        "firm_role"
    ] == "firm_admin"
    await seed.set_firm_role(who.tenant_id, who.user_id, None)
    assert (await client.get("/probe/context", headers=headers)).json()["firm_role"] is None
    await seed.set_firm_role(who.tenant_id, who.user_id, "quality_partner")
    assert (await client.get("/probe/context", headers=headers)).json()[
        "firm_role"
    ] == "quality_partner"


async def test_ac3_revoking_one_of_two_memberships_removes_only_that_tenant(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    subject, first, second = await _two_firms(seed)
    token = idp.token(subject)
    user_id = cast(
        uuid.UUID, await seed.value("SELECT id FROM users WHERE idp_subject = $1", subject)
    )
    assert (await client.get("/probe/context", headers=_auth(token, first))).status_code == 200
    await seed.revoke(first, user_id)
    _assert_forbidden(await client.get("/probe/context", headers=_auth(token, first)))
    assert (await client.get("/probe/context", headers=_auth(token, second))).status_code == 200


async def test_ac3_a_revoked_user_still_gets_me_but_without_the_revoked_firm(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed)
    headers = _auth(idp.token(who.subject))
    await seed.revoke(who.tenant_id, who.user_id)
    response = await client.get("/v1/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["memberships"] == []


# --- /v1/me --------------------------------------------------------------------------------------

ME_KEYS = {"user_id", "email", "display_name", "memberships", "active_tenant_id"}


async def test_ac1_me_with_one_membership_names_the_active_tenant(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, "firm_admin")
    response = await client.get("/v1/me", headers=_auth(idp.token(who.subject)))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == ME_KEYS
    assert body["user_id"] == str(who.user_id)
    assert body["email"] == f"{who.subject}@example.test"
    assert body["display_name"] == f"User {who.subject[-6:]}"
    assert body["active_tenant_id"] == str(who.tenant_id)
    [membership] = body["memberships"]
    assert set(membership) == {"tenant_id", "firm_name", "firm_role"}
    assert membership["tenant_id"] == str(who.tenant_id)
    assert membership["firm_role"] == "firm_admin"
    firm_name = await seed.value("SELECT name FROM firms WHERE tenant_id = $1", who.tenant_id)
    assert membership["firm_name"] == firm_name


async def test_ac1_me_with_no_firm_role_shows_null(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, None)
    body = (await client.get("/v1/me", headers=_auth(idp.token(who.subject)))).json()
    assert body["memberships"][0]["firm_role"] is None


async def test_ac1_me_with_several_memberships_has_no_active_tenant_and_orders_by_firm_name(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    suffix = uuid.uuid4().hex[:6]
    user_id, subject = await seed.user()
    names = [f"Charlie {suffix}", f"Alpha {suffix}", f"Bravo {suffix}"]
    for name in names:  # inserted out of order on purpose
        await seed.membership(await seed.firm(name), user_id)
    body = (await client.get("/v1/me", headers=_auth(idp.token(subject)))).json()
    assert body["active_tenant_id"] is None
    assert [m["firm_name"] for m in body["memberships"]] == sorted(names)


async def test_ac2_me_with_no_memberships_works_and_is_empty(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    user_id, subject = await seed.user()
    response = await client.get("/v1/me", headers=_auth(idp.token(subject)))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == ME_KEYS
    assert body["memberships"] == []
    assert body["active_tenant_id"] is None
    assert body["user_id"] == str(user_id)


async def test_ac3_me_lists_active_memberships_only(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    active, gone = await seed.firm(), await seed.firm()
    user_id, subject = await seed.user()
    await seed.membership(active, user_id)
    await seed.membership(gone, user_id, revoked=True)
    body = (await client.get("/v1/me", headers=_auth(idp.token(subject)))).json()
    assert [m["tenant_id"] for m in body["memberships"]] == [str(active)]
    assert body["active_tenant_id"] == str(active)


@pytest.mark.parametrize("header", [None, "not-a-uuid", str(uuid.uuid4())])
async def test_ac1_me_never_needs_or_uses_the_tenant_header(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder, header: str | None
) -> None:
    subject, _first, _second = await _two_firms(seed)
    response = await client.get("/v1/me", headers=_auth(idp.token(subject), header))
    assert response.status_code == 200
    assert len(response.json()["memberships"]) == 2


async def test_ac1_me_does_not_expose_other_users_or_firms(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    mine = await _single(seed)
    theirs = await _single(seed)
    body = (await client.get("/v1/me", headers=_auth(idp.token(mine.subject)))).json()
    assert str(theirs.tenant_id) not in str(body)
    assert str(theirs.user_id) not in str(body)


# --- 401 -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/v1/me", "/probe/context"])
async def test_ac1_no_token_is_401_with_www_authenticate(
    client: httpx.AsyncClient, path: str
) -> None:
    response = await client.get(path)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("path", ["/v1/me", "/probe/context"])
async def test_ac1_an_expired_token_is_401(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder, path: str
) -> None:
    who = await _single(seed)
    response = await client.get(path, headers=_auth(idp.token(who.subject, expires_in=-300)))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_ac1_a_token_signed_by_another_provider_is_401_even_for_a_known_user(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed)
    forged = FakeIdentityProvider().token(who.subject)
    response = await client.get("/v1/me", headers=_auth(forged))
    assert response.status_code == 401


async def test_ac1_a_token_older_than_an_hour_lifetime_is_401(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed)
    now = int(time.time())
    response = await client.get(
        "/v1/me", headers=_auth(idp.token(who.subject, iat=now, exp=now + 7200))
    )
    assert response.status_code == 401


# --- the guard and the 403 body, with a real context ---------------------------------------------


async def test_ac20_a_route_that_does_not_check_its_action_is_a_500(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, "firm_admin")
    response = await client.get("/probe/unchecked", headers=_auth(idp.token(who.subject)))
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}


async def test_ac20_forbidden_is_403_without_the_layer(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, None)  # no firm role, no engagement: relationship layer
    response = await client.get("/probe/update", headers=_auth(idp.token(who.subject)))
    _assert_forbidden(response)
    assert "relationship" not in response.text


async def test_ac20_a_role_denial_is_the_same_403(
    client: httpx.AsyncClient, idp: FakeIdentityProvider, seed: Seeder
) -> None:
    who = await _single(seed, "firm_admin")  # firm_admin may not engagement.update
    response = await client.get("/probe/update", headers=_auth(idp.token(who.subject)))
    _assert_forbidden(response)


# --- authorise against the real engagement_members (AC-6, AC-8) ----------------------------------


def _ctx(person: Person, firm_role: FirmRole | None = None) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(person.tenant_id, "human", str(person.user_id)),
        user_id=person.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _denied(ctx: AuthContext, action: str, resource: Resource) -> str:
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, action, resource, reason="documented")
    return raised.value.layer


async def test_ac6_firm_admin_without_engagement_membership_reads_metadata_not_content(
    seed: Seeder,
) -> None:
    who = await _single(seed, "firm_admin")
    ctx = _ctx(who, "firm_admin")
    resource = Resource.engagement(who.tenant_id, uuid.uuid4(), archived=False)
    await authorise(ctx, "engagement.read_metadata", resource)
    for action in ("engagement.read", "request_item.read", "evidence.read"):
        assert await _denied(ctx, action, resource) == "role"


async def test_ac6_firm_admin_who_is_also_an_engagement_member_reads_the_content(
    seed: Seeder,
) -> None:
    who = await _single(seed, "firm_admin")
    engagement_id = uuid.uuid4()
    await seed.engagement_member(who.tenant_id, engagement_id, who.user_id, "staff")
    ctx = _ctx(who, "firm_admin")
    resource = Resource.engagement(who.tenant_id, engagement_id, archived=False)
    for action in ("engagement.read", "request_item.read", "evidence.read"):
        await authorise(ctx, action, resource)


async def test_ac8_a_reviewer_cannot_create_a_request_item(seed: Seeder) -> None:
    who = await _single(seed)
    engagement_id = uuid.uuid4()
    await seed.engagement_member(who.tenant_id, engagement_id, who.user_id, "reviewer")
    resource = Resource.engagement(who.tenant_id, engagement_id, archived=False)
    assert await _denied(_ctx(who), "request_item.create", resource) == "role"


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior"])
async def test_ac8_roles_that_may_create_a_request_item_can(seed: Seeder, role: str) -> None:
    who = await _single(seed)
    engagement_id = uuid.uuid4()
    await seed.engagement_member(who.tenant_id, engagement_id, who.user_id, role)
    resource = Resource.engagement(who.tenant_id, engagement_id, archived=False)
    await authorise(_ctx(who), "request_item.create", resource)


async def test_ac20_an_engagement_role_applies_to_its_own_engagement_only(seed: Seeder) -> None:
    who = await _single(seed)
    mine, other = uuid.uuid4(), uuid.uuid4()
    await seed.engagement_member(who.tenant_id, mine, who.user_id, "manager")
    ctx = _ctx(who)
    own = Resource.engagement(who.tenant_id, mine, archived=False)
    await authorise(ctx, "request_item.create", own)
    foreign = Resource.engagement(who.tenant_id, other, archived=False)
    assert await _denied(ctx, "request_item.create", foreign) == "relationship"


async def test_ac20_another_users_engagement_role_is_not_mine(seed: Seeder) -> None:
    me = await _single(seed)
    engagement_id = uuid.uuid4()
    colleague, _subject = await seed.user()
    await seed.membership(me.tenant_id, colleague)
    await seed.engagement_member(me.tenant_id, engagement_id, colleague, "manager")
    resource = Resource.engagement(me.tenant_id, engagement_id, archived=False)
    assert await _denied(_ctx(me), "request_item.create", resource) == "relationship"


async def test_ac20_an_engagement_role_in_another_firm_does_not_count(seed: Seeder) -> None:
    mine, other_tenant = await seed.firm(), await seed.firm()
    user_id, subject = await seed.user()
    await seed.membership(mine, user_id)
    await seed.membership(other_tenant, user_id)
    engagement_id = uuid.uuid4()
    await seed.engagement_member(other_tenant, engagement_id, user_id, "manager")
    person = Person(user_id, subject, mine)
    resource = Resource.engagement(mine, engagement_id, archived=False)
    assert await _denied(_ctx(person), "request_item.create", resource) == "relationship"


async def test_ac20_an_archived_engagement_denies_a_write_even_for_a_manager(seed: Seeder) -> None:
    who = await _single(seed)
    engagement_id = uuid.uuid4()
    await seed.engagement_member(who.tenant_id, engagement_id, who.user_id, "manager")
    resource = Resource.engagement(who.tenant_id, engagement_id, archived=True)
    assert await _denied(_ctx(who), "request_item.create", resource) == "attribute"
    await authorise(_ctx(who), "request_item.read", resource)


async def test_ac20_a_resource_of_another_tenant_is_denied_at_tenancy(seed: Seeder) -> None:
    who = await _single(seed, "firm_admin")
    foreign = Resource.firm(await seed.firm())
    assert await _denied(_ctx(who, "firm_admin"), "engagement.create", foreign) == "tenancy"


# --- visible against a probe tenant table --------------------------------------------------------

METADATA = MetaData()
PROBE = Table(
    "visible_probe",
    METADATA,
    Column("id", Uuid(), primary_key=True),
    Column("tenant_id", Uuid(), nullable=False),
    Column("engagement_id", Uuid(), nullable=False),
    Column("body", Text()),
)


class RecordingOp:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)


@pytest.fixture
async def probe_table(migrated_db: Migrated) -> AsyncIterator[None]:
    engine = create_async_engine(migrated_db.owner_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(METADATA.drop_all)
        await conn.run_sync(METADATA.create_all)
        op = RecordingOp()
        tenant_table(cast(Operations, op), "visible_probe")
        for statement in op.statements:
            await conn.exec_driver_sql(statement)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(METADATA.drop_all)
    await engine.dispose()


async def _row(seed: Seeder, tenant_id: uuid.UUID, engagement_id: uuid.UUID, body: str) -> None:
    await seed.run(
        "INSERT INTO visible_probe (id, tenant_id, engagement_id, body) VALUES ($1, $2, $3, $4)",
        uuid.uuid4(),
        tenant_id,
        engagement_id,
        body,
    )


async def _visible_bodies(ctx: AuthContext, action: str) -> list[str]:
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(PROBE.c.body).where(visible(ctx, action, PROBE.c.engagement_id))
        )
        return sorted(rows.scalars().all())


@pytest.mark.usefixtures("probe_table")
async def test_ac6_visible_for_a_firm_role_allow_is_every_row_in_the_tenant_only(
    seed: Seeder,
) -> None:
    who = await _single(seed, "firm_admin")
    foreign = await seed.firm()
    await _row(seed, who.tenant_id, uuid.uuid4(), "a")
    await _row(seed, who.tenant_id, uuid.uuid4(), "b")
    await _row(seed, foreign, uuid.uuid4(), "foreign")
    assert await _visible_bodies(_ctx(who, "firm_admin"), "engagement.read_metadata") == ["a", "b"]


@pytest.mark.usefixtures("probe_table")
async def test_ac6_visible_content_for_a_firm_admin_is_only_their_engagements(
    seed: Seeder,
) -> None:
    who = await _single(seed, "firm_admin")
    mine = uuid.uuid4()
    await seed.engagement_member(who.tenant_id, mine, who.user_id, "staff")
    await _row(seed, who.tenant_id, mine, "mine")
    await _row(seed, who.tenant_id, uuid.uuid4(), "not mine")
    assert await _visible_bodies(_ctx(who, "firm_admin"), "engagement.read") == ["mine"]


@pytest.mark.usefixtures("probe_table")
async def test_ac20_visible_for_a_member_is_their_engagements(seed: Seeder) -> None:
    who = await _single(seed)
    first, second, third = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await seed.engagement_member(who.tenant_id, first, who.user_id, "manager")
    await seed.engagement_member(who.tenant_id, second, who.user_id, "reviewer")
    for body, engagement_id in (("first", first), ("second", second), ("third", third)):
        await _row(seed, who.tenant_id, engagement_id, body)
    assert await _visible_bodies(_ctx(who), "engagement.read") == ["first", "second"]


@pytest.mark.usefixtures("probe_table")
async def test_ac20_visible_counts_only_roles_the_matrix_allows_for_the_action(
    seed: Seeder,
) -> None:
    who = await _single(seed)
    as_partner, as_manager, as_senior = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await seed.engagement_member(who.tenant_id, as_partner, who.user_id, "engagement_partner")
    await seed.engagement_member(who.tenant_id, as_manager, who.user_id, "manager")
    await seed.engagement_member(who.tenant_id, as_senior, who.user_id, "senior")
    for body, engagement_id in (("p", as_partner), ("m", as_manager), ("s", as_senior)):
        await _row(seed, who.tenant_id, engagement_id, body)
    # connection.read_log: allowed for engagement_partner and manager, not senior.
    assert await _visible_bodies(_ctx(who), "connection.read_log") == ["m", "p"]


@pytest.mark.usefixtures("probe_table")
async def test_ac20_visible_for_a_user_with_no_engagements_is_nothing(seed: Seeder) -> None:
    who = await _single(seed)
    await _row(seed, who.tenant_id, uuid.uuid4(), "x")
    assert await _visible_bodies(_ctx(who), "engagement.read") == []


@pytest.mark.usefixtures("probe_table")
async def test_ac20_visible_ignores_other_users_memberships(seed: Seeder) -> None:
    who = await _single(seed)
    colleague, _subject = await seed.user()
    await seed.membership(who.tenant_id, colleague)
    engagement_id = uuid.uuid4()
    await seed.engagement_member(who.tenant_id, engagement_id, colleague, "manager")
    await _row(seed, who.tenant_id, engagement_id, "theirs")
    assert await _visible_bodies(_ctx(who), "engagement.read") == []


@pytest.mark.usefixtures("probe_table")
async def test_ac20_visible_for_an_in_scope_firm_role_falls_back_to_membership(
    seed: Seeder,
) -> None:
    who = await _single(seed, "practice_leader")  # in_scope is not modelled: not an allow
    mine = uuid.uuid4()
    await seed.engagement_member(who.tenant_id, mine, who.user_id, "senior")
    await _row(seed, who.tenant_id, mine, "mine")
    await _row(seed, who.tenant_id, uuid.uuid4(), "other")
    assert await _visible_bodies(_ctx(who, "practice_leader"), "engagement.read") == ["mine"]


@pytest.mark.usefixtures("probe_table")
async def test_ac20_visible_never_shows_another_tenants_rows_for_the_same_engagement_id(
    seed: Seeder,
) -> None:
    mine, other_tenant = await seed.firm(), await seed.firm()
    user_id, subject = await seed.user()
    await seed.membership(mine, user_id)
    await seed.membership(other_tenant, user_id)
    engagement_id = uuid.uuid4()
    await seed.engagement_member(mine, engagement_id, user_id, "manager")
    await seed.engagement_member(other_tenant, engagement_id, user_id, "manager")
    await _row(seed, mine, engagement_id, "mine")
    await _row(seed, other_tenant, engagement_id, "theirs")
    ctx = _ctx(Person(user_id, subject, mine))
    assert await _visible_bodies(ctx, "engagement.read") == ["mine"]


# --- tenant isolation of the identity tables for abacus_app --------------------------------------

COUNTS = {
    "memberships": "SELECT count(*) FROM memberships WHERE tenant_id = :v",
    "engagement_members": "SELECT count(*) FROM engagement_members WHERE tenant_id = :v",
    "firms": "SELECT count(*) FROM firms WHERE tenant_id = :v",
}


async def _app_count(ctx: TenantContext, table: str, value: uuid.UUID) -> int:
    async with tenant_session(ctx) as session:
        return cast(int, (await session.execute(text(COUNTS[table]), {"v": value})).scalar_one())


@pytest.mark.parametrize("table", ["memberships", "engagement_members", "firms"])
async def test_ac20_app_sees_only_its_own_tenants_rows(seed: Seeder, table: str) -> None:
    a = await _single(seed)
    b = await _single(seed)
    await seed.engagement_member(a.tenant_id, uuid.uuid4(), a.user_id, "staff")
    await seed.engagement_member(b.tenant_id, uuid.uuid4(), b.user_id, "staff")
    ctx_a = TenantContext(a.tenant_id, "human", str(a.user_id))
    assert await _app_count(ctx_a, table, a.tenant_id) == 1
    assert await _app_count(ctx_a, table, b.tenant_id) == 0


async def test_ac20_app_without_a_tenant_sees_no_identity_rows(
    seed: Seeder, migrated_db: Migrated
) -> None:
    await _single(seed)
    conn = await asyncpg.connect(_plain(migrated_db.app_url))
    try:
        assert await conn.fetchval("SELECT count(*) FROM memberships") == 0
        assert await conn.fetchval("SELECT count(*) FROM engagement_members") == 0
        assert await conn.fetchval("SELECT count(*) FROM firms") == 0
    finally:
        await conn.close()


@pytest.mark.parametrize("table", ["firms", "memberships", "engagement_members"])
async def test_ac20_app_may_only_select_the_tenant_identity_tables(
    seed: Seeder, table: str
) -> None:
    others = ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "TRIGGER", "REFERENCES")
    assert await seed.value(
        "SELECT has_table_privilege('abacus_app', $1, 'SELECT')", f"public.{table}"
    )
    for privilege in others:
        granted = await seed.value(
            "SELECT has_table_privilege('abacus_app', $1, $2)", f"public.{table}", privilege
        )
        assert granted is False, privilege


async def test_ac20_app_cannot_write_the_tenant_identity_tables_even_inside_its_tenant(
    seed: Seeder,
) -> None:
    who = await _single(seed)
    ctx = TenantContext(who.tenant_id, "human", str(who.user_id))
    for statement in (
        "UPDATE memberships SET firm_role = 'firm_admin'",
        "DELETE FROM memberships",
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "SELECT tenant_id, gen_random_uuid(), user_id, 'manager' FROM memberships",
        "UPDATE firms SET name = 'renamed'",
    ):
        with pytest.raises(DBAPIError):
            async with tenant_session(ctx) as session:
                await session.execute(text(statement))


@pytest.mark.parametrize("table", ["firms", "memberships", "engagement_members"])
async def test_ac20_tenant_identity_tables_have_forced_row_level_security(
    seed: Seeder, table: str
) -> None:
    row = (
        await seed.rows(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = $1 AND relnamespace = 'public'::regnamespace",
            table,
        )
    )[0]
    assert (row["relrowsecurity"], row["relforcerowsecurity"]) == (True, True)


# --- schema shape and constraints ----------------------------------------------------------------


async def _columns(seed: Seeder, table: str) -> set[str]:
    rows = await seed.rows(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = $1",
        table,
    )
    return {str(r["column_name"]) for r in rows}


async def test_ac20_users_is_global_with_no_tenant_id(seed: Seeder) -> None:
    columns = await _columns(seed, "users")
    assert "tenant_id" not in columns
    assert {"id", "idp_issuer", "idp_subject", "email", "display_name"} <= columns


async def test_ac20_the_identity_tables_have_the_contracted_columns(seed: Seeder) -> None:
    assert {"tenant_id", "name"} <= await _columns(seed, "firms")
    assert {"tenant_id", "id", "user_id", "firm_role", "status", "revoked_at"} <= await _columns(
        seed, "memberships"
    )
    assert {"tenant_id", "engagement_id", "user_id", "role"} <= await _columns(
        seed, "engagement_members"
    )


async def test_ac20_a_user_is_unique_per_issuer_and_subject(seed: Seeder) -> None:
    _user_id, subject = await seed.user()
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.user(subject)


async def test_ac20_one_membership_per_user_per_firm(seed: Seeder) -> None:
    who = await _single(seed)
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.membership(who.tenant_id, who.user_id)


@pytest.mark.parametrize("firm_role", ["engagement_partner", "reviewer", "superuser", ""])
async def test_ac20_firm_role_must_be_a_firm_role(seed: Seeder, firm_role: str) -> None:
    tenant_id = await seed.firm()
    user_id, _subject = await seed.user()
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.membership(tenant_id, user_id, firm_role)


async def test_ac20_membership_status_must_be_active_or_revoked(seed: Seeder) -> None:
    tenant_id = await seed.firm()
    user_id, _subject = await seed.user()
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'pending')",
            tenant_id,
            user_id,
        )


async def test_ac20_revoked_if_and_only_if_revoked_at_is_set(seed: Seeder) -> None:
    tenant_id = await seed.firm()
    user_id, _subject = await seed.user()
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'revoked')",
            tenant_id,
            user_id,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status, revoked_at) "
            "VALUES ($1, $2, 'active', now())",
            tenant_id,
            user_id,
        )


@pytest.mark.parametrize("role", ["firm_admin", "client_admin", "agent", ""])
async def test_ac20_engagement_role_must_be_an_engagement_role(seed: Seeder, role: str) -> None:
    who = await _single(seed)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.engagement_member(who.tenant_id, uuid.uuid4(), who.user_id, role)


async def test_ac20_an_engagement_member_must_be_a_member_of_the_same_firm(seed: Seeder) -> None:
    who = await _single(seed)
    elsewhere = await seed.firm()
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.engagement_member(elsewhere, uuid.uuid4(), who.user_id, "manager")


# --- abacus_app has no privileges on users -------------------------------------------------------

PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


async def test_ac20_app_has_no_privilege_on_users_at_any_level(seed: Seeder) -> None:
    for privilege in PRIVILEGES:
        assert (
            await seed.value(
                "SELECT has_table_privilege('abacus_app', 'public.users', $1)", privilege
            )
            is False
        ), privilege
    for column_name in await _columns(seed, "users"):
        for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
            assert (
                await seed.value(
                    "SELECT has_column_privilege('abacus_app', 'public.users', $1, $2)",
                    column_name,
                    privilege,
                )
                is False
            ), (column_name, privilege)


async def test_ac20_app_cannot_read_users(seed: Seeder, migrated_db: Migrated) -> None:
    await seed.user()
    conn = await asyncpg.connect(_plain(migrated_db.app_url))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch("SELECT * FROM users")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('a', 'b', 'c@d.test', 'e')"
            )
    finally:
        await conn.close()


async def test_ac20_app_cannot_read_users_through_a_tenant_session(seed: Seeder) -> None:
    who = await _single(seed)
    with pytest.raises(DBAPIError):
        async with tenant_session(TenantContext(who.tenant_id, "human", "x")) as session:
            await session.execute(text("SELECT id FROM users"))


# --- abacus_identity: reads exactly what the contract lists, and cannot write --------------------

IDENTITY_SELECT = (
    {
        ("users", name)
        for name in ("id", "idp_issuer", "idp_subject", "email", "display_name", "created_at")
    }
    | {("memberships", name) for name in ("tenant_id", "id", "user_id", "firm_role", "status")}
    | {("firms", "tenant_id"), ("firms", "name")}
)


async def test_ac20_identity_role_privileges_are_exactly_the_contracted_reads(
    seed: Seeder,
) -> None:
    columns = await seed.rows(
        "SELECT c.relname, a.attname FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid "
        "WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p') "
        "AND a.attnum > 0 AND NOT a.attisdropped"
    )
    readable: set[tuple[str, str]] = set()
    for row in columns:
        table, name = str(row["relname"]), str(row["attname"])
        qualified = f"public.{table}"
        if await seed.value(
            "SELECT has_column_privilege('abacus_identity', $1, $2, 'SELECT')", qualified, name
        ):
            readable.add((table, name))
        for privilege in ("INSERT", "UPDATE", "REFERENCES"):
            granted = await seed.value(
                "SELECT has_column_privilege('abacus_identity', $1, $2, $3)",
                qualified,
                name,
                privilege,
            )
            assert granted is False, (table, name, privilege)
    users_columns = {name for table, name in readable if table == "users"}
    assert {"id", "idp_issuer", "idp_subject", "email", "display_name"} <= users_columns
    assert {(t, n) for t, n in readable if t != "users"} == {
        (t, n) for t, n in IDENTITY_SELECT if t != "users"
    }
    assert users_columns == await _columns(seed, "users")


async def test_ac20_identity_role_has_no_table_level_write_privilege_anywhere(
    seed: Seeder,
) -> None:
    tables = [
        str(r["relname"])
        for r in await seed.rows(
            "SELECT relname FROM pg_class WHERE relnamespace = 'public'::regnamespace "
            "AND relkind IN ('r', 'p')"
        )
    ]
    assert {"users", "memberships", "firms", "engagement_members"} <= set(tables)
    for table in tables:
        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            granted = await seed.value(
                "SELECT has_table_privilege('abacus_identity', $1, $2)",
                f"public.{table}",
                privilege,
            )
            assert granted is False, (table, privilege)


async def test_ac20_identity_role_can_read_across_tenants_what_sign_in_needs(
    seed: Seeder, migrated_db: Migrated
) -> None:
    a, b = await _single(seed, "firm_admin"), await _single(seed)
    conn = await asyncpg.connect(_plain(migrated_db.identity_url))
    try:
        found = await conn.fetch(
            "SELECT tenant_id, user_id, firm_role, status FROM memberships "
            "WHERE user_id = ANY($1)",
            [a.user_id, b.user_id],
        )
        assert {r["tenant_id"] for r in found} == {a.tenant_id, b.tenant_id}
        names = await conn.fetch(
            "SELECT tenant_id, name FROM firms WHERE tenant_id = ANY($1)",
            [a.tenant_id, b.tenant_id],
        )
        assert len(names) == 2
        users = await conn.fetch("SELECT * FROM users WHERE id = ANY($1)", [a.user_id, b.user_id])
        assert len(users) == 2
    finally:
        await conn.close()


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT * FROM memberships",
        "SELECT created_at FROM memberships",
        "SELECT revoked_at FROM memberships",
        "SELECT created_at FROM firms",
        "SELECT * FROM firms",
        "SELECT * FROM engagement_members",
        "SELECT role FROM engagement_members",
        "SELECT * FROM audit_events",
        "SELECT * FROM outbox",
    ],
)
async def test_ac20_identity_role_cannot_read_beyond_its_grants(
    migrated_db: Migrated, statement: str
) -> None:
    conn = await asyncpg.connect(_plain(migrated_db.identity_url))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(statement)
    finally:
        await conn.close()


async def test_ac20_identity_role_is_read_only_by_default(migrated_db: Migrated) -> None:
    conn = await asyncpg.connect(_plain(migrated_db.identity_url))
    try:
        assert await conn.fetchval("SHOW default_transaction_read_only") == "on"
        assert await conn.fetchval("SELECT current_user") == "abacus_identity"
        with pytest.raises(asyncpg.ReadOnlySQLTransactionError):
            await conn.execute(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('a', 'b', 'c@d.test', 'e')"
            )
    finally:
        await conn.close()


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
        "VALUES ('a', 'b', 'c@d.test', 'e')",
        "UPDATE users SET email = 'x@y.test'",
        "DELETE FROM users",
        "UPDATE memberships SET firm_role = 'firm_admin'",
        "UPDATE memberships SET status = 'revoked'",
        "DELETE FROM memberships",
        "UPDATE firms SET name = 'x'",
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), 'manager')",
        "TRUNCATE users CASCADE",
    ],
)
async def test_ac20_identity_role_cannot_write_even_with_read_write_transactions(
    migrated_db: Migrated, statement: str
) -> None:
    conn = await asyncpg.connect(_plain(migrated_db.identity_url))
    try:
        await conn.execute("SET default_transaction_read_only = off")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(statement)
    finally:
        await conn.close()


async def test_ac20_identity_role_has_the_expected_attributes(seed: Seeder) -> None:
    [role] = await seed.rows(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls, rolcanlogin "
        "FROM pg_roles WHERE rolname = 'abacus_identity'"
    )
    assert role["rolbypassrls"] is True
    assert role["rolcanlogin"] is True
    assert (role["rolsuper"], role["rolcreatedb"], role["rolcreaterole"]) == (False, False, False)


# --- the production verifier path: no configure_verifier -----------------------------------------


@pytest.fixture
async def production_path(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[FakeIdentityProvider, httpx.AsyncClient]]:
    """The verifier is built from `ABACUS_IDENTITY_JWKS`, as outside tests."""
    provider = FakeIdentityProvider()
    monkeypatch.setenv("ABACUS_IDENTITY_JWKS", provider.jwks())
    settings.cache_clear()
    reset_verifier()
    transport = httpx.ASGITransport(app=create_app())
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield provider, http
    finally:
        reset_verifier()
        settings.cache_clear()


async def test_ac1_a_token_verified_against_the_jwks_setting_signs_in(
    production_path: tuple[FakeIdentityProvider, httpx.AsyncClient], seed: Seeder
) -> None:
    provider, http = production_path
    who = await _single(seed)
    response = await http.get("/v1/me", headers=_auth(provider.token(who.subject)))
    assert response.status_code == 200
    assert response.json()["user_id"] == str(who.user_id)


async def test_ac1_a_token_from_another_key_is_401_on_the_production_path(
    production_path: tuple[FakeIdentityProvider, httpx.AsyncClient], seed: Seeder
) -> None:
    _provider, http = production_path
    who = await _single(seed)
    response = await http.get("/v1/me", headers=_auth(FakeIdentityProvider().token(who.subject)))
    assert response.status_code == 401


async def test_ac1_the_default_empty_jwks_verifies_nothing_so_every_token_is_401(
    monkeypatch: pytest.MonkeyPatch, seed: Seeder
) -> None:
    monkeypatch.delenv("ABACUS_IDENTITY_JWKS", raising=False)
    settings.cache_clear()
    reset_verifier()
    who = await _single(seed)
    transport = httpx.ASGITransport(app=create_app())
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.get(
                "/v1/me", headers=_auth(FakeIdentityProvider().token(who.subject))
            )
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
    finally:
        reset_verifier()
        settings.cache_clear()


# --- the identity engine's own connection --------------------------------------------------------


async def test_ac20_the_identity_engine_connects_read_only_with_a_5s_statement_timeout() -> None:
    async with identity_engine().connect() as conn:
        user = (await conn.execute(text("SELECT current_user"))).scalar_one()
        read_only = (await conn.execute(text("SHOW default_transaction_read_only"))).scalar_one()
        timeout = (await conn.execute(text("SHOW statement_timeout"))).scalar_one()
        in_read_only = (await conn.execute(text("SHOW transaction_read_only"))).scalar_one()
    assert user == "abacus_identity"
    assert read_only == "on"
    assert in_read_only == "on"
    assert timeout == "5s"


# --- visible agrees with authorise for every role and read action --------------------------------

READ_ACTIONS = sorted(
    action
    for action in cast(
        dict[str, dict[str, str]],
        cast(dict[str, object], yaml.safe_load(pm.SOURCE.read_text()))["actions"],
    )
    if action.split(".", 1)[1] in {"read", "read_metadata", "read_log"}
)
FIRM_ROLES: tuple[FirmRole | None, ...] = (
    None,
    "firm_admin",
    "practice_leader",
    "quality_partner",
)
ENGAGEMENT_ROLES: tuple[str | None, ...] = (
    None,
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
)


@pytest.mark.usefixtures("probe_table")
@pytest.mark.parametrize("action", READ_ACTIONS)
async def test_ac20_visible_agrees_with_authorise_for_every_role_combination(
    seed: Seeder, action: str
) -> None:
    tenant_id = await seed.firm()
    cases: list[tuple[FirmRole | None, str | None, AuthContext, uuid.UUID]] = []
    for firm_role in FIRM_ROLES:
        for engagement_role in ENGAGEMENT_ROLES:
            user_id, subject = await seed.user()
            await seed.membership(tenant_id, user_id, firm_role)
            engagement_id = uuid.uuid4()
            if engagement_role is not None:
                await seed.engagement_member(tenant_id, engagement_id, user_id, engagement_role)
            await _row(seed, tenant_id, engagement_id, "row")
            ctx = _ctx(Person(user_id, subject, tenant_id), firm_role)
            cases.append((firm_role, engagement_role, ctx, engagement_id))
    for firm_role, engagement_role, ctx, engagement_id in cases:
        try:
            await authorise(
                ctx, action, Resource.engagement(tenant_id, engagement_id, archived=False)
            )
            allowed = True
        except Forbidden:
            allowed = False
        async with tenant_session(ctx.tenant) as session:
            rows = await session.execute(
                select(PROBE.c.engagement_id).where(
                    visible(ctx, action, PROBE.c.engagement_id),
                    PROBE.c.engagement_id == engagement_id,
                )
            )
            shown = rows.scalars().all() != []
        assert shown == allowed, (action, firm_role, engagement_role)
