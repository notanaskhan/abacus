"""The ledger snapshot's vendor pages slot (C-02-T45; DEC-6009; S54 gate fixes, DEC-6018).

The connections module reads a snapshot's vendor and vendor-payment pages (their runs, their raw
bytes, parsed); the closes module's vendor rollup consumes them. Neither imports the other:
nothing depends on connections but integrations and the portal (BOUND-002), and connections
never imports closes. Connections registers the reader; closes asks this slot.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext


@dataclass(frozen=True)
class VendorName:
    external_id: str
    name: str


@dataclass(frozen=True)
class VendorPayment:
    vendor_external_id: str
    txn_date: date
    amount: Decimal
    method: str


@dataclass(frozen=True)
class VendorPages:
    vendors: tuple[VendorName, ...] = ()
    payments: tuple[VendorPayment, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.vendors and not self.payments


Reader = Callable[[TenantContext, UUID], Awaitable[VendorPages]]
_READER: Final[list[Reader]] = []


def register_vendor_pages(reader: Reader) -> None:
    """The connections module's reader (one)."""
    if _READER and _READER[0] is not reader:
        raise ValueError("a vendor pages reader is already registered")
    if not _READER:
        _READER.append(reader)


async def vendor_pages_of(tenant: TenantContext, snapshot_id: UUID) -> VendorPages:
    """The snapshot's vendor pages; empty when no reader is registered or it pulled none."""
    if not _READER:
        return VendorPages()
    return await _READER[0](tenant, snapshot_id)


__all__ = [
    "VendorName",
    "VendorPages",
    "VendorPayment",
    "register_vendor_pages",
    "vendor_pages_of",
]
