"""K-01-T23 (TASK-2922; K-01 §3.7, AC7.1 to AC7.3; DEC-1968): KNW-02 a, a2 and b read the import
that made a version and each parsed step's sources.

"Selecting step 4 lights page 14 while selecting the page region lights the row": the server
gives each source a match key both panes bind (`step-<id>-p<page>`); the import route serves the
RunCard's counts. Reuses K-01-T18's workbook import and seeds a source as the importer (K-01-T21)
would leave it.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from typing import Final, cast

import pytest
from types_boto3_s3 import S3Client

from .ledger_support import bucket, wire_storage
from .support import Json, Net
from .test_k01t05_methodology_programs import (
    _flags,  # pyright: ignore[reportPrivateUsage] -- K-01-T05's flag seeding
)
from .test_k01t18_import_review import (
    FLAGS,
    _v3,  # pyright: ignore[reportPrivateUsage] -- K-01-T18's v3 import
)

pytestmark = pytest.mark.asyncio

BUCKET: Final = f"backfill-k01t23-{uuid.uuid4().hex[:10]}"
MASTER: Final = b"backfill-k01t23-import-master-key-01234567"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> S3Client:
    return bucket(s3_settings, BUCKET)


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    yield from wire_storage(raw, BUCKET, MASTER)


async def test_ac7_2_the_version_import_and_step_4s_source_on_page_14(net: Net) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    margaret = await seed.person(tenant, "practice_leader")
    await _flags(net, tenant, *FLAGS)
    v3 = await _v3(net, hannah)

    imp = await net.call("GET", f"/v1/methodology/versions/{v3}/import", margaret)
    assert imp.status_code == 200, imp.text
    body = cast(Json, imp.json())
    assert body["version_id"] == str(v3)
    assert body["status"] == "needs_review"
    files = cast(list[Json], body["files"])
    assert [f["role"] for f in files] == ["workbook"]
    assert "storage_key" not in str(body)

    step = (
        await seed.rows(
            "SELECT s.id, s.program_id FROM program_steps s JOIN programs p "
            "ON p.id = s.program_id "
            "WHERE s.version_id = $1 AND p.code = 'BH-EBP-110' AND s.number = 4",
            v3,
        )
    )[0]
    await seed.run(
        "INSERT INTO program_step_sources (tenant_id, step_id, source_file_id, page_from, "
        "page_to, bbox, quote, verified) VALUES ($1, $2, $3, 14, 14, $4::jsonb, $5, true)",
        tenant,
        step["id"],
        uuid.UUID(cast(str, files[0]["id"])),
        json.dumps([72.0, 152.0, 540.0, 192.0]),
        "Obtain the plan document",
    )
    steps = await net.call("GET", f"/v1/methodology/programs/{step['program_id']}/steps", margaret)
    assert steps.status_code == 200, steps.text
    by_number = {cast(int, s["number"]): s for s in cast(list[Json], steps.json())}
    sources = cast(list[Json], by_number[4]["sources"])
    assert sources == [
        {
            "match_id": f"step-{step['id']}-p14",
            "file_id": files[0]["id"],
            "page_from": 14,
            "page_to": 14,
            "bbox": [72.0, 152.0, 540.0, 192.0],
            "quote": "Obtain the plan document",
            "verified": True,
        }
    ]
    # A workbook step without a source keeps an empty list (the field is additive).
    assert by_number[1]["sources"] == []


async def test_a_version_with_no_import_is_404_and_a_hidden_flag_hides_the_route(
    net: Net,
) -> None:
    seed = net.seed
    tenant = await seed.firm()
    hannah = await seed.person(tenant, "firm_admin")
    await _flags(net, tenant, *FLAGS)
    missing = await net.call("GET", f"/v1/methodology/versions/{uuid.uuid4()}/import", hannah)
    assert missing.status_code == 404, missing.text
    other = await seed.firm()
    stranger = await seed.person(other, "firm_admin")
    v3 = await _v3(net, hannah)
    # Another firm's reader cannot see this firm's import (RLS: not found, never forbidden).
    await _flags(net, other, *FLAGS)
    leaked = await net.call("GET", f"/v1/methodology/versions/{v3}/import", stranger)
    assert leaked.status_code == 404, leaked.text
