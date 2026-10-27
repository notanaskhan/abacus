"""A-02-T19 (TASK-1419; ADR-078 independent AC suite) against Postgres: sealed integration
secrets (A-02 AC-13.3) and the write gate (AC-13.2; ADR-150; I-POLICY-NOT-ATTEST), written from
the acceptance criteria rather than the implementation.

- A secret is sealed with the tenant key and its owner row's id as associated data: the blob moved
  onto another install, or into another firm, does not open; the plaintext is never stored;
  erasing removes the only sealed copy and is audited.
- Every `execute_write` is refused `write_capability_refused` and audited, with defence in depth:
  a registry seeded to permit the write still meets the matrix (no role holds the action), and a
  gate whose matrix check is seeded away still refuses because v1 enables nothing.
- A W1-shaped capability is refused for an attest client at registry level whatever the file
  says, here a compiled entry seeded as enabled.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from abacus.kernel.crypto import DecryptionError, key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.integrations import writes
from abacus.modules.integrations.api import (
    WriteCapabilityEntry,
    WriteCapabilityRefused,
    erase_secret,
    execute_write,
    open_secret,
    registry,
    store_secret,
    write_capability,
)
from abacus.modules.integrations.capabilities import REASONS

from .support import Person, Seeder, Site

PLAINTEXT = b"synthetic-t19-token-not-a-secret"
W1 = next(w.key for w in registry().writes if w.shape == "W1")
OTHER = next(w.key for w in registry().writes if w.shape != "W1")


def _ctx(who: Person, firm_role: str | None = None, *, client: bool = False) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        client=client,
    )


async def _install(seed: Seeder, who: Person) -> uuid.UUID:
    """A firm-installed app in `who`'s firm, on a catalogue row of its own."""
    key = f"probe_{uuid.uuid4().hex[:12]}"
    await seed.run(
        "INSERT INTO integration_catalog (key, name, category, ownership_mode, surfaces, "
        "listing_status, scopes, icon, tone, sort_order, loaded_by) VALUES ($1, 'Probe bridge', "
        "'ledger', 'firm', ARRAY['workbench'], 'hidden', '{\"read\": []}'::jsonb, 'book-open', "
        "'olive', 1, 'probe-op')",
        key,
    )
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO firm_integrations (tenant_id, catalog_key, mode, created_by) "
            "VALUES ($1, $2, 'token', $3) RETURNING id",
            who.tenant_id,
            key,
            who.user_id,
        ),
    )


async def _sealed(seed: Seeder, install: uuid.UUID) -> tuple[bytes, str]:
    rows = await seed.rows(
        "SELECT sealed, key_id FROM integration_secrets WHERE firm_integration_id = $1", install
    )
    assert len(rows) == 1
    return bytes(rows[0]["sealed"]), str(rows[0]["key_id"])


async def _plant(seed: Seeder, tenant_id: uuid.UUID, install: uuid.UUID, sealed: bytes) -> None:
    """The seeded violation: a sealed blob copied, byte for byte, onto another owner row."""
    await seed.run(
        "INSERT INTO integration_secrets (tenant_id, firm_integration_id, sealed, key_id) "
        "VALUES ($1, $2, $3, $4)",
        tenant_id,
        install,
        sealed,
        key_service().key_id(tenant_id),
    )


async def _audits(seed: Seeder, tenant_id: uuid.UUID, action: str) -> list[dict[str, object]]:
    rows = await seed.rows(
        "SELECT target_type, target_id, after_ref FROM audit_events "
        "WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
        tenant_id,
        action,
    )
    out: list[dict[str, object]] = []
    for r in rows:
        raw: object = r["after_ref"]
        after = json.loads(raw) if isinstance(raw, str) else raw
        out.append({"target": (r["target_type"], str(r["target_id"])), "after": after or {}})
    return out


def _reason(audit: dict[str, object]) -> str:
    return REASONS[cast(int, cast(dict[str, object], audit["after"])["reason"])]


@pytest.fixture
async def admin(seed: Seeder) -> Person:
    return await seed.person(await seed.firm(), "firm_admin")


# --- sealed secrets (AC-13.3) --------------------------------------------------------------------


async def test_ac13_3_a_secret_opens_only_for_its_own_install(seed: Seeder, admin: Person) -> None:
    tenant = TenantContext(admin.tenant_id, "human", str(admin.user_id))
    owner = await _install(seed, admin)
    other = await _install(seed, admin)
    async with uow(tenant) as tx:
        await store_secret(tx, admin.tenant_id, owner, PLAINTEXT)
    assert await open_secret(tenant, owner) == PLAINTEXT

    sealed, key_id = await _sealed(seed, owner)
    assert PLAINTEXT not in sealed  # never stored in the clear
    assert key_id == key_service().key_id(admin.tenant_id)  # the tenant's key
    await _plant(seed, admin.tenant_id, other, sealed)
    with pytest.raises(DecryptionError):
        await open_secret(tenant, other)
    assert await open_secret(tenant, owner) == PLAINTEXT


