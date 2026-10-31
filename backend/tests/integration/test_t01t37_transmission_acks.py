"""T-01-T37 (TASK-2523; T-01 §3.13; R-04; DEC-1570) over HTTP against Postgres: "Daniel Reyes
records the Sep 18 transmission for federal, NY, IL and CO, Grace Holloway and the agent are
refused at every layer, and the four acks move the return to Accepted."

The Feld return (T-01-T19's world: Engine import V3 approved, so the chip reads Synced) with an
8879 binding as T-01-T36 leaves it. C7's e-file gate (a completed, non-superseded envelope) and
its retention extension are stubbed at filing's boundary so the test controls the signatures;
the status report is the fake engine's (federal ••••••2614, IL, CO, NY).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import cast

import asyncpg
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import filing
from abacus_tools.fakes.cch_axcess import CchAxcessFake, Export

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_t01t25_engine_export import Feld, Json, call_as, engines, feld_return

__all__ = ["engines"]

FELD = Export("2025I:FeldJ", 2025, "1040", ())
BOUND = {"US": {"agi": "245310", "refund": "253"}}
SENT = {"jurisdictions": ["US", "NY", "IL", "CO"], "method": "practitioner_pin"}


@dataclass
class Gate:
    envelope: uuid.UUID | None = None
    extended: list[tuple[uuid.UUID, date]] | None = None


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Iterator[Gate]:
    state = Gate(extended=[])

    async def efile_gate(tenant: object, return_id: uuid.UUID) -> tuple[uuid.UUID, date] | None:
        return None if state.envelope is None else (state.envelope, date(2026, 9, 17))

    async def extend(tenant: object, envelope_id: uuid.UUID, until: date) -> date:
        assert state.extended is not None
        state.extended.append((envelope_id, until))
        return until

    monkeypatch.setattr(filing, "efile_gate", efile_gate)
    monkeypatch.setattr(filing, "extend_retention", extend)
    yield state


async def _member(
    seed: Seeder,
    feld: Feld,
    name: str,
    role: str | None,
    *,
    signer: bool = False,
    firm_role: str | None = None,
) -> AuthContext:
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
            "VALUES ($1, $2, $3, 'active', 'manager', 'staff') RETURNING id",
            feld.tenant,
            user,
            firm_role,
        ),
    )
    if role:
        await seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            feld.tenant,
            feld.engagement,
            user,
            role,
        )
    if signer:
        await seed.run(
            "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
            "function, assigned_by) VALUES ($1, $2, $3, $4, 'signer', $4)",
            feld.tenant,
            feld.item,
            feld.engagement,
            user,
        )
    return AuthContext(
        TenantContext(feld.tenant, "human", str(user)),
        user,
        membership,
        cast(None, firm_role),
        datetime.now(UTC) - timedelta(minutes=1),
    )


@dataclass
class World:
    feld: Feld
    daniel: AuthContext
    grace: AuthContext
    admin: AuthContext
    binding: uuid.UUID
    envelope: uuid.UUID


async def _world(migrated_db: MigratedDatabase, gate: Gate) -> World:
    feld = await feld_return(migrated_db)
    seed = feld.seed
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.delivery_efile', 'true', 't01-t37', 'T-01-T37')",
        feld.tenant,
    )
    daniel = await _member(seed, feld, "Daniel Reyes", "engagement_partner", signer=True)
    grace = await _member(seed, feld, "Grace Holloway", "client_service")
    admin = await _member(seed, feld, "Felix Andersen", None, firm_role="firm_admin")
    await seed.run("UPDATE tax_returns SET status = 'approved' WHERE work_item_id = $1", feld.item)
    binding, envelope = uuid.uuid4(), uuid.uuid4()
    await seed.run(
        "INSERT INTO efile_amount_bindings (id, tenant_id, return_id, envelope_id, "
        "checkpoint_id, figures, figures_sha256, tolerances_ref) VALUES ($1, $2, $3, $4, $5, "
        "$6::jsonb, $7, $8)",
        binding,
        feld.tenant,
        feld.item,
        envelope,
        feld.checkpoint,
        json.dumps(BOUND),
        filing.figures_sha256(BOUND),
        uuid.UUID(int=85),
    )
    return World(feld, daniel, grace, admin, binding, envelope)


def _sent(world: World, **extra: object) -> dict[str, object]:
    return {
        **SENT,
        "transmitted_on": "2026-09-18",
        "seen_binding_id": str(world.binding),
        **extra,
    }


async def _designate(world: World, who: AuthContext, designated: bool = True) -> int:
    out = await call_as(world.admin)(
        "PUT", f"/v1/firm/members/{who.user_id}/ero", json={"designated": designated}
    )
    return out.status_code


async def _transmit(world: World, who: AuthContext, **extra: object) -> tuple[int, Json]:
    out = await call_as(who)(
        "POST",
        f"/v1/tax-returns/{world.feld.item}/transmissions",
        json=_sent(world, **extra),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    return out.status_code, cast(Json, out.json())


async def _status(world: World) -> str:
    return cast(
        str,
        await world.feld.seed.value(
            "SELECT status FROM tax_returns WHERE work_item_id = $1", world.feld.item
        ),
    )


async def _report(world: World, variant: str) -> None:
    """Samuel (manager on the return) uploads the engine's e-file status report."""
    uploaded = await call_as(world.feld.samuel)(
        "POST",
        f"/v1/tax-returns/{world.feld.item}/engine-imports",
        params={"kind": "acks"},
        headers={"X-File-Name": "2025I_FeldJ_efile_status.csv"},
        content=CchAxcessFake().efile_status_file(FELD, variant),  # pyright: ignore[reportArgumentType] -- the fake's variant literal
    )
    assert uploaded.status_code == 201, uploaded.text


