"""T-01-T19 (TASK-2317; T-01 §3.9, §3.10; DEC-1363) over HTTP against Postgres: "The Feld V3 file
yields 5 differing fields that change nothing until Samuel Ito approves, and approving 3 of 5
rows creates a checkpoint with only those 3."

A smaller synthetic return stands in for the seed's Feld household: one engagement, one 1040,
Samuel Ito as manager with the manager-reviewer function. Rows are read back as the superuser.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity.api import AuthContext, current_context

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

Json = dict[str, object]
Call = Callable[..., Awaitable[httpx.Response]]
HEAD = "return_id,version,field_key,form,line,value\n"
V3 = (
    HEAD
    + "2025I:FeldJ,V3,co_dr0104pn.co_source_income,DR 0104PN,34,96989\n"
    + "2025I:FeldJ,V3,f1040.direct_deposit_last4,1040,35b,6620\n"
    + "2025I:FeldJ,V3,f1040es_2026.voucher_amount,1040-ES,Q1-Q4,19990\n"
    + "2025I:FeldJ,V3,f8879.signature_method,8879,Part II,practitioner_pin\n"
    + "2025I:FeldJ,V3,il1040_schnr.il_source_income,IL-1040 Sch NR,47,141634\n"
).encode()
ACCEPTED = [
    "f1040es_2026.voucher_amount",
    "il1040_schnr.il_source_income",
    "co_dr0104pn.co_source_income",
]


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


def _as(principal: AuthContext) -> Call:
    async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
        app = create_app()
        app.dependency_overrides[current_context] = lambda: principal
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

    return call


async def _person(seed: Seeder, tenant: uuid.UUID, name: str) -> AuthContext:
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
            name,
        ),
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, kind) "
            "VALUES ($1, $2, NULL, 'active', 'manager', 'staff') RETURNING id",
            tenant,
            user,
        ),
    )
    return AuthContext(
        TenantContext(tenant, "human", str(user)),
        user,
        membership,
        None,
        datetime.now(UTC) - timedelta(minutes=1),
    )


async def test_ac_v3_waits_for_samuel_and_three_of_five_become_engine_import_v3(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.engine_bridge', 'true', 't01-t19', 'T-01-T19')",
        tenant,
    )
    samuel = await _person(seed, tenant, "Samuel Ito")
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Feld Household') RETURNING id", tenant
    )
    entity = await seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Feld') "
        "RETURNING id",
        tenant,
        client,
    )
    engagement = await seed.value(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, 'Feld TY2025', "
        "'2025-01-01', '2025-12-31', $4) RETURNING id",
        tenant,
        client,
        entity,
        samuel.user_id,
    )
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'manager')",
        tenant,
        engagement,
        samuel.user_id,
    )
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', 'Feld 1040', $5) "
            "RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            samuel.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
        "form, tax_year) VALUES ($1, $2, $3, $4, '1040', 2025)",
        tenant,
        item,
        engagement,
        entity,
    )
    await seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'manager_reviewer', $4)",
        tenant,
        item,
        engagement,
        samuel.user_id,
    )
    call = _as(samuel)

    uploaded = await call(
        "POST",
        f"/v1/tax-returns/{item}/engine-imports",
        params={"kind": "values"},
        headers={"X-File-Name": "2025I_FeldJ_V3.csv", "Content-Type": "text/csv"},
        content=V3,
    )
    assert uploaded.status_code == 201, uploaded.text
    out = cast(Json, uploaded.json())
    assert out["status"] == "pending_approval"
    assert len(cast(list[Json], out["rows"])) == 5
    # Nothing on the return changed yet; the chip waits on a person.
    assert (
        await seed.value("SELECT count(*) FROM field_value_versions WHERE target_id = $1", item)
        == 0
    )
    sync = cast(Json, (await call("GET", f"/v1/tax-returns/{item}/engine-sync")).json())
    assert (sync["state"], sync["engine_return_id"]) == ("import_pending_approval", "2025I:FeldJ")
    again = await call(
        "POST",
        f"/v1/tax-returns/{item}/engine-imports",
        params={"kind": "values"},
        headers={"X-File-Name": "again.csv"},
        content=V3,
    )
    assert (again.status_code, again.json()["detail"]) == (409, "import_pending")

    approved = await call(
        "POST",
        f"/v1/engine-imports/{out['id']}/approve",
        json={"accepted_field_keys": ACCEPTED, "seen_version": 1},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    written = {
        r["field_key"]
        for r in await seed.rows(
            "SELECT field_key FROM field_value_versions WHERE target_id = $1 "
            "AND value_source = 'engine_import'",
            item,
        )
    }
    assert written == set(ACCEPTED)
    checkpoints = await seed.rows(
        "SELECT c.id, c.name, c.status FROM checkpoints c WHERE c.target_id = $1 ORDER BY seq",
        item,
    )
    assert [(c["status"]) for c in checkpoints] == ["rejected", "approved"]
    assert checkpoints[1]["name"] == "Engine import V3"
    kept = {
        r["field_key"]
        for r in await seed.rows(
            "SELECT field_key FROM checkpoint_diffs WHERE checkpoint_id = $1", checkpoints[1]["id"]
        )
    }
    assert kept == set(ACCEPTED)
    assert (
        await seed.value("SELECT version FROM engine_return_links WHERE return_id = $1", item) == 3
    )
    sync = cast(Json, (await call("GET", f"/v1/tax-returns/{item}/engine-sync")).json())
    assert sync["state"] == "synced"
