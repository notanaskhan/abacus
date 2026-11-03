"""A-05-T19 against Postgres through the routes (TASK-3021; DEC-2068): "The Northwind census
imports 301 participants with SSNs sealed, and a register whose total does not foot is refused
with the difference shown."

The synthetic Northwind census and PayGrid register are uploaded as evidence versions on the
audit's engagement and imported through `POST /v1/audits/{id}/ebp/imports`: the register foots
to its keyed control total, the census ties to it and to the W-3 and writes 301 participants
with every SSN sealed (no plaintext digits in any table), and a register keyed with a different
total is recorded `refused` with its difference. Participants list masked.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Final

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import uow
from abacus.modules.evidence.api import NewItem, Provenance, add_version, stage_content
from abacus_tools.synthetic.scenarios.brightwater_hale import ebp

from .tb_support import Books, books

pytestmark = pytest.mark.asyncio

XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CENSUS_MAP: Final = {
    "participant_key": "Participant",
    "name": "Name",
    "ssn": "SSN",
    "hire_on": "Hire date",
    "status": "Status",
    "compensation": "Compensation",
}
REGISTER_MAP: Final = {
    "pay_date": "Pay date",
    "gross": "Gross wages",
    "deferral": "401(k) deferrals",
}
WAGES: Final = sum((p.wages for p in ebp.payrolls()), Decimal(0))


@pytest.fixture
async def world(net: object, object_store: str) -> Books:
    del object_store  # the uploads go to this session's S3, not the dev gateway (TASK-2927)
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    await found.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'ebp.modules', 'true', 'test-seed', 'A-05-T19') ON CONFLICT DO NOTHING",
        found.tenant_id,
    )
    forget_flags()
    return found


async def _version(world: Books, content: bytes) -> uuid.UUID:
    stored = await stage_content(world.tenant_id, content)
    async with uow(TenantContext(world.tenant_id, "system", "evidence.upload_processing")) as tx:
        ref = await add_version(
            tx,
            engagement_id=world.site.engagement_id,
            item=NewItem(f"Upload {uuid.uuid4().hex[:6]}"),
            stored=stored,
            media_type=XLSX,
            provenance=Provenance(source="upload", method="uploaded"),
        )
    return ref.id


async def _import(world: Books, body: dict[str, object]) -> httpx.Response:
    return await world.call(
        "POST",
        f"/v1/audits/{world.work_item_id}/ebp/imports",
        world.senior,
        body,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )


async def _register(world: Books, total: Decimal) -> httpx.Response:
    return await _import(
        world,
        {
            "evidence_version_id": str(await _version(world, ebp.payroll_register_xlsx())),
            "kind": "payroll_register",
            "column_map": REGISTER_MAP,
            "control_totals": {"gross": str(total)},
        },
    )


async def test_ac_the_northwind_census_imports_301_participants_sealed(world: Books) -> None:
    register = await _register(world, WAGES)
    assert register.status_code == 201, register.text
    response = await _import(
        world,
        {
            "evidence_version_id": str(await _version(world, ebp.census_xlsx())),
            "kind": "census",
            "column_map": CENSUS_MAP,
            "w3_box1": str(ebp.W3_BOX1),
            "w3_box12d": str(ebp.W3_BOX12D),
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["status"], body["row_count"]) == ("imported", 301)
    assert body["totals"]["compensation"] == "14560000.00"
    sealed = await world.seed.value(
        "SELECT count(*) FROM ebp_participants WHERE tenant_id = $1 AND ssn_sealed IS NOT NULL "
        "AND ssn_fp IS NOT NULL AND ssn_last4 IS NOT NULL",
        world.tenant_id,
    )
    assert sealed == 301
    first = ebp.census()[0]
    dump = await world.seed.value(
        "SELECT string_agg(t::text, '') FROM ebp_participants t WHERE tenant_id = $1",
        world.tenant_id,
    )
    assert f"XXX-XX-{first.ssn_last4}" not in str(dump)  # sealed, only the last four in clear
    listed = await world.call(
        "GET", f"/v1/audits/{world.work_item_id}/ebp/participants", world.senior
    )
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert page["total"] == 301
    assert page["items"][0]["dob_masked"] == "••/••/••••"
    assert page["items"][0]["ssn"]["last4"] == first.ssn_last4


async def test_ac_a_register_that_does_not_foot_is_refused_with_the_difference(
    world: Books,
) -> None:
    response = await _register(world, WAGES + Decimal("125.40"))
    assert response.status_code == 422, response.text
    facts: dict[str, str] = response.json()["facts"]
    assert (facts["reason"], facts["column"], facts["difference"]) == (
        "import_not_footing",
        "gross",
        "125.40",
    )
    shown = await world.call(
        "GET",
        f"/v1/audits/{world.work_item_id}/ebp/imports/{facts['import_id']}",
        world.senior,
    )
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert (body["status"], body["refusal_code"]) == ("refused", "import_not_footing")
    assert body["totals"]["refusal"] == {"differences": {"gross": "-125.40"}}


async def test_a_census_that_does_not_tie_to_the_w3_is_refused_and_writes_no_participant(
    world: Books,
) -> None:
    response = await _import(
        world,
        {
            "evidence_version_id": str(await _version(world, ebp.census_xlsx())),
            "kind": "census",
            "column_map": CENSUS_MAP,
            "w3_box1": str(ebp.W3_BOX1 - Decimal("600.00")),
            "w3_box12d": str(ebp.W3_BOX12D),
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["facts"]["reason"] == "import_not_tying"
    participants = await world.seed.value(
        "SELECT count(*) FROM ebp_participants WHERE tenant_id = $1", world.tenant_id
    )
    assert participants == 0
