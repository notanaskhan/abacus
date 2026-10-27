# ac-test-author: ayushkbhatia
"""Q-01-T43 (P-66; the platform-ops contract §3.7): the independent tests for platform controls
(Q-01-T37) and their history (Q-01-T36), from the contract only.

- Read-only refuses *every* mutating route in the route table: with `read_only` on for the
  platform, each non-GET route answers 503 `{"detail": "read_only"}`, except the sign-in,
  support-session and operational routes the contract exempts.
- Control history is insert-only: `platform_control_changes` takes no UPDATE or DELETE from the
  app role or the operator role, and the switch writes a new row each time.

The other T43 promises are covered elsewhere, or are infrastructure: AI pause before any provider
call (`ai_gateway`, DEC-338), keyops alone holding CreateKey (Terraform and the SCP, Q-01-T27 human
to-do), and the replica decrypt (needs KMS in two regions). Over HTTP through `create_app()` on the
migrated Postgres; the controls through the `set_platform_control` definer, as the operator.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from typing import Final, cast

import asyncpg
import pytest

from abacus.api import create_app
from abacus.kernel.controls import forget_controls
from abacus_tools.db_connect import connect

from .support import Migrated, Net, Person, Seeder

READ_ONLY: Final = {"detail": "read_only"}
AS_ROLE: Final = {
    "abacus_app": "SET LOCAL ROLE abacus_app",
    "abacus_ops": "SET LOCAL ROLE abacus_ops",
}
MUTATING: Final = {"POST", "PUT", "PATCH", "DELETE"}
# The exemptions table in the platform-ops contract, §3.7 (`read_only`, as built; DEC-338): sign-in
# (pre-session routes and the two sign-outs), staff routes, the support session, ending access,
# browser error reports and reads sent as POST. Anything else that writes answers the 503.
EXEMPT_PREFIXES: Final = re.compile(
    r"^/v1/(auth/|portal/auth/|portal/links/|invitations/preview$|platform/|support)"
)
EXEMPT_ROUTES: Final = {
    ("POST", "/v1/telemetry/errors"): "operational: browser error reports",
    ("PUT", "/v1/firm/support-access"): "the support session",
    ("POST", "/v1/knowledge/search"): "a read sent as POST",
    ("POST", "/v1/firm/staff/{user_id}/revoke"): "ending access: a person's",
    ("POST", "/v1/firm/staff/invitations/{invitation_id}/revoke"): "ending access: an invitation",
}


async def _switch(seed: Seeder, control: str, active: bool) -> None:
    await seed.value(
        "SELECT set_platform_control($1, 'platform', NULL, NULL, $2, 'drill', 'ana', NULL)",
        control,
        active,
    )
    forget_controls()


@pytest.fixture
async def platform_read_only(seed: Seeder) -> AsyncIterator[None]:
    forget_controls()
    await _switch(seed, "read_only", True)
    yield
    await seed.run("UPDATE platform_controls SET active = false")
    forget_controls()


def _mutating_routes() -> list[tuple[str, str]]:
    """Every non-GET operation the app serves, from its OpenAPI document (the route table)."""
    paths = cast(dict[str, dict[str, object]], create_app().openapi()["paths"])
    return sorted(
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
        if method.upper() in MUTATING
    )


def _concrete(path: str) -> str:
    """The path with each `{param}` filled by a fresh id: read-only refuses before any lookup."""
    return re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), path)


async def test_ac_read_only_refuses_every_mutating_route_in_the_route_table(
    net: Net, seed: Seeder, platform_read_only: None
) -> None:
    tenant = await seed.firm()
    admin: Person = await seed.person(tenant, "firm_admin")
    routes = _mutating_routes()
    assert len(routes) > 100  # the whole table, not a sample
    answered: list[str] = []
    for method, path in routes:
        if EXEMPT_PREFIXES.match(path) or (method, path) in EXEMPT_ROUTES:
            continue
        response = await net.call(method, _concrete(path), admin, body={})
        if response.status_code != 503 or response.json() != READ_ONLY:
            answered.append(f"{method} {path} -> {response.status_code}")
    assert answered == [], "\n".join(answered)


async def test_ac_read_only_still_lets_the_exempt_routes_through(
    net: Net, seed: Seeder, platform_read_only: None
) -> None:
    started = await net.http.post(
        "/v1/portal/auth/start", json={"email": "nobody@example.test"}, headers={"host": "x.test"}
    )
    assert started.status_code != 503
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    assert (await net.call("POST", "/v1/auth/sign-out", admin)).status_code != 503
    assert (await net.call("GET", "/v1/me", admin)).status_code == 200


@pytest.mark.parametrize("role", ["abacus_app", "abacus_ops"])
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE platform_control_changes SET reason = 'edited'",
        "DELETE FROM platform_control_changes",
    ],
)
async def test_ac_control_history_is_insert_only(
    seed: Seeder, migrated_db: Migrated, role: str, statement: str
) -> None:
    await _switch(seed, "email_pause", True)
    await _switch(seed, "email_pause", False)
    conn = await connect(migrated_db.superuser_dsn)
    try:
        async with conn.transaction():
            await conn.execute(AS_ROLE[role])
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(statement)
    finally:
        await conn.close()


async def test_ac_every_switch_adds_a_history_row(seed: Seeder) -> None:
    before = int(str(await seed.value("SELECT count(*) FROM platform_control_changes")))
    await _switch(seed, "email_pause", True)
    await _switch(seed, "email_pause", False)
    after = int(str(await seed.value("SELECT count(*) FROM platform_control_changes")))
    assert after == before + 2
