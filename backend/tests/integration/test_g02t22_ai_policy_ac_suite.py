# ac-test-author: ayushkbhatia
"""G-02-T22 (ADR-078 suite 3, written first under the solo amendment) for the AI policy:
SPEC-349 AC-31 to AC-44 for ADM-04, with AC-45 to AC-48 where they touch it.

Written from SPEC-349 §5.10 to §5.12, `docs/contracts/ai-policy.md`, ADR-186, ADR-187, ADR-005
and the permission matrix, not from the stub bodies or any implementation, over HTTP against the
app as the screen calls it: the sign-in dependency answers as the persona and the firm turns
`ai_policy.v1` on in `feature_flag_states`. The firm a test seeds is a real firm (`synthetic`
false) unless the test asks for a synthetic one.

**Against the stubs.** `STUBBED` lists the routes still answering 501 (G-02-T15). A behaviour
test on a stubbed route asserts the 501 and stops there; G-02-T24 removes the routes from
`STUBBED` as it makes them live, and the full assertions then run. With `STUBBED` emptied, every
behaviour test here fails against the stubs, including the requester approving their own
version (409 `approver_must_differ`). Tests that need no live route run in full now: the matrix,
the fresh-MFA register, request validation (no request shape names a gate approver, an opt-in or
an unknown cell), wrong-role and stale-factor refusals (the matrix answers before the stub), the
flag (404 off, 501 on), client 404 and agent and system 403 on every route, the route table, and
the immediate controls on their own live routes (pause and resume, SPEC-036's opt-in).

**Strict xfails.** ED-180 (the database accepts `ai_policy.approved` and `.declined` written as
the agent), ED-181 (a manager-level member is refused `ai_policy.read`), ED-182 (the agent and
the system pass `ai_policy.read`), and the legacy `PUT /v1/firm/autonomy`, which still answers a
flag-on firm until G-02-T24 makes it 409 `superseded_by_ai_policy` (ADR-186 item 7).

Readings this suite takes where the contract is silent (DEC-552): a `facts.field` path ends with
the cell's dotted path (`auto_mode_defaults.tax_return`); AC-38's parenthesised list is the whole
set of locked and default-strict cells; a retried approve, publish or withdraw writes no second
event and leaves the state where the first left it, whatever status the retry answers (the
contract names no `Idempotency-Key` on these routes); an approver who is not a member of the
firm is refused with 404 or 422 and no version is created.
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, cast

import httpx
import pytest
import yaml

from abacus.api import create_app
from abacus.api.export_openapi import document
from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.identity.authz.matrix import RULES

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

Route = tuple[str, str]
POLICY: Final = ("GET", "/v1/firm/ai-policy")
VERSIONS: Final = ("GET", "/v1/firm/ai-policy/versions")
VERSION: Final = ("GET", "/v1/firm/ai-policy/versions/{version_no}")
EFFECTIVE: Final = ("GET", "/v1/firm/ai-policy/effective")
DRAFT: Final = ("GET", "/v1/firm/ai-policy/draft")
DRAFT_PUT: Final = ("PUT", "/v1/firm/ai-policy/draft")
DRAFT_DELETE: Final = ("DELETE", "/v1/firm/ai-policy/draft")
PUBLISH: Final = ("POST", "/v1/firm/ai-policy/versions")
APPROVE: Final = ("POST", "/v1/firm/ai-policy/versions/{version_no}/approve")
DECLINE: Final = ("POST", "/v1/firm/ai-policy/versions/{version_no}/decline")
WITHDRAW: Final = ("POST", "/v1/firm/ai-policy/versions/{version_no}/withdraw")
ROUTES: Final[tuple[Route, ...]] = (
    POLICY,
    VERSIONS,
    VERSION,
    EFFECTIVE,
    DRAFT,
    DRAFT_PUT,
    DRAFT_DELETE,
    PUBLISH,
    APPROVE,
    DECLINE,
    WITHDRAW,
)
# The immediate controls' own routes (live; ADR-186 item 8).
PAUSE: Final = ("POST", "/v1/firm/agents/pause")
RESUME: Final = ("POST", "/v1/firm/agents/resume")
OPT_IN: Final = ("GET", "/v1/firm/ai-client-data")
OPT_IN_PUT: Final = ("PUT", "/v1/firm/ai-client-data")
LEGACY_AUTONOMY_PUT: Final = ("PUT", "/v1/firm/autonomy")

# Routes still answering 501 (the stubs); G-02-T24 made every route live.
LIVE: Final[frozenset[Route]] = frozenset(ROUTES)
STUBBED: Final = frozenset(ROUTES) - LIVE
READS: Final = (POLICY, VERSIONS, VERSION, EFFECTIVE)
# ED-182 (fixed): the agent and the system principals are refused `ai_policy.read` (403).
REFUSED_ROUTES: Final = [pytest.param(route, id=f"{route[0]} {route[1]}") for route in ROUTES]

FRESH_MFA_REGISTER: Final = (
    Path(__file__).resolve().parents[3] / "docs" / "architecture" / "fresh-mfa-actions.yaml"
)
PROVIDER_TERMS: Final = (
    Path(__file__).resolve().parents[3] / "docs" / "operations" / "provider-terms.yaml"
)
WRITES: Final = ("ai_policy.draft", "ai_policy.publish", "ai_policy.approve", "firm_agents.pause")
ENGAGEMENT_TYPES: Final = (
    "ebp_audit",
    "fs_audit",
    "review_compilation",
    "preparation",
    "tax_return",
    "monthly_close",
    "notice",
    "advisory",
)
# "Publish v4 · effective Sep 15, 2026" (AC-37, AC-39), requested the day before on the clock.
REQUESTED_ON: Final = datetime(2026, 9, 14, 15, 0, tzinfo=UTC)
EFFECTIVE_FROM: Final = "2026-09-15"
# Sep 15, 2026 00:00 in the firm's time zone (Central, UTC-5 in September).
JUST_BEFORE: Final = "2026-09-15T04:59:00+00:00"
JUST_AFTER: Final = "2026-09-15T05:01:00+00:00"


def _defaults() -> dict[str, object]:
    """`sections`, schema_version 1, as G-02 §4.2 writes the platform defaults."""
    return {
        "autonomy": {"level": 1},
        "gates": [{"action_key": "aje.approve_batch", "policy_acceptance_on": False}],
        "policy_principal": {"on": False},
        "auto_mode_defaults": {
            "ebp_audit": False,
            "fs_audit": False,
            "review_compilation": False,
            "preparation": False,
            "tax_return": True,
            "monthly_close": True,
            "notice": False,
            "advisory": False,
        },
        "client_data": {
            "require_7216_consent": True,
            "consent_template_ref": None,
            "disclosure_in_letters": True,
            "client_drafts_enabled": False,
        },
        "governance": {
            "install_role": "manager_plus",
            "publish_approver": "methodology_owner",
            "override_tolerance_pct": 8,
            "accuracy_sample_n": 25,
            "trace_retention_years": 7,
        },
    }


def _step(node: object, keys: list[str]) -> object:
    for key in keys:
        node = (
            cast(list[object], node)[int(key)]
            if key.isdigit()
            else cast(dict[str, object], node)[key]
        )
    return node


def _with(sections: object, path: str, value: object) -> dict[str, object]:
    """A copy of `sections` with the dotted `path` (list indexes as digits) set to `value`."""
    out = cast(dict[str, object], copy.deepcopy(sections))
    node = _step(out, path.split(".")[:-1])
    keys = path.split(".")
    last = keys[-1]
    if last.isdigit():
        cast(list[object], node)[int(last)] = value
    else:
        cast(dict[str, object], node)[last] = value
    return out


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    margaret: AuthContext  # quality_partner, partner level (the QM owner)
    daniel: AuthContext  # partner level
    felix: AuthContext  # security_admin
    grace: AuthContext  # firm_admin
    hannah: AuthContext  # manager
    client: AuthContext  # a client principal


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _member(
    seed: Seeder,
    tenant: uuid.UUID,
    name: str,
    *,
    firm_role: str | None,
    level: str | None = None,
    kind: str = "staff",
) -> AuthContext:
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
            name,
        ),
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, kind) "
            "VALUES ($1, $2, $3, 'active', $4, $5) RETURNING id",
            tenant,
            user,
            firm_role,
            level,
            kind,
        ),
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=membership,
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        client=kind == "client",
    )


async def _firm(seed: Seeder, *, flag: bool = True, synthetic: bool = False) -> World:
    tenant = await seed.firm()
    if synthetic:
        await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    if flag:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'ai_policy.v1', 'true', 'ac-suite', 'G-02-T22')",
            tenant,
        )
    return World(
        tenant,
        margaret=await _member(
            seed, tenant, "Margaret Okonkwo", firm_role="quality_partner", level="partner"
        ),
        daniel=await _member(seed, tenant, "Daniel Reyes", firm_role=None, level="partner"),
        felix=await _member(seed, tenant, "Felix Andersen", firm_role="security_admin"),
        grace=await _member(seed, tenant, "Grace Holloway", firm_role="firm_admin"),
        hannah=await _member(seed, tenant, "Hannah Leclerc", firm_role=None, level="manager"),
        client=await _member(seed, tenant, "Claire Feld", firm_role=None, kind="client"),
    )


@pytest.fixture
async def world(seed: Seeder) -> World:
    """A real firm with `ai_policy.v1` on."""
    return await _firm(seed)


def _stale(ctx: AuthContext) -> AuthContext:
    """The same person whose second factor is older than the fresh window."""
    return AuthContext(
        ctx.tenant,
        ctx.user_id,
        ctx.membership_id,
        ctx.firm_role,
        datetime.now(UTC) - timedelta(hours=2),
    )


def _principal(world: World, kind: str) -> AuthContext:
    """The agent (acting for Margaret, who holds every policy action) or the system."""
    actor = "agent:probe:run" if kind == "agent" else "system:probe"
    on_behalf_of = world.margaret.user_id if kind == "agent" else None
    return AuthContext(
        TenantContext(world.tenant, kind, actor, on_behalf_of),  # pyright: ignore[reportArgumentType] -- an actor kind code
        world.margaret.user_id,
        uuid.uuid4(),
        None,
        None,
    )


Call = Callable[..., Awaitable[httpx.Response]]


@pytest.fixture
def as_() -> Callable[[object], Call]:
    """`await as_(ctx)("GET", "/v1/firm/ai-policy")`: one request as that principal."""

    def bind(principal: object) -> Call:
        async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
            app = create_app()
            app.dependency_overrides[current_context] = lambda: principal
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

        return call

    return bind


def stubbed(route: Route, response: httpx.Response) -> bool:
    """True while `route` is the 501 stub (and asserts it is); the behaviour assertions run once
    the route is live."""
    if route in STUBBED:
        assert response.status_code == 501, (route, response.status_code, response.text)
        return True
    return False


def _path(route: Route, **params: object) -> str:
    return route[1].format(**params)


def _body(response: httpx.Response) -> dict[str, object]:
    return cast(dict[str, object], response.json())


def _detail(response: httpx.Response) -> object:
    return _body(response).get("detail")


def _field(response: httpx.Response) -> str:
    return cast(str, cast(dict[str, object], _body(response)["facts"])["field"])


async def _audited(seed: Seeder, tenant: uuid.UUID, action: str) -> list[tuple[str, str]]:
    rows = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
        "ORDER BY seq",
        tenant,
        action,
    )
    return [(cast(str, r["actor_kind"]), cast(str, r["actor_id"])) for r in rows]


def _human(ctx: AuthContext) -> tuple[str, str]:
    return ("human", str(ctx.user_id))


def _publish_body(approver: AuthContext) -> dict[str, object]:
    return {"effective_from": EFFECTIVE_FROM, "approver_user_id": str(approver.user_id)}


async def _draft(as_: Callable[[object], Call], who: AuthContext) -> dict[str, object] | None:
    """The firm's draft as `who` reads it, or None while the route is the stub."""
    response = await as_(who)(*DRAFT)
    if stubbed(DRAFT, response):
        return None
    assert response.status_code == 200, response.text
    return _body(response)


