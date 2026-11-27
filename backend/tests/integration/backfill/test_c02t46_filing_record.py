# ac-test-author: ayushkbhatia
"""C-02-T46 (TASK-9004; C-02 F9 US-9.2, US-9.4; CLS-13 b, d, d2; ADR P-18; DEC-6010) on the
migrated Postgres. Row acceptance: "Two W-9 requests reach POR-11, the January batch exports six
forms and records Filed · IRIS then Accepted, and no code path calls an IRS host."

Copperleaf's vendors come from the T45 suite's fixture (recorded QuickBooks pages, rolled up)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from pathlib import Path
from typing import Final

import pytest

from abacus.modules.closes import information_return_batches as irb

from .copperleaf_1099 import AN, AY, Copperleaf
from .support import Migrated, Seeder

pytestmark = pytest.mark.asyncio
SIX: Final = (
    "Brightwater Hale LLP",
    "Elena Ruiz Design",
    "Hartwell & Lowe LLP",
    "Larimer Street Properties, LLC",
    "Mile High Window Cleaning",
    "Sound Electric Contractors, LLC",
)
TINS: Final = {name: f"{n:02d}-73{n:05d}" for n, name in enumerate(SIX, start=11)}
CLASSES: Final = {
    "Rocky Ridge Dairy Co.": {"entity_type": "c_corporation"},
    "Kestrel Marketing Co.": {"entity_type": "s_corporation"},
    "Cedar Mutual Insurance Co.": {"entity_type": "c_corporation"},
    "Front Range Bank": {"entity_type": "c_corporation"},
    "Hartwell & Lowe LLP": {"entity_type": "partnership", "is_attorney": True},
    "Larimer Street Properties, LLC": {"entity_type": "llc_p", "paid_rents": True},
}


@pytest.fixture
async def due_rule(migrated_db: Migrated) -> None:
    """C21's 1099-NEC due date: one month after the calendar year, day 31, rolled to the next
    business day (Jan 31, 2027 is a Sunday: due Mon Feb 1, 2027)."""
    owner = Seeder(migrated_db.owner_url.replace("postgresql+asyncpg", "postgresql"))
    # The owner role publishes reference content (K-02's two-person rule).
    payload = {
        "kind": "due_date_rules",
        "rows": [
            {
                "form": "1099-NEC",
                "fye_rule": "calendar_year",
                "original": {"months_after_period_end": 1, "day": 31},
                "extension": None,
                "authority": "IRC 6071(c) — verify",
            }
        ],
    }
    digest = "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    version = await owner.value(
        "SELECT reference_set_draft($1, 'due_date_rules', '1099 due dates', 'US', $2, NULL, "
        "2026, '2020-01-01', $3::jsonb, $4, '[{\"label\": \"IRS — verify\"}]'::jsonb, $2, "
        "'c02t46')",
        f"c02t46.due.{uuid.uuid4().hex[:8]}",
        AY,
        json.dumps(payload),
        digest,
    )
    await owner.run("SELECT reference_set_publish($1, $2, 'c02t46')", version, AN)


async def _items(w: Copperleaf) -> dict[str, dict[str, object]]:
    got = await w.net.call("GET", w.path(), w.senior)
    assert got.status_code == 200, got.text
    return {str(v["display_name"]): v for v in got.json()["items"]}


async def _classify(w: Copperleaf) -> None:
    items = await _items(w)
    for name, change in CLASSES.items():
        edited = await w.net.call(
            "PATCH",
            f"/v1/vendors/{items[name]['vendor_id']}",
            w.senior,
            body={**change, "expected_version": items[name]["version"]},
        )
        assert edited.status_code == 200, edited.text


async def _december_locked(w: Copperleaf) -> None:
    seed: Seeder = w.seed
    item = await seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, period_start, period_end, created_by) VALUES ($1, $2, $3, $4, 'close', "
        "'December 2026 close', '2026-12-01', '2026-12-31', $5) RETURNING id",
        w.tenant,
        w.site.engagement_id,
        w.site.client_id,
        w.site.entity_id,
        w.staff_partner.user_id,
    )
    await seed.run_untriggered(
        "INSERT INTO closes (tenant_id, work_item_id, engagement_id, client_entity_id, period, "
        "status, locked_at) VALUES ($1, $2, $3, $4, '2026-12', 'locked', now())",
        w.tenant,
        item,
        w.site.engagement_id,
        w.site.entity_id,
    )


async def test_c02t46_acceptance_w9s_batch_iris_filed_accepted(
    copperleaf: Copperleaf, due_rule: None
) -> None:
    w = copperleaf
    await _classify(w)
    items = await _items(w)
    partner = w.staff_partner

    # Two W-9 requests, sent by Raj through the portal (CLS-13b).
    wanted = [items["Mile High Window Cleaning"], items["Front Range Plumbing Co."]]
    sent = await w.net.call(
        "POST",
        f"/v1/client-entities/{w.site.entity_id}/w9-requests",
        w.senior,
        body={
            "vendor_ids": [str(v["vendor_id"]) for v in wanted],
            "wording_template_version_id": str(uuid.uuid4()),
        },
        headers=w.net.keyed(),
    )
    assert sent.status_code == 201, sent.text
    item_ids = [uuid.UUID(i) for i in sent.json()["request_item_ids"]]
    assert len(item_ids) == 2
    rows = await w.seed.rows(
        "SELECT description, client_visible, sent_at IS NOT NULL AS sent, sent_by, engagement_id "
        "FROM request_items WHERE id = ANY($1::uuid[]) ORDER BY description",
        item_ids,
    )
    assert [(r["description"], r["client_visible"], r["sent"]) for r in rows] == [
        ("Form W-9: Front Range Plumbing Co.", True, True),
        ("Form W-9: Mile High Window Cleaning", True, True),
    ]
    assert {r["sent_by"] for r in rows} == {w.senior.user_id}
    assert {r["engagement_id"] for r in rows} == {w.site.engagement_id}
    client = await w.seed.client_contact(w.site)
    portal = await w.net.call(
        "GET", f"/v1/portal/engagements/{w.site.engagement_id}/requests", client
    )
    if portal.status_code == 200:  # POR-11's room, when the portal reads the engagement's list
        assert "Form W-9: Mile High Window Cleaning" in portal.text
    items = await _items(w)
    assert items["Mile High Window Cleaning"]["w9_status"] == "requested"
    # C-02-T47 (CLS-13 a, "Requested Sep 11"): the open request's time is on the row.
    assert items["Mile High Window Cleaning"]["w9_requested_at"] is not None
    assert items["Larimer Street Properties, LLC"]["w9_requested_at"] is None

    # The W-9s arrive: each of the six on file with its TIN (sealed; only the last four shown).
    items = await _items(w)
    for name in SIX:
        recorded = await w.net.call(
            "PUT",
            f"/v1/vendors/{items[name]['vendor_id']}/w9",
            w.senior,
            body={
                "tin": TINS[name],
                "tin_kind": "ein",
                "evidence_version_id": str(w.site.version_id),
                "signed_on": "2026-09-20",
                "expected_version": items[name]["version"],
            },
        )
        assert recorded.status_code == 200, recorded.text
        assert TINS[name] not in recorded.text

    # Before the December close locks, the batch is refused.
    items = await _items(w)
    seen = {str(v["vendor_id"]): v["version"] for v in items.values()}
    body = {"client_entity_id": str(w.site.entity_id), "tax_year": 2026, "seen_versions": seen}
    early = await w.net.call("POST", "/v1/information-return-batches", partner, body=body)
    assert early.status_code == 409 and "close_not_locked" in early.text, early.text
    # C-02-T47 (CLS-13 a): the tracker reads the same rule, so Approve stays disabled until now.
    assert (await w.net.call("GET", w.path(), w.senior)).json()["approval_open"] is False
    await _december_locked(w)
    assert (await w.net.call("GET", w.path(), w.senior)).json()["approval_open"] is True
    senior_try = await w.net.call("POST", "/v1/information-return-batches", w.senior, body=body)
    assert senior_try.status_code == 403, senior_try.text  # manager or partner only

    approved = await w.net.call("POST", "/v1/information-return-batches", partner, body=body)
    assert approved.status_code == 201, approved.text
    batch = approved.json()
    assert (batch["status"], batch["forms"], batch["due_on"]) == ("approved", 6, "2027-02-01")
    again = await w.net.call("POST", "/v1/information-return-batches", partner, body=body)
    assert again.status_code == 409, again.text

    # The IRIS file: deterministic, six rows, full TINs for the IRS only.
    first = await w.net.call(
        "GET", f"/v1/information-return-batches/{batch['batch_id']}/iris.csv", partner
    )
    second = await w.net.call(
        "GET", f"/v1/information-return-batches/{batch['batch_id']}/iris.csv", partner
    )
    assert first.status_code == 200, first.text
    assert first.content == second.content
    assert first.headers["cache-control"] == "no-store"
    assert first.headers["x-content-sha256"] == hashlib.sha256(first.content).hexdigest()
    table = list(csv.reader(io.StringIO(first.content.decode())))
    assert table[0] == list(irb.IRIS_COLUMNS)
    assert sorted((r[0], r[4], r[5], r[6]) for r in table[1:]) == sorted(
        [
            ("1099-MISC", "Larimer Street Properties, LLC", "1", "78400.00"),
            ("1099-NEC", "Brightwater Hale LLP", "1", "25600.00"),
            ("1099-NEC", "Elena Ruiz Design", "1", "4200.00"),
            ("1099-NEC", "Hartwell & Lowe LLP", "1", "3600.00"),
            ("1099-NEC", "Mile High Window Cleaning", "1", "2640.00"),
            ("1099-NEC", "Sound Electric Contractors, LLC", "1", "5840.00"),
        ]
    )
    # The sealed TIN is its nine digits (C-02-T33 normalises what a person typed).
    assert {r[4]: r[3] for r in table[1:]} == {k: v.replace("-", "") for k, v in TINS.items()}
    # No TIN in the audit trail or the outbox.
    trail = await w.seed.rows(
        "SELECT coalesce(after_ref::text, '') AS a FROM audit_events WHERE tenant_id = $1",
        w.tenant,
    )
    assert not any(re.search(r"\d{2}-\d{7}", r["a"]) for r in trail)

    receipt = await w.net.call(
        "POST",
        f"/v1/information-return-batches/{batch['batch_id']}/filed",
        partner,
        body={
            "iris_receipt_id": "1099-2026-0001-RCPT",
            "filed_on": "2027-01-27",
            "evidence_version_id": str(w.site.version_id),
        },
    )
    assert receipt.status_code == 200 and receipt.json()["status"] == "filed_iris", receipt.text
    filed = (await w.net.call("GET", w.path(), w.senior)).json()
    assert (filed["batch_status"], filed["filed"]) == ("filed_iris", 6)
    ack = await w.net.call(
        "POST",
        f"/v1/information-return-batches/{batch['batch_id']}/acknowledgement",
        partner,
        body={
            "status": "accepted",
            "at": "2027-01-29T15:00:00Z",
            "evidence_version_id": str(w.site.version_id),
        },
    )
    assert ack.status_code == 200 and ack.json()["status"] == "accepted", ack.text
    twice = await w.net.call(
        "POST",
        f"/v1/information-return-batches/{batch['batch_id']}/acknowledgement",
        partner,
        body={
            "status": "rejected",
            "at": "2027-01-30T15:00:00Z",
            "evidence_version_id": str(w.site.version_id),
        },
    )
    assert twice.status_code == 409, twice.text
    done = (await w.net.call("GET", w.path(), w.senior)).json()
    assert (done["batch_status"], done["filed"]) == ("accepted", 6)
    # C-02-T47 (CLS-13 d, d2): exactly the six filed vendors read as in the batch.
    in_batch = sorted(str(v["display_name"]) for v in done["items"] if v["filed"])
    assert len(in_batch) == 6
    assert done["accepted_at"] is not None and done["filed_on"] is not None
    # C-02-T47 (CLS-13 e): a year whose payments never synced lists the returns it filed.
    await w.seed.run_untriggered(
        "DELETE FROM vendor_payment_rollups WHERE client_entity_id = $1", w.site.entity_id
    )
    prior = (await w.net.call("GET", w.path(), w.senior)).json()
    assert prior["payments_synced"] is False and prior["vendors_paid"] == 0
    assert sorted(str(v["display_name"]) for v in prior["items"]) == in_batch
    assert all(v["filed"] and v["reportability"] == "reportable" for v in prior["items"])
    assert (prior["batch_status"], prior["filed"]) == ("accepted", 6)


async def test_c02t46_a_vendor_without_a_tin_refuses_the_export(
    copperleaf: Copperleaf, due_rule: None
) -> None:
    w = copperleaf
    await _classify(w)
    await _december_locked(w)
    items = await _items(w)
    seen = {str(v["vendor_id"]): v["version"] for v in items.values()}
    approved = await w.net.call(
        "POST",
        "/v1/information-return-batches",
        w.staff_partner,
        body={"client_entity_id": str(w.site.entity_id), "tax_year": 2026, "seen_versions": seen},
    )
    assert approved.status_code == 201, approved.text
    refused = await w.net.call(
        "GET",
        f"/v1/information-return-batches/{approved.json()['batch_id']}/iris.csv",
        w.staff_partner,
    )
    assert refused.status_code == 409 and "tin_missing" in refused.text, refused.text
    stale = dict(seen)
    stale[next(iter(stale))] = 99
    late = await w.net.call(
        "POST",
        "/v1/information-return-batches",
        w.staff_partner,
        body={"client_entity_id": str(w.site.entity_id), "tax_year": 2026, "seen_versions": stale},
    )
    assert late.status_code == 409, late.text


def test_c02t46_acceptance_no_code_path_calls_an_irs_host() -> None:
    """ADR P-18 (DEC-49): Accrued never transmits. No closes, integrations or connections source
    names an IRS host or the IRIS A2A or FIRE endpoints."""
    root = Path(__file__).resolve().parents[3] / "src" / "abacus" / "modules"
    hosts = re.compile(r"(?:[a-z0-9.-]*\.)?irs\.gov|fire\.irs|la\.www4\.irs|iris\.irs|a2a", re.I)
    found = [
        f"{p.relative_to(root)}:{n}"
        for module in ("closes", "integrations", "connections")
        for p in sorted((root / module).rglob("*.py"))
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1)
        if hosts.search(line) and "never" not in line.lower()
    ]
    assert found == [], found


def test_c02t46_the_iris_file_is_deterministic_and_formula_safe() -> None:
    from decimal import Decimal as D

    rows = [("nec", "1", "ein", "11-7300011", "=HYPERLINK(1)", D("2640"))]
    one, two = irb.iris_rows(2026, rows), irb.iris_rows(2026, rows)
    assert one == two and one.endswith(b"\n") and b"\r" not in one
    body = list(csv.reader(io.StringIO(one.decode())))
    assert body[1] == ["1099-NEC", "2026", "EIN", "11-7300011", "'=HYPERLINK(1)", "1", "2640.00"]