async def test_ac13_3_a_secret_moved_into_another_firm_does_not_open(
    seed: Seeder, admin: Person
) -> None:
    tenant = TenantContext(admin.tenant_id, "human", str(admin.user_id))
    owner = await _install(seed, admin)
    async with uow(tenant) as tx:
        await store_secret(tx, admin.tenant_id, owner, PLAINTEXT)
    sealed, _ = await _sealed(seed, owner)

    stranger = await seed.person(await seed.firm(), "firm_admin")
    theirs = TenantContext(stranger.tenant_id, "human", str(stranger.user_id))
    assert await open_secret(theirs, owner) is None  # the row is not theirs to read
    install = await _install(seed, stranger)
    await _plant(seed, stranger.tenant_id, install, sealed)
    with pytest.raises(DecryptionError):
        await open_secret(theirs, install)


async def test_ac13_3_erasing_removes_the_only_sealed_copy(seed: Seeder, admin: Person) -> None:
    tenant = TenantContext(admin.tenant_id, "human", str(admin.user_id))
    owner = await _install(seed, admin)
    async with uow(tenant) as tx:
        await store_secret(tx, admin.tenant_id, owner, PLAINTEXT)
    async with uow(tenant) as tx:
        assert await erase_secret(tx, owner) is True
    left = await seed.value(
        "SELECT count(*) FROM integration_secrets WHERE firm_integration_id = $1", owner
    )
    assert left == 0
    assert await open_secret(tenant, owner) is None
    async with uow(tenant) as tx:
        assert await erase_secret(tx, owner) is False  # nothing left to erase, nothing audited
        tx.record("integration_secret.probed", target=Target("firm_integration", owner))
    stored = await _audits(seed, admin.tenant_id, "integration_secret.stored")
    erased = await _audits(seed, admin.tenant_id, "integration_secret.erased")
    assert [a["target"] for a in stored] == [("firm_integration", str(owner))]
    assert [a["target"] for a in erased] == [("firm_integration", str(owner))]
    for audit in (*stored, *erased):
        assert PLAINTEXT.decode() not in json.dumps(audit["after"])


# --- the write gate (AC-13.2) --------------------------------------------------------------------


@pytest.fixture
async def site(seed: Seeder, admin: Person) -> Site:
    return await seed.site(admin.tenant_id, admin.user_id, "a02t19")


@pytest.mark.parametrize("role", ["manager", "senior"])
async def test_ac13_2_every_declared_and_undeclared_write_is_refused_and_audited_once(
    seed: Seeder, site: Site, role: str
) -> None:
    who = await seed.person(site.tenant_id)
    await seed.member(site, who, role)  # pyright: ignore[reportArgumentType] -- a staff role
    capabilities = [w.key for w in registry().writes] + ["ledger_void_invoices"]
    for capability in capabilities:
        with pytest.raises(WriteCapabilityRefused) as refused:
            await execute_write(_ctx(who), capability, site.client_id, idempotency_key="t19")
        assert refused.value.code == "write_capability_refused"
    found = await _audits(seed, site.tenant_id, "write_capability.refused")
    assert len(found) == len(capabilities)
    for audit, capability in zip(found, capabilities, strict=True):
        assert audit["target"] == ("client", str(site.client_id))
        after = cast(dict[str, object], audit["after"])
        assert after["capability"] == hashlib.sha256(capability.encode()).hexdigest()
        assert capability not in json.dumps(after)


async def test_ac13_2_a_registry_seeded_to_permit_still_meets_the_matrix(
    seed: Seeder, site: Site, admin: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defence in depth: were the registry to stop refusing, no role holds the action."""

    def no_refusal(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(writes, "policy_refusal", no_refusal)
    with pytest.raises(WriteCapabilityRefused) as refused:
        await execute_write(_ctx(admin, "firm_admin"), OTHER, site.client_id)
    assert refused.value.reason == "not_permitted"

    async def permit(*_args: object) -> None:
        return None

    monkeypatch.setattr(writes, "authorise", permit)  # and were the matrix check gone too
    with pytest.raises(WriteCapabilityRefused) as still:
        await execute_write(_ctx(admin, "firm_admin"), OTHER, site.client_id)
    assert still.value.reason == "not_enabled"  # v1 enables nothing: refused all the same
    found = await _audits(seed, site.tenant_id, "write_capability.refused")
    assert [_reason(a) for a in found] == ["not_permitted", "not_enabled"]


async def test_ac13_2_w1_is_refused_for_an_attest_client_even_when_seeded_enabled(
    seed: Seeder, site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    def enabled(key: str) -> WriteCapabilityEntry | None:
        entry = write_capability(key)
        if entry is None:
            return None
        return entry.model_copy(update={"enabled": True})  # unvalidated: what a later file says

    monkeypatch.setattr(writes, "write_capability", enabled)
    await seed.attest(site.tenant_id, site.engagement_id)
    partner = await seed.person(site.tenant_id)
    await seed.member(site, partner, "engagement_partner")
    with pytest.raises(WriteCapabilityRefused) as refused:
        await execute_write(_ctx(partner), W1, site.client_id)
    assert refused.value.reason == "attest_client"
    with pytest.raises(WriteCapabilityRefused) as other:  # not W1: the matrix still refuses
        await execute_write(_ctx(partner), OTHER, site.client_id)
    assert other.value.reason != "attest_client"
    found = await _audits(seed, site.tenant_id, "write_capability.refused")
    assert [_reason(a) for a in found] == ["attest_client", other.value.reason]
    assert cast(dict[str, object], found[0]["after"])["shape"] == 1
