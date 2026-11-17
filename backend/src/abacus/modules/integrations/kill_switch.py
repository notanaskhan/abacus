"""The per-integration kill switch (W-01-T07 rest; SPEC-659 AC-4, OQ-9; ADR-157; DEC-5433; red).

`integration_pause` is a platform control keyed by the integration's catalogue key, set per firm
or for everyone by an operator (`abacus_tools.platform_control`, migration 0948). While it is on:

- WB-10 and WB-11 read an installed integration as `paused` ("Paused") with its connect and
  reconnect hidden; an integration the firm has not installed reads `coming_soon` (AC-4: a tile is
  `available` only while its kill switch is clear);
- every connect start and completion refuses 409 `integration_paused` (firm, personal and
  POR-16's client start), so no adapter call is made for it;
- the health sweep leaves its installs alone.

Read through `kernel.controls.control_active` (ADR-157: a switch that bypasses it is a defect). The
pause is not fail-closed: when the controls can't be read, the last known value holds.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final
from uuid import UUID

from abacus.kernel.controls import control_active
from abacus.kernel.errors import DomainConflict

CONTROL: Final = "integration_pause"


class IntegrationPaused(DomainConflict):
    """An operator paused this integration (for the firm or the platform)."""

    code = "integration_paused"


async def integration_paused(tenant_id: UUID, key: str) -> bool:
    return await control_active(CONTROL, tenant_id, route=key)


async def paused_keys(tenant_id: UUID, keys: Iterable[str]) -> frozenset[str]:
    """The keys among `keys` paused for the firm or the platform (one cached read)."""
    return frozenset([k for k in keys if await integration_paused(tenant_id, k)])


async def ensure_not_paused(tenant_id: UUID, key: str) -> None:
    if await integration_paused(tenant_id, key):
        raise IntegrationPaused(facts={"catalog_key": key})