async def _save(
    as_: Callable[[object], Call], who: AuthContext, sections: object
) -> httpx.Response | None:
    """Save `sections` against the draft's current If-Match, or None while stubbed."""
    draft = await _draft(as_, who)
    if draft is None:
        return None
    response = await as_(who)(
        *DRAFT_PUT, json={"sections": sections}, headers={"If-Match": str(draft["version"])}
    )
    if stubbed(DRAFT_PUT, response):
        return None
    return response


async def _base(as_: Callable[[object], Call], who: AuthContext) -> dict[str, object] | None:
    draft = await _draft(as_, who)
    return None if draft is None else cast(dict[str, object], draft["sections"])


async def _request_v_next(as_: Callable[[object], Call], world: World) -> dict[str, object] | None:
    """Margaret steps the override tolerance 8% → 6% and requests the next version effective
    Sep 15, 2026 naming Daniel (AC-36, AC-37). None while any step is a stub."""
    base = await _base(as_, world.margaret)
    if base is None:
        return None
    saved = await _save(as_, world.margaret, _with(base, "governance.override_tolerance_pct", 6))
    if saved is None:
        return None
    assert saved.status_code == 200, saved.text
    response = await as_(world.margaret)(*PUBLISH, json=_publish_body(world.daniel))
    if stubbed(PUBLISH, response):
        return None
    assert response.status_code == 201, response.text
    return _body(response)


# --- AC-31: the effective policy -----------------------------------------------------------------


async def test_ac31_every_firm_reads_one_published_effective_version(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.margaret)(*POLICY)
    if stubbed(POLICY, response):
        return
    assert response.status_code == 200
    body = _body(response)
    effective = cast(dict[str, object], body["effective"])
    assert effective["state"] == "published"
    assert cast(int, effective["version_no"]) >= 1
    assert body["pending"] is None and body["scheduled"] is None
    # "Save as v4…" stays disabled while the draft equals the effective version.
    assert cast(dict[str, object], body["draft"])["differs"] is False
    assert body["real_firm"] is True


