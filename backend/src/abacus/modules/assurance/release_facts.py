"""AUD-24's also-required list (A-07-T30; A-07 F6; DEC-3107): each item computed by code from the
module that owns its facts, registered into `release.register_also_required`. An item with no
provider is unmet (fail closed), so G8 cannot be released past it.

- `fs_approved`: management approved the newest statement version (A-06 through C18).
- `bring_down`: the bring-down ran through the report date (A-07-T23's run; its provider is
  registered by A-07-T32's `audit.bring_down` capability, so until then the item is unmet).
- `independence`: every person on the engagement's team is cleared (P-04's ADR-164 answer).
- `final_materiality`: a decided or revised materiality version is in force (A-03).
- `governance_260`: the AU-C 260 completion letter was sent or acknowledged (A-07-T26).

Values are words for AUD-24's rows ("5 of 5"); the facts are identifiers and counts.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.assurance.release import AlsoRequired, register_also_required

_GOVERNANCE_260: Final = text(
    "SELECT status FROM governance_communications WHERE work_item_id = :wi "
    "AND kind = 'completion_260'"
)
_MATERIALITY: Final = text(
    "SELECT version_no FROM materiality_versions WHERE work_item_id = :wi "
    "AND status IN ('decided', 'revised', 'reassessed') ORDER BY version_no DESC LIMIT 1"
)


async def fs_approved(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID
) -> AlsoRequired:
    from abacus.modules.reporting import api as c11

    del engagement_id
    version = await c11.fs_approved_version_no(tenant, work_item_id)
    return AlsoRequired(
        "fs_approved", version is not None, None if version is None else f"v{version}"
    )


async def independence(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID
) -> AlsoRequired:
    from abacus.modules.engagements.api import independence_cleared
    from abacus.modules.identity.api import team_of

    del work_item_id
    team = sorted({member for member, _role in await team_of(tenant.tenant_id, engagement_id)})
    cleared = [m for m in team if await independence_cleared(tenant, engagement_id, m)]
    met = bool(team) and len(cleared) == len(team)
    return AlsoRequired("independence", met, f"{len(cleared)} of {len(team)}")


async def final_materiality(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID
) -> AlsoRequired:
    del engagement_id
    async with tenant_session(tenant) as session:
        version_no = await session.scalar(_MATERIALITY, {"wi": work_item_id})
    return AlsoRequired(
        "final_materiality",
        version_no is not None,
        None if version_no is None else f"v{version_no}",
    )


async def governance_260(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID
) -> AlsoRequired:
    del engagement_id
    async with tenant_session(tenant) as session:
        status = await session.scalar(_GOVERNANCE_260, {"wi": work_item_id})
    met = status in ("sent", "acknowledged")
    return AlsoRequired("governance_260", met, None if status is None else str(status))


def register() -> None:
    """At import (assurance/api.py)."""
    register_also_required("fs_approved", fs_approved)
    register_also_required("independence", independence)
    register_also_required("final_materiality", final_materiality)
    register_also_required("governance_260", governance_260)
