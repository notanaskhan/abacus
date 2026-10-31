"""K-01-T18 (TASK-2705; K-01 §3.6, AC3.4, AC7.7, AC7.9; DEC-1755): "The seeded EBP v3 import diffs
against v2 as 4 added, 9 changed, 1 removed and 54 unchanged on every run, and approve returns 409
while a flag is open."

Hannah (a firm admin, `methodology.manage`) imports; Margaret (a practice leader, the QM owner)
approves. v2 goes in through the SPEC-008 route; v3 through the import-review routes (a workbook
alone parses now). A parse flag and an unverified source are seeded as the importer (K-01-T21)
would leave them, below the triggers.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Final, cast

import httpx
import pytest
from types_boto3_s3 import S3Client

from abacus_tools.synthetic.scenarios.brightwater_hale.methodology import spec_of, workbook

from .ledger_support import bucket, wire_storage
from .support import Json, Net, Person
from .test_k01t05_methodology_programs import (
    _flags,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's flag seeding
    _import,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's workbook import
)

pytestmark = pytest.mark.asyncio

FLAGS = ("methodology.programs", "methodology.lifecycle", "methodology.import_review")
TEMPLATE = "BH Audit Methodology · EBP"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# The import's files go to evidence storage through the platform file store (DEC-1759): the
# suite's own bucket, so nothing reaches for a default endpoint.
BUCKET: Final = f"backfill-k01t18-{uuid.uuid4().hex[:10]}"
MASTER: Final = b"backfill-k01t18-import-master-key-01234567"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> S3Client:
    return bucket(s3_settings, BUCKET)


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    yield from wire_storage(raw, BUCKET, MASTER)


async def _new_import(net: Net, who: Person, key: str) -> Json:
    made = await net.http.post(
        "/v1/methodology/imports",
        json={"template_name": TEMPLATE, "engagement_types": ["ebp_audit"]},
        headers={**net.headers(who), "Idempotency-Key": key},
    )
    assert made.status_code == 201, made.text
    return cast(Json, made.json())


async def _put(
    net: Net, who: Person, import_id: str, role: str, name: str, data: bytes
) -> httpx.Response:
    return await net.http.put(
        f"/v1/methodology/imports/{import_id}/files/{role}?filename={name}",
        content=data,
        headers={**net.headers(who), "Content-Type": "application/octet-stream"},
    )


async def _v3(net: Net, hannah: Person) -> uuid.UUID:
    imp = await _new_import(net, hannah, f"k01t18-{uuid.uuid4()}")
    put = await _put(
        net,
        hannah,
        cast(str, imp["id"]),
        "workbook",
        "BH EBP v3.xlsx",
        workbook(spec_of("ebp", 3)),
    )
    assert put.status_code == 200, put.text
    started = await net.call("POST", f"/v1/methodology/imports/{imp['id']}/start", hannah)
    assert started.status_code == 200, started.text
    out = cast(Json, started.json())
    assert out["status"] == "needs_review"
    return uuid.UUID(cast(str, out["version_id"]))


async def test_ac6_1_the_seeded_v3_import_diffs_4_9_1_54_on_every_run(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    await _flags(net, tenant, *FLAGS)
    v2 = await _import(net, hannah, TEMPLATE, workbook(spec_of("ebp", 2)))
    v3 = await _v3(net, hannah)
    first = await net.call("GET", f"/v1/methodology/versions/{v3}/diff", hannah)
    assert first.status_code == 200, first.text
    body = cast(Json, first.json())
    assert body["against_version_id"] == str(v2)
    assert body["tiles"] == {"added": 4, "changed": 9, "removed": 1, "unchanged": 54}
    again = await net.call("GET", f"/v1/methodology/versions/{v3}/diff?against={v2}", hannah)
    assert again.json() == body
    # The source file is the workbook as uploaded, written once and never with its storage key.
    files = await seed.rows(
        "SELECT f.role, f.scan_status, f.sha256 FROM methodology_source_files f "
        "JOIN methodology_imports i ON i.id = f.import_id WHERE i.version_id = $1",
        v3,
    )
    assert [(r["role"], r["scan_status"]) for r in files] == [("workbook", "clean")]
    assert "storage_key" not in str(body)


async def test_ac3_4_approve_is_409_while_a_flag_is_open_then_a_confirm_clears_it(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "practice_leader")
    await _flags(net, tenant, *FLAGS)
    v3 = await _v3(net, hannah)
    step = (
        await seed.rows(
            "SELECT s.id, s.row_version FROM program_steps s JOIN programs p "
            "ON p.id = s.program_id "
            "WHERE s.version_id = $1 AND p.code = 'BH-EBP-110' AND s.number = 7",
            v3,
        )
    )[0]
    await seed.run_untriggered(
        "UPDATE program_steps SET parse_flag = 'split_across_pages' WHERE id = $1", step["id"]
    )
    state = cast(
        Json, (await net.call("GET", f"/v1/methodology/versions/{v3}/state", margaret)).json()
    )
    approve = {
        "effective_from": "2026-01-01",
        "checklist_hash": state["checklist_hash"],
        "row_version": state["row_version"],
    }
    blocked = await net.call(
        "POST", f"/v1/methodology/versions/{v3}/approve", margaret, body=approve
    )
    assert (blocked.status_code, blocked.json()["detail"]) == (409, "flags_open")

    # Hannah confirms the parse: the step keeps its key and its text; the event names her.
    resolved = await net.call(
        "POST",
        f"/v1/methodology/versions/{v3}/steps/{step['id']}/flag-resolution",
        hannah,
        body={"action": "confirm", "row_version": step["row_version"]},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolution"] == "confirmed"
    twice = await net.call(
        "POST",
        f"/v1/methodology/versions/{v3}/steps/{step['id']}/flag-resolution",
        hannah,
        body={"action": "confirm", "row_version": resolved.json()["row_version"]},
    )
    assert (twice.status_code, twice.json()["detail"]) == (409, "flag_not_open")
    activity = cast(
        Json, (await net.call("GET", f"/v1/methodology/versions/{v3}/activity", hannah)).json()
    )
    kinds = [e["kind"] for e in cast(list[Json], activity["items"])]
    assert "import_started" in kinds and "flag_resolved" in kinds
    assert all(
        e["actor_name"]
        for e in cast(list[Json], activity["items"])
        if e["kind"] == "flag_resolved"
    )

    ok = await net.call("POST", f"/v1/methodology/versions/{v3}/approve", margaret, body=approve)
    assert ok.status_code == 200, ok.text


async def test_ac7_5_an_unverified_source_blocks_approval(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "practice_leader")
    await _flags(net, tenant, *FLAGS)
    v3 = await _v3(net, hannah)
    step_id = (await seed.rows("SELECT id FROM program_steps WHERE version_id = $1 LIMIT 1", v3))[
        0
    ]["id"]
    file_id = (
        await seed.rows(
            "SELECT f.id FROM methodology_source_files f JOIN methodology_imports i "
            "ON i.id = f.import_id WHERE i.version_id = $1",
            v3,
        )
    )[0]["id"]
    await seed.run(
        "INSERT INTO program_step_sources (tenant_id, step_id, source_file_id, page_from, "
        "page_to, verified, verify_reason) VALUES ($1, $2, $3, 1, 1, false, 'quote_not_found')",
        tenant,
        step_id,
        file_id,
    )
    state = cast(
        Json, (await net.call("GET", f"/v1/methodology/versions/{v3}/state", margaret)).json()
    )
    blocked = await net.call(
        "POST",
        f"/v1/methodology/versions/{v3}/approve",
        margaret,
        body={
            "effective_from": "2026-01-01",
            "checklist_hash": state["checklist_hash"],
            "row_version": state["row_version"],
        },
    )
    assert (blocked.status_code, blocked.json()["detail"]) == (409, "unverified_sources")


async def test_ac7_7_a_document_import_needs_the_importer_and_keys_are_idempotent(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    await _flags(net, tenant, *FLAGS)
    first = await _new_import(net, hannah, "k01t18-same-key")
    second = await _new_import(net, hannah, "k01t18-same-key")
    assert first["id"] == second["id"]
    started = await net.call("POST", f"/v1/methodology/imports/{first['id']}/start", hannah)
    assert (started.status_code, started.json()["detail"]) == (409, "files_missing")
    put = await _put(
        net,
        hannah,
        cast(str, first["id"]),
        "workbook",
        "BH EBP v3.xlsx",
        workbook(spec_of("ebp", 3)),
    )
    assert put.status_code == 200, put.text
    again = await _put(
        net,
        hannah,
        cast(str, first["id"]),
        "workbook",
        "BH EBP v3.xlsx",
        workbook(spec_of("ebp", 3)),
    )
    assert (again.status_code, again.json()["detail"]) == (409, "file_exists")


async def test_standards_mapping_refuses_an_unknown_set_and_the_flag_hides_the_routes(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    off = await net.http.post(
        "/v1/methodology/imports",
        json={"template_name": TEMPLATE},
        headers={**net.headers(hannah), "Idempotency-Key": "k01t18-flag-off"},
    )
    assert off.status_code == 404
    await _flags(net, tenant, *FLAGS)
    v3 = await _v3(net, hannah)
    state = cast(
        Json, (await net.call("GET", f"/v1/methodology/versions/{v3}/state", hannah)).json()
    )
    mapped = await net.call(
        "PUT",
        f"/v1/methodology/versions/{v3}/standards-mapping",
        hannah,
        body={
            "standards_set_id": str(uuid.uuid4()),
            "engagement_types": ["ebp_audit"],
            "default_for_new_engagements": True,
            "row_version": state["row_version"],
        },
    )
    assert (mapped.status_code, mapped.json()["detail"]) == (422, "standards_set_invalid")
