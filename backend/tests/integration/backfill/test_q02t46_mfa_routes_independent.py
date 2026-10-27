# ac-test-author: ayushkbhatia
"""Q-02-T46 (TASK-1455): independent route tests (ADR-078) for MFA enforcement, Q-02 AC-42 and
AC-43 (SPEC-341 story 11; DEC-330).

AC-42 at the routes: a listed fresh-MFA action is refused on its live route without a second
factor verified in the last 15 minutes, and allowed with one. AC-43: a staff (firm app) session
without a verified second factor (no `amr: mfa`) answers 401 on every staff route.

Boundary: `create_app()` over HTTP with the fake identity provider's tokens: `mfa=True` carries
`amr: ["pwd", "mfa"]` and a fresh `auth_time`, `mfa=False` carries neither. The staff routes
sampled are Q-02's own firm reads (exports list, retention policies, legal holds). SPEC-341 marks
AC-43's staff refusal **partial** (it waits for WorkOS MFA in each environment; TASK-1200), so
that test is written from the AC and expected to fail until it lands.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Final, cast

import pytest

from abacus.kernel.flags import forget_flags

from .support import Net, Person

Json = dict[str, object]
STAFF_READS: Final = ("/v1/firm/data-exports", "/v1/retention/policies", "/v1/legal-holds")


@pytest.fixture(autouse=True)
def _flags() -> Iterator[None]:
    forget_flags()
    yield
    forget_flags()


async def _admin(net: Net) -> Person:
    tenant = await net.seed.firm()
    for flag in ("compliance.firm_export", "compliance.legal_holds", "compliance.incidents"):
        await net.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'Q-02-T46')",
            tenant,
            flag,
        )
    return await net.seed.person(tenant, "security_admin")


async def test_ac42_a_listed_action_needs_a_fresh_factor_on_its_route(net: Net) -> None:
    admin = await _admin(net)
    approver = await net.seed.person(admin.tenant_id, "security_admin")
    body = {"approver_user_id": str(approver.user_id), "scope": "all"}
    path = "/v1/firm/data-exports"
    headers = net.headers(admin, mfa=False) | {"Idempotency-Key": uuid.uuid4().hex}
    refused = await net.http.post(path, json=body, headers=headers)
    assert refused.status_code in (401, 403), refused.text
    facts = cast(Json, cast(Json, refused.json()).get("facts") or {})
    assert refused.status_code == 401 or facts.get("reason") == "mfa_required", refused.text
    headers = net.headers(admin, mfa=True) | {"Idempotency-Key": uuid.uuid4().hex}
    allowed = await net.http.post(path, json=body, headers=headers)
    assert allowed.status_code == 202, allowed.text


async def test_ac43_staff_reads_answer_with_a_verified_second_factor(net: Net) -> None:
    admin = await _admin(net)
    for path in STAFF_READS:
        response = await net.call("GET", path, admin, mfa=True)
        assert response.status_code == 200, (path, response.text)


@pytest.mark.xfail(
    strict=True,
    reason="TASK-1455: SPEC-341 AC-43 staff-route refusal without `amr: mfa` is not built "
    "(partial in SPEC-341; waits for WorkOS MFA per environment, TASK-1200)",
)
async def test_ac43_a_staff_session_without_a_second_factor_gets_401(net: Net) -> None:
    admin = await _admin(net)
    for path in STAFF_READS:
        response = await net.call("GET", path, admin, mfa=False)
        assert response.status_code == 401, (path, response.text)
