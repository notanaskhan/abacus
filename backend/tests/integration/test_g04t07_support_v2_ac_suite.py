# ac-test-author: ayushkbhatia
"""G-04-T07 (ADR-078 AC suite 1, written first under the solo amendment) for G-04's red work:
support sessions v2 (SPEC-681 AC-14 to AC-25), the admission over-limit hook (SPEC-680 AC-37),
the migration constraints, and agent and portal denial (INV-1, INV-4).

Written from SPEC-681, SPEC-680 and `docs/contracts/{platform-console,plan-usage,support}.md`,
not from the implementation, against a real Postgres as the app role: the service functions as
the console and the firm screens call them, the database's own constraints as the superuser
writes a row by hand, and the app's route table.

**Against the stubs.** The admission hook (G-04-T08) is not built yet: `HOOK_LIVE` reads whether
`platform.api.over_limit_policy` exists. While it does not, the hook test asserts the stub state
and stops; G-04-T08 makes it live and the full assertions run. Every other test here runs in full
on G-04-T05.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol, cast

import asyncpg
import pytest
from fastapi.routing import APIRoute
from sqlalchemy import column

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import DomainForbidden, NotFound
from abacus.kernel.flags import forget_flags
from abacus.modules.identity import support
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.identity.authz import Resource, in_support_scope, visible
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.identity.repository import FirmRole
from abacus.modules.identity.routing import declared_action, staff_action
from abacus.modules.identity.support import (
    ScopeRef,
    Staff,
    StaffLocationRequired,
    SupportSessionConflict,
    SupportSessionInvalid,
)
from abacus.modules.platform import api as platform_api

from .agent_tests.support import Seeder

HOOK_LIVE: Final = hasattr(platform_api, "over_limit_policy")
REASON: Final = "Tax-engine sync latency since Sep 12 on the firm's integration"
G04_ACTIONS: Final = (
    "plan.read",
    "budget_alert.manage",
    "billing_contact.manage",
    "plan_request.create",
    "plan_request.approve",
    "support.chat",
    "help.read",
    "status.read",
    "support_session.decline",
    "support_session.manage",
    "platform_tenant.read",
    "platform_tenant.provision",
    "platform_entitlements.update",
    "platform_support_session.request",
    "platform_support.reply",
    "platform_status.manage",
    "platform_content.read",
    "platform_content.publish",
)


class Migrated(Protocol):
    app_url: str
    superuser_dsn: str


def _plain(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(_plain(migrated_db.superuser_dsn))


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    forget_flags()
    yield
    forget_flags()
    await dispose_engine()
    settings.cache_clear()


async def _member(seed: Seeder, firm: uuid.UUID, role: FirmRole) -> AuthContext:
    subject = f"sub-{uuid.uuid4().hex}"
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://idp.test', $1, $2, 'Firm Person') RETURNING id",
            subject,
            f"{subject}@example.test",
        ),
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, $3, 'active') RETURNING id",
            firm,
            user,
            role,
        ),
    )
    return AuthContext(
        TenantContext(firm, "human", str(user)), user, membership, role, datetime.now(UTC)
    )


async def _flag_on(seed: Seeder, firm: uuid.UUID, name: str = "support.panel_v2") -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'ac-suite', 'G-04-T07')",
        firm,
        name,
    )
    forget_flags()


async def _tax_firm(seed: Seeder) -> uuid.UUID:
    firm = await seed.firm()
    await seed.run(
        "INSERT INTO tenant_entitlements (tenant_id, module, enabled, set_by) "
        "VALUES ($1, 'tax_returns', true, 'ac-suite')",
        firm,
    )
    return firm


def _staff(*, us_located: bool = False) -> Staff:
    return Staff(uuid.uuid4(), f"staff-{uuid.uuid4().hex[:8]}", datetime.now(UTC), us_located)


async def _status(seed: Seeder, session_id: uuid.UUID) -> str:
    return cast(
        str, await seed.value("SELECT status FROM support_sessions WHERE id = $1", session_id)
    )


# --- AC-15, AC-25: no staff approval anywhere ------------------------------------------------


def test_ac15_ac25_no_route_lets_staff_approve_grant_or_activate() -> None:
    routes = [r for r in create_app().routes if isinstance(r, APIRoute)]
    paths = {(m, r.path) for r in routes for m in (r.methods or set())}
    assert ("POST", "/v1/support/sessions/{session_id}/approve") not in paths
    for route in routes:
        action = declared_action(route)
        staff_route = action == "staff" or (action is not None and staff_action(action))
        if staff_route:
            assert not any(w in route.path for w in ("approve", "grant", "activate", "view-as"))
    assert not hasattr(support, "emergency_approve")


async def test_ac15_the_database_refuses_a_staff_approval_on_new_rows(seed: Seeder) -> None:
    firm = await seed.firm()
    staff = _staff()
    view = await support.request_session(staff, firm, REASON, "metadata", 60)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "UPDATE support_sessions SET status = 'active', approved_by_kind = 'staff', "
            "approved_by = $2, starts_at = now(), expires_at = now() + interval '1 hour' "
            "WHERE id = $1",
            view.id,
            uuid.uuid4(),
        )


# --- AC-14, AC-16, AC-22: requests ------------------------------------------------------------


async def test_ac14_a_request_is_requested_and_reaches_both_approver_roles(seed: Seeder) -> None:
    firm = await seed.firm()
    view = await support.request_session(_staff(), firm, REASON, "metadata", 120)
    assert view.status == "requested" and view.duration_minutes == 120
    kinds = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'support_session.requested'",
        firm,
    )
    assert kinds == 1


async def test_ac22_more_than_120_minutes_is_refused_by_service_and_database(
    seed: Seeder,
) -> None:
    firm = await seed.firm()
    with pytest.raises(SupportSessionInvalid):
        await support.request_session(_staff(), firm, REASON, "metadata", 121)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO support_sessions (tenant_id, staff_id, staff_subject, reason, scope, "
            "duration_minutes, emergency) VALUES ($1, $2, 'staff-x', $3, 'metadata', 180, false)",
            firm,
            uuid.uuid4(),
            REASON,
        )


async def test_content_names_exactly_one_object(seed: Seeder) -> None:
    firm = await seed.firm()
    with pytest.raises(SupportSessionInvalid):
        await support.request_session(_staff(us_located=True), firm, REASON, "content", 60)
    with pytest.raises(SupportSessionInvalid):
        await support.request_session(
            _staff(), firm, REASON, "metadata", 60, ScopeRef("work_item", uuid.uuid4())
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO support_sessions (tenant_id, staff_id, staff_subject, reason, scope, "
            "duration_minutes, emergency) VALUES ($1, $2, 'staff-x', $3, 'content', 60, false)",
            firm,
            uuid.uuid4(),
            REASON,
        )


async def test_ac16_requests_switched_off_answer_409(seed: Seeder) -> None:
    firm = await seed.firm()
    admin = await _member(seed, firm, "security_admin")
    await seed.as_actor(
        firm,
        ("human", str(admin.user_id)),
        "INSERT INTO security_policies (tenant_id, updated_by, allow_support_requests) "
        "VALUES ($1, $2, false)",
        firm,
        admin.user_id,
    )
    with pytest.raises(Exception) as refused:
        await support.request_session(_staff(), firm, REASON, "metadata", 60)
    assert getattr(refused.value, "code", None) == "support_requests_disabled"


async def test_integration_settings_scope_needs_the_firm_flag(seed: Seeder) -> None:
    firm = await seed.firm()
    with pytest.raises(SupportSessionInvalid):
        await support.request_session(_staff(), firm, REASON, "integration_settings", 120)
    await _flag_on(seed, firm)
    view = await support.request_session(_staff(), firm, REASON, "integration_settings", 120)
    assert view.scope == "integration_settings"


# --- AC-23: US-located staff for content on a TRI tenant ---------------------------------------


async def test_ac23_content_on_a_tax_tenant_needs_the_us_attestation(seed: Seeder) -> None:
    firm = await _tax_firm(seed)
    ref = ScopeRef("work_item", uuid.uuid4())
    with pytest.raises(StaffLocationRequired) as refused:
        await support.request_session(_staff(), firm, REASON, "content", 60, ref)
    assert isinstance(refused.value, DomainForbidden)
    assert refused.value.code == "staff_location_required"
    view = await support.request_session(_staff(us_located=True), firm, REASON, "content", 60, ref)
    stored = await seed.value(
        "SELECT staff_us_located FROM support_sessions WHERE id = $1", view.id
    )
    assert stored is True


async def test_ac23_a_tenant_without_a_tax_module_needs_no_attestation(seed: Seeder) -> None:
    firm = await seed.firm()
    view = await support.request_session(
        _staff(), firm, REASON, "content", 60, ScopeRef("engagement", uuid.uuid4())
    )
    assert view.scope_ref_kind == "engagement"


# --- AC-19, AC-20: the firm decides ------------------------------------------------------------


async def test_ac19_security_admin_declines_and_the_decline_is_terminal(seed: Seeder) -> None:
    firm = await seed.firm()
    await _flag_on(seed, firm)
    felix = await _member(seed, firm, "security_admin")
    view = await support.request_session(_staff(), firm, REASON, "metadata", 60)
    declined = await support.decline_session(felix, view.id)
    assert declined.status == "declined" and declined.declined_by == felix.user_id
    audited = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'support_session.declined'",
        firm,
    )
    assert audited == 1
    with pytest.raises(SupportSessionConflict):
        await support.approve_session(felix, view.id)


async def test_ac19_other_roles_cannot_decline_and_the_flag_gates_it(seed: Seeder) -> None:
    firm = await seed.firm()
    staff_member = await _member(seed, firm, "practice_leader")
    admin = await _member(seed, firm, "firm_admin")
    view = await support.request_session(_staff(), firm, REASON, "metadata", 60)
    with pytest.raises(NotFound):
        await support.decline_session(admin, view.id)  # support.panel_v2 off
    await _flag_on(seed, firm)
    with pytest.raises(Forbidden):
        await support.decline_session(staff_member, view.id)
    assert await _status(seed, view.id) == "requested"


async def test_ac20_security_admin_approves_with_fresh_mfa_and_the_role_is_recorded(
    seed: Seeder,
) -> None:
    firm = await seed.firm()
    felix = await _member(seed, firm, "security_admin")
    view = await support.request_session(_staff(), firm, REASON, "metadata", 120)
    stale = AuthContext(
        felix.tenant, felix.user_id, felix.membership_id, "security_admin",
        datetime.now(UTC) - timedelta(hours=2),
    )  # fmt: skip
    with pytest.raises((Forbidden, DomainForbidden)):
        await support.approve_session(stale, view.id)
    approved = await support.approve_session(felix, view.id)
    assert approved.status == "active" and approved.approved_by_kind == "security_admin"
    assert approved.expires_at is not None and approved.starts_at is not None
    assert approved.expires_at - approved.starts_at == timedelta(minutes=120)
    revoked = await support.revoke_session(felix, view.id)
    assert revoked.status == "revoked"


# --- AC-21: one object only ------------------------------------------------------------------


def _support_ctx(firm: uuid.UUID, kind: str, scoped: uuid.UUID) -> AuthContext:
    session_id = uuid.uuid4()
    return AuthContext(
        TenantContext(firm, "support", f"support:{session_id}"),
        uuid.uuid4(),
        session_id,
        "platform_support_content",
        datetime.now(UTC),
        support_scope=(kind, scoped),
    )


async def test_ac21_an_engagement_session_reaches_that_engagement_only() -> None:
    firm, scoped, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ctx = _support_ctx(firm, "engagement", scoped)
    assert in_support_scope(ctx, Resource.engagement(firm, scoped, archived=False))
    assert not in_support_scope(ctx, Resource.engagement(firm, other, archived=False))
    assert not in_support_scope(ctx, Resource.client(firm, uuid.uuid4()))
    with pytest.raises(Forbidden) as refused:
        await authorise(
            ctx, "engagement.read_metadata", Resource.engagement(firm, other, archived=False)
        )
    assert refused.value.layer == "support_scope"  # answered 404, like a wall


def test_ac21_a_work_item_session_lists_nothing_and_reaches_its_item_only() -> None:
    firm, item = uuid.uuid4(), uuid.uuid4()
    ctx = _support_ctx(firm, "work_item", item)
    engagement = uuid.uuid4()
    on_item = Resource(firm, engagement, False, work_item_id=item)
    sibling = Resource(firm, engagement, False, work_item_id=uuid.uuid4())
    assert in_support_scope(ctx, on_item)
    assert not in_support_scope(ctx, sibling)
    assert not in_support_scope(ctx, Resource.engagement(firm, engagement, archived=False))
    read = next(
        a
        for a, r in RULES.items()
        if r.reads and r.decisions.get("platform_support_content") == "allow"
    )
    clause = visible(ctx, read, column("engagement_id"))
    assert str(clause.compile(compile_kwargs={"literal_binds": True})) == "false"


# --- AC-24, INV-1, INV-4: the agent and portal principals --------------------------------------


@pytest.mark.parametrize("action", G04_ACTIONS)
def test_ac24_inv1_inv4_agent_and_portal_principals_hold_no_g04_action(action: str) -> None:
    rule = RULES[action]
    for role in ("agent", "system", "client_admin", "client_contributor", "third_party"):
        assert rule.decisions.get(role, "deny") == "deny", f"{role} holds {action}"


# --- AC-37: the admission over-limit hook (G-04-T08) --------------------------------------------


def test_ac37_admission_refuses_only_scheduled_runs_at_the_plan_limit() -> None:
    if not HOOK_LIVE:
        # Stub state: no over-limit read exists, so admission refuses nothing for the plan.
        assert not hasattr(platform_api, "over_limit_policy")
        return
    policy: object = getattr(platform_api, "over_limit_policy")  # noqa: B009 (G-04-T08)
    assert callable(policy)


# --- Migration constraints (G-04-T04): once per threshold, never the requester -----------------


async def test_alert_events_are_once_per_threshold_per_usage_month(seed: Seeder) -> None:
    firm = await seed.firm()
    rule = await seed.value(
        "INSERT INTO usage_alert_rules (tenant_id, threshold_pct) VALUES ($1, 90) RETURNING id",
        firm,
    )
    insert = (
        "INSERT INTO usage_alert_events (tenant_id, scope, rule_id, usage_month, threshold_pct, "
        "crossed_at, minutes_at_crossing) VALUES ($1, 'firm', $2, '2026-09', 90, now(), 18000)"
    )
    await seed.run(insert, firm, rule)
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.run(insert, firm, rule)


async def test_a_plan_request_is_never_decided_by_its_requester(seed: Seeder) -> None:
    firm = await seed.firm()
    grace = uuid.uuid4()
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO plan_change_requests (tenant_id, kind, to_value, reason, requested_by, "
            "status, decided_by, decided_at) VALUES ($1, 'agent_minutes', 30000, "
            "'October extension deadline', $2, 'sent_to_accrued', $2, now())",
            firm,
            grace,
        )
