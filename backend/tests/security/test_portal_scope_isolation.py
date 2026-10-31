# ac-test-author: ayushkbhatia
"""P-08-T25 (security, pen test #1 scope): portal scopes are isolated (INV-4).

Written from P-08 Stories 4.1, 6.1 and 6.5 and §2.3, SPEC-320 AC-8, AC-10 and AC-16,
`docs/contracts/portal-identity.md` §2.1 and §6 (one 404 for a scope no grant covers or a person
with no full-client grant), ADR-146 and DEC-129 (role union, `scope_only` per target scope) and
DEC-277 (every portal request re-applies the MFA floor), against the HTTP surface with portal
sessions minted through the pre-session routes:

- **role union** (Meera Shah): a `taxpayer` grant on her own 1040 and a `k1_recipient` grant on a
  Ridgeline K-1 package; nothing of the Ridgeline return (its client, engagement, work item,
  requests, binder or team) is reachable or named;
- **request-scoped third party** (Sam Ortiz): `third_party` grants on two of a plan's three
  requests; no home (404), and nothing of the third request;
- **owner versus contributor**: a contributor on one engagement reaches that engagement's scope
  only, while an owner of the client entity reaches the entity's scope; a person who becomes an
  owner mid-session reaches nothing the floor covers until a second step;
- **cross-tenant**: another firm's scope ids answer as unknown.

`_leaks` is the one judgement the probes use; `test_the_judgement_catches_a_planted_*` proves the
suite fails on a planted cross-scope read.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import issue_sign_in_code, totp_at
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp
from abacus.modules.portal.api import activate_portal_host, add_portal_host

from .portal_pbc_support import another_list, new_binder, signed_in
from .support import Net, Person, Seeder, Site

FLAGS = ("portal.sign_in_v2", "portal.home_v2")
REFUSED = (401, 403, 404)


@pytest.fixture(autouse=True)
def portal_idp() -> Iterator[None]:
    configure_portal_idp(InMemoryPortalIdp())
    yield
    configure_portal_idp(None)


@dataclass(frozen=True)
class Firm:
    tenant: uuid.UUID
    host: str
    admin: Person


async def _firm(seed: Seeder, label: str) -> Firm:
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-08-T25')",
            tenant,
            flag,
        )
    host = f"{label}-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    return Firm(tenant, host, await seed.person(tenant, "firm_admin"))


async def _client_person(seed: Seeder, firm: Firm) -> tuple[Person, str]:
    who = await seed.person(firm.tenant)
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant,
        who.user_id,
    )
    email = cast(str, await seed.value("SELECT email FROM users WHERE id = $1", who.user_id))
    return who, email


async def _grant(
    seed: Seeder, firm: Firm, who: Person, role: str, scope_kind: str, scope_id: uuid.UUID
) -> None:
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
        "granted_by) VALUES ($1, $2, $3, $4, $5, $6)",
        firm.tenant,
        who.user_id,
        role,
        scope_kind,
        scope_id,
        firm.admin.user_id,
    )


async def _work_item(seed: Seeder, firm: Firm, site: Site, name: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) RETURNING id",
            firm.tenant,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            name,
            firm.admin.user_id,
        ),
    )


async def _staff(seed: Seeder, firm: Firm, site: Site, role: str) -> str:
    """A named team member of the site's engagement: the name no other scope may show."""
    who = await seed.person(firm.tenant)
    name = f"Teammate {uuid.uuid4().hex[:8]}"
    await seed.run("UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, name)
    await seed.member(site, who, role)  # type: ignore[arg-type]  # a registry string for the Literal
    return name


async def _verify(http: httpx.AsyncClient, host: str, email: str) -> dict[str, object]:
    start = await http.post("/v1/portal/auth/start", json={"email": email}, headers={"host": host})
    assert start.status_code == 202, start.text
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    verified = await http.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": challenge, "code": issued.code},
        headers={"host": host},
    )
    http.cookies.clear()
    assert verified.status_code == 200, verified.text
    return cast(dict[str, object], verified.json())


