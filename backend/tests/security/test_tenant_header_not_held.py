"""P-01 AC 2.1.4 (ED-024, TASK-1175), swept over the served route table: a tenant header naming
a firm the person does not hold answers 404, and a real firm she is not in answers exactly as a
firm id that never existed (status, body and headers), so nothing tells them apart.

Grace Holloway is a firm admin of one firm. For every firm route (every `AbacusRouter` route that
resolves a tenant: a matrix action or `OWN`), she calls once naming Ashcombe, a firm that exists
and holds a member, and once naming an id no firm ever had; the path is the same for both. The
control proves the same call with her own firm's id is resolved (not a 404 from the header), so
the sweep cannot pass by refusing everything. The pattern is `test_walls_and_need_to_know.py`'s
walled-versus-never-existed sweep. Boundary: `create_app()` over HTTP on the migrated
testcontainer Postgres, seeded as the superuser.
"""

from __future__ import annotations

import re
import uuid
from typing import Final

import httpx

from abacus.api import create_app
from abacus.modules.identity.api import (
    IDENTITY,
    PORTAL_PUBLIC,
    PRE_SESSION,
    PROVIDER_WEBHOOK,
    SELF,
    STAFF,
)
from abacus_tools.codegen.security_tests import served

from .support import Net, Seeder

NOT_FOUND: Final = {"detail": "not found"}
NOT_FOUND_BODY: Final = '{"detail":"not found"}'
# Routes that never resolve a tenant from the header: they authenticate another way (the
# provider webhook names its firm in the path and verifies the provider's signature; ADR-152).
_NO_TENANT: Final = (SELF, STAFF, IDENTITY, PRE_SESSION, PORTAL_PUBLIC, PROVIDER_WEBHOOK)
_ROUTES: Final = served(create_app())[0]
_PARAM: Final = re.compile(r"\{(\w+)(?::\w+)?\}")
# Headers that differ between any two responses: the time and the request's own trace.
_PER_REQUEST: Final = frozenset({"date", "x-request-id", "traceparent", "server-timing"})


def _firm_routes() -> list[tuple[str, str]]:
    return sorted({(m, p) for m, p, action in _ROUTES if action not in _NO_TENANT})


def _fill(path: str) -> str:
    """One concrete path for the route: the same for both calls, so only the header differs."""

    def one(match: re.Match[str]) -> str:
        name = match.group(1)
        if name == "page_no":
            return "1"
        if name in ("which", "section", "target_type", "field_key", "ref"):
            return "x"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{path}:{name}"))

    return _PARAM.sub(one, path)


def _shape(response: httpx.Response) -> tuple[int, str, list[tuple[str, str]]]:
    headers = sorted((k, v) for k, v in response.headers.items() if k not in _PER_REQUEST)
    return response.status_code, response.text, headers


async def test_ac214_every_firm_route_answers_a_firm_not_held_as_one_that_never_existed(
    net: Net, seed: Seeder
) -> None:
    firm, ashcombe = await seed.firm(), await seed.firm()
    grace = await seed.person(firm, "firm_admin")
    await seed.person(ashcombe, "firm_admin")  # a real firm, with people in it
    routes = _firm_routes()
    assert len(routes) > 200  # the sweep is the API surface, not a sample
    found: list[str] = []
    for method, route in routes:
        path = _fill(route)
        real = await net.call(method, path, grace, tenant=ashcombe)
        never = await net.call(method, path, grace, tenant=uuid.uuid4())
        if (real.status_code, real.text) != (404, NOT_FOUND_BODY):
            found.append(f"{method} {route}: {real.status_code} {real.text[:120]}")
        elif _shape(real) != _shape(never):
            found.append(f"{method} {route}: {_shape(real)} vs {_shape(never)}")
        elif str(ashcombe) in real.text or str(firm) in real.text:
            found.append(f"{method} {route}: names a firm")
    assert found == []


async def test_ac214_the_control_her_own_firm_in_the_header_is_resolved(
    net: Net, seed: Seeder
) -> None:
    firm, ashcombe = await seed.firm(), await seed.firm()
    grace = await seed.person(firm, "firm_admin")
    own = await net.call("GET", "/v1/engagements", grace, tenant=firm)
    assert own.status_code == 200, own.text
    other = await net.call("GET", "/v1/engagements", grace, tenant=ashcombe)
    assert (other.status_code, other.json()) == (404, NOT_FOUND)


async def test_ac214_a_member_of_two_firms_reaches_each_and_no_third(
    net: Net, seed: Seeder
) -> None:
    firm, sandbox, ashcombe = await seed.firm(), await seed.firm(), await seed.firm()
    grace = await seed.person(firm, "firm_admin", also=sandbox)
    for tenant in (firm, sandbox):
        held = await net.call("GET", "/v1/engagements", grace, tenant=tenant)
        assert held.status_code == 200, held.text
    real = await net.call("GET", "/v1/engagements", grace, tenant=ashcombe)
    never = await net.call("GET", "/v1/engagements", grace, tenant=uuid.uuid4())
    assert (real.status_code, real.json()) == (404, NOT_FOUND)
    assert _shape(real) == _shape(never)
    # Without the header she holds two firms and named none: still the 403 it always was.
    unnamed = await net.call("GET", "/v1/engagements", grace)
    assert (unnamed.status_code, unnamed.json()) == (403, {"detail": "forbidden"})
