"""DEC-2264 (TASK-5012): the eight audit target types S26 and S27 record are placed. Each owner
lookup is valid against the real schema as the app role, under row-level security, and an id
nobody holds is left out, so its event stays hidden (fail closed)."""

from __future__ import annotations

import uuid

import pytest

import abacus.api as app_package  # loading it loads every module: each registers its targets
from abacus.kernel import audit_owners

from .support import Seeder, make_firm

pytestmark = pytest.mark.asyncio
ENGAGEMENT = [
    "control_activity",
    "control_exception",
    "deficiency",
    "sum_snapshot",
    "notice",
    "ocr_run",
    "questionnaire",
]


@pytest.mark.parametrize("kind", ENGAGEMENT)
async def test_an_engagement_owner_lookup_runs_and_leaves_an_unknown_id_out(
    seed: Seeder, kind: str
) -> None:
    assert app_package.create_app
    firm = await make_firm(seed)
    owners = audit_owners.engagement_owners()[kind]
    assert await owners(firm.system, kind, [uuid.uuid4()]) == {}


async def test_an_intake_lookup_runs_and_leaves_an_unknown_id_out(seed: Seeder) -> None:
    firm = await make_firm(seed)
    owners = audit_owners.client_owners()["notice_intake"]
    assert await owners(firm.system, "notice_intake", [uuid.uuid4()]) == {}


async def test_an_ocr_run_is_placed_on_its_versions_engagement(seed: Seeder) -> None:
    firm = await make_firm(seed)
    version = await firm.version(b"%PDF-1.4 owner probe")
    run = await seed.id(
        "INSERT INTO ocr_runs (tenant_id, evidence_version_id, provider, api, status, basis) "
        "VALUES ($1, $2, 'fake', 'detect_text', 'completed', 'synthetic') RETURNING id",
        firm.tenant_id,
        version,
    )
    owners = audit_owners.engagement_owners()["ocr_run"]
    assert await owners(firm.system, "ocr_run", [run]) == {run: firm.engagement_id}
