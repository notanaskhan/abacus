"""SPEC-014 AC-1, AC-2, AC-3 (TASK-029): on firm-level reads a person's engagement roles on
non-archived engagements count toward the matrix decision, against a real Postgres: the real
lookup (identity's `engagement_roles_in_firm`) and the real subquery of active engagements
(registered by the engagements module).

Expectations come from the spec and the permission matrix, not the implementation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest
import yaml

from abacus.kernel.db import TenantContext
from abacus.modules.engagements import api as _engagements  # registers the active engagements
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus_tools.codegen import permission_matrix as pm

from .support import Net, Person, Role, Seeder, Site

assert _engagements  # imported for its registration

ENGAGEMENT_ROLES: tuple[Role, ...] = (
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
)
READ_VERBS = {"read", "read_metadata", "read_log"}
MATRIX = cast(dict[str, dict[str, str]], yaml.safe_load(pm.SOURCE.read_text())["actions"])
FIRM_READS = sorted(a for a in MATRIX if a.split(".", 1)[1] in READ_VERBS)


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC),
    )


async def _allowed(who: Person, action: str) -> bool:
    try:
        await authorise(_ctx(who), action, Resource.firm(who.tenant_id))
    except Forbidden:
        return False
    return True


async def _archive(seed: Seeder, site: Site, *, archived: bool = True) -> None:
    await seed.run(
        "UPDATE engagements SET status = $2 WHERE id = $1",
        site.engagement_id,
        "archived" if archived else "active",
    )


@pytest.fixture
async def firm(seed: Seeder) -> uuid.UUID:
    return await seed.firm()


async def _team_member(seed: Seeder, tenant_id: uuid.UUID, role: Role) -> tuple[Person, Site]:
    admin = await seed.person(tenant_id)
    site = await seed.site(tenant_id, admin.user_id, "reads")
    member = await seed.person(tenant_id)  # no firm role
    await seed.member(site, member, role)
    return member, site


async def test_ac1_a_senior_on_an_active_engagement_reads_the_firms_knowledge(
    seed: Seeder, firm: uuid.UUID, net: Net
) -> None:
    senior, _ = await _team_member(seed, firm, "senior")
    assert await _allowed(senior, "knowledge.read")
    response = await net.call("GET", "/v1/knowledge/documents", senior)
    assert response.status_code == 200, response.text


async def test_ac1_a_person_with_no_role_anywhere_reads_nothing_at_firm_level(
    seed: Seeder, firm: uuid.UUID, net: Net
) -> None:
    nobody = await seed.person(firm)
    assert not await _allowed(nobody, "knowledge.read")
    assert (await net.call("GET", "/v1/knowledge/documents", nobody)).status_code == 403


async def test_ac2_a_manager_lists_methodology_templates_and_a_senior_does_not(
    seed: Seeder, firm: uuid.UUID, net: Net
) -> None:
    manager, _ = await _team_member(seed, firm, "manager")
    senior, _ = await _team_member(seed, firm, "senior")
    allowed = await net.call("GET", "/v1/methodology/templates", manager)
    assert allowed.status_code == 200, allowed.text
    refused = await net.call("GET", "/v1/methodology/templates", senior)
    assert refused.status_code == 403
    assert refused.json() == {"detail": "forbidden"}


@pytest.mark.parametrize("role", ENGAGEMENT_ROLES)
async def test_ac1_ac2_each_firm_level_read_follows_the_matrix_for_each_engagement_role(
    seed: Seeder, firm: uuid.UUID, role: Role
) -> None:
    member, _ = await _team_member(seed, firm, role)
    wrong: list[str] = []
    for action in FIRM_READS:
        entry = MATRIX[action]
        # A fresh-MFA person; a read that also needs a reason is never reached by role alone.
        expected = entry.get(role) == "allow" and entry.get("requires") != "reason"
        if await _allowed(member, action) != expected:
            wrong.append(f"{action}: expected {expected}")
    assert wrong == []
    assert any(MATRIX[a].get(role) == "allow" for a in FIRM_READS)  # the sweep proves something


@pytest.mark.parametrize("role", ENGAGEMENT_ROLES)
async def test_ac3_an_archived_engagement_no_longer_counts(
    seed: Seeder, firm: uuid.UUID, role: Role
) -> None:
    member, site = await _team_member(seed, firm, role)
    granted = [
        a for a in FIRM_READS if MATRIX[a].get(role) == "allow" and await _allowed(member, a)
    ]
    assert granted, "this role is granted some firm-level read while the engagement is active"
    await _archive(seed, site)
    assert [a for a in granted if await _allowed(member, a)] == []
    await _archive(seed, site, archived=False)  # and it counts again when it is
    assert [a for a in granted if not await _allowed(member, a)] == []


async def test_ac3_only_the_active_engagements_role_counts(seed: Seeder, firm: uuid.UUID) -> None:
    """A manager on an archived engagement and a senior on an active one: the senior's rights."""
    admin = await seed.person(firm)
    old = await seed.site(firm, admin.user_id, "old")
    current = await seed.site(firm, admin.user_id, "current")
    both = await seed.person(firm)
    await seed.member(old, both, "manager")
    await seed.member(current, both, "senior")
    await _archive(seed, old)
    assert await _allowed(both, "knowledge.read")  # the senior's
    assert not await _allowed(both, "methodology.read")  # the archived manager's, not counted


async def test_ac3_an_engagement_of_another_firm_never_counts(
    seed: Seeder, firm: uuid.UUID
) -> None:
    other = await seed.firm()
    admin = await seed.person(other)
    site = await seed.site(other, admin.user_id, "elsewhere")
    traveller = await seed.person(firm, also=other)  # a member of both firms, no firm role
    here = Person(traveller.user_id, firm, traveller.subject)
    there = Person(traveller.user_id, other, traveller.subject)
    await seed.member(site, there, "manager")  # a manager, but in the other firm
    assert not await _allowed(here, "methodology.read")
    assert await _allowed(there, "methodology.read")
