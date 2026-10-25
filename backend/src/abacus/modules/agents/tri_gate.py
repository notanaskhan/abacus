"""Tax-return information stays away from models until consent is registered (P-06-T20; P-06
Story 5.3; DEC-324).

An upload to a request on a `tax_return` work item is tax-return information (§7216). No model
may read it without the client's consent, which C19 (T-01) will register. Until then, no consent
exists, so the gate fails closed for every firm that is not synthetic. The local seed and
evaluation firms are synthetic and stay open. Code checks are not model calls and still run.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import is_synthetic_firm
from abacus.modules.requests.api import screening_subject

TAX_RETURN: Final = "tax_return"


async def model_blocked(tenant: TenantContext, item_ids: Iterable[UUID]) -> bool:
    """True when any of these requests sits on a tax-return work item at a real firm."""
    for item_id in dict.fromkeys(item_ids):
        subject = await screening_subject(tenant, item_id)
        if subject is not None and subject.work_item_kind == TAX_RETURN:
            return not await is_synthetic_firm(tenant)
    return False
