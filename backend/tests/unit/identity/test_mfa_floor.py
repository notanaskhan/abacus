"""P-08-T17 (SPEC-320 AC-10; DEC-34): the MFA floor slot fails closed, and the firm's policy can
only make it stricter. Without a database: the policy read is replaced."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import mfa_floor
from abacus.modules.identity.mfa_floor import (
    FLOOR,
    PortalSecurityPolicy,
    mfa_required,
    register_mfa_requirement,
)

TENANT, USER = uuid.uuid4(), uuid.uuid4()


async def _no(_tenant: TenantContext, _user: uuid.UUID) -> bool:
    return False


async def _yes(_tenant: TenantContext, _user: uuid.UUID) -> bool:
    return True


@pytest.fixture(autouse=True)
def floor(monkeypatch: pytest.MonkeyPatch) -> dict[str, mfa_floor.MfaRequirement]:
    registered: dict[str, mfa_floor.MfaRequirement] = dict.fromkeys(FLOOR, _no)
    monkeypatch.setattr(mfa_floor, "_REQUIREMENTS", registered)

    async def policy(_tenant: uuid.UUID) -> PortalSecurityPolicy:
        return PortalSecurityPolicy()

    monkeypatch.setattr(mfa_floor, "portal_security_policy", policy)
    return registered


async def test_ac10_no_predicate_true_means_no_second_step() -> None:
    assert not await mfa_required(TENANT, USER)


async def test_ac10_any_true_predicate_requires_it(
    floor: dict[str, mfa_floor.MfaRequirement],
) -> None:
    floor["owner_grant"] = _yes
    assert await mfa_required(TENANT, USER)


async def test_ac10_a_raising_predicate_requires_it(
    floor: dict[str, mfa_floor.MfaRequirement],
) -> None:
    async def raises(_tenant: TenantContext, _user: uuid.UUID) -> bool:
        raise LookupError("down")

    floor["tri_scope"] = raises
    assert await mfa_required(TENANT, USER)


async def test_ac10_a_slow_predicate_requires_it(
    floor: dict[str, mfa_floor.MfaRequirement], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def slow(_tenant: TenantContext, _user: uuid.UUID) -> bool:
        await asyncio.sleep(1)
        return False

    monkeypatch.setattr(mfa_floor, "PREDICATE_SECONDS", 0.05)
    floor["tri_scope"] = slow
    assert await mfa_required(TENANT, USER)


@pytest.mark.parametrize("missing", sorted(FLOOR))
async def test_ac10_an_unregistered_floor_predicate_requires_it(
    floor: dict[str, mfa_floor.MfaRequirement], missing: str
) -> None:
    del floor[missing]
    assert await mfa_required(TENANT, USER)


async def test_ac10_an_unreadable_policy_requires_it(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken(_tenant: uuid.UUID) -> PortalSecurityPolicy:
        raise ConnectionError

    monkeypatch.setattr(mfa_floor, "portal_security_policy", broken)
    assert await mfa_required(TENANT, USER)


async def test_ac10_the_firm_may_widen_the_floor_to_every_client_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def everyone(_tenant: uuid.UUID) -> PortalSecurityPolicy:
        return PortalSecurityPolicy(mfa_for_all_client_users=True)

    monkeypatch.setattr(mfa_floor, "portal_security_policy", everyone)
    assert await mfa_required(TENANT, USER)


def test_ac10_a_name_registers_one_predicate() -> None:
    register_mfa_requirement("owner_grant", _no)  # the same function again is fine
    with pytest.raises(ValueError, match="already registered"):
        register_mfa_requirement("owner_grant", _yes)


def test_ac10_the_floor_is_owner_grants_and_signing_and_approving_designations() -> None:
    # T-01-T12 adds the TRI-bearing scopes (a K-1 package, a tax return work item or an
    # engagement holding one).
    assert {"owner_grant", "engagement_designation", "tri_scope"} == FLOOR
