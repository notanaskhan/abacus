"""Copperleaf's 1099 world for the CLS-13 suites (C-02-T45, T46): its vendors from the
recorded QuickBooks pages, stored as a sync stores them and rolled up, and C21's 1099
threshold for 2025 and 2026. The fixtures are registered in the backfill conftest."""

from __future__ import annotations

import contextlib
import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Final, cast

import pytest

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.storage import s3_client
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.closes import vendor_rollups
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import stage_content
from abacus_tools.synthetic.scenarios.brightwater_hale import cas_delivery_slice as seed_slice

from .support import Migrated, Net, Person, Seeder, Site

EVIDENCE: Final = "c02t45-evidence"
MASTER: Final = b"c02t45-information-returns-master-key-0123"
AY, AN = "ayushkbhatia", "notanaskhan"
SIX: Final = sorted(
    [
        "Larimer Street Properties, LLC",
        "Brightwater Hale LLP",
        "Sound Electric Contractors, LLC",
        "Elena Ruiz Design",
        "Hartwell & Lowe LLP",
        "Mile High Window Cleaning",
    ]
)


@pytest.fixture(scope="module")
def bucket_1099(s3_settings: dict[str, str]) -> Iterator[object]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    # One bucket for both suites (each test module asks once).
    with contextlib.suppress(client.exceptions.BucketAlreadyOwnedByYou):
        client.create_bucket(Bucket=EVIDENCE, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture
def wired_1099(bucket_1099: object) -> Iterator[None]:
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket_1099, EVIDENCE)  # type: ignore[arg-type] -- an S3 client
    yield
    storage.reset_storage()
    reset_key_service()


@pytest.fixture
async def threshold_1099(migrated_db: Migrated) -> AsyncIterator[None]:
    """C21's 1099-NEC threshold for 2026 payments, published as K-02's two-person rule does."""
    owner = Seeder(migrated_db.owner_url.replace("postgresql+asyncpg", "postgresql"))
    # The owner role publishes reference content (K-02's two-person rule).
    payload = {
        "kind": "information_return_thresholds",
        "rows": [
            {
                "form": "nec",
                "payment_year": year,
                "threshold_usd": 2000,
                "min_transactions": None,
            }
            for year in (2025, 2026)
        ],
    }
    digest = "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    version = await owner.value(
        "SELECT reference_set_draft($1, 'information_return_thresholds', '1099 thresholds', "
        "'US', $2, NULL, 2026, '2020-01-01', $3::jsonb, $4, "
        "'[{\"label\": \"IRS — verify\"}]'::jsonb, $2, 'c02t45')",
        f"c02t45.thresholds.{uuid.uuid4().hex[:8]}",
        AY,
        json.dumps(payload),
        digest,
    )
    await owner.run("SELECT reference_set_publish($1, $2, 'c02t45')", version, AN)
    yield


@dataclass
class Copperleaf:
    net: Net
    tenant: uuid.UUID
    senior: Person
    staff_partner: Person
    site: Site
    snapshot: uuid.UUID

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    def path(self, year: int = 2026) -> str:
        return f"/v1/client-entities/{self.site.entity_id}/information-returns?tax_year={year}"


async def sync_pages(w: Copperleaf, pages: dict[str, bytes]) -> uuid.UUID:
    """One synced month whose vendor runs carry the recorded pages (stored as a sync stores)."""
    seed = w.seed
    snapshot = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, period_end, "
            "pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit) VALUES "
            "($1, $2, '2026-08-01', '2026-08-31', now(), 'import', md5(random()::text) || "
            "md5(random()::text), 0, 0, 0) RETURNING id",
            w.tenant,
            w.site.entity_id,
        ),
    )
    connection = await seed.value(
        "SELECT id FROM connections WHERE client_entity_id = $1", w.site.entity_id
    ) or await seed.value(
        "INSERT INTO connections (tenant_id, client_entity_id, provider, status, created_by) "
        "VALUES ($1, $2, 'quickbooks_online', 'active', 'test-seed') RETURNING id",
        w.tenant,
        w.site.entity_id,
    )
    for name, content in pages.items():
        stored = await stage_content(w.tenant, content)
        dataset = "vendors" if name == "qbo-vendors.json" else "vendor_payments"
        await seed.run_untriggered(
            "INSERT INTO sync_runs (tenant_id, client_entity_id, connection_id, engagement_id, "
            "request_item_id, dataset, period_start, period_end, status, raw_storage_key, "
            "raw_version_id, raw_fingerprint, raw_size_bytes, raw_pulled_at, source, "
            "snapshot_id, started_by, finished_at, trigger) VALUES ($1, $2, $3, $4, $5::uuid, "
            "$6, '2026-01-01', '2026-08-31', 'succeeded', $7, $8, $9, $10, now(), "
            "'quickbooks_online', $11, 'test-seed', now(), 'schedule')",
            w.tenant,
            w.site.entity_id,
            connection,
            w.site.engagement_id,
            None,
            dataset,
            stored.key,
            stored.version_id,
            stored.fingerprint,
            stored.size,
            snapshot,
        )
    return snapshot


async def roll_up_snapshot(w: Copperleaf, snapshot: uuid.UUID) -> None:
    await vendor_rollups.on_ledger_snapshot_recorded(
        OutboxEvent(
            uuid.uuid4(),
            w.tenant,
            "ledger_snapshot.recorded",
            {"client_entity_id": str(w.site.entity_id), "snapshot_id": str(snapshot)},
        )
    )


@pytest.fixture
async def copperleaf(net: Net, seed: Seeder, threshold_1099: None, wired_1099: None) -> Copperleaf:
    del threshold_1099, wired_1099
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'closes.information_returns', 'true', 'test-seed', 'C-02-T45')",
        tenant,
    )
    partner, senior = await seed.person(tenant), await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "Copperleaf")
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, senior, "senior")
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, period_start, period_end, created_by) VALUES ($1, $2, $3, $4, 'close', "
            "'August 2026 close', '2026-08-01', '2026-08-31', $5) RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            partner.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO closes (tenant_id, work_item_id, engagement_id, client_entity_id, period) "
        "VALUES ($1, $2, $3, $4, '2026-08')",
        tenant,
        item,
        site.engagement_id,
        site.entity_id,
    )
    w = Copperleaf(net, tenant, senior, partner, site, uuid.uuid4())
    w.snapshot = await sync_pages(w, seed_slice.copperleaf_vendor_recordings())
    await roll_up_snapshot(w, w.snapshot)
    return w
