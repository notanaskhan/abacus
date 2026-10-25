# ac-test-author: ayushkbhatia
"""P-08-T22: independent acceptance tests (ADR-078) for P-08-T13 (the portal home read model and
preferences) and T07's shell data.

Written from SPEC-320 AC-15 to AC-17, the epic's Stories 6.1 to 6.5 and §4.3 (the home DTO),
`docs/contracts/portal-identity.md` §2.1, §3, §4 and §6, DEC-129 (role union) and DEC-210 (the
upload to-do counts what `your_part` counts), against the HTTP surface with portal sessions
minted through the pre-session routes:

- `scope_only` per target scope: with two full-client scopes, each home counts its own requests
  only, and a scope no grant covers, or a person with no full-client grant, is 404;
- the upload to-do ties to `GET …/request-items/your-part` for the same person;
- no field carries a firm status code, an amount, materiality, an agent or a confidence: one DTO
  judgement over the contract's closed code sets, run on real homes and shown to reject a planted
  firm status code, an amount and an agent field;
- preferences persist per user and per scope, with a version (409 `portal_preferences_stale`) and
  the audit event `portal_preferences.updated`;
- `/v1/me` names Approvals only for an entity scope (T07).

Spec gap followed: the home DTO has no flat list of "firm status codes"; the judgement treats every
code of the status registry's firm objects that is not one of the contract's client codes as a firm
status code.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import httpx
import pytest
import yaml

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import issue_sign_in_code, totp_at
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp
from abacus.modules.portal.api import activate_portal_host, add_portal_host

from .support import Net, Person, Seeder, Site

Json = dict[str, object]
FLAGS = ("portal.sign_in_v2", "portal.home_v2")
REGISTRY: Final = Path(__file__).parents[4] / "docs" / "product" / "status-vocabulary.yaml"

# Contract §3: the closed client code sets a home may carry.
CLIENT_CODES: Final = {
    "todo.kind": {
        "upload",
        "answer",
        "sign",
        "deliverables",
        "approve",
        "reconnect",
        "review_statements",
        "control_requests",
        "exceptions",
        "description_approved",
    },
    "todo.state": {"open", "none", "overdue"},
    "pill.code": {
        "getting_started",
        "preparing_return",
        "reviewing_return",
        "reconciling_accounts",
        "filed_and_accepted",
        "finishing_audit",
        "testing_under_way",
    },
    "pill.variant": {"state", "success", "neutral"},
    "stage.code": {
        "gather_documents",
        "prepare",
        "review",
        "sign_form_8879",
        "file",
        "requests",
        "reconcile",
        "statements",
        "planning",
        "fieldwork",
        "statements_review",
        "report",
        "scoping",
        "system_description",
        "testing",
        "exceptions",
    },
    "stage.state": {"done", "current", "upcoming"},
    "team.role_code": {
        "partner_signs_return",
        "partner",
        "engagement_partner",
        "manager_reviews_return",
        "manager",
        "preparer_day_to_day",
        "preparer",
        "close_preparer",
        "day_to_day_contact",
        "client_service",
    },
    "earlier.kind": {
        "return_filed",
        "extension_filed",
        "engagement_letter_signed",
        "deliverable_released",
    },
    "note_code": {"waiting_on_k1", "waiting_on_your_k1"},
}
# SPEC-320 AC-16, P-08 Story 6.1: no amount, materiality, agent or confidence, by any name.
FORBIDDEN_KEY_PARTS: Final = (
    "amount",
    "balance",
    "materiality",
    "agent",
    "confidence",
    "model",
    "status",
)
# Plain words a client stage legitimately shares with a firm code (POR-02's trackers draw them).
SHARED_WORDS: Final = {"planning", "fieldwork", "review", "statements", "report", "requests"}


def _firm_status_codes() -> set[str]:
    objects = yaml.safe_load(REGISTRY.read_text())["objects"]
    codes = {str(code) for entry in objects.values() for code in entry.get("codes", {})}
    client: set[str] = set[str]().union(*CLIENT_CODES.values())
    return codes - client - SHARED_WORDS


FIRM_CODES: Final = _firm_status_codes()


def _walk(value: object, path: str = "") -> Iterator[tuple[str, object]]:
    if isinstance(value, dict):
        for key, inner in cast(dict[str, object], value).items():
            yield from _walk(inner, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for inner in cast(list[object], value):
            yield from _walk(inner, f"{path}[]")
    else:
        yield path, value


def dto_problems(home: Json) -> list[str]:
    """What in a home payload breaks AC-16: a firm status code anywhere, a key that names an
    amount, materiality, an agent or a confidence, or a code outside the contract's sets."""
    problems: list[str] = []
    slots = {
        "todos[].kind": "todo.kind",
        "todos[].state": "todo.state",
        "work_cards[].pill.code": "pill.code",
        "work_cards[].pill.variant": "pill.variant",
        "work_cards[].stages[].code": "stage.code",
        "work_cards[].stages[].state": "stage.state",
        "work_cards[].note_code": "note_code",
        "team[].role_code": "team.role_code",
        "earlier[].kind": "earlier.kind",
    }
    for path, value in _walk(home):
        leaf = path.split(".")[-1].rstrip("[]").casefold()
        if any(part in leaf for part in FORBIDDEN_KEY_PARTS):
            problems.append(f"{path}: forbidden field")
        if isinstance(value, str) and value in FIRM_CODES:
            problems.append(f"{path}: firm status code {value!r}")
        slot = slots.get(path)
        if slot is not None and value is not None and value not in CLIENT_CODES[slot]:
            problems.append(f"{path}: {value!r} is not a client code")
        if isinstance(value, str) and "accrued" in value.casefold():
            problems.append(f"{path}: names the product")
    return problems


