"""TASK-2152 (ADR-342; DEC-1279) against Postgres: a firm's DocuSeal install.

The catalogue's hidden `docuseal` row loads through the operator's load (once; a second load
keeps it); `connect` writes the install and its sealed secret in one unit of work, audited by
id; a second live install is refused; `rotate` replaces the only sealed copy; `disconnect` erases
it and closes the install, after which a new install may be made; a requester outside the firm
is refused by the database; and with W7 closed the adapter still gets no secret.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest
from sqlalchemy.exc import IntegrityError

from abacus.modules.integrations.api import (
    EsignInstallExists,
    connect_esign_install,
    disconnect_esign_install,
    esign_install_secret,
    esign_install_state,
    open_secret,
    rotate_esign_secret,
)
from abacus.modules.platform.api import operator_context
from abacus_tools import esign_install as tool

from .support import Migrated, Person, Seeder

OPERATOR = "probe-op"
FIRST = tool.secret_of("synthetic0key0one0not0a0secret0")
SECOND = tool.secret_of("synthetic0key0two0not0a0secret0")


def _ops(migrated_db: Migrated) -> str:
    # bootstrap-local.sql gives abacus_ops the local password; the role has EXECUTE only.
    url = migrated_db.app_url.replace("abacus_app:abacusapp", "abacus_ops:abacusops", 1)
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest.fixture
async def admin(seed: Seeder, migrated_db: Migrated) -> Person:
    await tool.ensure_catalogue_row(_ops(migrated_db), OPERATOR)
    return await seed.person(await seed.firm(), "firm_admin")


async def _installs(seed: Seeder, tenant_id: uuid.UUID) -> list[tuple[str, str]]:
    rows = await seed.rows(
        "SELECT id, status FROM firm_integrations WHERE tenant_id = $1 AND catalog_key = "
        "'docuseal' ORDER BY created_at",
        tenant_id,
    )
    return [(str(r["id"]), str(r["status"])) for r in rows]


async def _secrets(seed: Seeder, install: uuid.UUID) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT count(*) FROM integration_secrets WHERE firm_integration_id = $1", install
        ),
    )


async def test_the_catalogue_row_loads_once(seed: Seeder, migrated_db: Migrated) -> None:
    await tool.ensure_catalogue_row(_ops(migrated_db), OPERATOR)
    assert await tool.ensure_catalogue_row(_ops(migrated_db), OPERATOR) == "unchanged"
    row = (
        await seed.rows(
            "SELECT category, listing_status, adapter_key FROM integration_catalog "
            "WHERE key = 'docuseal'"
        )
    )[0]
    assert (row["category"], row["listing_status"], row["adapter_key"]) == (
        "esignature",
        "hidden",
        "docuseal",
    )


async def test_connect_seals_the_key_for_the_install_and_audits_by_id(
    seed: Seeder, admin: Person
) -> None:
    tenant = operator_context(admin.tenant_id, OPERATOR)
    install = await connect_esign_install(tenant, admin.user_id, FIRST)
    assert await open_secret(tenant, install) == FIRST
    assert await esign_install_state(tenant) == "connected"
    sealed = await seed.value(
        "SELECT sealed FROM integration_secrets WHERE firm_integration_id = $1", install
    )
    assert b"synthetic0key0one" not in bytes(cast(bytes, sealed))  # never stored in the clear
    audits = await seed.rows(
        "SELECT action, actor_id, target_id::text AS target FROM audit_events "
        "WHERE tenant_id = $1 AND target_type = 'firm_integration' ORDER BY seq",
        admin.tenant_id,
    )
    assert [(a["action"], a["target"]) for a in audits] == [
        ("integration_secret.stored", str(install)),
        ("firm_integration.connected", str(install)),
    ]
    assert {a["actor_id"] for a in audits} == {f"operator:{OPERATOR}"}
    # W7 is declared, never enabled: the adapter gets no secret for a connected install.
    assert await esign_install_secret(tenant) is None


async def test_a_second_live_install_is_refused(seed: Seeder, admin: Person) -> None:
    tenant = operator_context(admin.tenant_id, OPERATOR)
    await connect_esign_install(tenant, admin.user_id, FIRST)
    with pytest.raises(EsignInstallExists):
        await connect_esign_install(tenant, admin.user_id, SECOND)
    assert len(await _installs(seed, admin.tenant_id)) == 1


async def test_rotate_replaces_the_only_sealed_copy(seed: Seeder, admin: Person) -> None:
    tenant = operator_context(admin.tenant_id, OPERATOR)
    install = await connect_esign_install(tenant, admin.user_id, FIRST)
    assert await rotate_esign_secret(tenant, SECOND) == install
    assert await open_secret(tenant, install) == SECOND
    assert await _secrets(seed, install) == 1


async def test_disconnect_erases_the_key_and_a_new_install_may_follow(
    seed: Seeder, admin: Person
) -> None:
    tenant = operator_context(admin.tenant_id, OPERATOR)
    first = await connect_esign_install(tenant, admin.user_id, FIRST)
    assert await disconnect_esign_install(tenant) == first
    assert await _secrets(seed, first) == 0
    assert await esign_install_state(tenant) == "none"
    assert await open_secret(tenant, first) is None
    again = await connect_esign_install(tenant, admin.user_id, SECOND)
    assert again != first
    assert await _installs(seed, admin.tenant_id) == [
        (str(first), "disconnected"),
        (str(again), "connected"),
    ]


async def test_a_requester_outside_the_firm_is_refused(seed: Seeder, admin: Person) -> None:
    stranger = await seed.person(await seed.firm(), "firm_admin")
    tenant = operator_context(admin.tenant_id, OPERATOR)
    with pytest.raises(IntegrityError):
        await connect_esign_install(tenant, stranger.user_id, FIRST)
    assert await _installs(seed, admin.tenant_id) == []
