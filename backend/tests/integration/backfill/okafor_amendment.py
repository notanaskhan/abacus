"""The Okafors' accepted 2025 return for the TAX-16 suites (T-08-T30, T33): BH-TAX-02's
client, the approved as-filed checkpoint and engine summary; fixtures re-exported by the
backfill conftest."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import cast

import pytest

from .support import Net, Person, Seeder, Site

FILED = {
    "1040.11": "212400",
    "1040.12": "29200",
    "1040.15": "183200",
    "1040.16": "37400",
    "1040.24": "40386",
    "1040.33": "41000",
    "1040.34": "614",
    "il1040.agi": "212400",
    "il1040.tax": "10514",
}
AMENDED = {
    **FILED,
    "1040.12": "38660",
    "1040.15": "173740",
    "1040.16": "35206",
    "1040.24": "37678",
    "1040.34": "3322",
    "il1040.agi": "202400",
    "il1040.tax": "10019",
}


def _lines(values: dict[str, str]) -> str:
    return json.dumps([{"line_key": k, "amount": v} for k, v in values.items()])


@dataclass
class Okafor:
    net: Net
    tenant: uuid.UUID
    yusuf: Person
    site: Site
    original: uuid.UUID

    @property
    def seed(self) -> Seeder:
        return self.net.seed


async def engine_summary(
    seed: Seeder, tenant: uuid.UUID, item: uuid.UUID, values: dict[str, str]
) -> None:
    await seed.run(
        "INSERT INTO return_engine_summaries (tenant_id, work_item_id, engine_version, kind, "
        "lines, approved_at) VALUES ($1, $2, 'CCH Axcess 2025', 'final', $3::jsonb, now())",
        tenant,
        item,
        _lines(values),
    )


@pytest.fixture
async def okafor(net: Net, seed: Seeder) -> Okafor:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.amendments', 'true', 'test-seed', 'T-08-T30')",
        tenant,
    )
    yusuf = await seed.person(tenant)
    site = await seed.site(tenant, yusuf.user_id, "Okafor")
    await seed.member(site, yusuf, "senior")
    original = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2025 Form 1040', $5) "
            "RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            yusuf.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, '1040', 2025)",
        tenant,
        original,
        site.engagement_id,
        site.entity_id,
    )
    await seed.run_untriggered(
        "UPDATE tax_returns SET status = 'accepted' WHERE work_item_id = $1", original
    )
    await seed.run_untriggered(  # an engine import's approved checkpoint, as T-01 records one
        "INSERT INTO checkpoints (id, tenant_id, engagement_id, target_type, target_id, seq, "
        "author_kind, author_ref, cause, status, content_hash) VALUES ($1, $2, $3, 'tax_return', "
        "$4, 1, 'import', 'Imported from CCH Axcess 2025:OkaforD:V1', 'engine_import', "
        "'approved', $5)",
        uuid.uuid4(),
        tenant,
        site.engagement_id,
        original,
        hashlib.sha256(b"okafor-2025").hexdigest(),
    )
    await engine_summary(seed, tenant, original, FILED)
    return Okafor(net, tenant, yusuf, site, original)
