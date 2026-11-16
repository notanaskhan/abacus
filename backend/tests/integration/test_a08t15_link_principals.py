"""A-08-T15 (TASK-8083; ADR-146; SPEC-657 F6, F7) against Postgres: link principals.

Row acceptance: "Unknown, expired and revoked tokens are indistinguishable in status and timing,
and five wrong codes lock the link for 15 minutes." Resolution answers None for each (the route's
uniform view and padded floor are `test_a08t15_confirm_routes.py`'s).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.identity import link_principals as lp

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
EMAIL = "respondent@frontrangebank.example"


async def _live(tenant: TenantContext, subject: uuid.UUID) -> bool:
    return True


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[tuple[Seeder, uuid.UUID, uuid.UUID]]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    user = uuid.UUID(str(await seed.value(
        "INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES "
        "('https://probe.test', $1, $2, 'Raj Malhotra') RETURNING id", uuid.uuid4().hex, f"{uuid.uuid4().hex}@x.test",
    )))  # fmt: skip
    await seed.run("INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')", tenant, user)
    if "probe_purpose" not in lp.link_purposes():
        lp.register_link_purpose("probe_purpose", _live)
    yield seed, tenant, user
    await dispose_engine()


async def _mint(tenant: uuid.UUID, user: uuid.UUID, valid: timedelta = timedelta(days=30)) -> str:
    async with uow(TenantContext(tenant, "human", str(user))) as tx:
        return await lp.mint_link(
            tx, tenant_id=tenant, purpose="probe_purpose", subject_id=uuid.uuid4(), email=EMAIL,
            created_by=user, valid_for=valid,
        )  # fmt: skip


async def test_ac_unknown_expired_and_revoked_all_resolve_to_nothing(firm: tuple[Seeder, uuid.UUID, uuid.UUID]) -> None:
    seed, tenant, user = firm
    live = await _mint(tenant, user)
    assert await lp.resolve_link(live) is not None
    assert await lp.resolve_link("x" * 43) is None  # unknown
    expired = await _mint(tenant, user)
    await seed.run("UPDATE link_principals SET expires_at = created_at + interval '1 second' WHERE token_sha256 = $1", lp.sha256(expired))
    await seed.run("UPDATE link_principals SET created_at = created_at - interval '2 days', expires_at = expires_at - interval '2 days' WHERE token_sha256 = $1", lp.sha256(expired))
    assert await lp.resolve_link(expired) is None
    revoked = await _mint(tenant, user)
    await seed.run("UPDATE link_principals SET revoked_at = now() WHERE token_sha256 = $1", lp.sha256(revoked))
    assert await lp.resolve_link(revoked) is None


async def test_ac_five_wrong_codes_lock_the_link_for_15_minutes(firm: tuple[Seeder, uuid.UUID, uuid.UUID]) -> None:
    seed, tenant, user = firm
    token = await _mint(tenant, user)
    await lp.request_code(token, "someone.else@example.test")  # not the link's address
    assert await seed.value("SELECT count(*) FROM link_principal_challenges") == 0
    await lp.request_code(token, EMAIL.upper())  # the link's address, any case
    challenge = await seed.value("SELECT id FROM link_principal_challenges ORDER BY created_at DESC LIMIT 1")
    issued = await lp.issue_link_code(uuid.UUID(str(challenge)))
    assert issued is not None
    wrong = "000000" if issued.code != "000000" else "111111"
    for _ in range(lp.MAX_TRIES):
        assert await lp.verify_code(token, wrong) is None
    locked = await seed.value("SELECT locked_until - now() FROM link_principals WHERE token_sha256 = $1", lp.sha256(token))
    assert timedelta(minutes=14) < locked <= timedelta(minutes=15)  # type: ignore[operator]
    assert await lp.resolve_link(token) is None  # locked: the same as unknown
    assert await lp.verify_code(token, issued.code) is None  # even the right code, while locked


async def test_a_right_code_mints_the_page_credential(firm: tuple[Seeder, uuid.UUID, uuid.UUID]) -> None:
    seed, tenant, user = firm
    token = await _mint(tenant, user)
    await lp.request_code(token, EMAIL)
    challenge = await seed.value("SELECT id FROM link_principal_challenges ORDER BY created_at DESC LIMIT 1")
    issued = await lp.issue_link_code(uuid.UUID(str(challenge)))
    assert issued is not None
    verified = await lp.verify_code(token, issued.code)
    assert verified is not None
    found = await lp.credential_principal(verified.credential, verified.csrf)
    assert found is not None and found.tenant_id == tenant
    assert await lp.credential_principal(verified.credential, "wrong-csrf") is None
