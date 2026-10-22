"""F-03-T26 (ADR-146; DEC-129): the role-union shell and `scope_only` coverage, judged against
the grant for the target's own scope only. Postgres cases are in
tests/integration/test_client_access_grants.py."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import client_access
from abacus.modules.identity.client_access import FULL_ROLES, GRANT_ROLES, scope_covers, shell_of
from abacus.modules.identity.repository import GrantRow
from abacus.modules.identity.slots import ScopeFacts


@pytest.mark.parametrize(
    ("roles", "shell"),
    [
        ([], "none"),
        (["owner"], "full"),
        (["taxpayer", "k1_recipient"], "full"),  # Meera Shah: own 1040 and a K-1
        (["k1_recipient"], "k1"),
        (["k1_recipient", "k1_recipient"], "k1"),
        (["third_party"], "limited"),
        (["k1_recipient", "tcwg"], "limited"),
        (["component_auditor"], "limited"),
    ],
)
def test_the_shell_is_the_union_of_the_roles(roles: list[str], shell: str) -> None:
    assert shell_of(roles) == shell


def test_every_role_is_full_or_scoped() -> None:
    assert FULL_ROLES <= GRANT_ROLES
    scoped = GRANT_ROLES - FULL_ROLES
    assert scoped == {"third_party", "k1_recipient", "tcwg", "prospect", "component_auditor"}


TENANT = TenantContext(uuid.uuid4(), "human", "probe")
MEERA = uuid.uuid4()
OWN_RETURN, RIDGELINE_RETURN, K1_PACKAGE = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
SHAH_ENGAGEMENT, RIDGELINE_ENGAGEMENT = uuid.uuid4(), uuid.uuid4()
SHAH, RIDGELINE = uuid.uuid4(), uuid.uuid4()


def _grant(role: str, kind: str, scope: uuid.UUID) -> GrantRow:
    return GrantRow(uuid.uuid4(), MEERA, role, kind, scope, None, "active")


@pytest.fixture
def meera(monkeypatch: pytest.MonkeyPatch) -> None:
    """Meera Shah: a taxpayer grant on her own 1040 and a K-1 recipient grant on a Ridgeline K-1
    package. No resolver is registered for `k1_package` yet, so it covers nothing."""

    async def grants(_: TenantContext, user: uuid.UUID) -> list[GrantRow]:
        if user != MEERA:
            return []
        return [
            _grant("taxpayer", "work_item", OWN_RETURN),
            _grant("k1_recipient", "k1_package", K1_PACKAGE),
        ]

    async def resolve(_: TenantContext, kind: str, scope: uuid.UUID) -> ScopeFacts | None:
        if kind == "work_item" and scope == OWN_RETURN:
            return ScopeFacts(SHAH, engagement_id=SHAH_ENGAGEMENT, work_item_id=OWN_RETURN)
        return None

    async def client_of(_: TenantContext, engagement: uuid.UUID) -> uuid.UUID | None:
        return {SHAH_ENGAGEMENT: SHAH, RIDGELINE_ENGAGEMENT: RIDGELINE}.get(engagement)

    monkeypatch.setattr(client_access, "active_grants", grants)
    monkeypatch.setattr(client_access, "resolve_scope", resolve)
    monkeypatch.setattr(client_access, "engagement_client", client_of)


@pytest.mark.usefixtures("meera")
async def test_story_5_2_meera_reaches_her_own_return_only() -> None:
    assert await scope_covers(TENANT, MEERA, SHAH_ENGAGEMENT, OWN_RETURN) is True
    # Ridgeline's return: no grant names it (INV-4), so `scope_only` denies and routes 404.
    assert await scope_covers(TENANT, MEERA, RIDGELINE_ENGAGEMENT, RIDGELINE_RETURN) is False
    # A work-item grant isn't the whole engagement.
    assert await scope_covers(TENANT, MEERA, SHAH_ENGAGEMENT, None) is False
    assert await scope_covers(TENANT, MEERA, SHAH_ENGAGEMENT, uuid.uuid4()) is False


@pytest.mark.usefixtures("meera")
async def test_someone_without_grants_reaches_nothing() -> None:
    assert await scope_covers(TENANT, uuid.uuid4(), SHAH_ENGAGEMENT, OWN_RETURN) is False


async def test_an_engagement_grant_covers_its_engagement_and_a_client_grant_its_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engagement, other = uuid.uuid4(), uuid.uuid4()

    async def grants(*_: object) -> list[GrantRow]:
        return [_grant("owner", "engagement", engagement), _grant("trustee", "client", SHAH)]

    async def resolve(_: TenantContext, kind: str, scope: uuid.UUID) -> ScopeFacts | None:
        return ScopeFacts(SHAH) if kind == "client" and scope == SHAH else None

    async def client_of(_: TenantContext, e: uuid.UUID) -> uuid.UUID | None:
        return {engagement: RIDGELINE, other: SHAH}.get(e)

    monkeypatch.setattr(client_access, "active_grants", grants)
    monkeypatch.setattr(client_access, "resolve_scope", resolve)
    monkeypatch.setattr(client_access, "engagement_client", client_of)
    assert await scope_covers(TENANT, MEERA, engagement, uuid.uuid4()) is True
    assert await scope_covers(TENANT, MEERA, other, None) is True  # the client grant
    assert await scope_covers(TENANT, MEERA, uuid.uuid4(), None) is False


async def test_an_unregistered_scope_kind_covers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def grants(*_: object) -> list[GrantRow]:
        return [_grant("tcwg", "governance_room", uuid.uuid4())]

    async def client_of(*_: object) -> uuid.UUID:
        return SHAH

    monkeypatch.setattr(client_access, "active_grants", grants)
    monkeypatch.setattr(client_access, "engagement_client", client_of)
    assert await scope_covers(TENANT, MEERA, SHAH_ENGAGEMENT, None) is False


def test_a_scope_kind_has_one_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.identity import slots

    monkeypatch.setattr(slots, "_SCOPES", {})

    async def first(_: TenantContext, __: uuid.UUID) -> ScopeFacts | None:
        return None

    async def second(_: TenantContext, __: uuid.UUID) -> ScopeFacts | None:
        return None

    slots.register_scope_resolver("intake", first)
    slots.register_scope_resolver("intake", first)  # a reloaded module: no-op
    with pytest.raises(ValueError, match="already registered"):
        slots.register_scope_resolver("intake", second)
