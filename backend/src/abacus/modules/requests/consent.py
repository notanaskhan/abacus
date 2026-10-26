"""§7216 for third parties (ADR P-12; R-01-T13, DEC-388, DEC-389): whether an engagement's
requests may go to, or be reached by, a third party. Outside tax work always; on an engagement
holding a `tax_return` work item only under the client's C19 `third_party_disclosure` consent,
which nobody holds until T-01 registers it (fail closed).

The delegation routes refuse a new delegation with it, and `service.delegated_to`, the one fact
every `delegated_only` check reads, answers nobody without it: a delegation made before the gate
or before the engagement took on a tax return stays recorded but is inert until the consent
exists (DEC-389)."""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.kernel import clock
from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import client_of, holds_tax_return
from abacus.modules.identity.api import consent_given

THIRD_PARTY_DISCLOSURE: Final = "third_party_disclosure"


async def third_party_consented(tenant: TenantContext, engagement_id: UUID) -> bool:
    """Whether the engagement's requests may reach a third party."""
    if not await holds_tax_return(tenant, engagement_id):
        return True
    client = await client_of(tenant, engagement_id)
    return client is not None and await consent_given(
        tenant, client, THIRD_PARTY_DISCLOSURE, await clock.now(tenant)
    )
