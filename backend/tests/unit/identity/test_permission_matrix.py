"""AC-6, AC-8, AC-20: the permission matrix, `authorise` and `visible` (TASK-007 contract).

Tests over every (role, action) are generated from `docs/architecture/permission-matrix.yaml`, so
a matrix change changes the tests with it (ADR-027). `authorise` reads the engagement role from the
database when `resource.engagement_id` is set; here that read is replaced by `EngagementRoles`.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, cast, get_args

import pytest
import yaml
from sqlalchemy import Uuid, column

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.api import (
    MFA_RECENT,
    AuthContext,
    Forbidden,
    Resource,
    UnknownAction,
    authorise,
    visible,
)
from abacus.modules.identity.authz import matrix
from abacus.modules.identity.authz.matrix import RULES
from abacus_tools.codegen import permission_matrix as pm

FirmRole = Literal["firm_admin", "practice_leader", "quality_partner"]
FIRM_ROLES: tuple[FirmRole, ...] = get_args(FirmRole)
ENGAGEMENT_ROLES = ("engagement_partner", "manager", "senior", "staff", "reviewer")
HUMAN_ROLES = (*FIRM_ROLES, *ENGAGEMENT_ROLES)
READ_VERBS = {"read", "read_metadata", "read_log"}
MODIFIERS = {"mfa_recent", "requires", "notify"}

# Reached by the contract's `matrix._rule` / `matrix._decision` validators, which are private by
# name only; the contract tests them directly.
make_rule = matrix._rule  # pyright: ignore[reportPrivateUsage] -- contract tests the validator
make_decision = matrix._decision  # pyright: ignore[reportPrivateUsage] -- contract tests it

DOCUMENT = cast(dict[str, object], yaml.safe_load(pm.SOURCE.read_text()))
YAML_ROLES = cast(list[str], DOCUMENT["roles"])
YAML_ACTIONS = cast(dict[str, dict[str, str]], DOCUMENT["actions"])


def _verb(action: str) -> str:
    return action.split(".", 1)[1]


def _is_read(action: str) -> bool:
    return _verb(action) in READ_VERBS


ALL_PAIRS = [
    (action, role, entries.get(role))
    for action, entries in YAML_ACTIONS.items()
    for role in HUMAN_ROLES
]
PAIR_IDS = [f"{action}-{role}" for action, role, _ in ALL_PAIRS]
# `notify` is an obligation the platform can't meet yet, so those actions deny (contract rev. 1).
NOTIFY_PAIRS = [
    (a, r)
    for a, r, value in ALL_PAIRS
    if value == "allow" and YAML_ACTIONS[a].get("notify") is not None
]
NOTIFY_IDS = [f"{a}-{r}" for a, r in NOTIFY_PAIRS]
ALLOWED = [
    (a, r)
    for a, r, value in ALL_PAIRS
    if value == "allow" and YAML_ACTIONS[a].get("notify") is None
]
ALLOWED_IDS = [f"{a}-{r}" for a, r in ALLOWED]
NOT_ALLOWED = [(a, r, v) for a, r, v in ALL_PAIRS if v != "allow"]
NOT_ALLOWED_IDS = [f"{a}-{r}" for a, r, _ in NOT_ALLOWED]
MFA_PAIRS = [(a, r) for a, r in ALLOWED if YAML_ACTIONS[a].get("mfa_recent") == "required"]
MFA_IDS = [f"{a}-{r}" for a, r in MFA_PAIRS]
REASON_PAIRS = [(a, r) for a, r in ALLOWED if YAML_ACTIONS[a].get("requires") == "reason"]
REASON_IDS = [f"{a}-{r}" for a, r in REASON_PAIRS]
WRITE_PAIRS = [(a, r) for a, r in ALLOWED if not _is_read(a)]
WRITE_IDS = [f"{a}-{r}" for a, r in WRITE_PAIRS]
READ_PAIRS = [(a, r) for a, r in ALLOWED if _is_read(a)]
READ_IDS = [f"{a}-{r}" for a, r in READ_PAIRS]
REASON = "documented in the working paper"


def _resource(
    tenant_id: uuid.UUID, engagement_id: uuid.UUID | None = None, *, archived: bool = False
) -> Resource:
    return Resource(tenant_id, engagement_id, archived)


class EngagementRoles:
    """Stands in for the database read of `engagement_members`; records its calls."""

    def __init__(self) -> None:
        self.role: str | None = None
        self.calls: list[tuple[TenantContext, uuid.UUID, uuid.UUID]] = []

    async def __call__(
        self, tenant: TenantContext, user_id: uuid.UUID, engagement_id: uuid.UUID
    ) -> str | None:
        self.calls.append((tenant, user_id, engagement_id))
        return self.role


@pytest.fixture
def engagement(monkeypatch: pytest.MonkeyPatch) -> EngagementRoles:
    fake = EngagementRoles()
    monkeypatch.setattr(authz, "engagement_role", fake)
    return fake


def _ctx(
    *,
    firm_role: FirmRole | None = None,
    mfa_ago: timedelta | None = timedelta(minutes=1),
    tenant_id: uuid.UUID | None = None,
) -> AuthContext:
    user_id = uuid.uuid4()
    return AuthContext(
        tenant=TenantContext(tenant_id or uuid.uuid4(), "human", str(user_id)),
        user_id=user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,
        mfa_at=None if mfa_ago is None else datetime.now(UTC) - mfa_ago,
    )


def _arranged(
    role: str,
    engagement: EngagementRoles,
    *,
    mfa_ago: timedelta | None = timedelta(minutes=1),
    archived: bool = False,
) -> tuple[AuthContext, Resource]:
    """A context and resource where layers 1, 2 and 4 pass for `role`."""
    if role in FIRM_ROLES:
        ctx = _ctx(firm_role=role, mfa_ago=mfa_ago)
        return ctx, _resource(ctx.tenant_id, archived=archived)
    ctx = _ctx(mfa_ago=mfa_ago)
    engagement.role = role
    return ctx, _resource(ctx.tenant_id, engagement_id=uuid.uuid4(), archived=archived)


async def _denied_layer(
    ctx: AuthContext, action: str, resource: Resource, reason: str | None = REASON
) -> str:
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, action, resource, reason=reason)
    return raised.value.layer


# --- the generated module matches the YAML -----------------------------------------------------


def test_ac20_generated_matrix_module_matches_the_yaml() -> None:
    assert pm.render(pm.SOURCE.read_text()) == pm.TARGET.read_text()


def test_ac20_check_mode_returns_0_when_the_module_is_current() -> None:
    assert pm.main(["--check"]) == 0


def test_ac20_check_mode_returns_1_when_the_yaml_has_drifted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    drifted = tmp_path / "permission-matrix.yaml"
    drifted.write_text(pm.SOURCE.read_text() + "\n  probe.read: {firm_admin: allow}\n")
    monkeypatch.setattr(pm, "SOURCE", drifted)
    assert pm.main(["--check"]) == 1


def test_ac20_check_mode_does_not_write_the_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    before = pm.TARGET.read_text()
    drifted = tmp_path / "permission-matrix.yaml"
    drifted.write_text(pm.SOURCE.read_text() + "\n  probe.read: {firm_admin: allow}\n")
    monkeypatch.setattr(pm, "SOURCE", drifted)
    pm.main(["--check"])
    assert pm.TARGET.read_text() == before


def test_ac20_generate_mode_writes_the_rendered_module(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "_matrix.py"
    monkeypatch.setattr(pm, "TARGET", target)
    assert pm.main([]) == 0
    assert target.read_text() == pm.render(pm.SOURCE.read_text())


def test_ac20_render_is_deterministic() -> None:
    source = pm.SOURCE.read_text()
    assert pm.render(source) == pm.render(source)


DUPLICATES = {
    "top-level": (
        "roles: [firm_admin]\nroles: [manager]\nactions:\n  a.read: {firm_admin: allow}\n"
    ),
    "action": (
        "roles: [firm_admin, manager]\nactions:\n"
        "  a.read: {firm_admin: allow}\n  a.read: {manager: allow}\n"
    ),
    "role": (
        "roles: [firm_admin, manager]\nactions:\n  a.read: {firm_admin: allow, firm_admin: deny}\n"
    ),
    "actions-section": (
        "roles: [firm_admin]\nactions:\n  a.read: {firm_admin: allow}\n"
        "actions:\n  b.read: {firm_admin: allow}\n"
    ),
}


@pytest.mark.parametrize("where", sorted(DUPLICATES))
def test_ac20_render_rejects_a_duplicate_key_at_any_level(where: str) -> None:
    with pytest.raises(ValueError, match="duplicate key"):
        pm.render(DUPLICATES[where])


def test_ac20_render_accepts_the_same_document_without_the_duplicate() -> None:
    source = "roles: [firm_admin]\nactions:\n  a.read: {firm_admin: allow}\n"
    assert "a.read" in pm.render(source)


def test_ac20_render_includes_every_action_and_role() -> None:
    rendered = pm.render(pm.SOURCE.read_text())
    for action in YAML_ACTIONS:
        assert action in rendered
    for role in YAML_ROLES:
        assert role in rendered


def test_ac20_the_yaml_has_the_expected_role_partition() -> None:
    assert set(YAML_ROLES) - set(HUMAN_ROLES) == {
        "client_admin",
        "client_contributor",
        "agent",
        "system",
    }


# --- every (role, action): matrix-driven decisions (layer 3) -----------------------------------


@pytest.mark.parametrize(("action", "role"), ALLOWED, ids=ALLOWED_IDS)
async def test_ac20_matrix_allow_means_no_exception(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement)
    await authorise(ctx, action, resource, reason=REASON)


@pytest.mark.parametrize(("action", "role", "value"), NOT_ALLOWED, ids=NOT_ALLOWED_IDS)
async def test_ac20_matrix_anything_but_allow_is_forbidden_at_the_role_layer(
    engagement: EngagementRoles, action: str, role: str, value: str | None
) -> None:
    ctx, resource = _arranged(role, engagement)
    assert await _denied_layer(ctx, action, resource) == "role"


@pytest.mark.parametrize(("action", "role"), NOTIFY_PAIRS, ids=NOTIFY_IDS)
async def test_ac20_actions_carrying_notify_deny_at_the_attribute_layer(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement)
    assert await _denied_layer(ctx, action, resource) == "attribute"


def test_ac20_engagement_self_join_is_a_notify_action() -> None:
    assert ("engagement.self_join", "firm_admin") in NOTIFY_PAIRS


def test_ac20_generated_pair_lists_cover_every_human_role_and_action() -> None:
    assert len(ALL_PAIRS) == len(YAML_ACTIONS) * len(HUMAN_ROLES)
    assert len(ALLOWED) + len(NOTIFY_PAIRS) + len(NOT_ALLOWED) == len(ALL_PAIRS)
    assert ALLOWED
    assert NOT_ALLOWED


# --- each layer denies independently -----------------------------------------------------------


@pytest.mark.parametrize(("action", "role"), ALLOWED, ids=ALLOWED_IDS)
async def test_ac20_layer_tenancy_denies_a_resource_of_another_tenant(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement)
    other = _resource(uuid.uuid4(), engagement_id=resource.engagement_id)
    assert await _denied_layer(ctx, action, other) == "tenancy"


@pytest.mark.parametrize("action", sorted(YAML_ACTIONS))
async def test_ac20_layer_relationship_denies_a_context_with_no_role_at_all(
    engagement: EngagementRoles, action: str
) -> None:
    ctx = _ctx()
    assert await _denied_layer(ctx, action, _resource(ctx.tenant_id)) == "relationship"


@pytest.mark.parametrize("action", sorted(YAML_ACTIONS))
async def test_ac20_layer_relationship_denies_a_non_member_of_the_engagement(
    engagement: EngagementRoles, action: str
) -> None:
    engagement.role = None
    ctx = _ctx()
    resource = _resource(ctx.tenant_id, uuid.uuid4())
    assert await _denied_layer(ctx, action, resource) == "relationship"


@pytest.mark.parametrize(("action", "role"), WRITE_PAIRS, ids=WRITE_IDS)
async def test_ac20_layer_attribute_archived_engagement_denies_every_write(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement, archived=True)
    assert await _denied_layer(ctx, action, resource) == "attribute"


@pytest.mark.parametrize(("action", "role"), READ_PAIRS, ids=READ_IDS)
async def test_ac20_archived_engagement_still_allows_reads(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement, archived=True)
    await authorise(ctx, action, resource, reason=REASON)


@pytest.mark.parametrize(("action", "role"), MFA_PAIRS, ids=MFA_IDS)
async def test_ac20_layer_attribute_mfa_required_and_absent_is_denied(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement, mfa_ago=None)
    assert await _denied_layer(ctx, action, resource) == "attribute"


@pytest.mark.parametrize(("action", "role"), MFA_PAIRS, ids=MFA_IDS)
async def test_ac20_layer_attribute_mfa_older_than_15_minutes_is_denied(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement, mfa_ago=MFA_RECENT + timedelta(minutes=1))
    assert await _denied_layer(ctx, action, resource) == "attribute"


@pytest.mark.parametrize(("action", "role"), MFA_PAIRS, ids=MFA_IDS)
async def test_ac20_mfa_within_15_minutes_is_allowed(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement, mfa_ago=MFA_RECENT - timedelta(minutes=1))
    await authorise(ctx, action, resource, reason=REASON)


def test_ac20_mfa_recent_is_15_minutes() -> None:
    assert timedelta(minutes=15) == MFA_RECENT


@pytest.mark.parametrize(("action", "role"), REASON_PAIRS, ids=REASON_IDS)
@pytest.mark.parametrize("reason", [None, "", " ", "\t\n  "])
async def test_ac20_layer_attribute_missing_reason_is_denied(
    engagement: EngagementRoles, action: str, role: str, reason: str | None
) -> None:
    ctx, resource = _arranged(role, engagement)
    assert await _denied_layer(ctx, action, resource, reason) == "attribute"


@pytest.mark.parametrize(("action", "role"), REASON_PAIRS, ids=REASON_IDS)
async def test_ac20_a_real_reason_satisfies_requires_reason(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement)
    await authorise(ctx, action, resource, reason="superseded by a later PBC list")


NO_REASON_PAIRS = [(a, r) for a, r in ALLOWED if YAML_ACTIONS[a].get("requires") != "reason"]


@pytest.mark.parametrize(
    ("action", "role"), NO_REASON_PAIRS, ids=[f"{a}-{r}" for a, r in NO_REASON_PAIRS]
)
async def test_ac20_reason_is_not_needed_when_the_action_does_not_require_one(
    engagement: EngagementRoles, action: str, role: str
) -> None:
    ctx, resource = _arranged(role, engagement)
    await authorise(ctx, action, resource, reason=None)


# --- layer order -------------------------------------------------------------------------------


async def test_ac20_tenancy_is_checked_before_relationship(engagement: EngagementRoles) -> None:
    ctx = _ctx()  # no firm role, and the engagement read would find no membership
    other = _resource(uuid.uuid4(), engagement_id=uuid.uuid4())
    assert await _denied_layer(ctx, "engagement.read", other) == "tenancy"


async def test_ac20_relationship_is_checked_before_role(engagement: EngagementRoles) -> None:
    ctx = _ctx()
    assert await _denied_layer(ctx, "engagement.read", _resource(ctx.tenant_id)) == "relationship"


async def test_ac20_role_is_checked_before_attribute(engagement: EngagementRoles) -> None:
    ctx, resource = _arranged("reviewer", engagement, archived=True, mfa_ago=None)
    assert await _denied_layer(ctx, "request_item.waive", resource, None) == "role"


async def test_ac20_tenancy_is_checked_before_attribute(engagement: EngagementRoles) -> None:
    ctx = _ctx(firm_role="firm_admin", mfa_ago=None)
    other = _resource(uuid.uuid4(), archived=True)
    assert await _denied_layer(ctx, "firm.manage_settings", other) == "tenancy"


async def test_ac20_an_allowed_role_with_no_mfa_and_an_archived_resource_is_an_attribute_denial(
    engagement: EngagementRoles,
) -> None:
    ctx, resource = _arranged("engagement_partner", engagement, archived=True, mfa_ago=None)
    assert await _denied_layer(ctx, "export.create", resource) == "attribute"


# --- roles held: firm role union engagement role ------------------------------------------------


async def test_ac20_firm_role_and_engagement_role_are_combined(
    engagement: EngagementRoles,
) -> None:
    # practice_leader is `in_scope` (not allow) for engagement.read; manager on the engagement is.
    ctx = _ctx(firm_role="practice_leader")
    engagement.role = "manager"
    resource = _resource(ctx.tenant_id, uuid.uuid4())
    await authorise(ctx, "engagement.read", resource)


async def test_ac20_engagement_role_alone_does_not_gain_a_firm_roles_rights(
    engagement: EngagementRoles,
) -> None:
    ctx = _ctx()
    engagement.role = "manager"
    resource = _resource(ctx.tenant_id, uuid.uuid4())
    assert await _denied_layer(ctx, "engagement.create", resource) == "role"


async def test_ac20_engagement_role_is_read_for_the_resources_engagement_and_user(
    engagement: EngagementRoles,
) -> None:
    ctx = _ctx()
    engagement.role = "manager"
    engagement_id = uuid.uuid4()
    await authorise(ctx, "engagement.read", _resource(ctx.tenant_id, engagement_id))
    assert engagement.calls == [(ctx.tenant, ctx.user_id, engagement_id)]


async def test_ac20_engagement_role_is_not_read_without_an_engagement_id(
    engagement: EngagementRoles,
) -> None:
    ctx = _ctx(firm_role="firm_admin")
    await authorise(ctx, "engagement.create", _resource(ctx.tenant_id))
    assert engagement.calls == []


async def test_ac20_a_deny_beats_an_allow_from_another_held_role(
    engagement: EngagementRoles, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        RULES, "probe.read", make_rule("probe.read", {"firm_admin": "deny", "manager": "allow"})
    )
    ctx = _ctx(firm_role="firm_admin")
    engagement.role = "manager"
    resource = _resource(ctx.tenant_id, uuid.uuid4())
    assert await _denied_layer(ctx, "probe.read", resource) == "role"


@pytest.mark.parametrize(
    "decision",
    ["in_scope", "assigned_only", "client_visible_only", "task_scope", "firm_setting(some_flag)"],
)
async def test_ac20_conditions_without_a_model_yet_are_never_an_allow(
    engagement: EngagementRoles, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    monkeypatch.setitem(RULES, "probe.read", make_rule("probe.read", {"manager": decision}))
    ctx = _ctx()
    engagement.role = "manager"
    resource = _resource(ctx.tenant_id, uuid.uuid4())
    assert await _denied_layer(ctx, "probe.read", resource) == "role"


async def test_ac20_a_not_modelled_condition_does_not_cancel_an_allow_from_another_role(
    engagement: EngagementRoles, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        RULES,
        "probe.read",
        make_rule("probe.read", {"firm_admin": "in_scope", "manager": "allow"}),
    )
    ctx = _ctx(firm_role="firm_admin")
    engagement.role = "manager"
    await authorise(ctx, "probe.read", _resource(ctx.tenant_id, uuid.uuid4()))


# --- AC-6 and AC-8 at authorise level ----------------------------------------------------------


async def test_ac6_firm_admin_without_engagement_membership_may_read_metadata(
    engagement: EngagementRoles,
) -> None:
    engagement.role = None
    ctx = _ctx(firm_role="firm_admin")
    resource = _resource(ctx.tenant_id, uuid.uuid4())
    await authorise(ctx, "engagement.read_metadata", resource)


@pytest.mark.parametrize("action", ["engagement.read", "request_item.read", "evidence.read"])
async def test_ac6_firm_admin_without_engagement_membership_is_denied_content(
    engagement: EngagementRoles, action: str
) -> None:
    engagement.role = None
    ctx = _ctx(firm_role="firm_admin")
    resource = _resource(ctx.tenant_id, uuid.uuid4())
    assert await _denied_layer(ctx, action, resource) == "role"


@pytest.mark.parametrize("action", ["engagement.read", "request_item.read", "evidence.read"])
async def test_ac6_firm_admin_is_denied_content_even_without_naming_an_engagement(
    engagement: EngagementRoles, action: str
) -> None:
    ctx = _ctx(firm_role="firm_admin")
    assert await _denied_layer(ctx, action, _resource(ctx.tenant_id)) == "role"


async def test_ac8_reviewer_cannot_create_a_request_item(engagement: EngagementRoles) -> None:
    ctx, resource = _arranged("reviewer", engagement)
    assert await _denied_layer(ctx, "request_item.create", resource) == "role"


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior"])
async def test_ac8_roles_that_may_create_a_request_item_can(
    engagement: EngagementRoles, role: str
) -> None:
    ctx, resource = _arranged(role, engagement)
    await authorise(ctx, "request_item.create", resource)


async def test_ac8_reviewer_cannot_create_even_with_an_active_firm_wide_membership(
    engagement: EngagementRoles,
) -> None:
    ctx = _ctx(firm_role="quality_partner")
    engagement.role = "reviewer"
    resource = _resource(ctx.tenant_id, uuid.uuid4())
    assert await _denied_layer(ctx, "request_item.create", resource) == "role"


# --- UnknownAction -----------------------------------------------------------------------------


async def test_ac20_authorise_unknown_action_raises_unknown_action(
    engagement: EngagementRoles,
) -> None:
    ctx = _ctx(firm_role="firm_admin")
    with pytest.raises(UnknownAction):
        await authorise(ctx, "no.such_action", _resource(ctx.tenant_id))


async def test_ac20_unknown_action_is_a_value_error_not_a_forbidden(
    engagement: EngagementRoles,
) -> None:
    ctx = _ctx(firm_role="firm_admin")
    with pytest.raises(ValueError) as raised:
        await authorise(ctx, "no.such_action", _resource(ctx.tenant_id))
    assert isinstance(raised.value, UnknownAction)
    assert not isinstance(raised.value, Forbidden)


def test_ac20_unknown_action_class_is_a_value_error() -> None:
    assert issubclass(UnknownAction, ValueError)
    assert not issubclass(UnknownAction, Forbidden)


def test_ac20_forbidden_carries_its_layer() -> None:
    assert Forbidden("engagement.read", "role").layer == "role"


def test_ac20_visible_unknown_action_raises_unknown_action() -> None:
    with pytest.raises(UnknownAction):
        visible(_ctx(firm_role="firm_admin"), "no.such_action", column("engagement_id", Uuid()))


# --- visible: read actions only ----------------------------------------------------------------


@pytest.mark.parametrize("action", [a for a in YAML_ACTIONS if not _is_read(a)])
def test_ac20_visible_rejects_every_non_read_action(action: str) -> None:
    with pytest.raises(ValueError):
        visible(_ctx(firm_role="firm_admin"), action, column("engagement_id", Uuid()))


def _sql(expression: object) -> str:
    return " ".join(str(expression).split())


READ_ACTIONS = [a for a in YAML_ACTIONS if _is_read(a)]


@pytest.mark.parametrize("action", READ_ACTIONS)
def test_ac20_visible_for_a_firm_role_allow_compiles_to_true(action: str) -> None:
    for role in FIRM_ROLES:
        if YAML_ACTIONS[action].get(role) != "allow":
            continue
        assert (
            _sql(visible(_ctx(firm_role=role), action, column("engagement_id", Uuid()))) == "true"
        )


@pytest.mark.parametrize("action", READ_ACTIONS)
def test_ac20_visible_without_a_firm_allow_filters_on_engagement_membership(action: str) -> None:
    ctx = _ctx()
    expression = visible(ctx, action, column("engagement_id", Uuid()))
    roles = sorted(r for r in ENGAGEMENT_ROLES if YAML_ACTIONS[action].get(r) == "allow")
    compiled = expression.compile()
    assert _sql(expression).startswith(
        "engagement_id IN (SELECT engagement_members.engagement_id FROM engagement_members WHERE "
    )
    assert "engagement_members.tenant_id = :tenant_id_1" in _sql(expression)
    assert "engagement_members.user_id = :user_id_1" in _sql(expression)
    assert "engagement_members.role IN" in _sql(expression)
    assert compiled.params["tenant_id_1"] == ctx.tenant_id
    assert compiled.params["user_id_1"] == ctx.user_id
    assert sorted(compiled.params["role_1"]) == roles


def test_ac20_visible_with_no_engagement_role_allowed_is_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(RULES, "probe.read", make_rule("probe.read", {"client_admin": "allow"}))
    expression = visible(_ctx(), "probe.read", column("engagement_id", Uuid()))
    assert _sql(expression) == "false"


@pytest.mark.parametrize(
    "modifier", [{"mfa_recent": "required"}, {"requires": "reason"}, {"notify": "engagement_team"}]
)
def test_ac20_visible_refuses_a_read_action_carrying_a_modifier(
    monkeypatch: pytest.MonkeyPatch, modifier: dict[str, str]
) -> None:
    monkeypatch.setitem(
        RULES, "probe.read", make_rule("probe.read", {"manager": "allow", **modifier})
    )
    with pytest.raises(ValueError):
        visible(_ctx(firm_role="firm_admin"), "probe.read", column("engagement_id", Uuid()))


def test_ac20_the_authz_module_states_it_is_not_wall_safe() -> None:
    assert "not wall-safe" in (authz.__doc__ or "").lower()


def test_ac20_resource_has_no_defaults() -> None:
    with pytest.raises(TypeError):
        Resource(uuid.uuid4())  # pyright: ignore[reportCallIssue] -- the contract: no defaults


def test_ac20_resource_firm_and_engagement_constructors() -> None:
    tenant, engagement_id = uuid.uuid4(), uuid.uuid4()
    firm = Resource.firm(tenant)
    assert (firm.tenant_id, firm.engagement_id, firm.archived) == (tenant, None, False)
    live = Resource.engagement(tenant, engagement_id, archived=False)
    assert (live.tenant_id, live.engagement_id, live.archived) == (tenant, engagement_id, False)
    old = Resource.engagement(tenant, engagement_id, archived=True)
    assert old.archived is True
    assert Resource(tenant, engagement_id, True) == old


def test_ac20_resource_engagement_requires_archived() -> None:
    with pytest.raises(TypeError):
        Resource.engagement(uuid.uuid4(), uuid.uuid4())  # pyright: ignore[reportCallIssue] -- contract


def test_ac20_an_in_scope_firm_role_is_filtered_by_membership_not_true() -> None:
    ctx = _ctx(firm_role="practice_leader")  # in_scope is not an allow
    expression = visible(ctx, "engagement.read", column("engagement_id", Uuid()))
    assert _sql(expression) != "true"
    assert "engagement_members.user_id = :user_id_1" in _sql(expression)


# --- decisions are logged ----------------------------------------------------------------------


def _log_events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    captured = capsys.readouterr()
    lines = [line for line in (captured.out + captured.err).splitlines() if line.startswith("{")]
    return [json.loads(line) for line in lines]


async def test_ac20_an_allowed_decision_is_logged(
    engagement: EngagementRoles, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _ctx(firm_role="firm_admin")
    capsys.readouterr()
    await authorise(ctx, "engagement.create", _resource(ctx.tenant_id))
    [event] = [e for e in _log_events(capsys) if e["event"] == "authz.allowed"]
    assert event["action"] == "engagement.create"
    assert event["tenant_id"] == str(ctx.tenant_id)
    assert event["user_id"] == str(ctx.user_id)


@pytest.mark.parametrize(
    ("layer", "action"),
    [
        ("tenancy", "engagement.create"),
        ("relationship", "engagement.create"),
        ("role", "wall.create"),
    ],
)
async def test_ac20_a_denied_decision_is_logged_with_its_layer(
    engagement: EngagementRoles, capsys: pytest.CaptureFixture[str], layer: str, action: str
) -> None:
    if layer == "tenancy":
        ctx = _ctx(firm_role="firm_admin")
        resource = _resource(uuid.uuid4())
    elif layer == "relationship":
        ctx = _ctx()
        resource = _resource(ctx.tenant_id)
    else:
        ctx = _ctx(firm_role="practice_leader")
        resource = _resource(ctx.tenant_id)
    capsys.readouterr()
    assert await _denied_layer(ctx, action, resource) == layer
    [event] = [e for e in _log_events(capsys) if e["event"] == "authz.denied"]
    assert event["action"] == action
    assert event["layer"] == layer
    assert event["tenant_id"] == str(ctx.tenant_id)
    assert event["user_id"] == str(ctx.user_id)


# --- matrix validation (an invalid matrix fails at import) ---------------------------------------


def test_ac20_rule_accepts_roles_decisions_and_modifiers_the_matrix_uses() -> None:
    make_rule(
        "probe.read",
        {
            "manager": "allow",
            "reviewer": "deny",
            "practice_leader": "in_scope",
            "client_admin": "client_visible_only",
            "client_contributor": "assigned_only",
            "agent": "task_scope",
            "senior": "firm_setting(seniors_can_accept)",
            "mfa_recent": "required",
            "requires": "reason",
            "notify": "engagement_team",
        },
    )


def test_ac20_rule_rejects_an_unknown_role() -> None:
    with pytest.raises(ValueError):
        make_rule("probe.read", {"intern": "allow"})


def test_ac20_rule_rejects_an_unknown_decision() -> None:
    with pytest.raises(ValueError):
        make_rule("probe.read", {"manager": "maybe"})


@pytest.mark.parametrize(
    "decision", ["ALLOW", "allow ", "", "firm_setting", "firm_setting()", "firm_setting(Bad)"]
)
def test_ac20_rule_rejects_malformed_decisions(decision: str) -> None:
    with pytest.raises(ValueError):
        make_rule("probe.read", {"manager": decision})


@pytest.mark.parametrize(
    "entries",
    [
        {"mfa_recent": "optional"},
        {"mfa_recent": "allow"},
        {"requires": "approval"},
        {"notify": "everyone"},
    ],
)
def test_ac20_rule_rejects_an_unknown_modifier_value(entries: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        make_rule("probe.read", {"manager": "allow", **entries})


def test_ac20_rule_rejects_an_unknown_modifier_name() -> None:
    with pytest.raises(ValueError):
        make_rule("probe.read", {"manager": "allow", "requires_approval": "reason"})


@pytest.mark.parametrize("action", ["noverb", "Probe.read", "probe.", ".read", "probe.read.more"])
def test_ac20_rule_rejects_a_malformed_action_name(action: str) -> None:
    with pytest.raises(ValueError):
        make_rule(action, {"manager": "allow"})


@pytest.mark.parametrize(
    "value",
    [
        "allow",
        "deny",
        "in_scope",
        "assigned_only",
        "client_visible_only",
        "task_scope",
        "firm_setting(seniors_can_accept)",
    ],
)
def test_ac20_decision_accepts_every_documented_value(value: str) -> None:
    make_decision("probe.read", "manager", value)


@pytest.mark.parametrize("value", ["maybe", "", "Allow", "firm_setting(", "firm_setting(x y)"])
def test_ac20_decision_rejects_unknown_values(value: str) -> None:
    with pytest.raises(ValueError):
        make_decision("probe.read", "manager", value)
