"""A-04-T07 (TASK-2818; A-04 §3.1 AC1.9, §6 AC6.1, §7 AC7.1; SPEC-620 AC-9, AC-23; DEC-1867).

Row acceptance: "Northwind gets 67 procedures with 21 mandatory, tailoring a mandatory step returns
409 mandatory_step, and validating EBP v3 returns the BH-EBP-140 step 8 error verbatim." Also:
the procedures are written once (a second read writes nothing), tailoring needs a rationale and
the version the person saw, staff may not tailor, and the service-organization inventory AUD-04
and AUD-10 share adds, refuses a duplicate name and edits against its version.

Boundary: `create_app()` over HTTP on the migrated test database. The firm imports BH EBP v1 to v3
through K-01's workbook route (so the pinned version is "EBP v3"), and the engagement is pinned to
v3 as a roll-forward would leave it.
"""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.workpapers.api import PackConfigurationError, pack_errors, validate_pack
from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import spec_of, workbook

from .tb_support import Books, Json, books
from .test_k01t05_methodology_programs import (
    _import,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's workbook import
)

pytestmark = pytest.mark.asyncio

FLAGS: Final = ("workpapers.core", "methodology.programs")
TEMPLATE: Final = "BH Audit Methodology · EBP"
PACK_ERROR: Final = (
    "Pack configuration error: BH-EBP-140 step 8 points to a SOC 1 bridge-letter template that "
    "EBP v3 does not include. No evidence written."
)


@pytest.fixture
async def world(net: object) -> tuple[Books, uuid.UUID]:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    for flag in FLAGS:
        await found.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'A-04-T07') ON CONFLICT DO NOTHING",
            found.tenant_id,
            flag,
        )
    forget_flags()
    version = uuid.UUID(int=0)
    for number in (1, 2, 3):
        version = await _import(found.net, found.admin, TEMPLATE, workbook(spec_of("ebp", number)))
    await found.seed.run_untriggered(
        "UPDATE engagements SET methodology_version_id = $1 WHERE id = $2",
        version,
        found.site.engagement_id,
    )
    return found, version


def _path(world: Books, rest: str) -> str:
    return f"/v1/engagements/{world.site.engagement_id}{rest}"


async def _program(world: Books) -> list[Json]:
    response = await world.call("GET", _path(world, "/program-tailoring"), world.manager)
    assert response.status_code == 200, response.text
    return cast(list[Json], cast(Json, response.json())["items"])