async def _session(http: httpx.AsyncClient, host: str, email: str) -> str:
    """A signed-in portal session's access token (the second step set up when asked)."""
    body = await _verify(http, host, email)
    if body["state"] == "signed_in":
        return cast(str, body["access_token"])
    assert body["state"] == "mfa_setup_required", body
    token = cast(str, body["mfa_token"])
    setup = await http.post(
        "/v1/portal/auth/mfa/setup", json={"mfa_token": token}, headers={"host": host}
    )
    assert setup.status_code == 200, setup.text
    done = await http.post(
        "/v1/portal/auth/mfa/setup/verify",
        json={"mfa_token": token, "totp": totp_at(setup.json()["manual_key"], time.time())},
        headers={"host": host},
    )
    http.cookies.clear()
    assert done.status_code == 200, done.text
    session = done.json()["session"]
    assert session["state"] == "signed_in", session
    return cast(str, session["access_token"])


async def _get(http: httpx.AsyncClient, host: str, token: str, path: str) -> httpx.Response:
    http.cookies.clear()
    return await http.get(path, headers={"host": host, "authorization": f"Bearer {token}"})


def _leaks(response: httpx.Response, markers: Sequence[str]) -> list[str]:
    """What is wrong with a probe of a scope the caller holds no grant on: anything but a refusal,
    or any foreign identifier or name in the body."""
    problems = [] if response.status_code in REFUSED else [f"status {response.status_code}"]
    return problems + [f"names {m}" for m in markers if m in response.text]


async def _probe(
    http: httpx.AsyncClient, host: str, token: str, paths: Sequence[str], markers: Sequence[str]
) -> dict[str, list[str]]:
    found = {path: _leaks(await _get(http, host, token, path), markers) for path in paths}
    return {path: problems for path, problems in found.items() if problems}


def _foreign(site: Site, *extra: object) -> list[str]:
    return [
        site.marker,
        str(site.client_id),
        str(site.entity_id),
        str(site.engagement_id),
        str(site.item_id),
        *(str(e) for e in extra),
    ]


def _probes(site: Site, *scope_ids: uuid.UUID) -> list[str]:
    e = site.engagement_id
    return [
        *(
            f"/v1/portal/home?scope_id={s}"
            for s in (site.client_id, site.entity_id, e, *scope_ids)
        ),
        f"/v1/engagements/{e}/request-items",
        f"/v1/portal/request-items/{site.item_id}",
        f"/v1/engagements/{e}",
    ]


# --- Role union: Meera Shah ---------------------------------------------------------------------


@dataclass(frozen=True)
class Union:
    firm: Firm
    token: str
    meera: Person
    own: Site
    own_1040: uuid.UUID
    ridgeline: Site
    ridgeline_return: uuid.UUID
    k1_package: uuid.UUID
    ridgeline_team: str


async def _union(seed: Seeder, http: httpx.AsyncClient) -> Union:
    firm = await _firm(seed, "union")
    own = await seed.site(firm.tenant, firm.admin.user_id, "Shah")
    ridgeline = await seed.site(firm.tenant, firm.admin.user_id, "Ridgeline")
    own_1040 = await _work_item(seed, firm, own, f"2025 Form 1040 {own.marker}")
    ridgeline_return = await _work_item(seed, firm, ridgeline, f"Form 1065 {ridgeline.marker}")
    team = await _staff(seed, firm, ridgeline, "engagement_partner")
    meera, email = await _client_person(seed, firm)
    k1_package = uuid.uuid4()  # T-02's package: the grant names it, no resolver yet (DEC-213)
    await _grant(seed, firm, meera, "taxpayer", "work_item", own_1040)
    await _grant(seed, firm, meera, "k1_recipient", "k1_package", k1_package)
    token = await _session(http, firm.host, email)
    return Union(firm, token, meera, own, own_1040, ridgeline, ridgeline_return, k1_package, team)


