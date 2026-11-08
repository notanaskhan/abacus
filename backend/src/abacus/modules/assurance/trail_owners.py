"""The audit trail places S30's assurance targets on their engagements (A-07-T18, A-05-T53).

`eqr_digest_card`, `accounting_estimate` and `related_party` rows each carry their engagement, so
an explorer row naming one is shown only to a reader who sees that engagement (ADM-07).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_READS: Final = {
    "eqr_digest_card": text("SELECT id, engagement_id FROM eqr_digest_cards WHERE id = ANY(:ids)"),
    "accounting_estimate": text(
        "SELECT id, engagement_id FROM accounting_estimates WHERE id = ANY(:ids)"
    ),
    "related_party": text("SELECT id, engagement_id FROM related_parties WHERE id = ANY(:ids)"),
}
AUDIT_KINDS: Final = frozenset(_READS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For rows of `kind` named by audit events: id -> the owning engagement."""
    read = _READS.get(kind)
    if read is None or not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(read, {"ids": list(ids)})
        return {found: owned for found, owned in rows}