async def _tailor(world: Books, who: object, row: Json, body: Json) -> tuple[int, Json]:
    response = await world.net.http.patch(
        _path(world, f"/procedures/{row['id']}"),
        json=body,
        headers={
            **world.net.headers(who),  # pyright: ignore[reportArgumentType] -- a seeded person
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    return response.status_code, cast(Json, response.json())


async def test_ac_northwind_gets_67_procedures_with_21_mandatory(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, version = world
    rows = await _program(books_)
    assert len(rows) == 67
    assert sum(1 for r in rows if r["mandatory"]) == 21
    assert {r["methodology_version_id"] for r in rows} == {str(version)}
    assert [(r["program_code"], r["number"]) for r in rows[:2]] == [
        ("BH-EBP-110", 1),
        ("BH-EBP-110", 2),
    ]
    # Written once: a second read writes nothing and the trail holds one instantiation.
    again = await _program(books_)
    assert [r["id"] for r in again] == [r["id"] for r in rows]
    events = await books_.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = $2",
        books_.tenant_id,
        "procedure.instantiated",
    )
    assert events == 1
    one_program = await books_.call(
        "GET", _path(books_, "/program-tailoring?program=BH-EBP-140"), books_.manager
    )
    assert {r["program_code"] for r in cast(list[Json], one_program.json()["items"])} == {
        "BH-EBP-140"
    }


async def test_ac_tailoring_a_mandatory_step_is_409_mandatory_step(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, _ = world
    mandatory = next(r for r in await _program(books_) if r["mandatory"])
    status, body = await _tailor(
        books_,
        books_.manager,
        mandatory,
        {"expected_version": 1, "tailored": True, "rationale": "Not applicable this year."},
    )
    assert (status, body["detail"]) == (409, "mandatory_step")


async def test_a_non_mandatory_step_is_tailored_with_a_rationale_against_its_version(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, _ = world
    step = next(r for r in await _program(books_) if not r["mandatory"])
    status, body = await _tailor(
        books_, books_.manager, step, {"expected_version": 1, "tailored": True}
    )
    assert (status, body["detail"]) == (422, "rationale_required")
    status, body = await _tailor(
        books_,
        books_.manager,
        step,
        {"expected_version": 1, "tailored": True, "rationale": "No participant loans in 2025."},
    )
    assert status == 200, body
    assert (body["tailored"], body["row_version"]) == (True, 2)
    assert body["tailored_rationale"] == "No participant loans in 2025."
    status, body = await _tailor(
        books_, books_.manager, step, {"expected_version": 1, "tailored": False}
    )
    assert (status, body["detail"]) == (409, "version_conflict")
    status, body = await _tailor(
        books_, books_.partner, step, {"expected_version": 2, "tailored": False}
    )
    assert status == 200, body
    assert (body["tailored"], body["tailored_rationale"]) == (False, None)


async def test_staff_may_not_tailor(world: tuple[Books, uuid.UUID]) -> None:
    books_, _ = world
    step = next(r for r in await _program(books_) if not r["mandatory"])
    status, _ = await _tailor(
        books_,
        books_.staff,
        step,
        {"expected_version": 1, "tailored": True, "rationale": "Not this year."},
    )
    assert status == 403


async def test_ac_validating_ebp_v3_returns_the_bh_ebp_140_step_8_error_verbatim(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, version = world
    tenant = TenantContext(books_.tenant_id, "system", "a04t07-test")
    errors = await pack_errors(tenant, version)
    assert [(e.program_code, e.number, e.ref) for e in errors] == [
        ("BH-EBP-140", 8, "request:soc1_bridge_letter")
    ]
    with pytest.raises(PackConfigurationError) as refused:
        await validate_pack(tenant, version)
    assert refused.value.message == PACK_ERROR
    assert refused.value.facts == {
        "program_code": "BH-EBP-140",
        "number": 8,
        "ref": "request:soc1_bridge_letter",
    }


async def test_the_service_organization_inventory_adds_refuses_a_duplicate_and_edits(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, _ = world
    body = {
        "name": "Harborline Trust Company",
        "services": "Trustee and custodian",
        "relevant": True,
        "evidence_type": "soc1_type2",
    }
    made = await books_.net.http.post(
        _path(books_, "/service-organizations"),
        json=body,
        headers={**books_.net.headers(books_.manager), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert made.status_code == 201, made.text
    org = cast(Json, made.json())
    assert (org["status"], org["row_version"], org["allowed_actions"]) == (
        "pending",
        1,
        ["service_org.edit"],
    )
    twice = await books_.net.http.post(
        _path(books_, "/service-organizations"),
        json={**body, "name": "  Harborline Trust Company "},
        headers={**books_.net.headers(books_.manager), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert (twice.status_code, twice.json()["detail"]) == (409, "duplicate_name")
    edited = await books_.net.http.patch(
        _path(books_, f"/service-organizations/{org['id']}"),
        json={"expected_version": 1, "evidence_type": "certification"},
        headers={**books_.net.headers(books_.manager), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert edited.status_code == 200, edited.text
    assert (edited.json()["evidence_type"], edited.json()["row_version"]) == ("certification", 2)
    stale = await books_.net.http.patch(
        _path(books_, f"/service-organizations/{org['id']}"),
        json={"expected_version": 1, "relevant": False},
        headers={**books_.net.headers(books_.manager), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert (stale.status_code, stale.json()["detail"]) == (409, "version_conflict")
    # The reviewer reads the inventory without its edit (the matrix gives staff the edit).
    listed = await books_.call("GET", _path(books_, "/service-organizations"), books_.reviewer)
    assert listed.status_code == 200, listed.text
    page = cast(Json, listed.json())
    assert [o["name"] for o in cast(list[Json], page["items"])] == ["Harborline Trust Company"]
    assert cast(list[Json], page["items"])[0]["allowed_actions"] == []
