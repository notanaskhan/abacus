# ac-test-author: ayushkbhatia
"""T-01-T31 (ADR-078; TASK-2417): the independent suite for the engine bridge (T-01-T18 to
T-01-T20, T-01-T25 to T-01-T27), written from `docs/contracts/tax-engine-bridge.md`, the
human-only register and the row, not from the code.

The row's acceptance: "The suite ... passes on main, including a planted agent-context export that
fails at the matrix, live-human and database layers." Also: export only after final approval with
a valid grant (a voided grant refused), one export per approved checkpoint with identical bytes,
the download audited, Mark exported a person's and once, an import changes nothing until a
person approves it and the agent cannot approve it (INV-1), hostile engine files refused with a
reason and never echoed, and the chip moving through its states as the facts change.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import cast

import asyncpg
import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import Forbidden, authorise, engagement_resource
from abacus.modules.tax import export

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import (
    Json,
    call_as,
    engines,
    feld_return,
    final_approval_of,
    switched_on,
)

__all__ = ["engines", "switched_on"]  # the shared autouse engines and the switches


def _agent(feld_tenant: uuid.UUID) -> TenantContext:
    return TenantContext(feld_tenant, "agent", f"agent:preparer:{uuid.uuid4()}")


async def test_ac_a_planted_agent_export_fails_at_matrix_live_human_and_database(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    await final_approval_of(feld)
    planted = replace(feld.samuel, tenant=_agent(feld.tenant))
    # The matrix: `tax_return.export` is denied to the agent whatever its run's scope.
    resource = replace(
        await engagement_resource(feld.samuel.tenant, cast(uuid.UUID, feld.engagement)),
        work_item_id=feld.item,
    )
    with pytest.raises(Forbidden):
        await authorise(planted, export.EXPORT, resource)
    # The live-person check: the service refuses the agent before any grant is touched.
    with pytest.raises(Forbidden):
        await export.export_return(planted, feld.item, feld.checkpoint)
    over_http = await call_as(planted)(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-exports",
        json={"checkpoint_id": str(feld.checkpoint)},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert over_http.status_code in (403, 404)
    assert await feld.seed.value(
        "SELECT used_at IS NULL FROM approval_grants WHERE subject_id = $1", feld.item
    )
    # The database: no write operation and no export audit row can carry an agent.
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
    audit = (
        "WITH s AS (SELECT set_config('app.on_behalf_of', $4::text, true) AS v) "
        "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, "
        "target_id, on_behalf_of_user_id) SELECT $1::uuid, 'agent', $2::text, "
        "'engine_export.generated', 'tax_return', $3::text, $4::uuid FROM s"
    )
    actor = ("agent", "agent:preparer:planted")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await feld.seed.as_actor(
            feld.tenant, actor, audit, feld.tenant, actor[1], str(feld.item), feld.samuel.user_id
        )


async def test_export_needs_a_live_grant(migrated_db: MigratedDatabase, switched_on: None) -> None:
    feld = await feld_return(migrated_db)
    grant = await final_approval_of(feld)
    await feld.seed.run("UPDATE approval_grants SET voided_at = abacus_now() WHERE id = $1", grant)
    refused = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-exports",
        json={"checkpoint_id": str(feld.checkpoint)},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] in ("grant_refused", "not_final_approved")
    assert await feld.seed.value("SELECT count(*) FROM engine_exports") == 0


async def test_an_unapproved_checkpoint_is_never_exported(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    await final_approval_of(feld)
    other = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-exports",
        json={"checkpoint_id": str(uuid.uuid4())},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert (other.status_code, other.json()["detail"]) == (409, "not_final_approved")


async def test_mark_exported_is_a_persons_and_once(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    await final_approval_of(feld)
    made = cast(
        Json,
        (
            await feld.call(
                "POST",
                f"/v1/tax-returns/{feld.item}/engine-exports",
                json={"checkpoint_id": str(feld.checkpoint)},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )
        ).json(),
    )
    planted = replace(feld.samuel, tenant=_agent(feld.tenant))
    with pytest.raises(Forbidden):
        await export.mark_exported(planted, uuid.UUID(str(made["id"])), 1)
    async with feld.seed.held() as db:
        await db.execute("SELECT set_config('app.actor_kind', 'system', false)")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await db.execute(
                "UPDATE engine_exports SET marked_exported_at = now(), marked_exported_by = $1 "
                "WHERE id = $2",
                feld.samuel.user_id,
                uuid.UUID(str(made["id"])),
            )
    stale = await feld.call(
        "POST", f"/v1/engine-exports/{made['id']}/mark-exported", json={"seen_version": 7}
    )
    assert (stale.status_code, stale.json()["detail"]) == (409, "stale_version")


async def test_the_agent_cannot_approve_an_import(migrated_db: MigratedDatabase) -> None:
    feld = await feld_return(migrated_db)
    pending = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-imports",
        params={"kind": "values"},
        headers={"X-File-Name": "2025I_FeldJ_V4.csv"},
        content=(
            b"return_id,version,field_key,form,line,value\n"
            b"2025I:FeldJ,V4,f1040es_2026.voucher_amount,1040-ES,Q1-Q4,20000\n"
        ),
    )
    assert pending.status_code == 201, pending.text
    planted = replace(feld.samuel, tenant=_agent(feld.tenant))
    refused = await call_as(planted)(
        "POST",
        f"/v1/engine-imports/{pending.json()['id']}/approve",
        json={"accepted_field_keys": ["f1040es_2026.voucher_amount"], "seen_version": 1},
    )
    assert refused.status_code in (403, 404)
    sync = cast(Json, (await feld.call("GET", f"/v1/tax-returns/{feld.item}/engine-sync")).json())
    assert sync["state"] == "import_pending_approval"


@pytest.mark.parametrize(
    ("name", "content"),
    [
        (
            "evil.csv",
            b"return_id,version,field_key,form,line,value\n=cmd|' /C calc'!A0,V4,x,1,1,1\n",
        ),
        ("evil.csv", b"\xff\xfe not utf-8"),
        ("../../2025I_FeldJ_V3_k1.pdf", b"%PDF-1.7\n%%EOF"),
    ],
)
async def test_hostile_engine_files_are_refused_and_never_echoed(
    migrated_db: MigratedDatabase, name: str, content: bytes
) -> None:
    feld = await feld_return(migrated_db)
    kind = "pdfs" if name.endswith(".pdf") else "values"
    refused = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/engine-imports",
        params={"kind": kind},
        headers={"X-File-Name": name},
        content=content,
    )
    assert refused.status_code in (409, 422)
    assert "calc" not in refused.text and "../" not in refused.text