async def test_inv4_role_union_reaches_nothing_of_the_ridgeline_return(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    u = await _union(seed, http)
    markers = [*_foreign(u.ridgeline, u.ridgeline_return), u.ridgeline_team]
    paths = _probes(u.ridgeline, u.ridgeline_return, u.k1_package)
    assert await _probe(http, u.firm.host, u.token, paths, markers) == {}


async def test_inv4_role_union_her_own_reads_name_nothing_of_ridgeline(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    u = await _union(seed, http)
    markers = [*_foreign(u.ridgeline, u.ridgeline_return), u.ridgeline_team]
    for path in ("/v1/me", f"/v1/portal/home?scope_id={u.own_1040}", "/v1/portal/home"):
        response = await _get(http, u.firm.host, u.token, path)
        assert [m for m in markers if m in response.text] == [], path


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-1230 (#386; known open, not escaped): "
        "a `taxpayer` grant on a work item holds no engagement role, so "
        "Meera's home on her own 1040 answers 404 (P-08 Story 6.5, SPEC-320 AC-15; recorded "
        "open in DEC-213, owned by identity's role derivation, TASK-1000)"
    ),
)
async def test_story6_5_role_union_her_home_on_her_own_1040_is_served(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    u = await _union(seed, http)
    home = await _get(http, u.firm.host, u.token, f"/v1/portal/home?scope_id={u.own_1040}")
    assert home.status_code == 200, home.text
    assert home.json()["scope"]["id"] == str(u.own_1040)


# --- Request-scoped third party: Sam Ortiz ------------------------------------------------------


async def test_inv4_a_request_scoped_third_party_has_no_home_and_nothing_undelegated(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    firm = await _firm(seed, "third")
    plan = await seed.site(firm.tenant, firm.admin.user_id, "Northwind")
    delegated = [
        plan.item_id,
        cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by) SELECT tenant_id, engagement_id, "
                "request_list_id, 'Census data', 'Payroll', created_by FROM request_items "
                "WHERE id = $1 RETURNING id",
                plan.item_id,
            ),
        ),
    ]
    held_back_marker = f"Held back {uuid.uuid4().hex[:8]}"
    held_back = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by) SELECT tenant_id, engagement_id, request_list_id, $2, "
            "'Cash', created_by FROM request_items WHERE id = $1 RETURNING id",
            plan.item_id,
            held_back_marker,
        ),
    )
    sam, email = await _client_person(seed, firm)
    for item in delegated:
        await _grant(seed, firm, sam, "third_party", "request_item", item)
    token = await _session(http, firm.host, email)
    # No home at all (contract §2.1, Story 4.1): every scope the person could name is 404.
    for scope in (None, plan.client_id, plan.entity_id, plan.engagement_id, *delegated):
        path = "/v1/portal/home" + ("" if scope is None else f"?scope_id={scope}")
        home = await _get(http, firm.host, token, path)
        assert home.status_code == 404, (path, home.text)
    # The held-back request: never reached, never named, wherever it is asked for.
    e = plan.engagement_id
    paths = [f"/v1/portal/request-items/{held_back}", f"/v1/engagements/{e}/request-items"]
    for path in paths:
        response = await _get(http, firm.host, token, path)
        assert held_back_marker not in response.text and str(held_back) not in response.text, path
    assert (await _get(http, firm.host, token, paths[0])).status_code in REFUSED


# --- Owner versus contributor -------------------------------------------------------------------


@dataclass(frozen=True)
class Entity:
    firm: Firm
    site: Site
    sibling: uuid.UUID  # a second engagement of the same client entity
    sibling_marker: str


async def _entity(seed: Seeder) -> Entity:
    firm = await _firm(seed, "entity")
    site = await seed.site(firm.tenant, firm.admin.user_id, "Copperleaf")
    marker = f"Sibling {uuid.uuid4().hex[:8]}"
    sibling = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) "
            "VALUES ($1, $2, $3, $4, '2026-01-01', '2026-12-31', $5) RETURNING id",
            firm.tenant,
            site.client_id,
            site.entity_id,
            marker,
            firm.admin.user_id,
        ),
    )
    await seed.open_engagement(firm.tenant, sibling)
    return Entity(firm, site, sibling, marker)


