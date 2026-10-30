"""The outcome of `authorise` for one (action, human role), with every layer but the matrix's
satisfied: tenancy, no walls, the role held, independence confirmed, fresh MFA, a reason, no
firm overrides or settings, and no facts registered for the matrix conditions (which therefore
deny, fail closed). Used by the generated `test_permission_matrix_generated.py` (Q-02-T13)."""

from __future__ import annotations

import uuid
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    TargetFacts,
    authorise,
)
from abacus.modules.identity.authz.conditions import LOOKUPS
from abacus.modules.identity.authz.matrix import FUNCTIONS
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
    Actor,
    system_context_for_run,
)
from abacus.modules.identity.repository import FirmPolicy, FirmRole

FIRM_ROLES = frozenset({"firm_admin", "practice_leader", "quality_partner", "security_admin"})
REASON = "documented in the working paper"
Outcome = Literal["allow", "deny"]


def arrange(monkeypatch: pytest.MonkeyPatch, role: str) -> tuple[AuthContext, Resource]:
    async def none(*_: object) -> frozenset[uuid.UUID]:
        return frozenset()

    async def held(*_: object) -> str | None:
        return None if role in FIRM_ROLES else role

    async def confirmed(*_: object) -> bool:
        return True

    async def policy(*_: object) -> FirmPolicy:
        return FirmPolicy({}, frozenset())

    monkeypatch.setattr(authz, "walled_clients", none)
    monkeypatch.setattr(authz, "engagement_role", held)
    monkeypatch.setattr(authz, "engagement_roles_in_firm", none)
    monkeypatch.setattr(authz, "firm_policy", policy)

    async def not_ended(*_: object) -> bool:
        return False

    monkeypatch.setattr(authz, "access_has_ended", not_ended)
    monkeypatch.setattr(authz, "_independence", (None, confirmed))
    for field in fields(LOOKUPS):
        monkeypatch.setattr(LOOKUPS, field.name, None)
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        cast(FirmRole | None, role if role in FIRM_ROLES else None),
        datetime.now(UTC) - timedelta(minutes=1),
    )
    if role in FIRM_ROLES:
        return ctx, Resource.firm(ctx.tenant_id)
    return ctx, Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)


async def outcome(monkeypatch: pytest.MonkeyPatch, action: str, role: str) -> Outcome:
    ctx, resource = arrange(monkeypatch, role)
    try:
        await authorise(ctx, action, resource, reason=REASON)
    except Forbidden:
        return "deny"
    return "allow"


# --- P-04-T15: the target conditions, and the principals that may never resolve ---------------

Variant = Literal[
    "preparer",
    "not_preparer",
    "holder",
    "other_person",
    "other_role",
    "no_facts",
    "owner",  # K-02-T01: `owner_of_target`
    "not_owner",
    "consented",  # T-01-T11: `consent(<purpose>)`
    "not_consented",
    "no_subjects",
]
Principal = Literal["agent", "system", "support"]


def _target(variant: Variant, ctx: AuthContext, role: str) -> TargetFacts | None:
    """The target's facts for one case: the actor among its preparers or not; the card reserved
    to the actor's role and person, to someone else, or to another role; or no facts at all."""
    other_role = "eqr_reviewer" if role != "eqr_reviewer" else "manager"
    return {
        "preparer": TargetFacts(preparer_user_ids=frozenset({ctx.user_id, uuid.uuid4()})),
        "not_preparer": TargetFacts(preparer_user_ids=frozenset({uuid.uuid4()})),
        "holder": TargetFacts(reserved_role=role, reserved_user_id=ctx.user_id),
        "other_person": TargetFacts(reserved_role=role, reserved_user_id=uuid.uuid4()),
        "other_role": TargetFacts(reserved_role=other_role, reserved_user_id=ctx.user_id),
        "owner": TargetFacts(owner_user_id=ctx.user_id),
        "not_owner": TargetFacts(owner_user_id=uuid.uuid4()),
        "consented": TargetFacts(consent_subjects=frozenset({uuid.uuid4(), uuid.uuid4()})),
        "not_consented": TargetFacts(consent_subjects=frozenset({uuid.uuid4(), uuid.uuid4()})),
        "no_subjects": TargetFacts(),
        "no_facts": None,
    }[variant]