# ================================================================================================
# Seeding and sessions
# ================================================================================================


@pytest.fixture(autouse=True)
def portal_idp() -> Iterator[None]:
    configure_portal_idp(InMemoryPortalIdp())
    yield
    configure_portal_idp(None)


@dataclass(frozen=True)
class World:
    net: Net
    tenant: uuid.UUID
    host: str
    grace: Person
    a: Site
    b: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def http(self) -> httpx.AsyncClient:
        return self.net.http


@pytest.fixture
async def world(net: Net) -> World:
    seed = net.seed
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-08-T22')",
            tenant,
            flag,
        )
    host = f"t22-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    grace = await seed.person(tenant, "firm_admin")
    a = await seed.site(tenant, grace.user_id, "Feld")
    b = await seed.site(tenant, grace.user_id, "Shah")
    return World(net, tenant, host, grace, a, b)


async def _client(world: World, *grants: tuple[str, str, uuid.UUID]) -> tuple[Person, str]:
    who = await world.seed.person(world.tenant)
    await world.seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        world.tenant,
        who.user_id,
    )
    for role, kind, scope in grants:
        await world.seed.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
            "granted_by) VALUES ($1, $2, $3, $4, $5, $6)",
            world.tenant,
            who.user_id,
            role,
            kind,
            scope,
            world.grace.user_id,
        )
    email = cast(str, await world.seed.value("SELECT email FROM users WHERE id = $1", who.user_id))
    return who, email


async def _session(world: World, email: str) -> str:
    http = world.http
    http.cookies.clear()
    start = await http.post(
        "/v1/portal/auth/start", json={"email": email}, headers={"host": world.host}
    )
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    verified = await http.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": challenge, "code": issued.code},
        headers={"host": world.host},
    )
    http.cookies.clear()
    assert verified.status_code == 200, verified.text
    body = cast(Json, verified.json())
    if body["state"] == "signed_in":
        return cast(str, body["access_token"])
    token = cast(str, body["mfa_token"])
    setup = await http.post(
        "/v1/portal/auth/mfa/setup", json={"mfa_token": token}, headers={"host": world.host}
    )
    done = await http.post(
        "/v1/portal/auth/mfa/setup/verify",
        json={"mfa_token": token, "totp": totp_at(setup.json()["manual_key"], time.time())},
        headers={"host": world.host},
    )
    http.cookies.clear()
    assert done.status_code == 200, done.text
    return cast(str, done.json()["session"]["access_token"])


