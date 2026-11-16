"""One selected item of a sample-set version, for the agent's `sampling.read_selected_entry`
(A-08-T23; A-08 §6; ADR-233). Read only, over sampling's own tables; the tool itself is declared
in assurance (sampling never imports agents, ADR-008)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_ITEM: Final = text(
    "SELECT s.engagement_id, i.position, i.record_key, i.selection_reason, i.display, r.amount "
    "FROM sample_items i JOIN sample_set_versions v ON v.id = i.sample_set_version_id "
    "JOIN sample_sets s ON s.id = v.sample_set_id "
    "LEFT JOIN sample_population_records r ON r.population_id = v.population_id "
    "AND r.ordinal = i.population_record_ordinal "
    "WHERE i.sample_set_version_id = :v AND i.position = :p"
)


@dataclass(frozen=True)
class SelectedEntry:
    engagement_id: UUID
    position: int
    record_key: str
    selection_reason: str
    amount: Decimal | None
    score: str | None


async def selected_entry(
    tenant: TenantContext, sample_set_version_id: UUID, position: int
) -> SelectedEntry | None:
    async with tenant_session(tenant) as session:
        row = (
            (await session.execute(_ITEM, {"v": sample_set_version_id, "p": position}))
            .mappings()
            .first()
        )
    if row is None:
        return None
    display = row["display"]
    shown = json.loads(display) if isinstance(display, str) else dict(display or {})
    return SelectedEntry(
        engagement_id=row["engagement_id"],
        position=int(row["position"]),
        record_key=str(row["record_key"]),
        selection_reason=str(row["selection_reason"]),
        amount=row["amount"],
        score=None if shown.get("score") is None else str(shown["score"]),
    )