# --- AC-32: the twelve gates ---------------------------------------------------------------------


async def test_ac32_twelve_gate_rows_with_policy_acceptance_only_on_rows_1_and_5_off_and_locked(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.margaret)(*POLICY)
    if stubbed(POLICY, response):
        return
    gates = cast(list[dict[str, object]], _body(response)["gates"])
    assert [g["row"] for g in gates] == list(range(1, 13))
    assert {cast(int, g["row"]) for g in gates if g["policy_acceptance_available"]} == {1, 5}
    for gate in gates:
        assert gate["policy_acceptance_on"] is False
        assert gate["policy_acceptance_locked"] is True
        if gate["policy_acceptance_available"]:
            assert gate["attest"] == "never"
        for screen in cast(list[str], gate["where_shown"]):
            assert re.fullmatch(r"[A-Z]{3}-\d{2}", screen), screen


async def test_ac32_no_gate_names_an_approver_the_matrix_does_not_allow(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.margaret)(*POLICY)
    if stubbed(POLICY, response):
        return
    for gate in cast(list[dict[str, object]], _body(response)["gates"]):
        roles = set(cast(list[str], gate["default_approver_roles"]))
        assert roles, gate["gate_key"]
        assert not roles & {"agent", "system", "client_admin", "client_contributor"}
        for action in cast(list[str], gate["action_keys"]):
            allowed = {k for k, v in RULES[action].decisions.items() if v != "deny"}
            assert roles <= allowed, (gate["gate_key"], action, roles - allowed)


def test_ac32_ac38_a_draft_cannot_carry_a_gate_approver() -> None:
    """Gate rows store only stricter-only overrides; an approver is the catalogue's, never the
    draft's (ADR-186 item 3): the request shape has nowhere to put one."""
    schema = cast(dict[str, dict[str, object]], json.loads(document())["components"]["schemas"])
    gate = schema["GateOverride"]
    assert gate.get("additionalProperties") is False
    assert set(cast(dict[str, object], gate["properties"])) == {
        "action_key",
        "policy_acceptance_on",
    }


async def test_ac38_a_draft_naming_a_gate_approver_is_refused(
    world: World, as_: Callable[[object], Call]
) -> None:
    sections = _defaults()
    sections["gates"] = [
        {"action_key": "aje.approve_batch", "policy_acceptance_on": False, "approver": "staff"}
    ]
    response = await as_(world.margaret)(
        *DRAFT_PUT, json={"sections": sections}, headers={"If-Match": "0"}
    )
    assert response.status_code == 422


# --- AC-33, AC-40: who reads and who changes -----------------------------------------------------


