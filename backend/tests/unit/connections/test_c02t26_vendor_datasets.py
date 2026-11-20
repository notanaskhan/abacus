"""C-02-T26 (TASK-8808; CLS-13): QuickBooks vendor and payment read datasets.

"The Copperleaf sandbox and fake return 12 vendors with payments split check/ACH/card, and the
connector still exposes no write-shaped method." Here the real connector runs over the recorded
transport (fake_quickbooks_online) with Copperleaf's recordings; the parsers refuse an unmasked
tax id; CDC names the vendor datasets; and the connector has no write-shaped attribute.
"""

from __future__ import annotations

import inspect
import json
import uuid
from collections import Counter
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.modules.connections.api import (
    CONNECTORS,
    Period,
    parse_qbo_vendor_payments,
    parse_qbo_vendors,
    quickbooks_online,
)
from abacus.modules.connections.models import Connection
from abacus.modules.ledger.api import NormaliseError
from abacus_tools.fakes import ledgers as fakes
from abacus_tools.synthetic.scenarios.brightwater_hale import cas_delivery_slice as cas

YTD = Period(date(2026, 1, 1), date(2026, 8, 31))
WRITE_SHAPED = ("post", "create", "write", "update", "delete", "put", "patch", "send")


@pytest.fixture
def connector(tmp_path: Path) -> Iterator[object]:
    fakes.install_fake_ledgers(tmp_path)
    connection = Connection(
        id=uuid.uuid4(), tenant_id=uuid.uuid4(), client_entity_id=uuid.uuid4(),
        provider=fakes.FAKE_QBO,
    )  # fmt: skip
    folder = tmp_path / str(connection.id)
    folder.mkdir()
    for name, body in cas.copperleaf_vendor_recordings().items():
        (folder / name).write_bytes(body)
    yield CONNECTORS[fakes.FAKE_QBO](connection, None)
    fakes.uninstall_fake_ledgers()


async def test_ac_twelve_vendors_with_masked_tax_ids(
    connector: quickbooks_online.QuickBooksOnlineConnector,
) -> None:
    page = await connector.pull("vendors", YTD, None)
    vendors = parse_qbo_vendors(page.content)
    assert len(vendors) == 12
    assert {v.name for v in vendors} == {v.name for v in cas.VENDORS}
    assert all(v.tin_last4 is None or len(v.tin_last4) == 4 for v in vendors)
    assert sum(v.is_1099 for v in vendors) == 7
    assert page.next_cursor is None


async def test_ac_payments_split_check_ach_card(
    connector: quickbooks_online.QuickBooksOnlineConnector,
) -> None:
    first = await connector.pull("vendor_payments", YTD, None)
    assert first.next_cursor == "Purchase:1"
    second = await connector.pull("vendor_payments", YTD, first.next_cursor)
    assert second.next_cursor is None
    payments = parse_qbo_vendor_payments(first.content) + parse_qbo_vendor_payments(second.content)
    by_method = Counter(p.method for p in payments)
    assert set(by_method) == {"check", "ach", "card"}
    assert by_method["card"] == 1
    totals: dict[str, Decimal] = {}
    vendors = {
        v.external_id: v.name
        for v in parse_qbo_vendors((await connector.pull("vendors", YTD, None)).content)
    }
    for p in payments:
        totals[vendors[p.vendor_external_id]] = (
            totals.get(vendors[p.vendor_external_id], Decimal(0)) + p.amount
        )
    assert totals == {v.name: v.amount for v in cas.VENDORS}


def test_an_unmasked_tax_id_is_refused() -> None:
    body = {
        "QueryResponse": {
            "Vendor": [{"Id": "1", "DisplayName": "X", "TaxIdentifier": "900-45-6789"}]
        }
    }
    with pytest.raises(NormaliseError):
        parse_qbo_vendors(json.dumps(body).encode())


def test_purchases_to_non_vendors_are_left_out() -> None:
    body = {"QueryResponse": {"Purchase": [
        {"Id": "1", "EntityRef": {"value": "9", "type": "Employee"}, "TxnDate": "2026-08-01",
         "TotalAmt": 10.0, "PaymentType": "Cash"},
    ]}}  # fmt: skip
    assert parse_qbo_vendor_payments(json.dumps(body).encode()) == ()


def test_cdc_names_the_vendor_datasets() -> None:
    body = {
        "CDCResponse": [
            {"QueryResponse": [{"Vendor": [{"Id": "1"}]}, {"BillPayment": [{"Id": "2"}]}]}
        ]
    }
    entities = quickbooks_online._cdc_entities(json.dumps(body).encode())  # pyright: ignore[reportPrivateUsage] -- the CDC parser under test
    assert entities == {"Vendor", "BillPayment"}


def test_ac_the_connector_still_has_no_write_shaped_method() -> None:
    names = [n for n, _ in inspect.getmembers(quickbooks_online.QuickBooksOnlineConnector)]
    assert not [n for n in names if n.lstrip("_").split("_")[0] in WRITE_SHAPED]
    assert quickbooks_online.SCOPE == "com.intuit.quickbooks.accounting"