async def _get(world: World, token: str, path: str) -> httpx.Response:
    world.http.cookies.clear()
    return await world.http.get(
        path, headers={"host": world.host, "authorization": f"Bearer {token}"}
    )


async def _home(world: World, token: str, scope: uuid.UUID) -> Json:
    response = await _get(world, token, f"/v1/portal/home?scope_id={scope}")
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


def _upload(home: Json) -> int:
    todos = cast(list[Json], home["todos"])
    return sum(cast(int, t["count"]) for t in todos if t["kind"] == "upload")


async def _your_part(world: World, token: str, engagement: uuid.UUID) -> int:
    response = await _get(world, token, f"/v1/engagements/{engagement}/request-items/your-part")
    assert response.status_code == 200, response.text
    return cast(int, response.json()["items_left"])


async def _publish(world: World, site: Site) -> None:
    """The site's binder (its request list) published to the client (P-06; BND-02 a)."""
    await world.seed.run(
        "UPDATE request_lists SET status = 'published', published_at = now(), published_by = $2 "
        "WHERE engagement_id = $1",
        site.engagement_id,
        world.grace.user_id,
    )


async def _requests(
    world: World, site: Site, who: Person | None, n: int, *, publish: bool = True
) -> None:
    for i in range(n):
        await world.seed.item(site, f"Form 1099-{i} {site.marker}", assignee=who)
    if publish:
        await _publish(world, site)


# ================================================================================================
# AC-15, AC-16: scope_only per target scope, and the counts tie to your-part
# ================================================================================================


async def test_ac16_each_scope_counts_its_own_requests_and_ties_to_your_part(
    world: World,
) -> None:
    who, email = await _client(
        world,
        ("contributor", "engagement", world.a.engagement_id),
        ("contributor", "engagement", world.b.engagement_id),
    )
    await _requests(world, world.a, who, 3)
    await _requests(world, world.b, who, 1)
    token = await _session(world, email)
    home_a = await _home(world, token, world.a.engagement_id)
    home_b = await _home(world, token, world.b.engagement_id)
    part_a = await _your_part(world, token, world.a.engagement_id)
    part_b = await _your_part(world, token, world.b.engagement_id)
    assert part_a > part_b > 0, (part_a, part_b)
    assert (_upload(home_a), _upload(home_b)) == (part_a, part_b)
    # Each home names its own client, never the other scope's.
    assert world.a.marker in str(home_a["scope"]) and world.b.marker not in str(home_a)
    assert world.b.marker in str(home_b["scope"]) and world.a.marker not in str(home_b)


async def test_ac15_a_draft_binders_requests_count_nowhere_for_the_client(world: World) -> None:
    who, email = await _client(world, ("contributor", "engagement", world.a.engagement_id))
    await _requests(world, world.a, who, 3, publish=False)
    token = await _session(world, email)
    home = await _home(world, token, world.a.engagement_id)
    part = await _your_part(world, token, world.a.engagement_id)
    assert (_upload(home), part) == (0, 0)


async def test_ac16_a_scope_no_grant_covers_is_404(world: World) -> None:
    _, email = await _client(world, ("contributor", "engagement", world.a.engagement_id))
    token = await _session(world, email)
    for scope in (world.b.engagement_id, world.b.client_id, uuid.uuid4()):
        response = await _get(world, token, f"/v1/portal/home?scope_id={scope}")
        assert response.status_code == 404, (scope, response.text)
        assert response.json() == {"detail": "not found"}
        assert world.b.marker not in response.text


async def test_ac16_a_person_with_no_full_client_grant_has_no_home(world: World) -> None:
    _, email = await _client(world, ("third_party", "request_item", world.a.item_id))
    token = await _session(world, email)
    for path in ("/v1/portal/home", f"/v1/portal/home?scope_id={world.a.item_id}"):
        assert (await _get(world, token, path)).status_code == 404, path


async def test_ac16_firm_people_are_refused_the_home(world: World) -> None:
    """Contract §2.1 and §5: the home grants no firm role (a staff token is no client)."""
    response = await world.net.call(
        "GET", f"/v1/portal/home?scope_id={world.a.engagement_id}", world.grace
    )
    assert response.status_code in (401, 403, 404), response.text
    assert world.a.marker not in response.text


