"""A-02-T15 (TASK-1415; SPEC-333 AC-50; A-02 AC-13.2; ADR-150, ADR-040): every `execute_write`
call is refused `write_capability_refused` and audited, for every principal, and a W1-shaped
capability is refused for an attest client at registry level.

The audit event is on the client, written in its own unit of work so it is kept although the
call fails; its references are a fingerprint of the capability key and the reason's index (no
text, ADR-031). No writer is ever called: none exists.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext
from abacus.modules.integrations.api import (
    WriteCapabilityRefused,
    authorise_write,
    execute_write,
    registry,
)
from abacus.modules.integrations.capabilities import REASONS

from .support import Person, Seeder, Site


def _ctx(
    who: Person, firm_role: str | None, *, kind: str = "human", client: bool = False
) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, kind, str(who.user_id)),  # pyright: ignore[reportArgumentType] -- an actor-kind code
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        client=client,
    )


async def _refusals(seed: Seeder, site: Site) -> list[dict[str, object]]:
    rows = await seed.rows(
        "SELECT target_type, target_id, after_ref FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'write_capability.refused' ORDER BY seq",
        site.tenant_id,
    )
    return [{"target": (r["target_type"], r["target_id"]), "after": r["after_ref"]} for r in rows]


def _shape(key: str) -> str:
    return next(w.shape for w in registry().writes if w.key == key)


W1 = next(w.key for w in registry().writes if w.shape == "W1")
OTHERS = [w.key for w in registry().writes if w.shape != "W1"]


@pytest.fixture
async def site(seed: Seeder) -> Site:
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    return await seed.site(tenant, admin.user_id, "a02t15")


@pytest.mark.parametrize("capability", [W1, *OTHERS, "ledger_delete_everything"])
@pytest.mark.parametrize("role", ["firm_admin", "engagement_partner", "agent", "client"])
async def test_ac50_every_execute_write_is_refused_and_audited(
    seed: Seeder, site: Site, capability: str, role: str
) -> None:
    who = await seed.person(site.tenant_id, "firm_admin" if role == "firm_admin" else None)
    if role == "engagement_partner":
        await seed.member(site, who, "engagement_partner")
    if role == "client":
        who = await seed.client_contact(site)
    ctx = _ctx(
        who,
        "firm_admin" if role == "firm_admin" else None,
        kind="agent" if role == "agent" else "human",
        client=role == "client",
    )
    with pytest.raises(WriteCapabilityRefused) as refused:
        await execute_write(
            ctx, capability, site.client_id, approval_ref=uuid.uuid4(), idempotency_key="k-1"
        )
    assert refused.value.code == "write_capability_refused"
    found = await _refusals(seed, site)
    assert len(found) == 1
    assert found[0]["target"] == ("client", str(site.client_id))
    after = cast(dict[str, object], found[0]["after"])
    assert after["capability"] == hashlib.sha256(capability.encode()).hexdigest()
    expected = "unknown_capability" if capability.startswith("ledger_delete") else "not_enabled"
    assert REASONS[cast(int, after["reason"])] == expected
    assert capability not in str(after)  # the key itself is never written


async def test_ac50_w1_is_refused_for_an_attest_client_and_says_why(
    seed: Seeder, site: Site
) -> None:
    await seed.attest(site.tenant_id, site.engagement_id)
    partner = await seed.person(site.tenant_id)
    await seed.member(site, partner, "engagement_partner")
    with pytest.raises(WriteCapabilityRefused) as refused:
        await authorise_write(_ctx(partner, None), W1, site.client_id)
    assert refused.value.reason == "attest_client"
    for key in OTHERS:  # other shapes are refused because nothing is enabled
        with pytest.raises(WriteCapabilityRefused) as other:
            await authorise_write(_ctx(partner, None), key, site.client_id)
        assert other.value.reason == "not_enabled"
    reasons = [
        REASONS[cast(int, cast(dict[str, object], r["after"])["reason"])]
        for r in await _refusals(seed, site)
    ]
    assert reasons == ["attest_client", *["not_enabled"] * len(OTHERS)]
    assert _shape(W1) == "W1"


async def test_a_client_outside_the_firm_is_refused_without_naming_it(
    seed: Seeder, site: Site
) -> None:
    admin = await seed.person(site.tenant_id, "firm_admin")
    stranger = uuid.uuid4()
    with pytest.raises(WriteCapabilityRefused) as refused:
        await execute_write(_ctx(admin, "firm_admin"), W1, stranger)
    assert refused.value.reason == "unknown_client"
