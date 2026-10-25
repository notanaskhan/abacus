"""F-03-T33: independent acceptance tests (ADR-078) for roles, conditions, overrides, client
grants and walls, written from F-03 §3.4-§3.6 (stories 4.1-4.3, 5.2, 6.1), chapter 03 §4.4-§4.5,
ADR-145/146/147 and DEC-127/129, not from the code: "Walled, offshore, client_service and
role-union personas each have allow and deny cases that pass on main."

Unit level: the identity lookups `authorise` reads (walls, engagement roles, membership facts,
the firm's policy, grants) are replaced by an in-memory firm. The Postgres half, with real walls,
grants, overrides and client records, is tests/integration/test_f03_personas_db.py.

Personas (Brightwater Hale, synthetic):
- Lena Park, seasonal tax preparer in Denver, walled from Ashford (ADM-02d; INV-3).
- An offshore manager, who keeps ordinary rights but never reveals a TIN (§4.5; DEC-52).
- Grace Holloway, Firm Admin with `client_service` on Copperleaf (story 4.2; DEC-20).
- Meera Shah, taxpayer on her own 1040 and K-1 recipient from Ridgeline (story 5.2; DEC-129).
- A manager under an ADM-02 role template: stricter-only overrides (story 4.3; DEC-127).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, client_access
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    portal_scopes,
    shell_of,
)
from abacus.modules.identity.authz import matrix
from abacus.modules.identity.authz._matrix import ROLES
from abacus.modules.identity.authz.conditions import ConditionFacts, conditions_hold
from abacus.modules.identity.authz.matrix import RULES, Rule
from abacus.modules.identity.authz.overrides import apply_override
from abacus.modules.identity.client_access import scope_covers
from abacus.modules.identity.firm_settings import OverrideRefused, set_policy_override
from abacus.modules.identity.repository import FirmPolicy, GrantRow, MemberFacts
from abacus.modules.identity.slots import ScopeFacts

_parse = matrix._rule  # pyright: ignore[reportPrivateUsage]  # the matrix parser, as the codegen uses it

TENANT = uuid.uuid4()
# People.
LENA, GRACE, OFFSHORE, MANAGER, MARGARET, SECURITY = (uuid.uuid4() for _ in range(6))
MEERA, K1_ONLY, THIRD_PARTY = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
# Clients and their engagements.
ASHFORD, GRANITE, COPPERLEAF, SHAH, RIDGELINE = (uuid.uuid4() for _ in range(5))
ASHFORD_ENG, GRANITE_ENG, COPPERLEAF_ENG, SHAH_ENG, RIDGELINE_ENG = (
    uuid.uuid4() for _ in range(5)
)
ASHFORD_RETURN, OWN_1040, RIDGELINE_1065, K1_PACKAGE = (uuid.uuid4() for _ in range(4))
CLIENT_OF = {
    ASHFORD_ENG: ASHFORD,
    GRANITE_ENG: GRANITE,
    COPPERLEAF_ENG: COPPERLEAF,
    SHAH_ENG: SHAH,
    RIDGELINE_ENG: RIDGELINE,
}

# What a seasonal preparer does on a return she is staffed on (staff role, independence confirmed).
PREPARER_WORK = {
    "work_item.read_metadata",
    "engagement.read_metadata",
    "request_item.read",
    "evidence.read",
    "workpaper.read",
    "workpaper.edit",
}
# Story 4.2: binders, invitations and request status; never content.
BINDERS = {"request_item.create", "request_item.update"}
INVITATIONS = {"client_contact.invite"}
REQUEST_STATUS = {"request_item.read"}
CONTENT = {
    "evidence.read",
    "evidence.upload",
    "evidence.accept",
    "comment.read",
    "comment.create",
    "workpaper.read",
}
# Chapter 03 §4.4 names `tin.reveal` as a `not_offshore` action; DEC-52 adds a stated reason and
# fresh MFA. It lands with P-07-T04/T10; until then the rule is parsed exactly as the matrix
# file will declare it, and the guard below holds the real row to the same condition.
TIN_REVEAL_ENTRIES = {
    "engagement_partner": "allow",
    "manager": "allow",
    "not_offshore": "required",
    "mfa_recent": "required",
    "requires": "reason",
}


@dataclass
class Firm:
    """Brightwater Hale as `authorise` sees it: walls, engagement roles, memberships, policy."""

    walls: dict[uuid.UUID, frozenset[uuid.UUID]] = field(default_factory=lambda: {})
    roles: dict[tuple[uuid.UUID, uuid.UUID], str] = field(default_factory=lambda: {})
    members: dict[uuid.UUID, MemberFacts] = field(default_factory=lambda: {})
    overrides: dict[tuple[str, str], str] = field(default_factory=lambda: {})
    settings_on: frozenset[str] = frozenset()
    grants: dict[uuid.UUID, list[GrantRow]] = field(default_factory=lambda: {})


def _member(level: str, *, offshore: bool = False, client: bool = False) -> MemberFacts:
    return MemberFacts(level=level, offshore=offshore, service_lines=frozenset(), client=client)


def _grant(user: uuid.UUID, role: str, kind: str, scope: uuid.UUID) -> GrantRow:
    return GrantRow(uuid.uuid4(), user, role, kind, scope, None, "active")


@pytest.fixture
def firm(monkeypatch: pytest.MonkeyPatch) -> Iterator[Firm]:
    world = Firm()

    async def walled_clients(_: TenantContext, person: uuid.UUID) -> frozenset[uuid.UUID]:
        return world.walls.get(person, frozenset())

    async def engagement_role(
        _: TenantContext, user: uuid.UUID, engagement: uuid.UUID
    ) -> str | None:
        return world.roles.get((user, engagement))

    async def member_facts(_: TenantContext, user: uuid.UUID) -> MemberFacts | None:
        return world.members.get(user)

    async def firm_policy(_: TenantContext) -> FirmPolicy:
        return FirmPolicy(dict(world.overrides), world.settings_on)

    async def confirmed(*_: object) -> bool:
        return True  # independence confirmed: the layer under test is never independence

    async def active_grants(_: TenantContext, user: uuid.UUID) -> list[GrantRow]:
        return list(world.grants.get(user, []))

    async def resolve_scope(_: TenantContext, kind: str, scope: uuid.UUID) -> ScopeFacts | None:
        if kind == "work_item":
            return {
                OWN_1040: ScopeFacts(SHAH, engagement_id=SHAH_ENG, work_item_id=OWN_1040),
                RIDGELINE_1065: ScopeFacts(
                    RIDGELINE, engagement_id=RIDGELINE_ENG, work_item_id=RIDGELINE_1065
                ),
            }.get(scope)
        return None  # no K-1 package resolver yet: a K-1 grant reaches no return (fail closed)

    async def engagement_client(_: TenantContext, engagement: uuid.UUID) -> uuid.UUID | None:
        return CLIENT_OF.get(engagement)

    monkeypatch.setattr(authz, "walled_clients", walled_clients)
    monkeypatch.setattr(authz, "engagement_role", engagement_role)
    monkeypatch.setattr(authz, "member_facts", member_facts)
    monkeypatch.setattr(authz, "firm_policy", firm_policy)
    monkeypatch.setattr(authz, "_independence", (None, confirmed))
    monkeypatch.setattr(client_access, "active_grants", active_grants)
    monkeypatch.setattr(client_access, "resolve_scope", resolve_scope)
    monkeypatch.setattr(client_access, "engagement_client", engagement_client)
    yield world


def _ctx(user: uuid.UUID, firm_role: str | None = None, *, mfa: bool = True) -> AuthContext:
    return AuthContext(
        TenantContext(TENANT, "human", str(user)),
        user,
        uuid.uuid4(),
        firm_role,  # type: ignore[arg-type]  # a literal firm role or None
        datetime.now(UTC) if mfa else None,
    )


def _on(engagement: uuid.UUID, work_item: uuid.UUID | None = None) -> Resource:
    return Resource(TENANT, engagement, False, CLIENT_OF[engagement], None, work_item)


async def _layer(ctx: AuthContext, action: str, resource: Resource, **kw: str) -> str | None:
    """None when allowed; otherwise the layer that denied."""
    try:
        await authorise(ctx, action, resource, **kw)
    except Forbidden as denied:
        return denied.layer
    return None


# --- Walled: Lena Park ✕ Ashford (story 6.1; INV-3; ADR-026) ----------------------------------


@pytest.fixture
def lena(firm: Firm) -> AuthContext:
    """Staffed as a preparer on both Ashford and Granite, and walled from Ashford."""
    firm.members[LENA] = _member("seasonal")
    firm.roles[(LENA, ASHFORD_ENG)] = "staff"
    firm.roles[(LENA, GRANITE_ENG)] = "staff"
    firm.walls[LENA] = frozenset({ASHFORD})
    return _ctx(LENA)


async def test_walled_lena_is_denied_every_action_on_ashford_at_the_wall(
    lena: AuthContext,
) -> None:
    """Deny: the wall overrides her staff role for every action in the matrix, and it is the
    wall that answers (routes turn it into 404: Ashford doesn't exist for her)."""
    leaks = {
        action: layer
        for action in sorted(RULES)
        if (layer := await _layer(lena, action, _on(ASHFORD_ENG), reason="probe")) != "wall"
    }
    assert leaks == {}


async def test_walled_lena_is_denied_ashfords_work_item_too(lena: AuthContext) -> None:
    resource = _on(ASHFORD_ENG, ASHFORD_RETURN)
    assert await _layer(lena, "work_item.read_metadata", resource) == "wall"
    assert await allowed_actions(lena, resource) == frozenset()


async def test_walled_lena_is_offered_nothing_on_ashford(lena: AuthContext) -> None:
    assert await allowed_actions(lena, _on(ASHFORD_ENG)) == frozenset()


async def test_walled_lena_keeps_her_preparer_work_on_granite(lena: AuthContext) -> None:
    """Allow: the wall is on Ashford only; on Granite her staff role works as normal."""
    for action in sorted(PREPARER_WORK):
        assert await _layer(lena, action, _on(GRANITE_ENG)) is None, action
    assert await allowed_actions(lena, _on(GRANITE_ENG)) >= PREPARER_WORK


async def test_on_granite_lena_is_still_only_staff(lena: AuthContext) -> None:
    """Deny below the wall: off Ashford, the matrix decides as for any staff member."""
    assert await _layer(lena, "evidence.accept", _on(GRANITE_ENG)) == "role"
    assert await _layer(lena, "request_item.waive", _on(GRANITE_ENG)) == "role"


# --- Offshore: never reveals a TIN (chapter 03 §4.4/§4.5; DEC-52; ADR-147) -----------------------


@pytest.fixture
def tin_reveal(monkeypatch: pytest.MonkeyPatch) -> Rule:
    rule = _parse("tin.reveal", TIN_REVEAL_ENTRIES)
    monkeypatch.setitem(RULES, "tin.reveal", rule)
    return rule


def test_every_reveal_in_the_matrix_requires_not_offshore() -> None:
    """Guard: when `tin.reveal`, `pii.reveal` or any other reveal lands in the matrix, it carries
    `not_offshore: required` (§4.4)."""
    reveals = {action for action in RULES if action.split(".", 1)[1].startswith("reveal")}
    assert {action for action in reveals if not RULES[action].not_offshore} == set()


@pytest.mark.parametrize(
    ("offshore", "holds"),
    [(False, True), (True, False), (None, False)],
    ids=["onshore", "offshore", "unknown"],
)
def test_not_offshore_holds_only_for_a_known_onshore_person(
    tin_reveal: Rule, offshore: bool | None, holds: bool
) -> None:
    assert conditions_hold(tin_reveal, ConditionFacts(offshore=offshore), person=True) is holds


@pytest.fixture
def offshore_manager(firm: Firm) -> AuthContext:
    firm.members[OFFSHORE] = _member("manager", offshore=True)
    firm.roles[(OFFSHORE, GRANITE_ENG)] = "manager"
    return _ctx(OFFSHORE)


@pytest.mark.usefixtures("tin_reveal")
async def test_an_offshore_manager_cannot_reveal_a_tin(offshore_manager: AuthContext) -> None:
    """Deny: the role allows it, fresh MFA and a reason are given, and still the offshore
    condition refuses; capabilities never offer it."""
    layer = await _layer(offshore_manager, "tin.reveal", _on(GRANITE_ENG), reason="Form W-9 check")
    assert layer == "condition"
    assert await allowed_actions(offshore_manager, _on(GRANITE_ENG), ["tin.reveal"]) == frozenset()


@pytest.mark.usefixtures("tin_reveal")
async def test_the_same_manager_onshore_may_reveal(firm: Firm) -> None:
    """Allow: the identical person and engagement, with the membership not offshore."""
    firm.members[MANAGER] = _member("manager", offshore=False)
    firm.roles[(MANAGER, GRANITE_ENG)] = "manager"
    ctx = _ctx(MANAGER)
    assert await _layer(ctx, "tin.reveal", _on(GRANITE_ENG), reason="Form W-9 check") is None


@pytest.mark.usefixtures("tin_reveal")
async def test_an_offshore_manager_keeps_ordinary_work(offshore_manager: AuthContext) -> None:
    """Allow: offshore narrows only the actions that carry the condition."""
    for action in ("request_item.create", "evidence.read", "workpaper.read"):
        assert await _layer(offshore_manager, action, _on(GRANITE_ENG)) is None, action


@pytest.mark.usefixtures("tin_reveal")
async def test_a_membership_without_facts_cannot_reveal(firm: Firm) -> None:
    """Fail closed: no membership facts means offshore is unknown."""
    firm.roles[(MANAGER, GRANITE_ENG)] = "manager"
    assert await _layer(_ctx(MANAGER), "tin.reveal", _on(GRANITE_ENG), reason="x") == "condition"


# --- client_service: Grace Holloway on Copperleaf (story 4.2; DEC-20; ADR-147) -------------------


@pytest.fixture
def grace(firm: Firm) -> AuthContext:
    firm.members[GRACE] = _member("admin")
    firm.roles[(GRACE, COPPERLEAF_ENG)] = "client_service"
    return _ctx(GRACE, "firm_admin")


async def test_grace_runs_binders_invitations_and_request_status(grace: AuthContext) -> None:
    """Allow: through `authorise`, with fresh MFA so only the role decides."""
    for action in sorted(BINDERS | INVITATIONS | REQUEST_STATUS):
        assert await _layer(grace, action, _on(COPPERLEAF_ENG)) is None, action


async def test_grace_never_opens_evidence_or_comment_content(grace: AuthContext) -> None:
    """Deny: neither her firm role (metadata only, ADR-024) nor `client_service` grants content."""
    for action in sorted(CONTENT):
        assert await _layer(grace, action, _on(COPPERLEAF_ENG)) == "role", action


async def test_grace_capabilities_match(grace: AuthContext) -> None:
    allowed = await allowed_actions(grace, _on(COPPERLEAF_ENG))
    assert allowed >= BINDERS | INVITATIONS | REQUEST_STATUS
    assert allowed & CONTENT == set()


async def test_without_client_service_grace_runs_no_binder(grace: AuthContext, firm: Firm) -> None:
    """Deny: on an engagement where she holds no role, her firm role alone runs no binder."""
    firm.roles.pop((GRACE, COPPERLEAF_ENG))
    assert await _layer(grace, "request_item.create", _on(COPPERLEAF_ENG)) == "role"
    assert await _layer(grace, "client_contact.invite", _on(GRANITE_ENG)) == "role"


# --- security_admin (story 4.1): no client content ----------------------------------------------


async def test_security_admin_holds_no_content_action(firm: Firm) -> None:
    """Deny: IT/Security holds no engagement content right anywhere. (`security.manage`, the
    allow half of story 4.1, lands with G-02-T02.)"""
    firm.members[SECURITY] = _member("admin")
    ctx = _ctx(SECURITY, "security_admin")
    assert await allowed_actions(ctx, _on(COPPERLEAF_ENG), sorted(CONTENT)) == frozenset()


# --- Role union: Meera Shah (story 5.2; DEC-129; INV-4; ADR-146) --------------------------------


@pytest.fixture
def meera(firm: Firm) -> AuthContext:
    firm.grants[MEERA] = [
        _grant(MEERA, "taxpayer", "work_item", OWN_1040),
        _grant(MEERA, "k1_recipient", "k1_package", K1_PACKAGE),
    ]
    firm.members[MEERA] = _member("staff", client=True)
    return _ctx(MEERA)


async def test_meeras_shell_is_the_full_role_union_with_her_k1(meera: AuthContext) -> None:
    """Allow: a taxpayer grant opens the full shell, and the K-1 scope is listed beside it."""
    scopes = await portal_scopes(meera)
    assert scopes.shell == "full"
    assert {(s.role, s.scope_kind, s.scope_id) for s in scopes.scopes} == {
        ("taxpayer", "work_item", OWN_1040),
        ("k1_recipient", "k1_package", K1_PACKAGE),
    }


async def test_meeras_grant_covers_her_own_return(meera: AuthContext) -> None:
    assert await scope_covers(meera.tenant, MEERA, SHAH_ENG, OWN_1040) is True


async def test_meeras_grants_never_cover_ridgelines_return(meera: AuthContext) -> None:
    """Deny: the K-1 package doesn't open the partnership's return, its engagement or anything
    else at Ridgeline; nor does her 1040 grant open the rest of her own engagement."""
    assert await scope_covers(meera.tenant, MEERA, RIDGELINE_ENG, RIDGELINE_1065) is False
    assert await scope_covers(meera.tenant, MEERA, RIDGELINE_ENG, None) is False
    assert await scope_covers(meera.tenant, MEERA, SHAH_ENG, None) is False


async def test_meera_has_no_role_on_ridgelines_engagement(meera: AuthContext) -> None:
    """Deny: no grant names Ridgeline's engagement, so no matrix role exists there (404)."""
    assert await _layer(meera, "engagement.read_metadata", _on(RIDGELINE_ENG)) == "relationship"


async def test_a_k1_only_recipient_gets_the_k1_shell(firm: Firm) -> None:
    firm.grants[K1_ONLY] = [_grant(K1_ONLY, "k1_recipient", "k1_package", K1_PACKAGE)]
    ctx = _ctx(K1_ONLY)
    assert (await portal_scopes(ctx)).shell == "k1"
    assert await scope_covers(ctx.tenant, K1_ONLY, RIDGELINE_ENG, RIDGELINE_1065) is False


async def test_a_third_party_gets_the_limited_shell(firm: Firm) -> None:
    firm.grants[THIRD_PARTY] = [_grant(THIRD_PARTY, "third_party", "work_item", OWN_1040)]
    ctx = _ctx(THIRD_PARTY)
    assert (await portal_scopes(ctx)).shell == "limited"
    assert await scope_covers(ctx.tenant, THIRD_PARTY, SHAH_ENG, OWN_1040) is True
    assert await scope_covers(ctx.tenant, THIRD_PARTY, RIDGELINE_ENG, RIDGELINE_1065) is False


async def test_someone_without_grants_has_no_shell(firm: Firm) -> None:
    assert (await portal_scopes(_ctx(uuid.uuid4()))).shell == "none"


@pytest.mark.parametrize(
    ("roles", "shell"),
    [
        (("owner",), "full"),
        (("contributor",), "full"),
        (("plan_administrator",), "full"),
        (("trustee",), "full"),
        (("taxpayer",), "full"),
        (("spouse",), "full"),
        (("delegate",), "full"),
        (("taxpayer", "k1_recipient"), "full"),
        (("k1_recipient",), "k1"),
        (("k1_recipient", "k1_recipient"), "k1"),
        (("third_party",), "limited"),
        (("tcwg",), "limited"),
        (("prospect",), "limited"),
        (("component_auditor",), "limited"),
        (("k1_recipient", "third_party"), "limited"),
        ((), "none"),
    ],
)
def test_dec_129_shell_table(roles: tuple[str, ...], shell: str) -> None:
    assert shell_of(roles) == shell


# --- ADM-02 role templates: stricter-only overrides (story 4.3; DEC-127; ADR-147) ---------------


@pytest.fixture
def manager(firm: Firm) -> AuthContext:
    firm.members[MANAGER] = _member("manager")
    firm.roles[(MANAGER, GRANITE_ENG)] = "manager"
    return _ctx(MANAGER)


async def test_a_role_template_denies_a_manager_a_cell_the_matrix_allows(
    manager: AuthContext, firm: Firm
) -> None:
    assert await _layer(manager, "request_item.create", _on(GRANITE_ENG)) is None  # allow
    firm.overrides[("request_item.create", "manager")] = "deny"
    assert await _layer(manager, "request_item.create", _on(GRANITE_ENG)) == "role"  # deny
    assert "request_item.create" not in await allowed_actions(manager, _on(GRANITE_ENG))
    # Only that cell narrows: the manager's other rights stand.
    assert await _layer(manager, "request_item.update", _on(GRANITE_ENG)) is None


async def test_an_allow_override_grants_nothing(firm: Firm) -> None:
    """Deny: a staff member has no `request_item.create` cell, and a senior's
    `evidence.accept` is a firm setting that is off; an 'allow' override opens neither."""
    staff, senior = uuid.uuid4(), uuid.uuid4()
    firm.roles[(staff, GRANITE_ENG)] = "staff"
    firm.roles[(senior, GRANITE_ENG)] = "senior"
    firm.overrides[("request_item.create", "staff")] = "allow"
    firm.overrides[("evidence.accept", "senior")] = "allow"
    assert await _layer(_ctx(staff), "request_item.create", _on(GRANITE_ENG)) == "role"
    assert await _layer(_ctx(senior), "evidence.accept", _on(GRANITE_ENG)) == "role"


@pytest.mark.parametrize("override", ["allow", "deny", "in_scope", "firm_setting", "", None])
def test_no_override_widens_any_cell_of_the_matrix(override: str | None) -> None:
    """Every (action, role) cell: the effective decision is the ceiling or deny, never wider."""
    widened = [
        (action, role)
        for action, rule in RULES.items()
        for role in ROLES
        if apply_override(rule.decisions.get(role), override)
        not in (rule.decisions.get(role), "deny")
    ]
    assert widened == []


@pytest.mark.parametrize(
    ("action", "role", "decision"),
    [
        ("request_item.create", "staff", "allow"),  # widens: no cell
        ("request_item.create", "manager", "allow"),  # 'allow' isn't narrower than allow
        ("engagement.read_metadata", "manager", "deny"),  # a read: visible() can't see it
        ("firm.manage_settings", "firm_admin", "deny"),  # self-lockout
        ("request_item.create", "system", "deny"),  # a platform role
    ],
)
async def test_margaret_cannot_write_an_override_that_widens_or_cannot_hold(
    firm: Firm, action: str, role: str, decision: str
) -> None:
    """Deny (the writer): the QM owner, a firm administrator with fresh MFA, is refused before
    anything is stored."""
    margaret = _ctx(MARGARET, "firm_admin")
    with pytest.raises(OverrideRefused):
        await set_policy_override(
            margaret, action, role, reason="ADM-02 template", decision=decision
        )


async def test_only_a_firm_administrator_writes_overrides(manager: AuthContext) -> None:
    with pytest.raises(Forbidden):
        await set_policy_override(manager, "request_item.create", "manager", reason="template")