# ================================================================================================
# AC-16: the DTO judgement, on real homes and on planted payloads
# ================================================================================================


async def test_ac16_real_homes_carry_no_firm_status_amount_or_agent(world: World) -> None:
    _, email = await _client(world, ("owner", "client_entity", world.a.entity_id))
    await _requests(world, world.a, None, 2)
    for role in ("engagement_partner", "manager", "senior"):
        await world.seed.member(world.a, await world.seed.person(world.tenant), role)
    token = await _session(world, email)
    home = await _home(world, token, world.a.entity_id)
    assert cast(list[Json], home["team"]), home  # the team is there to be judged
    assert dto_problems(home) == []


def _planted_home() -> Json:
    return {
        "scope": {"kind": "client", "id": str(uuid.uuid4()), "label": "Jonah & Claire Feld"},
        "todos": [{"kind": "upload", "count": 2, "state": "open", "facts": {}}],
        "work_cards": [
            {
                "work_item_id": str(uuid.uuid4()),
                "kind": "tax_return",
                "pill": {"code": "reviewing_return", "variant": "state"},
                "stages": [{"code": "review", "state": "current", "facts": {}}],
            }
        ],
        "binder": {"binder_id": str(uuid.uuid4()), "done": 19, "total": 21, "sorted_count": 37},
        "team": [
            {"user_id": str(uuid.uuid4()), "display_name": "Kevin Osei", "role_code": "preparer"}
        ],
        "earlier": [],
        "first_visit": False,
        "welcome_dismissed": True,
        "all_done": False,
    }


def test_ac16_the_judgement_passes_the_contracts_example_home() -> None:
    assert dto_problems(_planted_home()) == []


def test_ac16_the_judgement_rejects_a_planted_firm_status_code() -> None:
    home = _planted_home()
    cards = cast(list[Json], home["work_cards"])
    cast(Json, cards[0]["pill"])["code"] = "in_review"  # "In review · Manager"
    assert dto_problems(home) == [
        "work_cards[].pill.code: firm status code 'in_review'",
        "work_cards[].pill.code: 'in_review' is not a client code",
    ]
    home = _planted_home()  # "Draft K-1 · pre-release" is the k1 package's `draft`
    cast(list[Json], home["todos"])[0]["facts"] = {"k1": "draft"}
    assert dto_problems(home) == ["todos[].facts.k1: firm status code 'draft'"]
    home = _planted_home()
    cast(list[Json], cast(list[Json], home["work_cards"])[0]["stages"])[0]["code"] = "prepared"
    assert any("firm status code 'prepared'" in p for p in dto_problems(home))


def test_ac16_the_judgement_rejects_an_amount_materiality_an_agent_or_a_confidence() -> None:
    for key in ("amount", "balance_due", "materiality", "agent_name", "confidence"):
        home = _planted_home()
        home[key] = 1
        assert dto_problems(home) == [f"{key}: forbidden field"], key
    home = _planted_home()
    cast(Json, home["binder"])["sorted_by_agent"] = 37
    assert dto_problems(home) == ["binder.sorted_by_agent: forbidden field"]


# ================================================================================================
# AC-17: preferences per user and per scope
# ================================================================================================


async def _dismiss(world: World, token: str, scope: uuid.UUID, version: int) -> httpx.Response:
    world.http.cookies.clear()
    return await world.http.put(
        "/v1/portal/preferences",
        json={"scope_id": str(scope), "welcome_dismissed": True, "version": version},
        headers={"host": world.host, "authorization": f"Bearer {token}"},
    )


