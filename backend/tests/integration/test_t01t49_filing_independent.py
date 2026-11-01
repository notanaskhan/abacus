"""T-01-T49 (TASK-2621; ADR-078) against Postgres: independent tests for T-01-T35's packet approval
rights (DEC-38) and T-01-T37's transmission record and ERO designation, through the routes.

- A senior or a staff member on the return never approves the delivery packet (only the signer or
  a manager does, DEC-38); assembling asks no model.
- A partner whose ERO designation was withdrawn can no longer record a transmission.
- A return already transmitted takes no second transmission record.
"""

from __future__ import annotations

import uuid
from typing import cast

from abacus.modules.identity.api import AuthContext

from . import test_t01t35_delivery_packet as t01t35
from . import test_t01t37_transmission_acks as t01t37
from .conftest import MigratedDatabase
from .test_t01t25_engine_export import Json, call_as, engines, switched_on

__all__ = ["engines", "gate", "no_gateway", "switched_on"]
# The implementing suites' worlds and fixtures, reused as seeds only (DEC-1668).
gate = t01t37.gate
no_gateway = t01t35.no_gateway
_world = t01t37._world  # pyright: ignore[reportPrivateUsage] -- T-01-T37's world seed
_designate = t01t37._designate  # pyright: ignore[reportPrivateUsage] -- T-01-T37's seed
_transmit = t01t37._transmit  # pyright: ignore[reportPrivateUsage] -- T-01-T37's seed
_ready = t01t35._ready  # pyright: ignore[reportPrivateUsage] -- T-01-T35's world seed
_member = t01t35._member  # pyright: ignore[reportPrivateUsage] -- T-01-T35's seed
_assemble_path = t01t35._assemble_path  # pyright: ignore[reportPrivateUsage] -- T-01-T35's seed


async def test_ac_dec38_a_senior_or_staff_member_never_approves_the_packet(
    migrated_db: MigratedDatabase, switched_on: None, no_gateway: list[object]
) -> None:
    feld = await _ready(migrated_db)
    grace = await _member(feld.seed, feld, "Grace Holloway", "client_service")
    made = await call_as(grace)(
        "POST", _assemble_path(feld), headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert made.status_code == 201, made.text
    packet = cast(Json, made.json())
    assert no_gateway == []  # assembly asked no model
    for name, role in (("Ana Cruz", "staff"), ("Marcus Delaney", "senior")):
        who: AuthContext = await _member(feld.seed, feld, name, role)
        refused = await call_as(who)(
            "POST", f"/v1/delivery-packets/{packet['id']}/approve", json={"seen_version": 1}
        )
        assert refused.status_code == 403, (role, refused.text)
    still = await feld.seed.value(
        "SELECT status FROM delivery_packets WHERE id = $1", uuid.UUID(cast(str, packet["id"]))
    )
    assert still == "draft"


async def test_ac_a_withdrawn_ero_designation_refuses_the_transmission(
    migrated_db: MigratedDatabase, gate: t01t37.Gate
) -> None:
    world = await _world(migrated_db, gate)
    gate.envelope = world.envelope
    assert await _designate(world, world.daniel) == 200
    assert await _designate(world, world.daniel, designated=False) == 200
    status, body = await _transmit(world, world.daniel)
    assert status == 403, body
    count = await world.feld.seed.value(
        "SELECT count(*) FROM transmissions WHERE return_id = $1", world.feld.item
    )
    assert count == 0


async def test_ac_a_transmitted_return_takes_no_second_record(
    migrated_db: MigratedDatabase, gate: t01t37.Gate
) -> None:
    world = await _world(migrated_db, gate)
    gate.envelope = world.envelope
    assert await _designate(world, world.daniel) == 200
    first, body = await _transmit(world, world.daniel)
    assert first == 201, body
    second, body = await _transmit(world, world.daniel, transmitted_on="2026-09-19")
    assert second == 409, body
    count = await world.feld.seed.value(
        "SELECT count(*) FROM transmissions WHERE return_id = $1", world.feld.item
    )
    assert count == 1