async def test_ac_the_ero_designation_takes_a_firm_admin_with_fresh_mfa(
    migrated_db: MigratedDatabase, gate: Gate
) -> None:
    world = await _world(migrated_db, gate)
    stale = replace(world.admin, mfa_at=datetime.now(UTC) - timedelta(hours=3))
    refused = await call_as(stale)(
        "PUT", f"/v1/firm/members/{world.daniel.user_id}/ero", json={"designated": True}
    )
    assert refused.status_code == 403
    by_grace = await call_as(world.grace)(
        "PUT", f"/v1/firm/members/{world.daniel.user_id}/ero", json={"designated": True}
    )
    assert by_grace.status_code == 403
    assert await _designate(world, world.daniel) == 200
    designated = await world.feld.seed.value(
        "SELECT ero_designated FROM memberships WHERE user_id = $1", world.daniel.user_id
    )
    assert designated is True
    audited = await world.feld.seed.rows(
        "SELECT actor_id FROM audit_events WHERE action = 'member.ero_designated' "
        "AND target_id = $1",
        str(world.daniel.user_id),
    )
    assert [a["actor_id"] for a in audited] == [str(world.admin.user_id)]


async def test_ac_daniel_records_the_sep_18_transmission_and_the_return_is_filed(
    migrated_db: MigratedDatabase, gate: Gate
) -> None:
    world = await _world(migrated_db, gate)
    assert await _designate(world, world.daniel) == 200
    # Only Claire signed: the gate is unmet.
    status, body = await _transmit(world, world.daniel)
    assert (status, body["detail"]) == (409, "signatures_incomplete")
    gate.envelope = world.envelope
    # A binding he did not see (a relock since he read the page).
    status, body = await _transmit(world, world.daniel, seen_binding_id=str(uuid.uuid4()))
    assert (status, body["detail"]) == (409, "binding_superseded")
    status, body = await _transmit(world, world.daniel)
    assert status == 201, body
    assert body["jurisdictions"] == ["US", "NY", "IL", "CO"]
    assert body["transmitted_on"] == "2026-09-18"
    assert await _status(world) == "filed"
    rows = await world.feld.seed.rows(
        "SELECT ero_user_id, recorded_by, actor_kind, method FROM transmissions "
        "WHERE return_id = $1",
        world.feld.item,
    )
    assert [(r["ero_user_id"], r["actor_kind"], r["method"]) for r in rows] == [
        (world.daniel.user_id, "human", "practitioner_pin")
    ]
    moves = await world.feld.seed.rows(
        "SELECT event, actor_kind FROM tax_return_status_events WHERE work_item_id = $1 "
        "AND event IN ('envelope_sent', 'transmission_recorded') ORDER BY at",
        world.feld.item,
    )
    assert [(m["event"], m["actor_kind"]) for m in moves] == [
        ("envelope_sent", "human"),
        ("transmission_recorded", "human"),
    ]
    audited = await world.feld.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE action = 'transmission.recorded' "
        "AND target_id = $1",
        str(world.feld.item),
    )
    assert [(a["actor_kind"], a["actor_id"]) for a in audited] == [
        ("human", str(world.daniel.user_id))
    ]
    read = await call_as(world.grace)("GET", f"/v1/tax-returns/{world.feld.item}/delivery")
    assert cast(Json, read.json())["transmitted_on"] == "2026-09-18"


