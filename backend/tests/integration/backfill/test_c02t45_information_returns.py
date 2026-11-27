# ac-test-author: ayushkbhatia
"""C-02-T45 (TASK-9003; C-02 F9 US-9.1; CLS-13 a, e, f; DEC-6009) on the migrated Postgres.

Copperleaf's recorded QuickBooks vendor pages (the C-02-T26 sandbox recordings) are stored as a
sync's raw bytes, rolled up on `ledger_snapshot.recorded`, and read through CLS-13's route: 12
vendors paid, exactly six reportable at the C21 threshold of $2,000 for 2026 payments (Larimer on
1099-MISC box 1 once a person marks its payments as rents), Cascade Coffee's $41,260.00 of card
payments excluded, Hartwell & Lowe reportable as an attorney; a person's edit holds across a
re-sync; a stale edit is refused; a year with no payments is empty."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal as D
from typing import cast

import pytest

from abacus.modules.closes import vendor_rollups
from abacus_tools.synthetic.scenarios.brightwater_hale import cas_delivery_slice as seed_slice

from .copperleaf_1099 import SIX, Copperleaf, roll_up_snapshot, sync_pages
from .support import Person

pytestmark = pytest.mark.asyncio


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
    # C-02-T47 (CLS-13 drawer): payments by method; card never counted toward 1099-NEC.
    card = [p for p in cast(list[dict[str, object]], cascade["payments"]) if p["method"] == "card"]
    assert card and all(p["counted"] is False for p in card)
    rents = cast(list[dict[str, object]], by_name["Larimer Street Properties, LLC"]["payments"])
    assert sum(float(str(p["amount"])) for p in rents if p["counted"]) == 78400.0
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
    await roll_up_snapshot(w, await sync_pages(w, pages))

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
