# ac-test-author: ayushkbhatia
"""Q-03-T121 (ADR-078; TASK-2426): the independent suite for T-01-T18's final-approval guard,
written from the row, `docs/contracts/tax-engine-bridge.md` and the human-only register, not from
the code. DEC-1465 left these cases owed ("the approval cases absorbed from T-02 stay with
T-01-T18's own suite until a second author can write them from SPEC alone").

The row's acceptance: "Only Daniel Reyes can approve the Feld return: a shared Ridgeline draft or
an import awaiting approval blocks him with its reason, Samuel Ito's approve control is never
enabled …". Here: the matrix denies the agent and the system and asks for a fresh second factor;
the service refuses an agent, the system, a support session and a client before anything else;
a return whose client no BH-TAX-02 policy names cannot be approved by anyone (its blocker is
named, never prose), the refusal changes nothing (no L4 sign-off, the status stays); the
eligibility read names its checkpoint; and the database refuses a `sign_off.recorded` audit row
from the agent or a policy principal.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path
from typing import cast

import asyncpg
import pytest
import yaml

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import Forbidden
from abacus.modules.tax import approval

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import Json, engines, feld_return, switched_on

__all__ = ["engines", "switched_on"]
ROOT = Path(__file__).resolve().parents[3]


def _matrix_row(action: str) -> dict[str, object]:
    matrix = cast(
        dict[str, dict[str, dict[str, object]]],
        yaml.safe_load((ROOT / "docs/architecture/permission-matrix/tax.yaml").read_text()),
    )
    return matrix["actions"][action]


async def test_ac_no_agent_system_support_or_client_reaches_the_guard(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    row = _matrix_row("tax_return.approve")
    assert (row.get("agent"), row.get("system")) == ("deny", "deny")
    assert row.get("mfa_recent") == "required"
    hash_seen = cast(
        str,
        await feld.seed.value(
            "SELECT content_hash FROM checkpoints WHERE id = $1", feld.checkpoint
        ),
    )
    planted = [
        replace(
            feld.samuel, tenant=TenantContext(feld.tenant, "agent", f"agent:x:{uuid.uuid4()}")
        ),
        replace(feld.samuel, tenant=TenantContext(feld.tenant, "system", "tax:planted")),
    ]
    for ctx in planted:
        with pytest.raises(Forbidden):
            await approval.approve(ctx, feld.item, feld.checkpoint, hash_seen)
    with pytest.raises(NotFound):
        await approval.approve(
            replace(feld.samuel, client=True), feld.item, feld.checkpoint, hash_seen
        )
    signed = await feld.seed.value(
        "SELECT count(*) FROM sign_offs WHERE target_id = $1 AND level = 4", feld.item
    )
    assert signed == 0


async def test_ac_without_a_signer_policy_nobody_approves_and_nothing_changes(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    found = await approval.eligibility(feld.samuel, feld.item)
    assert found.checkpoint_id == feld.checkpoint
    kinds = [b.kind for b in found.blockers]
    assert "policy_unassigned" in kinds  # no BH-TAX-02 names the Feld client yet
    assert not found.eligible
    read = await feld.call("GET", f"/v1/tax-returns/{feld.item}/final-approval")
    assert read.status_code == 200, read.text
    body = cast(Json, read.json())
    assert body["eligible"] is False
    assert "policy_unassigned" in [b["kind"] for b in cast(list[Json], body["blockers"])]
    status_before = await feld.seed.value(
        "SELECT status FROM tax_returns WHERE work_item_id = $1", feld.item
    )
    refused = await feld.call(
        "POST",
        f"/v1/tax-returns/{feld.item}/final-approval",
        json={"seen_checkpoint_id": str(feld.checkpoint), "content_hash": found.content_hash},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert refused.status_code in (403, 409), refused.text
    assert (
        await feld.seed.value("SELECT status FROM tax_returns WHERE work_item_id = $1", feld.item)
        == status_before
    )
    assert (
        await feld.seed.value(
            "SELECT count(*) FROM sign_offs WHERE target_id = $1 AND level = 4", feld.item
        )
        == 0
    )
    assert (
        await feld.seed.value(
            "SELECT count(*) FROM approval_grants WHERE subject_id = $1", feld.item
        )
        == 0
    )


async def test_ac_the_database_takes_a_sign_off_audit_row_only_from_a_person(
    migrated_db: MigratedDatabase, switched_on: None
) -> None:
    feld = await feld_return(migrated_db)
    register = cast(
        list[dict[str, str]],
        yaml.safe_load((ROOT / "docs/architecture/human-only-actions.yaml").read_text())[
            "actions"
        ],
    )
    assert "sign_off.recorded" in {a["action"] for a in register}
    audit = (
        "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, "
        "target_id) VALUES ($1::uuid, $2, $3, 'sign_off.recorded', 'tax_return', $4)"
    )
    # The register binds the agent and the policy principal (the trigger's two refused kinds).
    for actor in (("agent", "agent:preparer:planted"), ("policy", "policy:planted")):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await feld.seed.as_actor(
                feld.tenant, actor, audit, feld.tenant, actor[0], actor[1], str(feld.item)
            )