async def test_ac_grace_samuel_the_agent_and_the_system_are_refused_at_every_layer(
    migrated_db: MigratedDatabase, gate: Gate
) -> None:
    world = await _world(migrated_db, gate)
    gate.envelope = world.envelope
    # Layer 1-2 (matrix): Grace is client service, not the signer.
    status, _ = await _transmit(world, world.grace)
    assert status == 403
    # The ERO designation: Samuel is a signer on the return but not the firm's ERO.
    status, _ = await _transmit(world, world.feld.samuel)
    assert status == 403
    assert await _designate(world, world.feld.samuel) == 200
    assert await _designate(world, world.feld.samuel, designated=False) == 200
    status, _ = await _transmit(world, world.feld.samuel)
    assert status == 403
    # Layers 3-4 (a live person; the status machine): the agent, the system and support.
    assert await _designate(world, world.daniel) == 200
    for kind in ("agent", "system", "support"):
        planted = replace(
            world.daniel, tenant=TenantContext(world.feld.tenant, kind, f"{kind}:planted")
        )
        with pytest.raises(Forbidden):
            await filing.record_transmission(
                planted,
                world.feld.item,
                jurisdictions=["US"],
                transmitted_on=date(2026, 9, 18),
                method="practitioner_pin",
                seen_binding_id=world.binding,
            )
    with pytest.raises(NotFound):
        await filing.record_transmission(
            replace(world.daniel, client=True),
            world.feld.item,
            jurisdictions=["US"],
            transmitted_on=date(2026, 9, 18),
            method="practitioner_pin",
            seen_binding_id=world.binding,
        )
    # Layer 5 (the database): a transmission row from anyone but a person is refused.
    with pytest.raises(asyncpg.CheckViolationError):
        await world.feld.seed.run(
            "INSERT INTO transmissions (tenant_id, return_id, binding_id, envelope_id, "
            "ero_user_id, method, jurisdictions, transmitted_on, recorded_by, actor_kind) "
            "VALUES ($1, $2, $3, $4, $5, 'practitioner_pin', ARRAY['US'], '2026-09-18', $5, "
            "'agent')",
            world.feld.tenant,
            world.feld.item,
            world.binding,
            world.envelope,
            world.daniel.user_id,
        )
    assert await _status(world) == "approved"
    found = await world.feld.seed.value(
        "SELECT count(*) FROM transmissions WHERE return_id = $1", world.feld.item
    )
    assert found == 0


