"""F-03-T24 acceptance (second half): "a property test proves no firm override widens the matrix
ceiling", and the generic `firm_setting(<key>)` grants only while the firm has <key> on
(chapter 03 §4.4; DEC-38, DEC-127)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.authz import Forbidden, Resource, authorise, matrix
from abacus.modules.identity.authz._matrix import ROLES
from abacus.modules.identity.authz.matrix import FIRM_SETTING_KEYS, RULES
from abacus.modules.identity.authz.overrides import PLATFORM_ROLES, apply_override, refusal
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import FirmPolicy

_parse = matrix._rule  # pyright: ignore[reportPrivateUsage]  # the parser, tested directly


def _grants(decision: str | None) -> bool:
    """Whether a decision can ever allow (anything but no cell and deny)."""
    return decision not in (None, "deny")


_actions = st.sampled_from(sorted(RULES))
_roles = st.sampled_from(sorted(ROLES))
# Any decision a row could hold: the matrix vocabulary, setting names and junk.
_decisions = st.one_of(
    st.sampled_from(
        [
            *("deny", "allow", "in_scope", "task_scope", "assigned_only", "client_visible_only"),
            *("firm_setting", "firm_setting(seniors_can_accept)", "DENY", ""),
        ]
    ),
    st.text(max_size=20),
)


@given(action=_actions, role=_roles, override=st.one_of(st.none(), _decisions))
def test_no_override_widens_the_ceiling(action: str, role: str, override: str | None) -> None:
    ceiling = RULES[action].decisions.get(role)
    effective = apply_override(ceiling, override)
    assert effective in (ceiling, "deny")
    assert _grants(effective) <= _grants(ceiling)


@given(
    overrides=st.dictionaries(st.tuples(_actions, _roles), _decisions, max_size=40),
)
def test_a_whole_firm_policy_never_widens_any_cell(overrides: dict[tuple[str, str], str]) -> None:
    for action, rule in RULES.items():
        for role in ROLES:
            ceiling = rule.decisions.get(role)
            effective = apply_override(ceiling, overrides.get((action, role)))
            assert _grants(effective) <= _grants(ceiling), (action, role)


@given(action=_actions, role=_roles, decision=_decisions)
def test_the_writer_accepts_only_what_narrows(action: str, role: str, decision: str) -> None:
    if refusal(action, role, decision) is None:
        ceiling = RULES[action].decisions.get(role)
        assert apply_override(ceiling, decision) == "deny"
        assert ceiling is not None


@pytest.mark.parametrize(
    ("action", "role", "decision", "why"),
    [
        ("request_item.create", "manager", "deny", None),
        ("request_item.create", "manager", "allow", "widens"),
        ("request_item.create", "staff", "deny", "no_cell"),
        ("request_item.create", "system", "deny", "platform_role"),
        ("engagement.read_metadata", "manager", "deny", "read_action"),
        ("firm.manage_settings", "firm_admin", "deny", "locks_out"),
        ("no.such_action", "manager", "deny", "unknown_action"),
    ],
)
def test_the_writer_names_why_it_refuses(
    action: str, role: str, decision: str, why: str | None
) -> None:
    assert refusal(action, role, decision) == why


def test_platform_roles_are_matrix_roles() -> None:
    assert set(ROLES) >= PLATFORM_ROLES


# --- firm settings: registered keys only --------------------------------------------------------


def test_a_person_cell_may_name_only_a_registered_setting() -> None:
    assert _parse("x.do", {"senior": "firm_setting(seniors_can_accept)"}).firm_settings == (
        ("senior", "seniors_can_accept"),
    )
    with pytest.raises(ValueError, match="unregistered firm setting"):
        _parse("x.do", {"senior": "firm_setting(anything_goes)"})
    # An agent's only setting is the autonomy policy, and a person can't name it.
    _parse("x.do", {"agent": "firm_setting(autonomy_policy)"})
    with pytest.raises(ValueError, match="unregistered firm setting"):
        _parse("x.do", {"agent": "firm_setting(seniors_can_accept)"})
    with pytest.raises(ValueError, match="unregistered firm setting"):
        _parse("x.do", {"senior": "firm_setting(autonomy_policy)"})


def test_every_setting_in_the_matrix_is_registered() -> None:
    named = {
        name for rule in RULES.values() for role, name in rule.firm_settings if role != "agent"
    }
    assert named <= FIRM_SETTING_KEYS


def test_the_migration_check_lists_the_registered_keys() -> None:
    from pathlib import Path

    migration = (
        Path(__file__).parents[3] / "migrations/versions/0081_firm_policy_overrides_settings.py"
    )
    text = migration.read_text()
    assert all(f"'{key}'" in text for key in FIRM_SETTING_KEYS)


# --- through `authorise` ------------------------------------------------------------------------


def _person() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


def _policy(
    overrides: dict[tuple[str, str], str] | None = None, on: frozenset[str] = frozenset()
) -> Callable[[TenantContext], Awaitable[FirmPolicy]]:
    async def read(_: TenantContext) -> FirmPolicy:
        return FirmPolicy(overrides or {}, on)

    return read


@pytest.fixture
def on_engagement(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """The person holds `role` on the engagement, is walled from nothing, and has confirmed
    their independence."""

    async def walled(*_: object) -> frozenset[uuid.UUID]:
        return frozenset()

    async def confirmed(*_: object) -> bool:
        return True

    monkeypatch.setattr(authz, "walled_clients", walled)
    monkeypatch.setattr(authz, "_independence", (None, confirmed))

    def hold(role: str) -> None:
        async def engagement_role(*_: object) -> str:
            return role

        monkeypatch.setattr(authz, "engagement_role", engagement_role)

    return hold


async def test_an_override_denies_a_cell_the_matrix_allows(
    monkeypatch: pytest.MonkeyPatch, on_engagement: Callable[[str], None]
) -> None:
    on_engagement("manager")
    ctx = _person()
    resource = Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)
    await authorise(ctx, "request_item.create", resource)
    monkeypatch.setattr(
        authz, "firm_policy", _policy({("request_item.create", "manager"): "deny"})
    )
    with pytest.raises(Forbidden) as denied:
        await authorise(ctx, "request_item.create", resource)
    assert denied.value.layer == "role"


async def test_an_override_on_another_role_leaves_this_one(
    monkeypatch: pytest.MonkeyPatch, on_engagement: Callable[[str], None]
) -> None:
    on_engagement("manager")
    ctx = _person()
    resource = Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)
    monkeypatch.setattr(authz, "firm_policy", _policy({("request_item.create", "senior"): "deny"}))
    await authorise(ctx, "request_item.create", resource)


async def test_an_allow_override_grants_nothing(
    monkeypatch: pytest.MonkeyPatch, on_engagement: Callable[[str], None]
) -> None:
    on_engagement("staff")
    ctx = _person()
    resource = Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)
    monkeypatch.setattr(authz, "firm_policy", _policy({("request_item.create", "staff"): "allow"}))
    with pytest.raises(Forbidden):
        await authorise(ctx, "request_item.create", resource)


async def test_a_firm_setting_cell_allows_only_while_the_setting_is_on(
    monkeypatch: pytest.MonkeyPatch, on_engagement: Callable[[str], None]
) -> None:
    on_engagement("senior")
    ctx = _person()
    resource = Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)
    with pytest.raises(Forbidden) as denied:
        await authorise(ctx, "review.take", resource)
    assert denied.value.layer == "role"
    monkeypatch.setattr(authz, "firm_policy", _policy(on=frozenset({"seniors_can_publish"})))
    with pytest.raises(Forbidden):
        await authorise(ctx, "review.take", resource)
    monkeypatch.setattr(authz, "firm_policy", _policy(on=frozenset({"seniors_can_accept"})))
    await authorise(ctx, "review.take", resource)


async def test_an_override_beats_a_firm_setting(
    monkeypatch: pytest.MonkeyPatch, on_engagement: Callable[[str], None]
) -> None:
    on_engagement("senior")
    ctx = _person()
    resource = Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)
    monkeypatch.setattr(
        authz,
        "firm_policy",
        _policy({("review.take", "senior"): "deny"}, on=frozenset({"seniors_can_accept"})),
    )
    with pytest.raises(Forbidden):
        await authorise(ctx, "review.take", resource)


async def test_the_policy_is_read_once_per_request(
    monkeypatch: pytest.MonkeyPatch, on_engagement: Callable[[str], None]
) -> None:
    on_engagement("manager")
    reads: list[uuid.UUID] = []

    async def read(tenant: TenantContext) -> FirmPolicy:
        reads.append(tenant.tenant_id)
        return FirmPolicy({}, frozenset())

    monkeypatch.setattr(authz, "firm_policy", read)
    ctx = _person()
    resource = Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)
    with authz.recording_checks():
        await authorise(ctx, "request_item.create", resource)
        await authorise(ctx, "request_item.create", resource)
    assert reads == [ctx.tenant_id]
