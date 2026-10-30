"""T-01-T25 (TASK-2414; T-01 §3.9; tax-engine-bridge §2, §6; DEC-1462) over HTTP against Postgres:
"Samuel Ito exports 2025I:FeldJ:V3 only after final approval, the same checkpoint yields
byte-identical files, and a second consume of the grant is refused."

The T-01-T19 Feld return is imported and approved as Engine import V3; the final approval's
outcome (the return at Approved and its grant on that checkpoint's hash) is written as the
superuser, since final approval itself is T-01-T18's and tested there. The W2 capability and the
firm's install are switched on by patching the two reads the export makes (the registry ships W2
disabled until P-18 is accepted; ADR-150).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import asyncpg
import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.integrations.api import ExportSettings
from abacus.modules.tax import export

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


@dataclass
class Feld:
    seed: Seeder
    tenant: uuid.UUID
    samuel: AuthContext
    item: uuid.UUID
    engagement: object
    checkpoint: uuid.UUID
    call: Call


async def _feld(migrated_db: MigratedDatabase) -> Feld:
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
    await seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'signer', $4)",
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
    approved = await call(
        "POST",
        f"/v1/engine-imports/{out['id']}/approve",
        json={"accepted_field_keys": ACCEPTED, "seen_version": 1},
    )
    assert approved.status_code == 200, approved.text
    assert approved.status_code == 200, approved.text
    checkpoint = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM checkpoints WHERE target_id = $1 AND status = 'approved'", item
        ),
    )
    return Feld(seed, tenant, samuel, item, engagement, checkpoint, call)


async def _final_approval(feld: Feld, *, open_for: timedelta = timedelta(days=1)) -> uuid.UUID:
    """What T-01-T18's approval leaves behind: the return Approved and one grant on the hash."""
    seed = feld.seed
    await seed.run("UPDATE tax_returns SET status = 'approved' WHERE work_item_id = $1", feld.item)
    digest = cast(
        str,
        await seed.value("SELECT content_hash FROM checkpoints WHERE id = $1", feld.checkpoint),
    )
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO approval_grants (tenant_id, subject_type, subject_id, action, "
            "approver_user_id, engagement_id, work_item_id, payload_sha256, not_before, "
            "expires_at) VALUES ($1, 'tax_return', $2, 'tax_return.approve', $3, $4, $2, $5, "
            "abacus_now() - interval '1 minute', abacus_now() + $6::interval) RETURNING id",
            feld.tenant,
            feld.item,
            feld.samuel.user_id,
            feld.engagement,
            digest.removeprefix("sha256:"),
            f"{int(open_for.total_seconds())} seconds",
        ),
    )


@pytest.fixture
def switched_on(monkeypatch: pytest.MonkeyPatch) -> None:
    async def settings_on(tenant: object) -> ExportSettings:
        return ExportSettings(
            enabled=True,
            return_id_template="{Tax year}{Type}:{Client code}:V{n}",
            client_code_rule="last_name_first_initial",
            type_letters={"1040": "I"},
            who_may_export="reviewer_manager_signer",
        )

    def enabled(key: str) -> SimpleNamespace:
        return SimpleNamespace(key=key, enabled=True)

    monkeypatch.setattr(export, "write_capability", enabled)
    monkeypatch.setattr(export, "export_settings", settings_on)