async def condition_outcome(
    monkeypatch: pytest.MonkeyPatch, action: str, role: str, variant: Variant
) -> Outcome:
    if role == authz.FIRM_PARTNER:
        # K-02-T01: the derived partner cell (DEC-132), a partner member at firm level.
        ctx, _ = arrange(monkeypatch, "staff")
        resource = Resource.firm(ctx.tenant_id)

        async def partner(*_: object) -> bool:
            return True

        monkeypatch.setattr(authz, "_partner_level", partner)
    else:
        ctx, resource = arrange(monkeypatch, role)

    async def consented(*_: object) -> bool:
        return variant == "consented"  # T-01-T11: every subject holds every purpose, or none

    monkeypatch.setattr(authz, "consent_given", consented)
    target = replace(resource, target=_target(variant, ctx, role))
    try:
        await authorise(ctx, action, target, reason=REASON)
    except Forbidden:
        return "deny"
    return "allow"


async def principal_outcome(
    monkeypatch: pytest.MonkeyPatch, action: str, principal: Principal
) -> Outcome:
    """`authorise` for an agent, a system run or a break-glass support session, with every fact a
    person would need: the action in the agent's task scope, an initiator who is the firm's admin
    and the engagement's partner, every function on the work item, and target facts that a person
    holding the role would meet."""
    initiator, resource = arrange(monkeypatch, "engagement_partner")
    all_functions = frozenset(FUNCTIONS)

    async def functions(*_: object) -> frozenset[str]:
        return all_functions

    monkeypatch.setattr(LOOKUPS, "functions", functions)
    initiator = replace(initiator, firm_role="firm_admin")
    full = replace(
        resource,
        work_item_id=uuid.uuid4(),
        target=TargetFacts(
            preparer_user_ids=frozenset(),
            reserved_role="engagement_partner",
            reserved_user_id=initiator.user_id,
            owner_user_id=initiator.user_id,
        ),
    )
    assert full.engagement_id is not None
    actor: Actor
    if principal == "agent":
        run = uuid.uuid4()
        actor = AgentContext(
            tenant=TenantContext(
                initiator.tenant_id, "agent", f"agent:probe:{run}", initiator.user_id
            ),
            agent_id="probe",
            agent_run_id=run,
            engagement_id=full.engagement_id,
            task_scope=frozenset({action}),
            initiator=initiator,
            issued_by=_ISSUER,
        )
    elif principal == "system":
        actor = system_context_for_run(
            tenant_id=initiator.tenant_id,
            run_id=uuid.uuid4(),
            engagement_id=full.engagement_id,
            on_behalf_of=initiator.user_id,
        )
    else:

        async def no_membership(*_: object) -> str | None:
            return None  # a support session holds no engagement role (SPEC-012)

        monkeypatch.setattr(authz, "engagement_role", no_membership)
        staff = uuid.uuid4()
        actor = AuthContext(
            TenantContext(initiator.tenant_id, "support", f"staff:{staff}"),
            staff,
            uuid.uuid4(),
            "platform_support",
            datetime.now(UTC) - timedelta(minutes=1),
        )
    try:
        await authorise(actor, action, full, reason=REASON)
    except Forbidden:
        return "deny"
    return "allow"


# --- Q-02-T37: the fresh-MFA overlay (Q-02 AC-42) ---------------------------------------------

Freshness = Literal["fresh", "stale", "none"]
_AGES: dict[Freshness, timedelta | None] = {
    "fresh": timedelta(minutes=1),
    "stale": authz.MFA_RECENT + timedelta(minutes=1),
    "none": None,
}


def without_conditions(rule: authz.Rule) -> authz.Rule:
    """The rule with its F-03-T24 and P-04-T15 conditions cleared, so a case isolates the MFA
    attribute (the conditions have their own generated cases)."""
    return replace(
        rule,
        level_in=frozenset(),
        function_in=frozenset(),
        not_offshore=False,
        attest_client=None,
        gates_met=(),
        scope_only=False,
        not_preparer_of_target=False,
        reserved_role=False,
        owner_of_target=False,
    )


async def mfa_outcome(
    monkeypatch: pytest.MonkeyPatch, action: str, role: str, freshness: Freshness
) -> Outcome:
    """`authorise` for a role the row allows, every other layer satisfied, with the second factor
    verified a minute ago (`fresh`), just over `MFA_RECENT` ago (`stale`) or never (`none`).
    `firm_partner` is the derived cell (a partner-level member at firm level, DEC-132)."""
    monkeypatch.setitem(authz.RULES, action, without_conditions(authz.RULES[action]))
    if role == authz.FIRM_PARTNER:
        ctx, _ = arrange(monkeypatch, "staff")
        resource = Resource.firm(ctx.tenant_id)

        async def partner(*_: object) -> bool:
            return True

        monkeypatch.setattr(authz, "_partner_level", partner)
    else:
        ctx, resource = arrange(monkeypatch, role)
    age = _AGES[freshness]
    ctx = replace(ctx, mfa_at=None if age is None else datetime.now(UTC) - age)
    try:
        await authorise(ctx, action, resource, reason=REASON)
    except Forbidden:
        return "deny"
    return "allow"
