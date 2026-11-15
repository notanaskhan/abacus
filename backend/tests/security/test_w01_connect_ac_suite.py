# ac-test-author: ayushkbhatia
"""W-01-T06 (TASK-8064; ADR-078; SPEC-659; DEC-5049): AY's independent AC suite 1 for N's red
Connect work, over HTTP against the running app.

What the stub already answers is asserted plainly: the flag-off 404 (AC-34), the matrix's 403 for
a non-admin's firm connect (AC-6, AC-7), the 403 `mfa_required` on a stale session (AC-7), and a
portal-free firm route set (AC-8). What only the services can answer (counts, honesty, OAuth
state, typed disconnect, attribution) is written now against the real behaviour and marked
strict-xfail with TASK-8064: each fails against the 501 stub and turns the suite red the moment
W-01-T07/T08 make it pass, so the marker is removed with that change.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from tests.security.support import Net, Person

pytestmark = pytest.mark.usefixtures("engines")


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    felix: Person  # security_admin
    grace: Person  # firm_admin
    hannah: Person  # no firm role


async def _firm(net: Net, *, flag: bool = True) -> Firm:
    tenant = await net.seed.firm()
    await net.seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    felix = await net.seed.person(tenant, "security_admin")
    grace = await net.seed.person(tenant, "firm_admin")
    hannah = await net.seed.person(tenant)
    if flag:
        await net.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'integrations.connect_v1', 'true', 'test-seed', 'W-01 AC suite')",
            tenant,
        )
    return Firm(net, tenant, felix, grace, hannah)


def _key() -> dict[str, str]:
    return {"Idempotency-Key": f"w01-{uuid.uuid4().hex}"}


async def _post(
    firm: Firm, path: str, who: Person, body: object = None, *, mfa: bool = True
) -> int:
    headers = {**firm.net.headers(who, mfa=mfa), **_key()}
    response = await firm.net.http.post(path, json=body, headers=headers)
    return response.status_code


async def test_ac34_with_the_flag_off_every_connect_route_is_404(net: Net) -> None:
    firm = await _firm(net, flag=False)
    for path in ("/v1/integrations/catalog", "/v1/integrations/cch"):
        response = await net.call("GET", path, firm.felix)
        assert response.status_code == 404, path


async def test_ac6_a_non_admin_cannot_connect_a_firm_integration(net: Net) -> None:
    firm = await _firm(net)
    assert await _post(firm, "/v1/integrations/ultratax/connect", firm.hannah) == 403


async def test_ac7_a_stale_session_is_refused(net: Net) -> None:
    # The matrix's `mfa_recent` refuses a stale second factor with the plain 403 the shell reads
    # as a step-up (ADR-030) before the stub is reached.
    firm = await _firm(net)
    headers = {**net.headers(firm.felix, mfa=False), **_key()}
    response = await net.http.post("/v1/integrations/ultratax/connect", headers=headers)
    assert response.status_code == 403


@pytest.mark.xfail(
    strict=True, reason="the facts reason lands with the W-01-T07 service (TASK-8064)"
)
async def test_ac7_a_stale_session_gets_mfa_required(net: Net) -> None:
    firm = await _firm(net)
    headers = {**net.headers(firm.felix, mfa=False), **_key()}
    response = await net.http.post("/v1/integrations/ultratax/connect", headers=headers)
    assert response.status_code == 403
    assert response.json().get("facts", {}).get("reason") == "mfa_required"


async def test_ac7_both_admin_roles_reach_the_firm_connect(net: Net) -> None:
    firm = await _firm(net)
    for who in (firm.felix, firm.grace):
        assert await _post(firm, "/v1/integrations/ultratax/connect", who) in (200, 501)


@pytest.mark.xfail(strict=True, reason="501 stub until W-01-T07/T08 (TASK-8064)")
async def test_ac1_the_catalogue_reads_53_9_38_6(net: Net) -> None:
    firm = await _firm(net)
    response = await net.call("GET", "/v1/integrations/catalog", firm.felix)
    assert response.status_code == 200
    assert response.json()["counts"] == {
        "all": 53,
        "connected": 9,
        "available": 38,
        "coming_soon": 6,
    }


@pytest.mark.xfail(strict=True, reason="501 stub until W-01-T07/T08 (TASK-8064)")
async def test_ac2_filters_keep_catalogue_total_category_counts(net: Net) -> None:
    firm = await _firm(net)
    response = await net.call("GET", "/v1/integrations/catalog?q=Karbon", firm.felix)
    body = response.json()
    assert [t["name"] for t in body["items"]] == ["Karbon"]
    assert {c["code"]: c["count"] for c in body["categories"]}["tax"] == 8


@pytest.mark.xfail(strict=True, reason="501 stub until W-01-T07/T08 (TASK-8064)")
async def test_ac4_a_real_firm_sees_only_registered_adapters_as_available(net: Net) -> None:
    firm = await _firm(net)
    await net.seed.run("UPDATE firms SET synthetic = false WHERE tenant_id = $1", firm.tenant_id)
    from abacus.modules.integrations.adapters import registered_keys  # W-01-T07

    response = await net.call("GET", "/v1/integrations/catalog", firm.felix)
    available = {t["key"] for t in response.json()["items"] if t["status"] == "available"}
    assert available <= set(registered_keys())


@pytest.mark.xfail(strict=True, reason="501 stub until W-01-T07/T08 (TASK-8064)")
async def test_ac12_a_replayed_or_foreign_state_is_invalid_state(net: Net) -> None:
    firm = await _firm(net)
    status = await _post(
        firm, "/v1/integrations/connect/complete", firm.hannah, {"state": "x" * 32, "code": "c"}
    )
    assert status == 409


@pytest.mark.xfail(strict=True, reason="501 stub until W-01-T07/T08 (TASK-8064)")
async def test_ac24_a_mismatched_name_is_422_confirm_name_mismatch(net: Net) -> None:
    firm = await _firm(net)
    status = await _post(
        firm,
        "/v1/integrations/cch/disconnect",
        firm.felix,
        {"confirm_name": "CCH Axcess", "seen_version": 1},
    )
    assert status == 422


@pytest.mark.xfail(strict=True, reason="501 stub until W-01-T07/T08 (TASK-8064)")
async def test_ac26_personal_disconnect_of_anyone_elses_row_is_404(net: Net) -> None:
    firm = await _firm(net)
    assert await _post(firm, "/v1/me/integrations/box/disconnect", firm.hannah) == 404


@pytest.mark.xfail(strict=True, reason="501 stub until W-01-T07/T08 (TASK-8064)")
async def test_ac31_notify_me_is_idempotent(net: Net) -> None:
    firm = await _firm(net)
    first = await _post(firm, "/v1/integrations/adp/interest", firm.hannah)
    second = await _post(firm, "/v1/integrations/adp/interest", firm.hannah)
    assert (first, second) == (200, 200)
