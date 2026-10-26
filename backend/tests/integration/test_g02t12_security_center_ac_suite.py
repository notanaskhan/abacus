# ac-test-author: ayushkbhatia
"""G-02-T12 (ADR-078 suite 2, written first under the solo amendment) for the security center:
SPEC-349 AC-15 to AC-30 for ADM-06, with AC-45 to AC-47 where they touch it.

Written from SPEC-349 §5.4 to §5.9 and `docs/contracts/security-center.md`, not from the stubs or
any implementation, over HTTP against the app as the screen calls it: the sign-in dependency
answers as the persona, and the firm turns `security_center.v1`, `compliance.incidents` and
`compliance.firm_export` on in `feature_flag_states`. Incidents are recorded through Q-02's live
route, the only way a firm records one.

**Against the stubs.** `STUBBED` lists the routes still answering 501 (G-02-T11 and Q-02-T38). A
behaviour test on a stubbed route asserts the 501 and stops there; the task that makes a route
live removes it from `STUBBED` (G-02-T14 identity's routes, T18 incidents, T19 the schedule, T20
safeguards, Q-02-T43 the on-demand export), and the full assertions then run. With `STUBBED`
emptied, every behaviour test here fails against the stubs (TASK-1333 records it). Tests that
need no live route run in full now: the matrix, the fresh-MFA register, the database, request
validation (no field turns a locked floor off), wrong-role and stale-factor refusals (the matrix
answers before the stub), client 404 and agent 403 on every route, and the support approval by
`security_admin` on SPEC-012's live routes (DEC-72).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, cast

import httpx
import pytest
import yaml
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.api import create_app
from abacus.api.export_openapi import document
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_connection
from abacus.modules.identity.api import AuthContext, Staff, current_context, current_staff
from abacus.modules.identity.authz.matrix import RULES

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

Route = tuple[str, str]
OVERVIEW: Final = ("GET", "/v1/firm/security")
SIGN_IN: Final = ("PUT", "/v1/firm/security/sign-in")
PORTAL: Final = ("PUT", "/v1/firm/security/portal-sign-in")
EXEMPT: Final = ("PUT", "/v1/firm/security/sso-exempt-account")
SESSIONS: Final = ("GET", "/v1/firm/security/sessions")
SIGN_OUT: Final = ("POST", "/v1/firm/security/sessions/{session_id}/sign-out")
POSTURE: Final = ("GET", "/v1/firm/security/posture")
UNLOCK: Final = ("POST", "/v1/firm/staff/{user_id}/unlock")
SUPPORT: Final = ("GET", "/v1/firm/support-access")
SUPPORT_PUT: Final = ("PUT", "/v1/firm/support-access")
INCIDENTS: Final = ("GET", "/v1/firm/security/incidents")
INCIDENT: Final = ("GET", "/v1/firm/security/incidents/{incident_id}")
TIMELINE: Final = ("POST", "/v1/firm/security/incidents/{incident_id}/timeline")
DECIDE: Final = ("POST", "/v1/firm/security/incidents/{incident_id}/decisions")
SCHEDULE: Final = ("GET", "/v1/firm/data-exports/schedule")
SCHEDULE_PUT: Final = ("PUT", "/v1/firm/data-exports/schedule")
SCHEDULE_APPROVE: Final = ("POST", "/v1/firm/data-exports/schedule/approve")
SAFEGUARDS: Final = ("GET", "/v1/firm/safeguards")
SAFEGUARDS_PUT: Final = ("PUT", "/v1/firm/safeguards")
CONTROL_PUT: Final = ("PUT", "/v1/firm/safeguards/controls/{control_key}")
WISP_PACK: Final = ("POST", "/v1/firm/safeguards/wisp-pack")
# Q-02's on-demand export (compliance-kernel v1.1), which AC-24 exercises.
EXPORTS: Final = ("GET", "/v1/firm/data-exports")
EXPORT_REQUEST: Final = ("POST", "/v1/firm/data-exports")
EXPORT_APPROVE: Final = ("POST", "/v1/firm/data-exports/{export_id}/approve")
ROUTES: Final[tuple[Route, ...]] = (
    OVERVIEW,
    SIGN_IN,
    PORTAL,
    EXEMPT,
    SESSIONS,
    SIGN_OUT,
    POSTURE,
    UNLOCK,
    SUPPORT,
    SUPPORT_PUT,
    INCIDENTS,
    INCIDENT,
    TIMELINE,
    DECIDE,
    SCHEDULE,
    SCHEDULE_PUT,
    SCHEDULE_APPROVE,
    SAFEGUARDS,
    SAFEGUARDS_PUT,
    CONTROL_PUT,
    WISP_PACK,
)
# Routes still answering 501 (the stubs); remove each as its task makes it live.
STUBBED: Final = frozenset({*ROUTES, EXPORTS, EXPORT_REQUEST, EXPORT_APPROVE})

FRESH_MFA_REGISTER: Final = (
    Path(__file__).resolve().parents[3] / "docs" / "architecture" / "fresh-mfa-actions.yaml"
)
# Every write in the family (AC-45, INV-1).
WRITES: Final = (
    "security.manage",
    "session.end",
    "staff.unlock",
    "support_session.manage",
    "incident.manage",
    "incident.decide",
    "firm_export.request",
    "firm_export.approve",
    "firm_export.schedule",
)
REASON: Final = "Investigating an integration settings question for the firm"


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    felix: AuthContext  # security_admin, the Qualified Individual
    grace: AuthContext  # firm_admin
    margaret: AuthContext  # quality_partner, partner level (QM owner)
    daniel: AuthContext  # partner level
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


async def _flags(seed: Seeder, tenant: uuid.UUID) -> None:
    for flag in ("security_center.v1", "compliance.incidents", "compliance.firm_export"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'ac-suite', 'G-02-T12')",
            tenant,
            flag,
        )


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant = await seed.firm()
    await _flags(seed, tenant)
    return World(
        tenant,
        felix=await _member(seed, tenant, "Felix Andersen", firm_role="security_admin"),
        grace=await _member(seed, tenant, "Grace Holloway", firm_role="firm_admin"),
        margaret=await _member(
            seed, tenant, "Margaret Okonkwo", firm_role="quality_partner", level="partner"
        ),
        daniel=await _member(seed, tenant, "Daniel Reyes", firm_role=None, level="partner"),
        hannah=await _member(seed, tenant, "Hannah Leclerc", firm_role=None, level="manager"),
        client=await _member(seed, tenant, "Claire Feld", firm_role=None, kind="client"),
    )


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
    """The agent (acting for Hannah) or the system, at this firm."""
    actor = "agent:probe:run" if kind == "agent" else "system:probe"
    on_behalf_of = world.hannah.user_id if kind == "agent" else None
    return AuthContext(
        TenantContext(world.tenant, kind, actor, on_behalf_of),  # pyright: ignore[reportArgumentType] -- an actor kind code
        world.hannah.user_id,
        uuid.uuid4(),
        None,
        None,
    )


Call = Callable[..., Awaitable[httpx.Response]]


@pytest.fixture
def as_() -> Callable[[object], Call]:
    """`await as_(ctx)("GET", "/v1/firm/security")`: one request as that principal. A `Staff`
    calls the staff issuer's routes (SPEC-012)."""

    def bind(principal: object) -> Call:
        async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
            app = create_app()
            if isinstance(principal, Staff):
                app.dependency_overrides[current_staff] = lambda: principal
            else:
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