async def test_ac17_dismissing_the_welcome_is_per_scope_versioned_and_audited(
    world: World,
) -> None:
    who, email = await _client(
        world,
        ("contributor", "engagement", world.a.engagement_id),
        ("contributor", "engagement", world.b.engagement_id),
    )
    token = await _session(world, email)
    before = await _home(world, token, world.a.engagement_id)
    assert before["welcome_dismissed"] is False and before["first_visit"] is True
    saved = await _dismiss(world, token, world.a.engagement_id, 0)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["scope_id"], body["welcome_dismissed"], body["version"]) == (
        str(world.a.engagement_id),
        True,
        1,
    )
    assert body["welcome_dismissed_at"]
    after_a = await _home(world, token, world.a.engagement_id)
    after_b = await _home(world, token, world.b.engagement_id)
    assert after_a["welcome_dismissed"] is True and after_a["first_visit"] is False
    assert after_b["welcome_dismissed"] is False  # the other scope keeps its welcome
    stale = await _dismiss(world, token, world.a.engagement_id, 0)
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"] == "portal_preferences_stale"
    assert stale.json()["facts"]["version"] == 1
    rows = await world.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'portal_preferences.updated'",
        world.tenant,
    )
    assert [(r["actor_kind"], r["actor_id"]) for r in rows] == [("human", str(who.user_id))]


async def test_ac17_preferences_are_per_person(world: World) -> None:
    _, first = await _client(world, ("contributor", "engagement", world.a.engagement_id))
    _, second = await _client(world, ("contributor", "engagement", world.a.engagement_id))
    one, two = await _session(world, first), await _session(world, second)
    assert (await _dismiss(world, one, world.a.engagement_id, 0)).status_code == 200
    assert (await _home(world, two, world.a.engagement_id))["welcome_dismissed"] is False


async def test_ac17_a_scope_no_grant_covers_takes_no_preference(world: World) -> None:
    _, email = await _client(world, ("contributor", "engagement", world.a.engagement_id))
    token = await _session(world, email)
    refused = await _dismiss(world, token, world.b.engagement_id, 0)
    assert refused.status_code == 404, refused.text
    assert (
        await world.seed.value(
            "SELECT count(*) FROM portal_preferences WHERE tenant_id = $1", world.tenant
        )
        == 0
    )


# ================================================================================================
# T07: the shell data, Approvals only for an entity scope
# ================================================================================================


async def _me_portal(world: World, token: str) -> Json:
    response = await _get(world, token, "/v1/me")
    assert response.status_code == 200, response.text
    portal = response.json().get("portal")
    assert portal is not None, response.json()
    return cast(Json, portal)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-1230 (#386; DEC-212 'not yet', owed by P-08-T07, not escaped): "
        "`GET /v1/me` answers 401 to a portal session on its own host, so "
        "`/v1/me.portal` (shell, scopes, nav) never reaches the portal SPA (contract §2.1 'Me, "
        "extended: anyone signed in', §3 MePortalOut; T07 acceptance; DEC-212 left it 'not yet')"
    ),
)
async def test_t07_approvals_is_in_the_nav_only_for_an_entity_scope(world: World) -> None:
    _, household = await _client(world, ("taxpayer", "client", world.a.client_id))
    _, entity = await _client(world, ("owner", "client_entity", world.b.entity_id))
    plain = await _me_portal(world, await _session(world, household))
    owner = await _me_portal(world, await _session(world, entity))
    assert plain["shell"] == owner["shell"] == "full"
    assert "approvals" not in cast(list[str], plain["nav"])
    assert "approvals" in cast(list[str], owner["nav"])
    for portal in (plain, owner):
        assert "home" in cast(list[str], portal["nav"])
        assert "bell" not in str(portal) and "notifications" not in str(portal)  # DEC-58(d)


# ================================================================================================
# Leftovers from the S8 wave B acceptance suites (DEC-210; INV-4)
# ================================================================================================


async def test_leftover_the_binder_picker_of_a_client_with_nothing_published_is_empty(
    world: World,
) -> None:
    """A client whose only binder is a draft gets an empty picker, never a 500 from the route
    guard (no binder meant no `portal_documents.read` check was ever recorded)."""
    await world.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'portal.documents_v2', 'true', 'test-seed', 'leftover')",
        world.tenant,
    )
    who, email = await _client(world, ("contributor", "engagement", world.a.engagement_id))
    await _requests(world, world.a, who, 2, publish=False)
    token = await _session(world, email)
    response = await _get(world, token, "/v1/portal/binders")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["items"], body["total"]) == ([], 0)