async def test_inv4_a_contributor_on_one_engagement_reaches_that_scope_only(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    x = await _entity(seed)
    ben, email = await _client_person(seed, x.firm)
    await _grant(seed, x.firm, ben, "contributor", "engagement", x.site.engagement_id)
    token = await _session(http, x.firm.host, email)
    own = await _get(http, x.firm.host, token, f"/v1/portal/home?scope_id={x.site.engagement_id}")
    assert own.status_code == 200, own.text
    paths = [
        f"/v1/portal/home?scope_id={x.sibling}",
        f"/v1/portal/home?scope_id={x.site.entity_id}",
        f"/v1/portal/home?scope_id={x.site.client_id}",
        f"/v1/engagements/{x.sibling}/request-items",
        f"/v1/engagements/{x.sibling}",
    ]
    markers = [x.sibling_marker, str(x.sibling)]
    assert await _probe(http, x.firm.host, token, paths, markers) == {}


async def test_inv4_an_owner_of_the_entity_reaches_the_entity_scope_after_a_second_step(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    x = await _entity(seed)
    tess, email = await _client_person(seed, x.firm)
    await _grant(seed, x.firm, tess, "owner", "client_entity", x.site.entity_id)
    first = await _verify(http, x.firm.host, email)
    assert first["state"] == "mfa_setup_required" and first.get("access_token") is None
    token = await _session(http, x.firm.host, email)
    home = await _get(http, x.firm.host, token, f"/v1/portal/home?scope_id={x.site.entity_id}")
    assert home.status_code == 200, home.text
    assert home.json()["scope"]["kind"] == "client_entity"
    # The entity's grant covers both of its engagements' requests (contributor above: one).
    part = await _get(
        http, x.firm.host, token, f"/v1/engagements/{x.sibling}/request-items/your-part"
    )
    assert part.status_code == 200, part.text


async def test_inv4_a_session_without_a_second_step_reaches_nothing_the_floor_covers(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    """DEC-277: a contributor signed in without a second step, then made the entity's owner, is
    under the floor; their session reaches nothing the owner grant covers until they pass it."""
    x = await _entity(seed)
    who, email = await _client_person(seed, x.firm)
    await _grant(seed, x.firm, who, "contributor", "engagement", x.site.engagement_id)
    token = await _session(http, x.firm.host, email)
    await _grant(seed, x.firm, who, "owner", "client_entity", x.site.entity_id)
    paths = [
        f"/v1/portal/home?scope_id={x.site.entity_id}",
        f"/v1/engagements/{x.sibling}/request-items",
    ]
    assert await _probe(http, x.firm.host, token, paths, [x.sibling_marker]) == {}


async def test_inv4_your_part_of_an_uncovered_engagement_is_refused_not_an_error(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    x = await _entity(seed)
    other = await _firm(seed, "part-b")
    elsewhere = await seed.site(other.tenant, other.admin.user_id, "Elsewhere")
    ben, email = await _client_person(seed, x.firm)
    await _grant(seed, x.firm, ben, "contributor", "engagement", x.site.engagement_id)
    token = await _session(http, x.firm.host, email)
    own = f"/v1/engagements/{x.site.engagement_id}/request-items/your-part"
    assert (await _get(http, x.firm.host, token, own)).status_code == 200
    paths = [
        f"/v1/engagements/{x.sibling}/request-items/your-part",
        f"/v1/engagements/{elsewhere.engagement_id}/request-items/your-part",
        f"/v1/engagements/{uuid.uuid4()}/request-items/your-part",
    ]
    assert await _probe(http, x.firm.host, token, paths, [x.sibling_marker]) == {}


# --- Cross-tenant: another firm's scope ids -----------------------------------------------------


async def test_inv4_another_firms_scope_ids_answer_as_unknown(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    a, b = await _firm(seed, "iso-a"), await _firm(seed, "iso-b")
    site_a = await seed.site(a.tenant, a.admin.user_id, "Mine")
    site_b = await seed.site(b.tenant, b.admin.user_id, "Theirs")
    who, email = await _client_person(seed, a)
    await _grant(seed, a, who, "contributor", "engagement", site_a.engagement_id)
    token = await _session(http, a.host, email)
    unknown = await _get(http, a.host, token, f"/v1/portal/home?scope_id={uuid.uuid4()}")
    assert unknown.status_code == 404
    found = await _probe(http, a.host, token, _probes(site_b), _foreign(site_b))
    assert found == {}
    theirs = await _get(http, a.host, token, f"/v1/portal/home?scope_id={site_b.engagement_id}")
    assert (theirs.status_code, theirs.text) == (unknown.status_code, unknown.text)


# --- The judgement fails on a planted cross-scope read ------------------------------------------


def _response(status: int, body: str) -> httpx.Response:
    return httpx.Response(status, text=body, request=httpx.Request("GET", "http://test/"))


def test_the_judgement_catches_a_planted_cross_scope_read() -> None:
    marker = "Client Ridgeline-0a1b2c3d"
    assert _leaks(_response(404, '{"detail":"not found"}'), [marker]) == []
    planted = _response(200, '{"scope":{"label":"' + marker + '"},"work_cards":[]}')
    assert _leaks(planted, [marker]) == ["status 200", f"names {marker}"]
    # A refusal that still names the other scope is a leak too.
    assert _leaks(_response(404, '{"detail":"' + marker + '"}'), [marker]) == [f"names {marker}"]


# --- R-01-T20 (TASK-1351): the documents, the request sheet and the room ------------------------
# Written from C5 section `portal-pbc` §2 and §6 ("one answer for every case"), DEC-333 and
# DEC-387/388. The firm, binders and sessions come from `portal_pbc_support`.


async def test_r01_room_isolation_the_third_party_reaches_only_delegated_requests(
    net: Net,
) -> None:
    b = await new_binder(net, "room", kind="pbc", categories=("Recordkeeper reports", "Census"))
    delegated = await b.request("Schedule of account balances", "Recordkeeper reports")
    held = f"Census held back {uuid.uuid4().hex[:8]}"
    held_back = await b.request(held, "Census")
    elsewhere = await new_binder(net, "room-other", firm=(b.tenant, b.host, b.admin))
    other_marker = f"Another client {uuid.uuid4().hex[:8]}"
    other = await elsewhere.request(other_marker, "Income")
    _, contact, email = await b.outsider("Sam Ortiz", "Keystone Retirement Services")
    assert (await b.delegate(delegated, contact)).status_code == 201
    sam = await signed_in(b, email)
    room = await sam.get("/v1/portal/room")
    assert room.status_code == 200, room.text
    assert str(delegated) in room.text
    assert held not in room.text and other_marker not in room.text
    paths = [
        "/v1/portal/binders",
        f"/v1/portal/binders/{b.binder}",
        f"/v1/portal/binders/{elsewhere.binder}",
        f"/v1/portal/request-items/{held_back}",
        f"/v1/portal/request-items/{other}",
        f"/v1/engagements/{b.eid}/request-items/{held_back}/comments",
        f"/v1/engagements/{elsewhere.eid}/request-items/{other}/comments",
    ]
    markers = [held, other_marker, str(held_back), str(other), *_foreign(elsewhere.site)]
    found = {p: _leaks(await sam.get(p), markers) for p in paths}
    # The picker may answer an empty list rather than refuse; it must name nothing.
    picker = found.pop("/v1/portal/binders")
    assert [p for p in picker if p.startswith("names")] == []
    assert {p: v for p, v in found.items() if v} == {}


async def test_r01_forged_binder_and_request_ids_get_one_answer(net: Net) -> None:
    b = await new_binder(net, "forged")
    await b.request("Form W-2", "Income")
    internal = await b.request("Internal tie-out", "Income", visible=False)
    draft = await another_list(b, status="draft", part=3)
    await b.request("Draft request", "Income", binder=draft)
    unpublished = await another_list(b, status="unpublished", part=4)
    sibling = await new_binder(net, "forged-sibling", firm=(b.tenant, b.host, b.admin))
    sibling_item = await sibling.request("Sibling request", "Income")
    stranger = await new_binder(net, "forged-stranger")
    stranger_item = await stranger.request("Stranger request", "Income")
    _, contact, _ = await b.outsider("Sam Ortiz", "Keystone Retirement Services")
    delegated = await b.request("Delegated request", "Income")
    assert (await b.delegate(delegated, contact)).status_code == 201
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    unknown = await claire.get(f"/v1/portal/binders/{uuid.uuid4()}")
    assert unknown.status_code == 404
    for path in (
        f"/v1/portal/binders/{draft}",
        f"/v1/portal/binders/{unpublished}",
        f"/v1/portal/binders/{sibling.binder}",
        f"/v1/portal/binders/{stranger.binder}",
    ):
        found = await claire.get(path)
        assert (found.status_code, found.text) == (404, unknown.text), path
    unknown_item = await claire.get(f"/v1/portal/request-items/{uuid.uuid4()}")
    for item in (internal, sibling_item, stranger_item, delegated):
        found = await claire.get(f"/v1/portal/request-items/{item}")
        assert (found.status_code, found.text) == (404, unknown_item.text), item


async def test_r01_contributor_scope_reaches_only_assigned_requests(net: Net) -> None:
    b = await new_binder(net, "contrib", kind="pbc", categories=("Census",))
    dana, email = await b.client("Dana Kowalski", role="contributor")
    mine = await b.request("Census file", "Census", assignee=dana)
    marker = f"Trustee minutes {uuid.uuid4().hex[:8]}"
    theirs = await b.request(marker, "Census")
    portal = await signed_in(b, email)
    binder = await portal.get(f"/v1/portal/binders/{b.binder}?filter=all")
    assert binder.status_code == 200 and str(mine) in binder.text
    assert _leaks(binder, [marker, str(theirs)]) == ["status 200"]
    for path in (
        f"/v1/portal/request-items/{theirs}",
        f"/v1/engagements/{b.eid}/request-items/{theirs}/comments",
    ):
        assert _leaks(await portal.get(path), [marker]) == [], path
    ignored = await portal.post(
        f"/v1/portal/request-items/{theirs}/ignore", {"reason": "dont_have"}
    )
    assert ignored.status_code in REFUSED, ignored.text


async def test_r01_a_closed_binder_reads_read_only(net: Net) -> None:
    b = await new_binder(net, "closed", status="closed")
    await b.request("Form 1099-INT", "Income")
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    read = await claire.get(f"/v1/portal/binders/{b.binder}")
    assert read.status_code == 200, read.text
    assert read.json()["allowed_actions"] == []


async def test_r01_a_closed_binder_reads_but_takes_no_client_act(net: Net) -> None:
    b = await new_binder(net, "closed", status="closed")
    item = await b.request("Form 1099-INT", "Income")
    _, email = await b.client("Claire Feld")
    claire = await signed_in(b, email)
    read = await claire.get(f"/v1/portal/binders/{b.binder}")
    assert read.status_code == 200, read.text
    acts = [
        await claire.post(f"/v1/portal/request-items/{item}/ignore", {"reason": "dont_have"}),
        await claire.post(f"/v1/portal/binders/{b.binder}/mark-done"),
        await claire.post(
            f"/v1/portal/request-items/{item}/upload-intents", {"files_expected": 1}
        ),
    ]
    assert all(400 <= a.status_code < 500 for a in acts), [a.text for a in acts]
    assert (
        await b.seed.value("SELECT status FROM request_items WHERE id = $1", item) == "requested"
    )


async def test_r01_a_tax_engagement_never_reaches_a_third_party_without_consent(
    net: Net,
) -> None:
    """Even a delegation already on file (written before the work item became a tax return)
    reaches nothing: the room leaves the engagement out and the request routes refuse."""
    b = await new_binder(net, "tax")
    marker = f"Form 1099-B {uuid.uuid4().hex[:8]}"
    item = await b.request(marker, "Income")
    who, contact, email = await b.outsider("Marta Lindqvist", "Halvard Securities")
    assert (await b.delegate(item, contact)).status_code == 201
    await b.seed.run(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2025 Form 1040', $5)",
        b.tenant,
        b.eid,
        b.site.client_id,
        b.site.entity_id,
        b.admin.user_id,
    )
    del who
    marta = await signed_in(b, email)
    for path in (
        "/v1/portal/room",
        f"/v1/portal/request-items/{item}",
        f"/v1/engagements/{b.eid}/request-items/{item}/comments",
    ):
        found = await marta.get(path)
        if path == "/v1/portal/room" and found.status_code == 200:
            assert found.json()["total"] == 0, found.text
            assert marker not in found.text
        else:
            assert _leaks(found, [marker]) == [], path
    intent = await marta.post(
        f"/v1/portal/request-items/{item}/upload-intents", {"files_expected": 1}
    )
    assert intent.status_code in REFUSED, intent.text


def test_r01_the_judgement_catches_a_planted_cross_scope_room_read() -> None:
    marker = "Census held back 0a1b2c3d"
    room = (
        '{"total": 2, "bands": [{"label": "Census", "rows": [{"id": "x", "title": "'
        + marker
        + '"}]}]}'
    )
    assert _leaks(_response(200, room), [marker]) == ["status 200", f"names {marker}"]
    assert _leaks(_response(404, '{"detail":"not_found"}'), [marker]) == []


# --- T-02-T30 (TASK-2533): K-1 recipients, the role union's K-1, an inquiry's addressee ----------
# Written from T-02 §3.5 to §3.7, `docs/contracts/k1-packages.md` ("a recipient sees only their own
# packages, released and later; drafts never reach the portal"; another recipient's package, a
# draft or an unknown id: 404) and `docs/contracts/questionnaires.md` (an inquiry is its
# addressee's only). Delta #2's build, the K-1 room and POR-05, is what these probes cover.

T02_FLAGS = ("tax.k1_release", "questionnaires.v1")


async def _t02_flags(seed: Seeder, firm: Firm) -> None:
    for flag in T02_FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'T-02-T30')",
            firm.tenant,
            flag,
        )


async def _k1(
    seed: Seeder, firm: Firm, item: uuid.UUID, name: str, amount: str, *, released: bool = True
) -> uuid.UUID:
    """One recipient's package on the issuing return, released (or a draft), with one box."""
    recipient = await seed.value(
        "INSERT INTO k1_recipients (tenant_id, work_item_id, engine_ref, display_name, "
        "recipient_kind) VALUES ($1, $2, $3, $4, 'lp') RETURNING id",
        firm.tenant,
        item,
        f"P{uuid.uuid4().hex[:6]}",
        name,
    )
    package = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO k1_packages (tenant_id, recipient_id, work_item_id, form, tax_year, "
            "status, is_final_set, released_at, version_no) VALUES ($1, $2, $3, '1065', 2025, "
            "$4, true, $5, 1) RETURNING id",
            firm.tenant,
            recipient,
            item,
            "released" if released else "draft",
            datetime.now(UTC) if released else None,
        ),
    )
    await seed.run(
        "INSERT INTO k1_box_lines (tenant_id, package_id, document_kind, box_code, description, "
        "amount, position) VALUES ($1, $2, 'k1', '2', 'Net rental real estate income', $3, 0)",
        firm.tenant,
        package,
        Decimal(amount),
    )
    return package


@dataclass(frozen=True)
class K1Room:
    firm: Firm
    ridgeline: Site
    issuing: uuid.UUID
    team: str
    mine: uuid.UUID
    theirs: uuid.UUID
    draft: uuid.UUID
    token: str
    own_1040: uuid.UUID


THEIR_NAME = "Pell Street II LLC"
THEIR_AMOUNT = "731337"  # the other recipient's box 2: never in this person's answers
MY_AMOUNT = "400270"


async def _k1_room(seed: Seeder, http: httpx.AsyncClient) -> K1Room:
    firm = await _firm(seed, "k1room")
    await _t02_flags(seed, firm)
    ridgeline = await seed.site(firm.tenant, firm.admin.user_id, "Ridgeline")
    own = await seed.site(firm.tenant, firm.admin.user_id, "Shah")
    issuing = await _work_item(seed, firm, ridgeline, f"Form 1065 {ridgeline.marker}")
    own_1040 = await _work_item(seed, firm, own, f"2025 Form 1040 {own.marker}")
    team = await _staff(seed, firm, ridgeline, "engagement_partner")
    mine = await _k1(seed, firm, issuing, "Pell Street Ventures LLC", MY_AMOUNT)
    theirs = await _k1(seed, firm, issuing, THEIR_NAME, THEIR_AMOUNT)
    draft = await _k1(seed, firm, issuing, "Ridgeline GP LLC", "25000", released=False)
    person, email = await _client_person(seed, firm)
    other, _ = await _client_person(seed, firm)
    await _grant(seed, firm, person, "k1_recipient", "k1_package", mine)
    await _grant(seed, firm, person, "k1_recipient", "k1_package", draft)  # granted, yet a draft
    await _grant(seed, firm, other, "k1_recipient", "k1_package", theirs)
    await _grant(seed, firm, person, "taxpayer", "work_item", own_1040)  # the role union
    token = await _session(http, firm.host, email)
    return K1Room(firm, ridgeline, issuing, team, mine, theirs, draft, token, own_1040)


async def test_t02t30_a_k1_recipient_reads_only_their_own_released_package(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    r = await _k1_room(seed, http)
    listed = await _get(http, r.firm.host, r.token, "/v1/portal/k1s")
    assert listed.status_code == 200, listed.text
    assert [p["id"] for p in cast(list[dict[str, object]], listed.json())] == [str(r.mine)]
    own = await _get(http, r.firm.host, r.token, f"/v1/portal/k1s/{r.mine}")
    assert own.status_code == 200, own.text
    assert MY_AMOUNT in own.text
    markers = [THEIR_NAME, THEIR_AMOUNT, str(r.theirs), str(r.draft)]
    paths = [
        f"/v1/portal/k1s/{r.theirs}",
        f"/v1/portal/k1s/{r.theirs}/download",
        f"/v1/portal/k1s/{r.theirs}/attachments/{uuid.uuid4()}",
        f"/v1/portal/k1s/{r.draft}",
        f"/v1/portal/k1s/{r.draft}/download",
        f"/v1/portal/k1s/{uuid.uuid4()}",
    ]
    assert await _probe(http, r.firm.host, r.token, paths, markers) == {}
    for path in ("/v1/portal/k1s", f"/v1/portal/k1s/{r.mine}"):
        body = (await _get(http, r.firm.host, r.token, path)).text
        assert [m for m in markers if m in body] == [], path


async def test_t02t30_the_role_unions_k1_names_nothing_of_the_issuing_return(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    r = await _k1_room(seed, http)
    # The card names its issuer by design (POR-13); the return, its engagement, its entity and
    # its team are never in a recipient's answers.
    markers = [
        str(r.ridgeline.engagement_id),
        str(r.ridgeline.entity_id),
        str(r.ridgeline.item_id),
        str(r.issuing),
        r.team,
    ]
    for path in ("/v1/portal/k1s", f"/v1/portal/k1s/{r.mine}"):
        response = await _get(http, r.firm.host, r.token, path)
        assert response.status_code == 200, (path, response.text)
        assert [m for m in markers if m in response.text] == [], path
    me = await _get(http, r.firm.host, r.token, "/v1/me")
    assert [m for m in markers if m in me.text] == []
    assert await _probe(http, r.firm.host, r.token, _probes(r.ridgeline, r.issuing), markers) == {}


async def test_t02t30_an_inquiry_is_its_addressees_only(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    firm = await _firm(seed, "inquiry")
    await _t02_flags(seed, firm)
    site = await seed.site(firm.tenant, firm.admin.user_id, "Northwind")
    item = await _work_item(seed, firm, site, f"Fraud inquiries {site.marker}")
    dana, dana_email = await _client_person(seed, firm)
    luis, luis_email = await _client_person(seed, firm)
    contacts: dict[uuid.UUID, uuid.UUID] = {}
    for who, email in ((dana, dana_email), (luis, luis_email)):
        await _grant(seed, firm, who, "contributor", "engagement", site.engagement_id)
        contacts[who.user_id] = cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO contacts (tenant_id, client_id, display_name, email, contact_kind, "
                "portal_state, user_id) VALUES ($1, $2, $3, $4, 'client_person', 'active', $5) "
                "RETURNING id",
                firm.tenant,
                site.client_id,
                f"Contact {uuid.uuid4().hex[:6]}",
                email,
                who.user_id,
            ),
        )
    title = f"Fraud risk inquiry {uuid.uuid4().hex[:8]}"
    inquiry = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO questionnaires (tenant_id, engagement_id, work_item_id, kind, title, "
            "addressed_to_contact_id, created_by) VALUES ($1, $2, $3, 'inquiry', $4, $5, $6) "
            "RETURNING id",
            firm.tenant,
            site.engagement_id,
            item,
            title,
            contacts[dana.user_id],
            firm.admin.user_id,
        ),
    )
    section = await seed.value(
        "INSERT INTO questionnaire_sections (tenant_id, questionnaire_id, name, position) "
        "VALUES ($1, $2, 'Inquiries', 0) RETURNING id",
        firm.tenant,
        inquiry,
    )
    await seed.run(  # one sent question: the portal shows only what a person has sent
        "INSERT INTO questions (tenant_id, questionnaire_id, section_id, position, type, "
        "client_wording, origin, created_by, sent_by, sent_at) VALUES ($1, $2, $3, 0, "
        "'long_text', $4, 'fraud_inquiry', $5, $5, now())",
        firm.tenant,
        inquiry,
        section,
        f"{title}: are you aware of any fraud?",
        firm.admin.user_id,
    )
    dana_token = await _session(http, firm.host, dana_email)
    listed = await _get(http, firm.host, dana_token, "/v1/portal/questionnaires")
    assert listed.status_code == 200, listed.text
    assert str(inquiry) in listed.text
    luis_token = await _session(http, firm.host, luis_email)
    markers = [title, str(inquiry)]
    paths = [f"/v1/portal/questionnaires/{inquiry}"]
    assert await _probe(http, firm.host, luis_token, paths, markers) == {}
    theirs = await _get(http, firm.host, luis_token, "/v1/portal/questionnaires")
    assert [m for m in markers if m in theirs.text] == []


def test_t02t30_the_judgement_catches_a_planted_cross_scope_k1_read() -> None:
    planted = _response(200, '{"lines":[{"box_code":"2","amount":"' + THEIR_AMOUNT + '.00"}]}')
    assert _leaks(planted, [THEIR_AMOUNT]) == ["status 200", f"names {THEIR_AMOUNT}"]
    assert _leaks(_response(404, '{"detail":"not found"}'), [THEIR_AMOUNT]) == []
