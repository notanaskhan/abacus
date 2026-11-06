"""What the portal and CLI-05 may read of a notice (N-04-T22; N-04 US-8.3, INV-4).

`portal_notice_rows` answers POR-02's info row for work items the portal has already authorised:
agency, tax year and a client code, only for notices the firm marked `client_visible`. The code
reads "waiting for your signature" once the response envelope is out. `open_notice_rows` is
CLI-05's band, through `visible_notices`, so a wall or a role that can't read the notice leaves it
off.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import service
from abacus.modules.organisations.api import OpenNoticeRowOut
from abacus.modules.signatures.api import envelope_status

_OUT_FOR_SIGNATURE: Final = ("sent", "viewed", "partially_signed")

_ROWS = text(
    "SELECT n.work_item_id, n.agency_name, n.notice_code, n.tax_year, r.envelope_id "
    "FROM notices n "
    "LEFT JOIN notice_responses r ON r.work_item_id = n.work_item_id "
    "WHERE n.work_item_id = ANY(:ids) AND n.client_visible AND n.status <> 'closed' "
    "ORDER BY n.received_on DESC"
)


@dataclass(frozen=True)
class PortalNoticeRow:
    notice_id: UUID
    waiting: bool
    subject: str


def _subject(agency: str | None, year: int | None) -> str:
    who = agency or "Tax agency"
    return f"{who} notice" if year is None else f"{who} notice, tax year {year}"


async def portal_notice_rows(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> list[PortalNoticeRow]:
    if not work_item_ids:
        return []
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_ROWS, {"ids": list(work_item_ids)})).mappings().all()
    out: list[PortalNoticeRow] = []
    for r in rows:
        envelope = r["envelope_id"]
        status = None if envelope is None else await envelope_status(tenant, envelope)
        out.append(
            PortalNoticeRow(
                r["work_item_id"],
                status in _OUT_FOR_SIGNATURE,
                _subject(r["agency_name"], r["tax_year"]),
            )
        )
    return out


async def open_notice_rows(ctx: AuthContext, client_entity_id: UUID) -> list[OpenNoticeRowOut]:
    return [
        OpenNoticeRowOut(
            notice_id=n.id,
            notice_code=n.notice_code,
            tax_year=n.tax_year,
            respond_by=n.respond_by,
        )
        for n in await service.visible_notices(ctx)
        if n.open and n.client_entity_id == client_entity_id
    ]