@pytest.mark.parametrize(
    "who",
    [
        "margaret",
        "daniel",
        "felix",
        "grace",
        "hannah",  # ED-181 (fixed): the derived firm_manager reads the policy
    ],
)
async def test_ac33_every_firm_member_reads_the_policy_its_history_and_its_effective_cells(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    ctx = cast(AuthContext, getattr(world, who))
    for route, kwargs in (
        (POLICY, {}),
        (VERSIONS, {}),
        (EFFECTIVE, {"params": {"engagement_type": "tax_return"}}),
    ):
        response = await as_(ctx)(*route, **kwargs)
        assert response.status_code != 403, (who, route)
        if stubbed(route, response):
            continue
        assert response.status_code == 200, (who, route, response.text)


async def test_ac33_a_manager_reads_only_with_the_partners_lock(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.hannah)(*POLICY)
    if stubbed(POLICY, response):
        return
    body = _body(response)
    actions = set(cast(list[str], body["actions"]))
    assert "ai_policy.read" in actions
    assert not actions & {"ai_policy.draft", "ai_policy.publish", "ai_policy.approve"}
    assert "not_a_partner" in {
        cast(str, lock["reason"]) for lock in cast(list[dict[str, object]], body["locks"])
    }


async def test_ac40_the_firm_admin_reads_only_and_may_pause(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.grace)(*POLICY)
    if stubbed(POLICY, response):
        return
    actions = set(cast(list[str], _body(response)["actions"]))
    assert not actions & {"ai_policy.draft", "ai_policy.publish", "ai_policy.approve"}
    assert "firm_agents.pause" in actions


async def test_ac40_the_security_admin_drafts_client_data_only(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*POLICY)
    if stubbed(POLICY, response):
        return
    body = _body(response)
    actions = set(cast(list[str], body["actions"]))
    assert "ai_policy.draft" in actions
    assert not actions & {"ai_policy.publish", "ai_policy.approve"}
    assert "client_data_only" in {
        cast(str, lock["reason"]) for lock in cast(list[dict[str, object]], body["locks"])
    }


@pytest.mark.parametrize("who", ["grace", "hannah", "daniel"])
async def test_ac40_only_the_qm_owner_and_the_security_admin_touch_the_draft(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    ctx = cast(AuthContext, getattr(world, who))
    headers = {"If-Match": "0"}
    for route, kwargs in (
        (DRAFT, {}),
        (DRAFT_PUT, {"json": {"sections": _defaults()}, "headers": headers}),
        (DRAFT_DELETE, {"headers": headers}),
    ):
        response = await as_(ctx)(*route, **kwargs)
        assert response.status_code == 403, (who, route, response.text)


@pytest.mark.parametrize("who", ["felix", "grace", "hannah", "daniel"])
async def test_ac40_only_the_qm_owner_requests_or_withdraws_a_version(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    ctx = cast(AuthContext, getattr(world, who))
    publish = await as_(ctx)(*PUBLISH, json=_publish_body(world.daniel))
    assert publish.status_code == 403, publish.text
    withdraw = await as_(ctx)("POST", _path(WITHDRAW, version_no=2))
    assert withdraw.status_code == 403, withdraw.text


@pytest.mark.parametrize("who", ["felix", "grace", "hannah"])
async def test_ac37_ac40_only_a_partner_approves_or_declines(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    ctx = cast(AuthContext, getattr(world, who))
    approve = await as_(ctx)("POST", _path(APPROVE, version_no=2))
    assert approve.status_code == 403, approve.text
    decline = await as_(ctx)(
        "POST", _path(DECLINE, version_no=2), json={"reason_code": "needs_changes"}
    )
    assert decline.status_code == 403, decline.text


async def test_ac40_the_security_admin_saves_a_client_data_change(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    base = await _base(as_, world.felix)
    if base is None:
        return
    saved = await _save(as_, world.felix, _with(base, "client_data.disclosure_in_letters", False))
    if saved is None:
        return
    assert saved.status_code == 200, saved.text
    assert await _audited(seed, world.tenant, "ai_policy.draft_saved") == [_human(world.felix)]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("autonomy.level", 0),
        ("governance.override_tolerance_pct", 6),
        ("auto_mode_defaults.fs_audit", False),
    ],
)
async def test_ac40_the_security_admin_cannot_change_another_section(
    world: World, as_: Callable[[object], Call], seed: Seeder, path: str, value: object
) -> None:
    """Even a stricter change outside fieldset D is refused, naming its path (contract §5)."""
    base = await _base(as_, world.felix)
    if base is None:
        return
    saved = await _save(as_, world.felix, _with(base, path, value))
    if saved is None:
        return
    assert saved.status_code == 422
    assert _detail(saved) == "policy_loosening_refused"
    assert _field(saved).endswith(path)
    assert await _audited(seed, world.tenant, "ai_policy.draft_saved") == []


# --- AC-34: version history ----------------------------------------------------------------------


async def test_ac34_history_lists_newest_first_with_requester_and_approver(
    world: World, as_: Callable[[object], Call]
) -> None:
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        no = requested["version_no"]
        approved = await as_(world.daniel)("POST", _path(APPROVE, version_no=no))
        if stubbed(APPROVE, approved):
            return
        listed = await as_(world.grace)(*VERSIONS)
        if stubbed(VERSIONS, listed):
            return
    items = cast(list[dict[str, object]], _body(listed)["items"])
    numbers = [cast(int, v["version_no"]) for v in items]
    assert numbers == sorted(numbers, reverse=True) and numbers[0] == no
    newest = items[0]
    assert newest["state"] == "published"
    assert cast(dict[str, object], newest["requested_by"])["user_id"] == str(
        world.margaret.user_id
    )
    assert cast(dict[str, object], newest["approver"])["user_id"] == str(world.daniel.user_id)
    assert cast(dict[str, object], newest["decided_by"])["user_id"] == str(world.daniel.user_id)
    for version in items:
        assert version["state"] in ("awaiting_approval", "published", "declined", "withdrawn")


async def test_ac34_a_version_carries_its_diff_against_the_one_before(
    world: World, as_: Callable[[object], Call]
) -> None:
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        detail = await as_(world.grace)("GET", _path(VERSION, version_no=requested["version_no"]))
        if stubbed(VERSION, detail):
            return
    assert detail.status_code == 200
    diff = cast(list[dict[str, object]], _body(detail)["diff"])
    assert [
        (d["before"], d["after"])
        for d in diff
        if cast(str, d["path"]).endswith("governance.override_tolerance_pct")
    ] == [(8, 6)]
    assert len(diff) == 1


async def test_ac34_an_unknown_version_is_not_found(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.margaret)("GET", _path(VERSION, version_no=999))
    if stubbed(VERSION, response):
        return
    assert response.status_code == 404


# --- AC-35: Auto mode ----------------------------------------------------------------------------


async def test_ac35_on_a_real_firm_every_auto_mode_cell_reads_off_and_locked(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.margaret)(*POLICY)
    if stubbed(POLICY, response):
        return
    body = _body(response)
    assert body["real_firm"] is True
    locks = cast(list[dict[str, object]], body["locks"])
    for kind in ENGAGEMENT_TYPES:
        assert [
            lock["reason"]
            for lock in locks
            if cast(str, lock["path"]).endswith(f"auto_mode_defaults.{kind}")
        ] == ["real_firm_season_1"], kind
        effective = await as_(world.margaret)(*EFFECTIVE, params={"engagement_type": kind})
        if stubbed(EFFECTIVE, effective):
            continue
        assert _body(effective)["auto_mode_effective"] is False, kind
        assert _body(effective)["auto_mode_lock"] == "real_firm_season_1", kind


async def test_ac35_a_synthetic_firm_keeps_its_stored_auto_mode(
    seed: Seeder, as_: Callable[[object], Call]
) -> None:
    """Brightwater Hale is synthetic: Auto mode reads as stored, with no Season 1 lock."""
    bh = await _firm(seed, synthetic=True)
    base = await _base(as_, bh.margaret)
    if base is None:
        return
    saved = await _save(as_, bh.margaret, _with(base, "auto_mode_defaults.tax_return", False))
    assert saved is not None and saved.status_code == 200, saved and saved.text
    turned_on = await _save(as_, bh.margaret, _with(base, "auto_mode_defaults.tax_return", True))
    assert turned_on is not None and turned_on.status_code == 200, turned_on and turned_on.text
    response = await as_(bh.margaret)(*POLICY)
    if stubbed(POLICY, response):
        return
    assert _body(response)["real_firm"] is False
    reasons = {
        cast(str, lock["reason"])
        for lock in cast(list[dict[str, object]], _body(response)["locks"])
    }
    assert "real_firm_season_1" not in reasons


# --- AC-36: the draft ----------------------------------------------------------------------------


async def test_ac36_a_stepped_tolerance_shows_unsaved_changes_and_is_audited(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    base = await _base(as_, world.margaret)
    if base is None:
        return
    saved = await _save(as_, world.margaret, _with(base, "governance.override_tolerance_pct", 6))
    assert saved is not None and saved.status_code == 200, saved and saved.text
    draft = _body(saved)
    assert draft["differs"] is True
    assert (
        cast(dict[str, dict[str, object]], draft["sections"])["governance"][
            "override_tolerance_pct"
        ]
        == 6
    )
    diff = cast(list[dict[str, object]], draft["diff"])
    assert [(d["before"], d["after"]) for d in diff] == [(8, 6)]
    assert await _audited(seed, world.tenant, "ai_policy.draft_saved") == [_human(world.margaret)]


async def test_ac36_a_stale_if_match_is_refused_and_writes_nothing(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    """Idempotency of the draft: the same If-Match twice saves once (409 `stale_version`)."""
    draft = await _draft(as_, world.margaret)
    if draft is None:
        return
    sections = _with(draft["sections"], "governance.override_tolerance_pct", 6)
    headers = {"If-Match": str(draft["version"])}
    first = await as_(world.margaret)(*DRAFT_PUT, json={"sections": sections}, headers=headers)
    if stubbed(DRAFT_PUT, first):
        return
    assert first.status_code == 200
    again = await as_(world.margaret)(*DRAFT_PUT, json={"sections": sections}, headers=headers)
    assert again.status_code == 409 and _detail(again) == "stale_version"
    discard = await as_(world.margaret)(*DRAFT_DELETE, headers=headers)
    assert discard.status_code == 409 and _detail(discard) == "stale_version"
    assert await _audited(seed, world.tenant, "ai_policy.draft_saved") == [_human(world.margaret)]
    assert await _audited(seed, world.tenant, "ai_policy.draft_discarded") == []


async def test_ac36_discard_returns_to_the_effective_version_and_is_audited(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    base = await _base(as_, world.margaret)
    if base is None:
        return
    saved = await _save(as_, world.margaret, _with(base, "governance.override_tolerance_pct", 6))
    assert saved is not None and saved.status_code == 200
    discarded = await as_(world.margaret)(
        *DRAFT_DELETE, headers={"If-Match": str(_body(saved)["version"])}
    )
    if stubbed(DRAFT_DELETE, discarded):
        return
    assert discarded.status_code == 200
    assert _body(discarded)["differs"] is False
    assert _body(discarded)["sections"] == base
    assert await _audited(seed, world.tenant, "ai_policy.draft_discarded") == [
        _human(world.margaret)
    ]


async def test_ac36_saving_a_draft_needs_no_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    """The matrix asks for fresh MFA at publish and approve, not at save (contract §2)."""
    response = await as_(_stale(world.margaret))(
        *DRAFT_PUT, json={"sections": _defaults()}, headers={"If-Match": "0"}
    )
    assert response.status_code != 403, response.text


async def test_ac36_a_save_needs_if_match(world: World, as_: Callable[[object], Call]) -> None:
    response = await as_(world.margaret)(*DRAFT_PUT, json={"sections": _defaults()})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "extra",
    [
        {"client_data": "opt_in"},
        {"autonomy": "approver"},
        {"policy_principal": "allowed_clients"},
        {"governance": "publish_without_approval"},
    ],
    ids=lambda e: next(iter(e)),
)
async def test_ac38_a_draft_with_an_unknown_cell_is_refused(
    world: World, as_: Callable[[object], Call], extra: dict[str, str]
) -> None:
    """Inputs forbid unknown fields (contract §3): no cell outside sections A to E, so no draft
    reaches the opt-in (SPEC-036 unchanged, AC-41) or a publish without approval."""
    ((section, cell),) = extra.items()
    sections = _with(_defaults(), f"{section}.{cell}", True)
    response = await as_(world.margaret)(
        *DRAFT_PUT, json={"sections": sections}, headers={"If-Match": "0"}
    )
    assert response.status_code == 422


# --- AC-38: stricter only ------------------------------------------------------------------------

LOOSENINGS: Final = (
    ("gates.0.policy_acceptance_on", True),
    ("policy_principal.on", True),
    ("client_data.require_7216_consent", False),
    ("client_data.client_drafts_enabled", True),
    ("governance.trace_retention_years", 6),
    ("governance.trace_retention_years", 1),
    ("autonomy.level", 2),
    ("autonomy.level", 3),
)


@pytest.mark.parametrize(("path", "value"), LOOSENINGS, ids=lambda v: str(v))
async def test_ac38_ac48_a_loosening_is_refused_with_its_path_and_writes_nothing(
    world: World, as_: Callable[[object], Call], seed: Seeder, path: str, value: object
) -> None:
    base = await _base(as_, world.margaret)
    if base is None:
        return
    if path.startswith("gates."):
        base = {
            **base,
            "gates": [{"action_key": "aje.approve_batch", "policy_acceptance_on": False}],
        }
    saved = await _save(as_, world.margaret, _with(base, path, value))
    assert saved is not None
    assert saved.status_code == 422, saved.text
    assert _detail(saved) == "policy_loosening_refused"
    assert _field(saved).endswith(path.split(".", 2)[-1] if path.startswith("gates.") else path)
    assert await _audited(seed, world.tenant, "ai_policy.draft_saved") == []


@pytest.mark.parametrize("kind", ENGAGEMENT_TYPES)
async def test_ac35_ac38_auto_mode_cannot_be_turned_on_for_a_real_firm(
    world: World, as_: Callable[[object], Call], kind: str
) -> None:
    base = await _base(as_, world.margaret)
    if base is None:
        return
    off = copy.deepcopy(base)
    cast(dict[str, object], off["auto_mode_defaults"]).update(
        dict.fromkeys(ENGAGEMENT_TYPES, False)
    )
    tightened = await _save(as_, world.margaret, off)
    assert tightened is not None and tightened.status_code == 200, tightened and tightened.text
    turned_on = await _save(as_, world.margaret, _with(off, f"auto_mode_defaults.{kind}", True))
    assert turned_on is not None
    assert turned_on.status_code == 422
    assert _detail(turned_on) == "policy_loosening_refused"
    assert _field(turned_on).endswith(f"auto_mode_defaults.{kind}")


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("autonomy.level", 0),
        ("governance.trace_retention_years", 10),
        ("governance.install_role", "partner_only"),
        ("governance.override_tolerance_pct", 6),
    ],
)
async def test_ac38_a_stricter_change_is_saved(
    world: World, as_: Callable[[object], Call], path: str, value: object
) -> None:
    base = await _base(as_, world.margaret)
    if base is None:
        return
    saved = await _save(as_, world.margaret, _with(base, path, value))
    assert saved is not None and saved.status_code == 200, saved and saved.text


# --- AC-37: publish and approve ------------------------------------------------------------------


async def test_ac37_ac47_margaret_requests_and_daniel_approves_each_audited(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    await _opt_in_flag(seed, world.tenant)
    opt_in_before = await as_(world.grace)(*OPT_IN)
    assert opt_in_before.status_code == 200, opt_in_before.text
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        no = requested["version_no"]
        assert requested["state"] == "awaiting_approval"
        assert cast(dict[str, object], requested["approver"])["user_id"] == str(
            world.daniel.user_id
        )
        assert cast(dict[str, object], requested["requested_by"])["user_id"] == str(
            world.margaret.user_id
        )
        assert requested["effective_from"] == EFFECTIVE_FROM or str(
            requested["effective_from"]
        ).startswith(EFFECTIVE_FROM)
        pending = await as_(world.margaret)(*POLICY)
        if not stubbed(POLICY, pending):
            assert cast(dict[str, object], _body(pending)["pending"])["version_no"] == no
        approved = await as_(world.daniel)("POST", _path(APPROVE, version_no=no))
        if stubbed(APPROVE, approved):
            return
    assert approved.status_code == 200, approved.text
    assert _body(approved)["state"] == "published"
    assert await _audited(seed, world.tenant, "ai_policy.publish_requested") == [
        _human(world.margaret)
    ]
    assert await _audited(seed, world.tenant, "ai_policy.approved") == [_human(world.daniel)]
    # The policy never changes the SPEC-036 opt-in (AC-41).
    assert _body(await as_(world.grace)(*OPT_IN)) == _body(opt_in_before)


async def test_ac37_the_requester_cannot_name_herself_as_approver(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    base = await _base(as_, world.margaret)
    if base is None:
        return
    saved = await _save(as_, world.margaret, _with(base, "governance.override_tolerance_pct", 6))
    assert saved is not None and saved.status_code == 200
    with frozen(REQUESTED_ON):
        response = await as_(world.margaret)(*PUBLISH, json=_publish_body(world.margaret))
    if stubbed(PUBLISH, response):
        return
    assert response.status_code == 409
    assert _detail(response) == "approver_must_differ"
    assert await _audited(seed, world.tenant, "ai_policy.publish_requested") == []


async def test_ac37_the_requester_approving_her_own_version_answers_409(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    """Margaret is a partner, so the matrix lets her reach approve; the service refuses."""
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            # Against the stub, her approve reaches the stub: the matrix does not refuse it.
            response = await as_(world.margaret)("POST", _path(APPROVE, version_no=2))
            assert stubbed(APPROVE, response)
            return
        response = await as_(world.margaret)(
            "POST", _path(APPROVE, version_no=requested["version_no"])
        )
    assert response.status_code == 409
    assert _detail(response) == "approver_must_differ"
    assert await _audited(seed, world.tenant, "ai_policy.approved") == []


async def test_ac37_publish_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(_stale(world.margaret))(*PUBLISH, json=_publish_body(world.daniel))
    assert response.status_code == 403


@pytest.mark.parametrize("route", [APPROVE, DECLINE], ids=["approve", "decline"])
async def test_ac37_approve_and_decline_need_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call], route: Route
) -> None:
    kwargs = {"json": {"reason_code": "needs_changes"}} if route == DECLINE else {}
    response = await as_(_stale(world.daniel))("POST", _path(route, version_no=2), **kwargs)
    assert response.status_code == 403


async def test_ac37_withdraw_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(_stale(world.margaret))("POST", _path(WITHDRAW, version_no=2))
    assert response.status_code == 403


async def test_ac37_ac47_daniel_declines_with_a_reason_and_it_is_audited(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        declined = await as_(world.daniel)(
            "POST",
            _path(DECLINE, version_no=requested["version_no"]),
            json={"reason_code": "wrong_effective_date"},
        )
    if stubbed(DECLINE, declined):
        return
    assert declined.status_code == 200
    assert _body(declined)["state"] == "declined"
    assert await _audited(seed, world.tenant, "ai_policy.declined") == [_human(world.daniel)]
    assert await _audited(seed, world.tenant, "ai_policy.approved") == []


async def test_ac37_ac47_the_requester_withdraws_once_and_nothing_leaves_published(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        path = _path(WITHDRAW, version_no=requested["version_no"])
        withdrawn = await as_(world.margaret)("POST", path)
        if stubbed(WITHDRAW, withdrawn):
            return
        again = await as_(world.margaret)("POST", path)
        approve_after = await as_(world.daniel)(
            "POST", _path(APPROVE, version_no=requested["version_no"])
        )
    assert withdrawn.status_code == 200 and _body(withdrawn)["state"] == "withdrawn"
    assert again.status_code in (200, 409)
    assert approve_after.status_code == 409
    assert await _audited(seed, world.tenant, "ai_policy.withdrawn") == [_human(world.margaret)]
    assert await _audited(seed, world.tenant, "ai_policy.approved") == []


async def test_ac37_a_retried_approve_approves_once(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        path = _path(APPROVE, version_no=requested["version_no"])
        first = await as_(world.daniel)("POST", path)
        if stubbed(APPROVE, first):
            return
        again = await as_(world.daniel)("POST", path)
        withdraw = await as_(world.margaret)(
            "POST", _path(WITHDRAW, version_no=requested["version_no"])
        )
    assert first.status_code == 200
    assert again.status_code in (200, 409)
    if again.status_code == 200:
        assert _body(again)["state"] == "published"
    # Nothing leaves `published`.
    assert withdraw.status_code == 409
    assert await _audited(seed, world.tenant, "ai_policy.approved") == [_human(world.daniel)]
    assert await _audited(seed, world.tenant, "ai_policy.withdrawn") == []


async def test_ac37_a_retried_publish_request_opens_one_version(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        again = await as_(world.margaret)(*PUBLISH, json=_publish_body(world.daniel))
        listed = await as_(world.margaret)(*VERSIONS)
    if again.status_code == 201:
        assert _body(again)["version_no"] == requested["version_no"]
    else:
        assert again.status_code == 409
    if not stubbed(VERSIONS, listed):
        waiting = [
            v
            for v in cast(list[dict[str, object]], _body(listed)["items"])
            if v["state"] == "awaiting_approval"
        ]
        assert len(waiting) == 1
    assert await _audited(seed, world.tenant, "ai_policy.publish_requested") == [
        _human(world.margaret)
    ]


# --- AC-39: the effective version on kernel.clock ------------------------------------------------


async def _effective_no(
    as_: Callable[[object], Call], who: AuthContext, at: str | None = None
) -> int | None:
    params = {"engagement_type": "tax_return", **({"at": at} if at else {})}
    response = await as_(who)(*EFFECTIVE, params=params)
    if stubbed(EFFECTIVE, response):
        return None
    assert response.status_code == 200, response.text
    return cast(int, _body(response)["version_no"])


async def test_ac39_the_earlier_version_holds_until_sep_15_and_the_new_one_after(
    world: World, as_: Callable[[object], Call]
) -> None:
    with frozen(REQUESTED_ON):
        before = await _effective_no(as_, world.grace)
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        approved = await as_(world.daniel)(
            "POST", _path(APPROVE, version_no=requested["version_no"])
        )
        if stubbed(APPROVE, approved):
            return
        assert before is not None
        # Published, but not yet effective: "v4 · effective Sep 15".
        assert await _effective_no(as_, world.grace) == before
        assert await _effective_no(as_, world.grace, JUST_BEFORE) == before
        assert await _effective_no(as_, world.grace, JUST_AFTER) == requested["version_no"]
        policy = await as_(world.grace)(*POLICY)
        if not stubbed(POLICY, policy):
            body = _body(policy)
            assert cast(dict[str, object], body["effective"])["version_no"] == before
            assert (
                cast(dict[str, object], body["scheduled"])["version_no"] == requested["version_no"]
            )
    with frozen(datetime(2026, 9, 16, 15, 0, tzinfo=UTC)):
        assert await _effective_no(as_, world.grace) == requested["version_no"]


async def test_ac39_superseded_is_derived_from_the_clock(
    world: World, as_: Callable[[object], Call]
) -> None:
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        approved = await as_(world.daniel)(
            "POST", _path(APPROVE, version_no=requested["version_no"])
        )
        if stubbed(APPROVE, approved):
            return
        early = await as_(world.grace)(*VERSIONS)
        if stubbed(VERSIONS, early):
            return
    with frozen(datetime(2026, 9, 16, 15, 0, tzinfo=UTC)):
        late = await as_(world.grace)(*VERSIONS)

    def superseded(response: httpx.Response) -> dict[int, bool]:
        return {
            cast(int, v["version_no"]): cast(bool, v["superseded"])
            for v in cast(list[dict[str, object]], _body(response)["items"])
            if v["state"] == "published"
        }

    no = cast(int, requested["version_no"])
    assert not any(superseded(early).values())
    assert {k for k, v in superseded(late).items() if v} == {k for k in superseded(late) if k < no}


# --- AC-41: the opt-in and agent stages (SPEC-036 unchanged) -------------------------------------


async def _opt_in_flag(seed: Seeder, tenant: uuid.UUID) -> None:
    """SPEC-036's routes answer 404 until `agents.client_data_optin` is on for the firm."""
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agents.client_data_optin', 'true', 'ac-suite', 'G-02-T22')",
        tenant,
    )


async def test_ac41_only_the_firm_admin_with_a_fresh_factor_opts_in(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    await _opt_in_flag(seed, world.tenant)
    for ctx in (world.margaret, world.felix, world.hannah, _stale(world.grace)):
        response = await as_(ctx)(*OPT_IN_PUT, json={"on": True})
        assert response.status_code == 403, (ctx.firm_role, response.text)
    agent = await as_(_principal(world, "agent"))(*OPT_IN_PUT, json={"on": True})
    assert agent.status_code == 403


async def test_ac41_the_opt_in_records_who_when_and_the_register_version(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    """SPEC-036 AC-3 as it stands. The register (DF-16) may hold no entry yet, in which case the
    opt-in is not available and nothing is recorded."""
    await _opt_in_flag(seed, world.tenant)
    state = await as_(world.grace)(*OPT_IN)
    assert state.status_code == 200, state.text
    response = await as_(world.grace)(*OPT_IN_PUT, json={"on": True})
    if not _body(state)["available"]:
        assert response.status_code in (409, 422), response.text
        assert await _audited(seed, world.tenant, "firm.ai_client_data_opted_in") == []
        return
    assert response.status_code == 200, response.text
    body = _body(response)
    assert body["current"] is True
    assert body["opted_in_by"] == str(world.grace.user_id)
    assert body["opted_in_at"] is not None
    assert await _audited(seed, world.tenant, "firm.ai_client_data_opted_in") == [
        _human(world.grace)
    ]
    policy = await as_(world.grace)(*POLICY)
    if not stubbed(POLICY, policy):
        opt_in = cast(dict[str, dict[str, object]], _body(policy)["immediate"])[
            "client_data_opt_in"
        ]
        assert opt_in["on"] is True and opt_in["register_version"] is not None
    off = await as_(world.grace)(*OPT_IN_PUT, json={"on": False})
    assert off.status_code == 200 and _body(off)["current"] is False


def test_ac41_no_policy_route_promotes_an_agent_or_changes_the_opt_in() -> None:
    """The AI-policy family is exactly the contract's eleven operations: stages are read-only on
    ADM-04 (SPEC-036 Q3) and the opt-in keeps its own route."""
    paths = cast(dict[str, dict[str, object]], json.loads(document())["paths"])
    found = {
        (method.upper(), path)
        for path, ops in paths.items()
        if path.startswith("/v1/firm/ai-policy")
        for method in ops
    }
    assert found == set(ROUTES)


async def test_ac41_each_agent_reads_shadow_or_live_since(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.grace)(*POLICY)
    if stubbed(POLICY, response):
        return
    immediate = cast(dict[str, object], _body(response)["immediate"])
    for stage in cast(list[dict[str, object]], immediate["agent_stages"]):
        assert stage["stage"] in ("shadow", "live")
        assert stage["since"] is not None


# --- AC-42: pause and resume ---------------------------------------------------------------------


@pytest.mark.parametrize("who", ["grace", "felix", "margaret"])
async def test_ac42_ac47_the_admins_and_the_qm_owner_pause_and_resume_audited(
    world: World, as_: Callable[[object], Call], seed: Seeder, who: str
) -> None:
    ctx = cast(AuthContext, getattr(world, who))
    paused = await as_(ctx)(*PAUSE)
    assert paused.status_code == 200, paused.text
    assert _body(paused)["paused_at"] is not None
    # The existing per-firm pause's own action names (SPEC-027, TASK-050); G-02 §4.7 spells them
    # `firm_agents.paused` / `.resumed` but calls them existing (DEC-552).
    assert await _audited(seed, world.tenant, "firm.agents_paused") == [_human(ctx)], (
        await seed.actions(world.tenant)
    )
    policy = await as_(world.grace)(*POLICY)
    if not stubbed(POLICY, policy):
        pause = cast(dict[str, dict[str, object]], _body(policy)["immediate"])["firm_pause"]
        assert pause["paused"] is True
        assert cast(dict[str, object], pause["paused_by"])["user_id"] == str(ctx.user_id)
    resumed = await as_(ctx)(*RESUME)
    assert resumed.status_code == 200, resumed.text
    assert _body(resumed)["paused_at"] is None
    assert await _audited(seed, world.tenant, "firm.agents_resumed") == [_human(ctx)], (
        await seed.actions(world.tenant)
    )


@pytest.mark.parametrize("who", ["daniel", "hannah"])
async def test_ac42_no_one_else_pauses(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    response = await as_(getattr(world, who))(*PAUSE)
    assert response.status_code == 403


async def test_ac42_resume_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    assert (await as_(world.grace)(*PAUSE)).status_code == 200
    response = await as_(_stale(world.grace))(*RESUME)
    assert response.status_code == 403


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_ac42_ac45_the_agent_and_the_system_never_pause_or_resume(
    world: World, as_: Callable[[object], Call], kind: str
) -> None:
    for route in (PAUSE, RESUME):
        response = await as_(_principal(world, kind))(*route)
        assert response.status_code == 403, (kind, route)


# --- AC-43, AC-44: sub-processors and the §7216 lock ---------------------------------------------


async def test_ac43_sub_processors_are_the_registers_and_never_name_the_model_vendor(
    world: World, as_: Callable[[object], Call]
) -> None:
    register = cast(dict[str, list[dict[str, object]]], yaml.safe_load(PROVIDER_TERMS.read_text()))
    names = {cast(str, e["provider"]) for e in register["entries"]} | {
        cast(str, s)
        for e in register["entries"]
        for s in cast(list[object], e.get("subprocessors", []))
    }
    response = await as_(world.grace)(*POLICY)
    if stubbed(POLICY, response):
        return
    body = _body(response)
    rows = cast(list[dict[str, object]], body["sub_processors"])
    assert bool(rows) == bool(register["entries"])
    for row in rows:
        assert any(n in cast(str, row["name"]) for n in names), row["name"]
        assert not (
            "anthropic" in cast(str, row["name"]).lower()
            and "inference" in cast(str, row["purpose"]).lower()
        )
        assert row["trains_on_data"] is False
    if body["model_family"]:
        assert body["model_family"] not in {r["name"] for r in rows}


async def test_ac44_the_7216_consent_and_the_policy_principal_are_on_and_off_and_locked(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.grace)(*POLICY)
    if stubbed(POLICY, response):
        return
    body = _body(response)
    sections = cast(dict[str, dict[str, object]], body["sections"])
    assert sections["client_data"]["require_7216_consent"] is True
    assert sections["client_data"]["client_drafts_enabled"] is False
    assert sections["policy_principal"]["on"] is False
    locks = {
        cast(str, lock["path"]).split("sections.")[-1]: lock["reason"]
        for lock in cast(list[dict[str, object]], body["locks"])
    }
    assert locks.get("client_data.require_7216_consent") == "platform_floor"
    assert locks.get("client_data.client_drafts_enabled") == "platform_floor"
    assert locks.get("governance.trace_retention_years") == "platform_floor"
    assert locks.get("policy_principal.on") == "policy_principal_dormant"
    effective = await as_(world.grace)(*EFFECTIVE, params={"engagement_type": "fs_audit"})
    if not stubbed(EFFECTIVE, effective):
        assert _body(effective)["policy_principal_on"] is False


# --- Tenant isolation ----------------------------------------------------------------------------


async def test_another_firms_partner_cannot_approve_or_see_this_firms_version(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    other = await _firm(seed)
    with frozen(REQUESTED_ON):
        requested = await _request_v_next(as_, world)
        if requested is None:
            return
        no = requested["version_no"]
        approve = await as_(other.daniel)("POST", _path(APPROVE, version_no=no))
        if stubbed(APPROVE, approve):
            return
        theirs = await as_(other.hannah)(*VERSIONS)
    assert approve.status_code == 404
    assert all(
        v["state"] != "awaiting_approval"
        for v in cast(list[dict[str, object]], _body(theirs)["items"])
    )
    assert await _audited(seed, world.tenant, "ai_policy.approved") == []
    assert await _audited(seed, other.tenant, "ai_policy.approved") == []
    assert await _audited(seed, other.tenant, "ai_policy.publish_requested") == []


async def test_an_approver_from_another_firm_is_refused(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    other = await _firm(seed)
    base = await _base(as_, world.margaret)
    if base is None:
        return
    saved = await _save(as_, world.margaret, _with(base, "governance.override_tolerance_pct", 6))
    assert saved is not None and saved.status_code == 200
    with frozen(REQUESTED_ON):
        response = await as_(world.margaret)(*PUBLISH, json=_publish_body(other.daniel))
    if stubbed(PUBLISH, response):
        return
    assert response.status_code in (404, 422), response.text
    assert await _audited(seed, world.tenant, "ai_policy.publish_requested") == []


# --- The flag and the stubs (contract §1) --------------------------------------------------------


def _request(route: Route, world: World) -> tuple[str, str, dict[str, object]]:
    path = route[1].format(version_no=2)
    kwargs: dict[str, object] = {}
    if route == DRAFT_PUT:
        kwargs = {"json": {"sections": _defaults()}, "headers": {"If-Match": "0"}}
    elif route == DRAFT_DELETE:
        kwargs = {"headers": {"If-Match": "0"}}
    elif route == PUBLISH:
        kwargs = {"json": _publish_body(world.daniel)}
    elif route == DECLINE:
        kwargs = {"json": {"reason_code": "needs_changes"}}
    elif route == EFFECTIVE:
        kwargs = {"params": {"engagement_type": "tax_return"}}
    return route[0], path, kwargs


def _holder(world: World, route: Route) -> AuthContext:
    """A person who holds the route's action: Daniel approves, Margaret does the rest."""
    return world.daniel if route in (APPROVE, DECLINE) else world.margaret


@pytest.mark.parametrize("route", sorted(STUBBED), ids=lambda r: f"{r[0]} {r[1]}")
async def test_stub_a_permitted_person_gets_501_not_implemented_with_the_flag_on(
    world: World, as_: Callable[[object], Call], route: Route
) -> None:
    method, path, kwargs = _request(route, world)
    response = await as_(_holder(world, route))(method, path, **kwargs)
    assert response.status_code == 501, response.text
    assert _detail(response) == "not_implemented"


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: f"{r[0]} {r[1]}")
async def test_stub_the_flag_off_answers_404_after_the_matrix(
    seed: Seeder, as_: Callable[[object], Call], route: Route
) -> None:
    off = await _firm(seed, flag=False)
    method, path, kwargs = _request(route, off)
    response = await as_(_holder(off, route))(method, path, **kwargs)
    assert response.status_code == 404, response.text
    # The matrix answers before the flag (security review L1).
    refused = await as_(off.grace if route not in READS else off.client)(method, path, **kwargs)
    assert refused.status_code == (403 if route not in READS else 404)


@pytest.mark.parametrize("kind", ["agent", "system"])
@pytest.mark.parametrize("route", REFUSED_ROUTES)
async def test_ac45_the_agent_and_the_system_are_refused_with_the_flag_off(
    seed: Seeder, as_: Callable[[object], Call], route: Route, kind: str
) -> None:
    off = await _firm(seed, flag=False)
    method, path, kwargs = _request(route, off)
    response = await as_(_principal(off, kind))(method, path, **kwargs)
    assert response.status_code == 403, response.text


# --- AC-45, AC-46: the agent, the system and client principals ----------------------------------


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: f"{r[0]} {r[1]}")
async def test_ac46_a_client_principal_finds_no_policy_route(
    world: World, as_: Callable[[object], Call], route: Route
) -> None:
    method, path, kwargs = _request(route, world)
    response = await as_(world.client)(method, path, **kwargs)
    assert response.status_code == 404


@pytest.mark.parametrize("kind", ["agent", "system"])
@pytest.mark.parametrize("route", REFUSED_ROUTES)
async def test_ac45_the_agent_and_the_system_are_refused_everywhere(
    world: World, as_: Callable[[object], Call], route: Route, kind: str
) -> None:
    """The agent acts for Margaret, who holds every policy action: still refused (INV-1)."""
    method, path, kwargs = _request(route, world)
    response = await as_(_principal(world, kind))(method, path, **kwargs)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("action", WRITES)
def test_ac45_no_policy_write_is_held_by_the_agent_the_system_or_a_client(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert decisions.get(principal, "deny") == "deny", (action, principal)


def test_ac40_the_matrix_rows_are_the_contracts() -> None:
    def allowed(action: str) -> set[str]:
        return {k for k, v in RULES[action].decisions.items() if v == "allow"}

    assert allowed("ai_policy.draft") == {"quality_partner", "security_admin"}
    assert allowed("ai_policy.publish") == {"quality_partner"}
    assert allowed("ai_policy.approve") == {"firm_partner"}
    assert allowed("firm_agents.pause") == {"firm_admin", "security_admin", "quality_partner"}
    assert "firm_admin" in allowed("ai_policy.read")
    assert "firm_admin" not in allowed("ai_policy.draft") | allowed("ai_policy.publish")


@pytest.mark.parametrize("action", ["ai_policy.publish", "ai_policy.approve", "firm_agents.pause"])
def test_ac37_ac42_fresh_mfa_is_asked_and_registered(action: str) -> None:
    assert RULES[action].mfa_recent
    register = cast(
        dict[str, list[dict[str, str]]], yaml.safe_load(FRESH_MFA_REGISTER.read_text())
    )
    assert action in {entry["action"] for entry in register["actions"]}


@pytest.mark.parametrize("action", ["ai_policy.approved", "ai_policy.declined"])
async def test_ac45_the_database_refuses_a_policy_decision_written_as_the_agent(
    world: World, action: str
) -> None:
    agent = TenantContext(world.tenant, "agent", "agent:probe:run", world.margaret.user_id)
    with pytest.raises(Exception, match=r"(?i)human|check|violat|refus"):
        async with uow(agent) as tx:
            tx.record(action, target=Target("ai_policy", uuid.uuid4()), after=Ref(version=2))


# --- The legacy autonomy route (ADR-186 item 7) --------------------------------------------------


# G-02-T24 built the 409 (DEC-712): the strict xfail is lifted.
async def test_ac38_the_legacy_autonomy_route_is_closed_for_a_flag_on_firm(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    response = await as_(world.grace)(*LEGACY_AUTONOMY_PUT, json={"level": 1})
    assert response.status_code == 409, response.text
    assert _detail(response) == "superseded_by_ai_policy"


async def test_the_legacy_autonomy_route_is_unchanged_for_a_flag_off_firm(
    seed: Seeder, as_: Callable[[object], Call]
) -> None:
    off = await _firm(seed, flag=False)
    response = await as_(off.grace)(*LEGACY_AUTONOMY_PUT, json={"level": 1})
    assert response.status_code == 200, response.text
    assert _body(response)["level"] == 1
