"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121), for the tax
module's kinds. A `tax_return` target is its work item (T-02-T07 records status moves on it); the
engagement module answers which engagement holds the work item, so the explorer shows the event
to whoever may see that engagement. Unknown ids are left out (fail closed)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import work_item_engagement

AUDIT_KINDS = frozenset({"tax_return"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `tax_return` rows named by an audit event: their work item id -> its engagement."""
    owned: dict[UUID, UUID] = {}
    for work_item_id in ids:
        engagement = await work_item_engagement(tenant, work_item_id)
        if engagement is not None:
            owned[work_item_id] = engagement
    return owned