async def test_ac_the_four_acks_move_the_return_to_accepted_once(
    migrated_db: MigratedDatabase, gate: Gate
) -> None:
    world = await _world(migrated_db, gate)
    assert await _designate(world, world.daniel) == 200
    gate.envelope = world.envelope
    status, body = await _transmit(world, world.daniel)
    assert status == 201, body
    for _ in range(2):  # the report uploaded again is the same four acks
        await _report(world, "accepted")
    acks = await world.feld.seed.rows(
        "SELECT jurisdiction, status, submission_id_last4, source, transmission_id "
        "FROM efile_acks WHERE return_id = $1 ORDER BY jurisdiction",
        world.feld.item,
    )
    assert {(a["jurisdiction"], a["submission_id_last4"]) for a in acks} == {
        ("CO", "4407"),
        ("IL", "8831"),
        ("NY", "5190"),
        ("federal", "2614"),
    }
    assert len(acks) == 4
    assert {a["source"] for a in acks} == {"engine_file"}
    assert len({a["transmission_id"] for a in acks}) == 1
    assert await _status(world) == "accepted"
    announced = await world.feld.seed.rows(
        "SELECT payload ->> 'status' AS s FROM outbox WHERE event_type = 'filing.acknowledged' "
        "AND payload ->> 'return_id' = $1",
        str(world.feld.item),
    )
    assert [a["s"] for a in announced] == ["accepted"]
    # Pub 1345: the 8879 is kept until the IRS received date (Sep 18, 2026) plus three years.
    assert gate.extended and gate.extended[-1] == (world.envelope, date(2029, 9, 18))
    read = cast(
        Json,
        (await call_as(world.grace)("GET", f"/v1/tax-returns/{world.feld.item}/delivery")).json(),
    )
    assert len(cast(list[Json], read["acks"])) == 4


async def test_ac_a_federal_rejection_raises_its_issue_and_moves_rejected_to_fixing(
    migrated_db: MigratedDatabase, gate: Gate
) -> None:
    world = await _world(migrated_db, gate)
    assert await _designate(world, world.daniel) == 200
    gate.envelope = world.envelope
    status, _ = await _transmit(world, world.daniel)
    assert status == 201
    await _report(world, "rejected")
    assert await _status(world) == "rejected"
    ack = cast(
        uuid.UUID,
        await world.feld.seed.value(
            "SELECT id FROM efile_acks WHERE return_id = $1 AND status = 'rejected'",
            world.feld.item,
        ),
    )
    raised = await call_as(world.feld.samuel)(
        "POST",
        f"/v1/tax-returns/{world.feld.item}/acks/{ack}/issue",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert raised.status_code == 201, raised.text
    issues = await world.feld.seed.rows(
        "SELECT kind, source_ref FROM issues WHERE work_item_id = $1 AND kind = "
        "'engine_diagnostic' AND source_ref LIKE 'efile:%'",
        world.feld.item,
    )
    assert [i["source_ref"] for i in issues] == ["efile:federal:IND-181-01"]
    assert await _status(world) == "fixing"


async def test_a_manual_ack_requires_its_evidence_upload(
    migrated_db: MigratedDatabase, gate: Gate
) -> None:
    world = await _world(migrated_db, gate)
    out = await call_as(world.grace)(
        "POST",
        f"/v1/tax-returns/{world.feld.item}/acks",
        json={
            "jurisdiction": "US",
            "status": "accepted",
            "submission_id_last4": "2614",
            "received_at": "2026-09-18T14:47:00-05:00",
            "upload_id": str(uuid.uuid4()),
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert out.status_code == 409, out.text
    with pytest.raises(asyncpg.CheckViolationError):
        await world.feld.seed.run(
            "INSERT INTO efile_acks (tenant_id, return_id, jurisdiction, status, "
            "submission_id_last4, received_at, source, recorded_by) VALUES ($1, $2, 'federal', "
            "'accepted', '2614', abacus_now(), 'manual', $3)",
            world.feld.tenant,
            world.feld.item,
            world.grace.user_id,
        )
