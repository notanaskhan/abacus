# ac-test-author: ayushkbhatia
"""C-02-T45 (TASK-9003; C-02 F9 US-9.1; CLS-13 a, e, f; DEC-6009) on the migrated Postgres.

Copperleaf's recorded QuickBooks vendor pages (the C-02-T26 sandbox recordings) are stored as a
sync's raw bytes, rolled up on `ledger_snapshot.recorded`, and read through CLS-13's route: 12
vendors paid, exactly six reportable at the C21 threshold of $2,000 for 2026 payments (Larimer on
1099-MISC box 1 once a person marks its payments as rents), Cascade Coffee's $41,260.00 of card
payments excluded, Hartwell & Lowe reportable as an attorney; a person's edit holds across a
re-sync; a stale edit is refused; a year with no payments is empty."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal as D
from typing import Final, cast

import asyncpg
import pytest

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.storage import s3_client
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.closes import vendor_rollups
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import stage_content
from abacus_tools.synthetic.scenarios.brightwater_hale import cas_delivery_slice as seed_slice

from .support import Migrated, Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio
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
def bucket(s3_settings: dict[str, str]) -> Iterator[object]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=EVIDENCE, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(bucket: object) -> Iterator[None]:
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket, EVIDENCE)  # type: ignore[arg-type] -- an S3 client
    yield
    storage.reset_storage()
    reset_key_service()


@pytest.fixture
async def threshold(migrated_db: Migrated) -> AsyncIterator[None]:
    """C21's 1099-NEC threshold for 2026 payments, published as K-02's two-person rule does."""
    owner = await asyncpg.connect(
        migrated_db.owner_url.replace("postgresql+asyncpg", "postgresql")
    )
    try:
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
        digest = (
            "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        )
        version = await owner.fetchval(
            "SELECT reference_set_draft($1, 'information_return_thresholds', '1099 thresholds', "
            "'US', $2, NULL, 2026, '2020-01-01', $3::jsonb, $4, "
            "'[{\"label\": \"IRS — verify\"}]'::jsonb, $2, 'c02t45')",
            f"c02t45.thresholds.{uuid.uuid4().hex[:8]}",
            AY,
            json.dumps(payload),
            digest,
        )
        await owner.execute("SELECT reference_set_publish($1, $2, 'c02t45')", version, AN)
        yield
    finally:
        await owner.close()


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


async def _sync(w: Copperleaf, pages: dict[str, bytes]) -> uuid.UUID:
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


async def _rolled(w: Copperleaf, snapshot: uuid.UUID) -> None:
    await vendor_rollups.on_ledger_snapshot_recorded(
        OutboxEvent(
            uuid.uuid4(),
            w.tenant,
            "ledger_snapshot.recorded",
            {"client_entity_id": str(w.site.entity_id), "snapshot_id": str(snapshot)},
        )
    )


@pytest.fixture
async def copperleaf(net: Net, seed: Seeder, threshold: None) -> Copperleaf:
    del threshold
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
    w.snapshot = await _sync(w, seed_slice.copperleaf_vendor_recordings())
    await _rolled(w, w.snapshot)
    return w


async def _rows(w: Copperleaf, who: Person | None = None) -> dict[str, object]:
    got = await w.net.call("GET", w.path(), who or w.senior)
    assert got.status_code == 200, got.text
    return cast(dict[str, object], got.json())


async def test_c02t45_acceptance_six_reportable_card_excluded_attorney_kept(
    copperleaf: Copperleaf,
) -> None:
    w = copperleaf
    body = await _rows(w)
    items = cast(list[dict[str, object]], body["items"])
    by_name = {str(v["display_name"]): v for v in items}
    assert body["vendors_paid"] == 12
    # Corporations are "unknown" until classified: set them as the W-9s say (a person's edit).
    for name, kind in (
        ("Rocky Ridge Dairy Co.", "c_corporation"),
        ("Kestrel Marketing Co.", "s_corporation"),
        ("Cedar Mutual Insurance Co.", "c_corporation"),
        ("Front Range Bank", "c_corporation"),
    ):
        vendor = by_name[name]
        edited = await w.net.call(
            "PATCH",
            f"/v1/vendors/{vendor['vendor_id']}",
            w.senior,
            body={"entity_type": kind, "expected_version": vendor["version"]},
        )
        assert edited.status_code == 200, edited.text
    hartwell = by_name["Hartwell & Lowe LLP"]
    larimer = by_name["Larimer Street Properties, LLC"]
    for vendor, body_ in (
        (hartwell, {"entity_type": "partnership", "is_attorney": True}),
        (larimer, {"entity_type": "llc_p", "paid_rents": True}),
    ):
        edited = await w.net.call(
            "PATCH",
            f"/v1/vendors/{vendor['vendor_id']}",
            w.senior,
            body={**body_, "expected_version": vendor["version"]},
        )
        assert edited.status_code == 200, edited.text

    body = await _rows(w)
    items = cast(list[dict[str, object]], body["items"])
    by_name = {str(v["display_name"]): v for v in items}
    reportable = sorted(n for n, v in by_name.items() if v["reportability"] == "reportable")
    assert reportable == SIX
    assert body["reportable"] == 6 and body["vendors_paid"] == 12
    assert body["threshold_rule"] == (
        "threshold $2,000 for 2026 payments (rules table) · card and payment-app payments "
        "excluded (reported on Form 1099-K)"
    )
    cascade = by_name["Cascade Coffee Importers, Inc."]
    assert (cascade["reportability"], cascade["amount"]) == ("paid_by_card", "0.00")
    assert (by_name["Hartwell & Lowe LLP"]["form"], by_name["Hartwell & Lowe LLP"]["box"]) == (
        "nec",
        "1",
    )
    rent = by_name["Larimer Street Properties, LLC"]
    assert (rent["form"], rent["box"], rent["amount"]) == ("misc", "1", "78400.00")
    assert by_name["Front Range Plumbing Co."]["reportability"] == "below_threshold"
    for name in ("Rocky Ridge Dairy Co.", "Front Range Bank"):
        assert by_name[name]["reportability"] == "exempt_corporation"
    assert body["batch_status"] == "not_started" and body["filed"] == 0
    for vendor in items:
        assert vendor["tin_last4"] is None  # the ledger's masked id is never stored as a TIN


async def test_c02t45_a_resync_keeps_a_persons_classification_and_replaces_the_year(
    copperleaf: Copperleaf,
) -> None:
    w = copperleaf
    items = cast(list[dict[str, object]], (await _rows(w))["items"])
    larimer = next(v for v in items if str(v["display_name"]).startswith("Larimer"))
    edited = await w.net.call(
        "PATCH",
        f"/v1/vendors/{larimer['vendor_id']}",
        w.senior,
        body={"paid_rents": True, "expected_version": larimer["version"]},
    )
    assert edited.status_code == 200, edited.text
    stale = await w.net.call(
        "PATCH",
        f"/v1/vendors/{larimer['vendor_id']}",
        w.senior,
        body={"is_attorney": True, "expected_version": larimer["version"]},
    )
    assert stale.status_code == 409 and "stale_version" in stale.text, stale.text

    # A September sync: the year-to-date pages now hold one more rent payment.
    pages = seed_slice.copperleaf_vendor_recordings()
    name = next(k for k in pages if "Purchase" in k)
    purchases = json.loads(pages[name])
    rent = next(
        p
        for p in purchases["QueryResponse"]["Purchase"]
        if p["EntityRef"]["name"].startswith("Larimer")
    )
    purchases["QueryResponse"]["Purchase"].append({**rent, "Id": "99999", "TxnDate": "2026-09-15"})
    pages[name] = json.dumps(purchases, sort_keys=True).encode()
    await _rolled(w, await _sync(w, pages))

    items = cast(list[dict[str, object]], (await _rows(w))["items"])
    larimer = next(v for v in items if str(v["display_name"]).startswith("Larimer"))
    assert (larimer["amount"], larimer["form"]) == ("88200.00", "misc")  # rents kept
    rows = await w.seed.rows(
        "SELECT method, amount, txn_count FROM vendor_payment_rollups WHERE vendor_id = $1 "
        "AND tax_year = 2026 ORDER BY method",
        uuid.UUID(str(larimer["vendor_id"])),
    )
    assert [(r["method"], r["amount"], r["txn_count"]) for r in rows] == [
        ("ach", D("88200.00"), 9),
        ("card", D("0.00"), 0),
        ("check", D("0.00"), 0),
        ("other", D("0.00"), 0),
        ("payment_app", D("0.00"), 0),
    ]
    assert (
        await w.seed.value(
            "SELECT entity_type_source FROM vendors_1099 WHERE id = $1",
            uuid.UUID(str(larimer["vendor_id"])),
        )
        == "person"
    )


async def test_c02t45_a_year_without_payments_is_empty_and_readers_are_the_team(
    copperleaf: Copperleaf,
) -> None:
    w = copperleaf
    empty = await w.net.call("GET", w.path(2025), w.senior)
    assert empty.status_code == 200, empty.text
    assert (empty.json()["vendors_paid"], empty.json()["items"]) == (0, [])
    outsider = await w.seed.person(w.tenant)
    refused = await w.net.call("GET", w.path(), outsider)
    assert refused.status_code in (403, 404), refused.text
    stranger = await w.seed.person(await w.seed.firm())
    absent = await w.net.call("GET", w.path(), stranger)
    assert absent.status_code == 404, absent.text
    # A year with no published threshold is never defaulted (DEC-85).
    no_rule = await w.net.call("GET", w.path(2031), w.senior)
    assert no_rule.status_code == 503, no_rule.text


def test_c02t45_roll_up_is_per_vendor_year_and_method() -> None:
    rolled = vendor_rollups.roll_up(
        [
            ("v1", date(2026, 1, 15), D("100.00"), "check"),
            ("v1", date(2026, 2, 15), D("50.00"), "check"),
            ("v1", date(2025, 12, 31), D("10.00"), "card"),
            ("v2", date(2026, 3, 1), D("7.50"), "cash"),
        ]
    )
    got = [
        (r.vendor_external_id, r.tax_year, r.method, r.amount, r.txn_count)
        for r in rolled
        if r.txn_count
    ]
    assert got == [
        ("v1", 2025, "card", D("10.00"), 1),
        ("v1", 2026, "check", D("150.00"), 2),
        ("v2", 2026, "other", D("7.50"), 1),
    ]
    assert len(rolled) == 3 * len(vendor_rollups.METHODS)  # every method of each vendor-year
    assert vendor_rollups.rollup_method("ach") == "ach"
    assert vendor_rollups.rollup_method("venmo") == "other"
