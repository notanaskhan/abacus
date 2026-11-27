"""A ledger snapshot's vendor pages, parsed (C-02-T45, TASK-9003; C-02-T26; CONN-001).

C-02-T26 pulls QuickBooks vendors and vendor payments beside the month's set and keeps their raw
bytes write-once (`sync_runs.raw_storage_key`), checked as hostile content before they are kept.
CLS-13's rollup (closes' `VendorRollupConsumer`) reads them again here, through the owner of the
runs and the store: the succeeded `vendors` and `vendor_payments` runs that recorded the snapshot,
their bytes from the encrypted store, parsed by `qbo_format`. Read only; nothing is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.vendor_pages import (
    VendorName,
    VendorPages,
    VendorPayment,
    register_vendor_pages,
)
from abacus.modules.connections.qbo_format import (
    QboVendor,
    QboVendorPayment,
    parse_qbo_vendor_payments,
    parse_qbo_vendors,
)
from abacus.modules.evidence.api import StoredObject, read_content

_RUNS: Final = text(
    "SELECT dataset, raw_storage_key, raw_version_id, raw_fingerprint, raw_size_bytes "
    "FROM sync_runs WHERE snapshot_id = :s AND status = 'succeeded' "
    "AND dataset IN ('vendors', 'vendor_payments') AND raw_storage_key IS NOT NULL "
    "ORDER BY dataset, started_at, id"
)


@dataclass(frozen=True)
class VendorDatasets:
    vendors: tuple[QboVendor, ...]
    payments: tuple[QboVendorPayment, ...]

    @property
    def empty(self) -> bool:
        return not self.vendors and not self.payments


async def vendor_datasets_of(tenant: TenantContext, snapshot_id: UUID) -> VendorDatasets:
    """The vendors and payments the snapshot's sync pulled (empty when it pulled none)."""
    async with tenant_session(tenant) as session:
        runs = list((await session.execute(_RUNS, {"s": snapshot_id})).all())
    vendors: dict[str, QboVendor] = {}
    payments: dict[tuple[str, str], QboVendorPayment] = {}
    for run in runs:
        content = await read_content(
            tenant,
            StoredObject(
                str(run.raw_storage_key), str(run.raw_version_id), str(run.raw_fingerprint),
                int(run.raw_size_bytes),
            ),
        )  # fmt: skip
        if run.dataset == "vendors":
            for vendor in parse_qbo_vendors(content):
                vendors[vendor.external_id] = vendor
        else:
            for payment in parse_qbo_vendor_payments(content):
                payments[(payment.entity, payment.external_id)] = payment  # one row per txn
    return VendorDatasets(tuple(vendors.values()), tuple(payments.values()))


__all__ = ["VendorDatasets", "vendor_datasets_of"]


async def vendor_pages(tenant: TenantContext, snapshot_id: UUID) -> VendorPages:
    """`kernel.vendor_pages`' reader: the parsed pages as the kernel's neutral rows (DEC-6018)."""
    found = await vendor_datasets_of(tenant, snapshot_id)
    return VendorPages(
        tuple(VendorName(v.external_id, v.name) for v in found.vendors),
        tuple(
            VendorPayment(p.vendor_external_id, p.txn_date, p.amount, p.method)
            for p in found.payments
        ),
    )


def register() -> None:
    register_vendor_pages(vendor_pages)