def _detail(response: httpx.Response) -> object:
    return cast(dict[str, object], response.json()).get("detail")


async def _audited(seed: Seeder, world: World, action: str) -> list[tuple[str, str]]:
    rows = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
        "ORDER BY seq",
        world.tenant,
        action,
    )
    return [(cast(str, r["actor_kind"]), cast(str, r["actor_id"])) for r in rows]


def _sign_in(**over: object) -> dict[str, object]:
    return {
        "require_sso": False,
        "session_absolute_minutes": 720,
        "session_idle_minutes": 30,
        "version": 0,
        **over,
    }


async def _incident(world: World, as_: Callable[[object], Call]) -> dict[str, object]:
    """Felix records one through Q-02's live route, discovered four days ago."""
    response = await as_(world.felix)(
        "POST",
        "/v1/firm/security/incidents",
        json={
            "title": "Credential-stuffing attempts against client portal sign-in",
            "event_kind": "credential_attack",
            "discovered_at": (datetime.now(UTC) - timedelta(days=4)).isoformat(),
            "consumers_affected": 0,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


# --- AC-15: Require SSO --------------------------------------------------------------------------


async def test_ac15_require_sso_before_a_verified_admin_sso_sign_in_is_refused(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*SIGN_IN, json=_sign_in(require_sso=True))
    if stubbed(SIGN_IN, response):
        return
    assert response.status_code == 409
    assert _detail(response) == "sso_not_verified"


@pytest.mark.parametrize("who", ["grace", "margaret", "hannah"])
async def test_ac15_only_the_qi_changes_firm_sign_in(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    response = await as_(getattr(world, who))(*SIGN_IN, json=_sign_in())
    assert response.status_code == 403


async def test_ac15_firm_sign_in_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(_stale(world.felix))(*SIGN_IN, json=_sign_in())
    assert response.status_code == 403


# --- AC-16: MFA ----------------------------------------------------------------------------------


async def test_ac16_no_request_can_turn_mfa_off(
    world: World, as_: Callable[[object], Call]
) -> None:
    for field in ("mfa_required", "require_mfa", "mfa_enforced"):
        response = await as_(world.felix)(*SIGN_IN, json=_sign_in(**{field: False}))
        assert response.status_code == 422, field


async def test_ac16_mfa_reads_enforced_and_locked_over_the_firms_seats(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    response = await as_(world.felix)(*OVERVIEW)
    if stubbed(OVERVIEW, response):
        return
    mfa = response.json()["mfa"]
    assert mfa["enforced"] is True and mfa["locked"] is True
    seats = await seed.value(
        "SELECT count(*) FROM memberships WHERE tenant_id = $1 AND kind = 'staff' "
        "AND status = 'active'",
        world.tenant,
    )
    assert mfa["seats"] == seats
    assert 0 <= mfa["enrolled"] <= mfa["seats"]
    # Without the "IdP enforces MFA" record, SSO users don't count by the IdP's claim (R-29).
    assert mfa["idp_claim_counted"] is (
        response.json()["sign_in"]["idp_mfa_attested_at"] is not None
    )


# --- AC-17: stricter only ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"), [("session_absolute_minutes", 780), ("session_idle_minutes", 45)]
)
async def test_ac17_a_longer_session_than_the_platform_allows_is_refused(
    world: World, as_: Callable[[object], Call], field: str, value: int
) -> None:
    response = await as_(world.felix)(*SIGN_IN, json=_sign_in(**{field: value}))
    if stubbed(SIGN_IN, response):
        return
    assert response.status_code == 422
    assert _detail(response) == "policy_loosening_refused"
    assert response.json()["facts"]["field"] == field


async def test_ac17_ac47_shorter_limits_are_saved_and_audited_naming_felix(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    response = await as_(world.felix)(
        *SIGN_IN, json=_sign_in(session_absolute_minutes=600, session_idle_minutes=20)
    )
    if stubbed(SIGN_IN, response):
        return
    assert response.status_code == 200
    policy = response.json()
    assert (policy["session_absolute_minutes"], policy["session_idle_minutes"]) == (600, 20)
    assert policy["require_sso"] is False
    stale = await as_(world.felix)(*SIGN_IN, json=_sign_in(version=0))
    assert stale.status_code == 409 and _detail(stale) == "stale_version"
    assert await _audited(seed, world, "security_policy.updated") == [
        ("human", str(world.felix.user_id))
    ]


# --- AC-18: the SSO-exempt account --------------------------------------------------------------


async def test_ac18_designating_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(_stale(world.felix))(
        *EXEMPT, json={"user_id": str(world.grace.user_id), "version": 0}
    )
    assert response.status_code == 403


async def test_ac18_an_account_without_a_hardware_key_cannot_be_exempt(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(
        *EXEMPT, json={"user_id": str(world.hannah.user_id), "version": 0}
    )
    if stubbed(EXEMPT, response):
        return
    assert response.status_code == 409
    assert _detail(response) == "sso_exempt_needs_hardware_key"


async def test_ac18_there_is_at_most_one_exempt_account(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*OVERVIEW)
    if stubbed(OVERVIEW, response):
        return
    exempt = response.json()["sign_in"]["sso_exempt_account"]
    assert exempt is None or isinstance(exempt, dict)


# --- AC-19: the portal floor ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"passwordless_email_code": False},
        {"mfa_floor": False},
        {"failed_code_limit": 5},
        {"lockout_minutes": 5},
    ],
)
async def test_ac19_no_request_can_loosen_a_locked_portal_floor(
    world: World, as_: Callable[[object], Call], extra: dict[str, object]
) -> None:
    response = await as_(world.felix)(
        *PORTAL, json={"session_minutes": 480, "version": 0, **extra}
    )
    assert response.status_code == 422


async def test_ac19_a_portal_session_over_eight_hours_is_refused(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*PORTAL, json={"session_minutes": 600, "version": 0})
    if stubbed(PORTAL, response):
        return
    assert response.status_code == 422
    assert _detail(response) == "policy_loosening_refused"


async def test_ac19_the_portal_floor_reads_locked(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*OVERVIEW)
    if stubbed(OVERVIEW, response):
        return
    portal = response.json()["portal"]
    assert portal["passwordless_email_code"] is True and portal["passwordless_locked"] is True
    assert portal["mfa_floor"] is True and portal["mfa_floor_locked"] is True
    assert (portal["failed_code_limit"], portal["lockout_minutes"]) == (3, 15)
    assert portal["lockout_locked"] is True
    assert portal["session_minutes"] <= 480


# --- AC-20: sessions and unlock ------------------------------------------------------------------


async def _session(seed: Seeder, user: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO auth_sessions (user_id, provider, mfa_at, idle_expires_at, "
            "absolute_expires_at) VALUES ($1, 'workos', now(), now() + interval '30 minutes', "
            "now() + interval '12 hours') RETURNING id",
            user,
        ),
    )


async def test_ac20_sessions_are_the_firms_current_members_only(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    mine = await _session(seed, world.grace.user_id)
    other_firm = await seed.firm()
    outsider = await _member(seed, other_firm, "Someone Elsewhere", firm_role="firm_admin")
    theirs = await _session(seed, outsider.user_id)
    response = await as_(world.felix)(*SESSIONS)
    if stubbed(SESSIONS, response):
        return
    ids = {cast(str, s["id"]) for s in response.json()["items"]}
    assert str(mine) in ids
    assert str(theirs) not in ids
    for row in response.json()["items"]:
        assert {"person", "started_at", "last_seen_at", "ip", "device_label", "mfa_at"} <= set(row)


@pytest.mark.parametrize("who", ["grace", "margaret"])
async def test_ac20_only_the_qi_signs_a_session_out(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    response = await as_(getattr(world, who))("POST", _path(SIGN_OUT, session_id=uuid.uuid4()))
    assert response.status_code == 403


async def test_ac20_signing_out_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(_stale(world.felix))("POST", _path(SIGN_OUT, session_id=uuid.uuid4()))
    assert response.status_code == 403


async def test_ac20_ac47_sign_out_ends_the_session_here_only_and_is_audited(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    session = await _session(seed, world.grace.user_id)
    response = await as_(world.felix)("POST", _path(SIGN_OUT, session_id=session))
    if stubbed(SIGN_OUT, response):
        return
    assert response.status_code == 200
    assert response.json()["session_id"] == str(session)
    listed = await as_(world.felix)(*SESSIONS)
    assert str(session) not in {s["id"] for s in listed.json()["items"]}
    # The person's other firms are unaffected: the global session is not ended.
    ended = await seed.value("SELECT ended_at FROM auth_sessions WHERE id = $1", session)
    assert ended is None
    assert await _audited(seed, world, "session.signed_out") == [
        ("human", str(world.felix.user_id))
    ]


async def test_ac20_a_session_that_is_not_a_members_is_not_found(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    other_firm = await seed.firm()
    outsider = await _member(seed, other_firm, "Someone Elsewhere", firm_role="firm_admin")
    theirs = await _session(seed, outsider.user_id)
    response = await as_(world.felix)("POST", _path(SIGN_OUT, session_id=theirs))
    if stubbed(SIGN_OUT, response):
        return
    assert response.status_code == 404


@pytest.mark.parametrize("who", ["hannah", "margaret"])
async def test_ac20_unlock_is_the_security_or_firm_admins(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    response = await as_(getattr(world, who))("POST", _path(UNLOCK, user_id=world.hannah.user_id))
    assert response.status_code == 403


async def test_ac20_unlock_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(_stale(world.grace))("POST", _path(UNLOCK, user_id=world.hannah.user_id))
    assert response.status_code == 403


@pytest.mark.parametrize("who", ["felix", "grace"])
async def test_ac20_unlock_clears_the_lock_or_says_when_it_ends(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    response = await as_(getattr(world, who))("POST", _path(UNLOCK, user_id=world.hannah.user_id))
    if stubbed(UNLOCK, response):
        return
    assert response.status_code == 200
    lock = response.json()
    assert lock["user_id"] == str(world.hannah.user_id)
    if lock["cleared"]:
        assert lock["locked"] is False
    if lock["locked"]:
        assert lock["unlocks_at"] is not None


# --- AC-21: the register and its clock -----------------------------------------------------------


async def test_ac21_the_register_shows_the_kernel_clock(
    world: World, as_: Callable[[object], Call]
) -> None:
    recorded = await _incident(world, as_)
    response = await as_(world.felix)(*INCIDENTS)
    if stubbed(INCIDENTS, response):
        return
    rows = {cast(str, r["id"]): r for r in response.json()["items"]}
    row = rows[cast(str, recorded["id"])]
    assert row["status"] == "investigating"
    assert (row["clock_day"], row["clock_days"]) == (recorded["clock_day"], 30)
    assert row["ftc_notify_by"] == recorded["ftc_notify_by"]
    assert row["notification_event"] is False
    detail = await as_(world.felix)("GET", _path(INCIDENT, incident_id=recorded["id"]))
    assert detail.status_code == 200
    assert detail.json()["ref"] == recorded["ref"]


@pytest.mark.parametrize("who", ["felix", "grace", "margaret", "daniel"])
async def test_ac21_the_qi_admins_and_partners_read_the_register(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    response = await as_(getattr(world, who))(*INCIDENTS)
    if stubbed(INCIDENTS, response):  # 501 means the matrix let them through
        return
    assert response.status_code == 200


async def test_ac21_a_manager_does_not_read_the_register(
    world: World, as_: Callable[[object], Call]
) -> None:
    assert (await as_(world.hannah)(*INCIDENTS)).status_code == 403


# --- AC-22: two-person decisions ----------------------------------------------------------------


def _decision(kind: str = "close_not_reportable", second: uuid.UUID | None = None) -> object:
    body: dict[str, object] = {"kind": kind}
    if second is not None:
        body["second_decider_user_id"] = str(second)
    return body


async def test_ac22_a_decision_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    recorded = await _incident(world, as_)
    response = await as_(_stale(world.felix))(
        "POST",
        _path(DECIDE, incident_id=recorded["id"]),
        json=_decision(second=world.margaret.user_id),
    )
    assert response.status_code == 403


@pytest.mark.parametrize("who", ["hannah", "grace"])
async def test_ac22_neither_a_manager_nor_a_firm_admin_decides(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    recorded = await _incident(world, as_)
    response = await as_(getattr(world, who))(
        "POST",
        _path(DECIDE, incident_id=recorded["id"]),
        json=_decision(second=world.margaret.user_id),
    )
    assert response.status_code == 403


async def test_ac22_ac47_the_qi_and_a_partner_decide_together_and_both_are_logged(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    recorded = await _incident(world, as_)
    path = _path(DECIDE, incident_id=recorded["id"])
    first = await as_(world.felix)("POST", path, json=_decision(second=world.margaret.user_id))
    if stubbed(DECIDE, first):
        return
    assert first.status_code == 200
    pending = first.json()["pending_decision"]
    assert pending["waiting_for"]["user_id"] == str(world.margaret.user_id)
    assert first.json()["status"] == "investigating"
    # The same person twice, or a partner who was not named, cannot complete it.
    again = await as_(world.felix)("POST", path, json=_decision())
    assert again.status_code == 409 and _detail(again) == "decider_must_differ"
    other = await as_(world.daniel)("POST", path, json=_decision())
    assert other.status_code == 409 and _detail(other) == "decider_must_differ"
    second = await as_(world.margaret)("POST", path, json=_decision())
    assert second.status_code == 200
    decided = second.json()
    assert decided["status"] == "closed"
    assert {d["decided_by"]["user_id"] for d in decided["decisions"]} == {
        str(world.felix.user_id),
        str(world.margaret.user_id),
    }
    assert {d["seat"] for d in decided["decisions"]} == {"partner", "qualified_individual"}
    late = await as_(world.daniel)("POST", path, json=_decision())
    assert late.status_code == 409 and _detail(late) == "already_decided"
    assert await _audited(seed, world, "incident.decision_recorded") == [
        ("human", str(world.felix.user_id)),
        ("human", str(world.margaret.user_id)),
    ]


async def test_ac22_two_partners_cannot_decide_without_the_qi(
    world: World, as_: Callable[[object], Call]
) -> None:
    recorded = await _incident(world, as_)
    response = await as_(world.margaret)(
        "POST",
        _path(DECIDE, incident_id=recorded["id"]),
        json=_decision(second=world.daniel.user_id),
    )
    if stubbed(DECIDE, response):
        return
    assert response.status_code == 422


# --- AC-23: the timeline -------------------------------------------------------------------------

_ENTRY: Final = {
    "occurred_at": "2026-09-10T07:14:00+00:00",
    "code": "sign_ins_blocked",
    "facts": {"failed": 1812, "network": "203.0.113.0/24"},
}


def test_ac23_no_route_edits_or_removes_a_timeline_entry() -> None:
    paths = cast(dict[str, dict[str, object]], json.loads(document())["paths"])
    for path, ops in paths.items():
        if "/timeline" in path:
            assert set(ops) == {"post"}, path


async def test_ac23_only_the_qi_appends_to_the_timeline(
    world: World, as_: Callable[[object], Call]
) -> None:
    recorded = await _incident(world, as_)
    response = await as_(world.margaret)(
        "POST", _path(TIMELINE, incident_id=recorded["id"]), json=_ENTRY
    )
    assert response.status_code == 403


async def test_ac23_an_entry_is_appended_and_attributed(
    world: World, as_: Callable[[object], Call]
) -> None:
    recorded = await _incident(world, as_)
    response = await as_(world.felix)(
        "POST", _path(TIMELINE, incident_id=recorded["id"]), json=_ENTRY
    )
    if stubbed(TIMELINE, response):
        return
    assert response.status_code == 201
    assert response.json()["author"]["user_id"] == str(world.felix.user_id)
    assert response.json()["source"] == "firm"
    detail = await as_(world.felix)("GET", _path(INCIDENT, incident_id=recorded["id"]))
    assert [e["id"] for e in detail.json()["timeline"]][-1] == response.json()["id"]
    # Reminders on days 20, 25 and 29 of the clock.
    assert len(detail.json()["reminders_on"]) == 3


@pytest.mark.parametrize(
    "statement",
    ["UPDATE security_incidents SET title = 'x'", "DELETE FROM security_incidents"],
)
async def test_ac23_an_incidents_facts_cannot_be_rewritten_or_removed(
    world: World, as_: Callable[[object], Call], statement: str
) -> None:
    await _incident(world, as_)
    with pytest.raises(DBAPIError):
        async with tenant_connection(world.felix.tenant) as conn:
            await conn.execute(text(statement))


# --- AC-24: the on-demand export (Q-02's routes) ----------------------------------------------


def test_ac24_the_on_demand_export_is_the_qis_and_a_partner_approves_with_fresh_factors() -> None:
    request, approve = RULES["firm_export.request"], RULES["firm_export.approve"]
    assert request.mfa_recent and approve.mfa_recent
    assert {k for k, v in request.decisions.items() if v == "allow"} == {"security_admin"}
    assert {"security_admin", "firm_partner"} <= {
        k for k, v in approve.decisions.items() if v == "allow"
    }


async def test_ac24_ac47_felix_requests_and_only_another_person_approves(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    requested = await as_(world.felix)(
        *EXPORT_REQUEST,
        json={"approver_user_id": str(world.margaret.user_id)},
        headers={"Idempotency-Key": "g02t12-export"},
    )
    if stubbed(EXPORT_REQUEST, requested):
        return
    assert requested.status_code == 202
    export = requested.json()
    assert export["status"] == "awaiting_approval"
    assert export["approver"]["user_id"] == str(world.margaret.user_id)
    path = _path(EXPORT_APPROVE, export_id=export["id"])
    own = await as_(world.felix)("POST", path)
    assert own.status_code == 409 and _detail(own) == "approver_must_differ"
    approved = await as_(world.margaret)("POST", path)
    if stubbed(EXPORT_APPROVE, approved):
        return
    assert approved.status_code == 200
    assert await _audited(seed, world, "firm_export.requested") == [
        ("human", str(world.felix.user_id))
    ]


# --- AC-25: the schedule's dual approval ---------------------------------------------------------

_SCHEDULE: Final = {
    "contents": ["clients", "entities", "files", "workpapers", "returns", "closes", "audit_log"],
    "version": 0,
}


@pytest.mark.parametrize("who", ["margaret", "grace"])
async def test_ac25_only_the_qi_sets_the_schedule(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    response = await as_(getattr(world, who))(*SCHEDULE_PUT, json=_SCHEDULE)
    assert response.status_code == 403


async def test_ac25_setting_the_schedule_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(_stale(world.felix))(*SCHEDULE_PUT, json=_SCHEDULE)
    assert response.status_code == 403


async def test_ac25_a_manager_neither_reads_nor_approves_the_schedule(
    world: World, as_: Callable[[object], Call]
) -> None:
    assert (await as_(world.hannah)(*SCHEDULE)).status_code == 403
    assert (await as_(world.hannah)(*SCHEDULE_APPROVE)).status_code == 403


async def test_ac25_the_schedule_runs_only_after_the_qi_and_a_partner_approve(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    put = await as_(world.felix)(*SCHEDULE_PUT, json=_SCHEDULE)
    if stubbed(SCHEDULE_PUT, put):
        return
    assert put.status_code == 200
    assert put.json()["status"] == "pending_approval"
    assert (put.json()["cadence"], put.json()["day_of_month"], put.json()["local_time"]) == (
        "monthly",
        1,
        "02:00",
    )
    felix = await as_(world.felix)(*SCHEDULE_APPROVE)
    assert felix.status_code == 200 and felix.json()["status"] == "pending_approval"
    twice = await as_(world.felix)(*SCHEDULE_APPROVE)
    assert twice.status_code == 409 and _detail(twice) == "approver_must_differ"
    margaret = await as_(world.margaret)(*SCHEDULE_APPROVE)
    assert margaret.status_code == 200
    schedule = margaret.json()
    assert schedule["status"] == "active"
    assert {a["seat"] for a in schedule["approvals"]} == {"security_admin", "partner"}
    assert {a["approved_by"]["user_id"] for a in schedule["approvals"]} == {
        str(world.felix.user_id),
        str(world.margaret.user_id),
    }
    # A change takes it back to waiting for both.
    changed = await as_(world.felix)(*SCHEDULE_PUT, json={**_SCHEDULE, "version": 1})
    assert changed.json()["status"] == "pending_approval"
    assert len(await _audited(seed, world, "firm_export_schedule.approved")) == 2


async def test_ac25_the_history_tray_is_q02s_list(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.felix)(*EXPORTS)
    if stubbed(EXPORTS, response):
        return
    assert response.status_code == 200
    assert len(response.json()["items"]) <= 12


# --- AC-26: residency and retention --------------------------------------------------------------


async def test_ac26_residency_comes_from_the_firm_and_is_locked(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    response = await as_(world.felix)(*OVERVIEW)
    if stubbed(OVERVIEW, response):
        return
    residency = response.json()["residency"]
    region = await seed.value("SELECT region FROM firms WHERE id = $1", world.tenant)
    assert residency["region"] == region
    assert residency["ai_inference"] == "us_only"
    assert residency["locked"] is True


def test_ac26_retention_is_never_written_from_the_security_center() -> None:
    paths = cast(dict[str, dict[str, object]], json.loads(document())["paths"])
    for path in paths:
        if path.startswith(("/v1/firm/security", "/v1/firm/safeguards")):
            assert "retention" not in path, path
            assert "hold" not in path, path


# --- AC-27: safeguards ---------------------------------------------------------------------------


def test_ac27_safeguards_edits_are_the_security_admins_alone() -> None:
    manage = RULES["security.manage"]
    assert {k for k, v in manage.decisions.items() if v == "allow"} == {"security_admin"}
    assert manage.mfa_recent


@pytest.mark.parametrize(
    ("route", "body"),
    [
        (SAFEGUARDS_PUT, {"version": 0}),
        (CONTROL_PUT, {"status": "evidenced"}),
        (WISP_PACK, None),
    ],
)
@pytest.mark.parametrize("who", ["margaret", "grace"])
async def test_ac27_partners_and_firm_admins_do_not_edit_safeguards(
    world: World, as_: Callable[[object], Call], route: Route, body: object, who: str
) -> None:
    path = _path(route, control_key="annual_penetration_test")
    kwargs: dict[str, object] = {} if body is None else {"json": body}
    response = await as_(getattr(world, who))(route[0], path, **kwargs)
    assert response.status_code == 403


async def test_ac27_the_safeguards_record_counts_its_open_controls(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(world.margaret)(*SAFEGUARDS)
    if stubbed(SAFEGUARDS, response):
        return
    record = response.json()
    assert 0 <= record["controls_evidenced"] <= record["controls_total"]
    assert len(record["open_controls"]) == record["controls_total"] - record["controls_evidenced"]
    assert all(c["status"] == "open" for c in record["open_controls"])


async def test_ac27_ac47_the_wisp_pack_is_prepared_and_audited(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    response = await as_(world.felix)(*WISP_PACK)
    if stubbed(WISP_PACK, response):
        return
    assert response.status_code == 202
    assert response.json()["requested_by"]["user_id"] == str(world.felix.user_id)
    assert await _audited(seed, world, "wisp_pack.prepared") == [
        ("human", str(world.felix.user_id))
    ]


# --- AC-28: support access -----------------------------------------------------------------------


def _staff() -> Staff:
    return Staff(uuid.uuid4(), f"staff-{uuid.uuid4().hex[:8]}", datetime.now(UTC))


async def _support_request(
    world: World, as_: Callable[[object], Call], staff: Staff
) -> httpx.Response:
    return await as_(staff)(
        "POST",
        "/v1/support/sessions",
        json={
            "firm_id": str(world.tenant),
            "reason": REASON,
            "scope": "metadata",
            "duration_minutes": 60,
        },
    )


@pytest.mark.parametrize("who", ["hannah", "margaret"])
async def test_ac28_the_switch_is_the_firm_or_security_admins(
    world: World, as_: Callable[[object], Call], who: str
) -> None:
    response = await as_(getattr(world, who))(
        *SUPPORT_PUT, json={"allow_support_requests": False, "version": 0}
    )
    assert response.status_code == 403


async def test_ac28_the_switch_needs_a_fresh_second_factor(
    world: World, as_: Callable[[object], Call]
) -> None:
    response = await as_(_stale(world.grace))(
        *SUPPORT_PUT, json={"allow_support_requests": False, "version": 0}
    )
    assert response.status_code == 403


async def test_ac28_dec72_the_qi_approves_and_revokes_a_support_session(
    world: World, as_: Callable[[object], Call]
) -> None:
    requested = await _support_request(world, as_, _staff())
    assert requested.status_code == 201, requested.text
    session = requested.json()["id"]
    stale = await as_(_stale(world.felix))("POST", f"/v1/support-sessions/{session}/approve")
    assert stale.status_code == 403
    granted = await as_(world.felix)("POST", f"/v1/support-sessions/{session}/approve")
    assert granted.status_code == 200, granted.text
    assert granted.json()["status"] == "active"
    assert granted.json()["expires_at"] is not None  # "Granted until 11:40 AM"
    revoked = await as_(world.felix)("POST", f"/v1/support-sessions/{session}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"


async def test_ac28_switched_off_refuses_new_requests_and_keeps_granted_ones(
    world: World, as_: Callable[[object], Call]
) -> None:
    staff = _staff()
    requested = await _support_request(world, as_, staff)
    session = requested.json()["id"]
    granted = await as_(world.grace)("POST", f"/v1/support-sessions/{session}/approve")
    assert granted.status_code == 200
    off = await as_(world.felix)(
        *SUPPORT_PUT, json={"allow_support_requests": False, "version": 0}
    )
    if stubbed(SUPPORT_PUT, off):
        return
    assert off.status_code == 200 and off.json()["allow_support_requests"] is False
    refused = await _support_request(world, as_, _staff())
    assert refused.status_code == 409
    assert _detail(refused) == "support_requests_disabled"
    listed = await as_(world.felix)("GET", "/v1/support-sessions")
    kept = next(s for s in listed.json() if s["id"] == session)
    assert kept["status"] == "active"
    assert kept["expires_at"] == granted.json()["expires_at"]


# --- AC-29: Margaret reads, Felix manages --------------------------------------------------------


async def test_ac29_margaret_reads_the_screen_and_may_approve_exports_but_not_manage(
    world: World, as_: Callable[[object], Call]
) -> None:
    assert (await as_(world.margaret)(*SIGN_IN, json=_sign_in())).status_code == 403
    assert (await as_(world.margaret)(*SCHEDULE_PUT, json=_SCHEDULE)).status_code == 403
    # The matrix lets her through to approve (501 while stubbed; never 403).
    approve = await as_(world.margaret)(*SCHEDULE_APPROVE)
    assert stubbed(SCHEDULE_APPROVE, approve) or approve.status_code != 403
    response = await as_(world.margaret)(*OVERVIEW)
    if stubbed(OVERVIEW, response):  # 501: the matrix let her through to read
        return
    actions = set(response.json()["actions"])
    assert "security.manage" not in actions
    assert {"security.read", "firm_export.approve"} <= actions


# --- AC-30: posture ------------------------------------------------------------------------------


async def test_ac30_posture_agrees_with_the_fieldsets(
    world: World, as_: Callable[[object], Call]
) -> None:
    await _incident(world, as_)
    posture = await as_(world.felix)(*POSTURE)
    if stubbed(POSTURE, posture):
        return
    facts = posture.json()
    overview = (await as_(world.felix)(*OVERVIEW)).json()
    incidents = (await as_(world.felix)(*INCIDENTS)).json()
    safeguards = (await as_(world.felix)(*SAFEGUARDS)).json()
    assert facts["sso_enforced"] == overview["sign_in"]["require_sso"]
    assert (facts["mfa_enrolled"], facts["mfa_seats"]) == (
        overview["mfa"]["enrolled"],
        overview["mfa"]["seats"],
    )
    assert facts["residency_region"] == overview["residency"]["region"]
    assert facts["open_incidents"] == sum(
        1 for i in incidents["items"] if i["status"] == "investigating"
    )
    assert facts["pub4557_open"] == safeguards["controls_total"] - safeguards["controls_evidenced"]


# --- AC-45, AC-46: the agent, the system and client principals ----------------------------------

_BODIES: Final[dict[Route, object]] = {
    SIGN_IN: _sign_in(),
    PORTAL: {"session_minutes": 480, "version": 0},
    EXEMPT: {"user_id": None, "version": 0},
    SUPPORT_PUT: {"allow_support_requests": True, "version": 0},
    TIMELINE: _ENTRY,
    DECIDE: {"kind": "close_not_reportable"},
    SCHEDULE_PUT: _SCHEDULE,
    SAFEGUARDS_PUT: {"version": 0},
    CONTROL_PUT: {"status": "evidenced"},
}


def _request(route: Route) -> tuple[str, str, dict[str, object]]:
    path = route[1].format(
        session_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        incident_id=uuid.uuid4(),
        control_key="annual_penetration_test",
    )
    body = _BODIES.get(route)
    return route[0], path, ({} if body is None else {"json": body})


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: f"{r[0]} {r[1]}")
async def test_ac46_a_client_principal_finds_no_security_route(
    world: World, as_: Callable[[object], Call], route: Route
) -> None:
    method, path, kwargs = _request(route)
    response = await as_(world.client)(method, path, **kwargs)
    assert response.status_code == 404


@pytest.mark.parametrize("kind", ["agent", "system"])
@pytest.mark.parametrize("route", ROUTES, ids=lambda r: f"{r[0]} {r[1]}")
async def test_ac45_the_agent_and_the_system_are_refused_everywhere(
    world: World, as_: Callable[[object], Call], route: Route, kind: str
) -> None:
    method, path, kwargs = _request(route)
    response = await as_(_principal(world, kind))(method, path, **kwargs)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("action", WRITES)
def test_ac45_no_write_is_held_by_the_agent_the_system_or_a_client(action: str) -> None:
    decisions = RULES[action].decisions
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert decisions.get(principal, "deny") == "deny", (action, principal)


@pytest.mark.parametrize(
    "action",
    [
        "security.manage",
        "session.end",
        "staff.unlock",
        "incident.decide",
        "firm_export.request",
        "firm_export.approve",
        "firm_export.schedule",
    ],
)
def test_ac45_every_decision_and_policy_write_asks_for_a_fresh_second_factor(action: str) -> None:
    assert RULES[action].mfa_recent
    register = cast(
        dict[str, list[dict[str, str]]], yaml.safe_load(FRESH_MFA_REGISTER.read_text())
    )
    assert action in {entry["action"] for entry in register["actions"]}