async def test_ac_samuel_exports_v3_only_after_final_approval(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await _feld(migrated_db)
    body = {"checkpoint_id": str(feld.checkpoint)}
    key = {"Idempotency-Key": str(uuid.uuid4())}
    before = await feld.call(
        "POST", f"/v1/tax-returns/{feld.item}/engine-exports", json=body, headers=key
    )
    assert (before.status_code, before.json()["detail"]) == (409, "not_final_approved")
    await _final_approval(feld)
    made = await feld.call(
        "POST", f"/v1/tax-returns/{feld.item}/engine-exports", json=body, headers=key
    )
    assert made.status_code == 201, made.text
    out = cast(Json, made.json())
    assert out["file_name"] == "2025I_FeldJ_V3.xlsx"
    operations = await feld.seed.rows(
        "SELECT capability, payload_sha256 FROM write_operations WHERE subject_id = $1", feld.item
    )
    assert [(o["capability"], o["payload_sha256"]) for o in operations] == [
        ("tax_engine_file_bridge", out["sha256"])
    ]
    events = await feld.seed.rows(
        "SELECT kind FROM engine_sync_events WHERE return_id = $1 ORDER BY at", feld.item
    )
    assert events[-1]["kind"] == "export_generated"

    downloaded = await feld.call("GET", f"/v1/engine-exports/{out['id']}/file")
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == out["sha256"]
    assert (
        await feld.seed.value(
            "SELECT count(*) FROM audit_events WHERE action = 'engine_export.downloaded' "
            "AND tenant_id = $1",
            feld.tenant,
        )
        == 1
    )

    marked = await feld.call(
        "POST", f"/v1/engine-exports/{out['id']}/mark-exported", json={"seen_version": 1}
    )
    assert marked.status_code == 200, marked.text
    sync = cast(Json, (await feld.call("GET", f"/v1/tax-returns/{feld.item}/engine-sync")).json())
    assert sync["state"] == "synced"
    again = await feld.call(
        "POST", f"/v1/engine-exports/{out['id']}/mark-exported", json={"seen_version": 2}
    )
    assert (again.status_code, again.json()["detail"]) == (409, "already_marked")


async def test_ac_the_same_checkpoint_yields_byte_identical_files(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await _feld(migrated_db)
    await _final_approval(feld)
    body = {"checkpoint_id": str(feld.checkpoint)}
    first = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-exports",
        json=body,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    second = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-exports",
        json=body,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["sha256"] == second.json()["sha256"]
    book = export.workbook(
        engine_id="2025I:FeldJ:V3",
        tax_year=2025,
        form="1040",
        values={
            "f1040.l1z": {"t": "money", "v": "123223.00"},
            "f1040.name": {"t": "text", "v": "=1+1"},
        },
        at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert book == export.workbook(
        engine_id="2025I:FeldJ:V3",
        tax_year=2025,
        form="1040",
        values={
            "f1040.name": {"t": "text", "v": "=1+1"},
            "f1040.l1z": {"t": "money", "v": "123223.00"},
        },
        at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert (
        await feld.seed.value(
            "SELECT count(*) FROM write_operations WHERE subject_id = $1", feld.item
        )
        == 1
    )


async def test_ac_a_second_consume_of_the_grant_is_refused(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await _feld(migrated_db)
    grant = await _final_approval(feld)
    made = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-exports",
        json={"checkpoint_id": str(feld.checkpoint)},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert made.status_code == 201, made.text
    # The same grant handed to another export (another consumer) is refused by identity's gate.
    from abacus.modules.identity.api import consume_grant

    digest = cast(
        str,
        await feld.seed.value("SELECT payload_sha256 FROM approval_grants WHERE id = $1", grant),
    )
    assert await consume_grant(feld.tenant, grant, uuid.uuid4(), digest) is False
    # And the database keeps one write per grant.
    with pytest.raises(asyncpg.UniqueViolationError):
        await feld.seed.run(
            "INSERT INTO write_operations (tenant_id, capability, subject_type, subject_id, "
            "grant_id, payload_sha256, performed_by, actor_kind) VALUES ($1, "
            "'tax_engine_file_bridge', 'tax_return', $2, $3, $4, $5, 'human')",
            feld.tenant,
            feld.item,
            grant,
            "0" * 64,
            feld.samuel.user_id,
        )


async def test_switches_and_people_only(migrated_db: MigratedDatabase) -> None:
    feld = await _feld(migrated_db)
    await _final_approval(feld)
    body = {"checkpoint_id": str(feld.checkpoint)}
    off = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-exports",
        json=body,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert (off.status_code, off.json()["detail"]) == (409, "export_disabled")
    agent = replace(
        feld.samuel, tenant=TenantContext(feld.tenant, "agent", f"agent:preparer:{uuid.uuid4()}")
    )
    refused = await _as(agent)(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-exports",
        json=body,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert refused.status_code == 403
    with pytest.raises(asyncpg.CheckViolationError):
        await feld.seed.run(
            "INSERT INTO write_operations (tenant_id, capability, subject_type, subject_id, "
            "grant_id, payload_sha256, performed_by, actor_kind) VALUES ($1, "
            "'tax_engine_file_bridge', 'tax_return', $2, gen_random_uuid(), $3, $4, 'agent')",
            feld.tenant,
            feld.item,
            "0" * 64,
            feld.samuel.user_id,
        )


def test_client_codes() -> None:
    assert export.client_code("last_name_first_initial", "Jonah & Claire Feld") == "FeldJ"
    assert export.client_code("entity_name", "Ridgeline Property Partners, LP") == (
        "RidgelinePropertyPar"
    )
