"""The filings tracker (A-07-T36; A-07 F6, AUD-24 f; SPEC-644). Manual EFAST2 tracking only: the
client files Form 5500, Accrued records it. EFAST2 has no public API and is never integrated.

- **Open.** An EBP audit's release opens one `form_5500` row (`awaiting_client_filing`) with the
  plan year's due date and Form 5558 extended date computed by code (`clocks.form_5500_due`); the
  filer is the client entity. Once per work item (the table's unique `(work_item, form)`).
- **Update.** A manager or senior (`filing.update`) records "Filed <date>" with the EFAST2
  acknowledgement as an evidence version of the same engagement, under `seen_version` (409
  `stale_version`). The table's CHECK refuses `filed` without both. Audited `filing.updated` with
  identifiers; `filing.updated` on the outbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.assurance.clocks import form_5500_due
from abacus.modules.assurance.completion_errors import StaleVersion
from abacus.modules.assurance.events import FilingUpdated
from abacus.modules.evidence.api import version_view
from abacus.modules.identity.api import AuthContext

FORM: Final = "form_5500"


class FilingEvidenceRequired(DomainInvalid):
    """`filed` needs the filed date and the EFAST2 acknowledgement of this engagement."""

    code = "filing_evidence_required"


@dataclass(frozen=True)
class Filing:
    id: UUID
    form: str
    channel: str
    filer_name: str
    due_on: date | None
    extended_due_on: date | None
    status: str
    filed_on: date | None
    ack_evidence_version_id: UUID | None
    version: int


_BY_WORK_ITEM = text(
    "SELECT id, form, channel, filer_name, due_on, extended_due_on, status, filed_on, "
    "ack_evidence_version_id, version FROM filings WHERE work_item_id = :wi ORDER BY form"
)


async def filings_of(tenant: TenantContext, work_item_id: UUID) -> list[Filing]:
    """After the caller's `report.read` on the work item."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                _BY_WORK_ITEM,
                {"wi": work_item_id},
            )
        ).all()
    return [Filing(*r) for r in rows]


async def open_filing(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    work_item_id: UUID,
    filer_name: str,
    plan_year_end: date,
) -> UUID | None:
    """`report.released` on an EBP audit → its Form 5500 row, once (None when it existed)."""
    due, extended = form_5500_due(plan_year_end)
    made = await tx.session.scalar(
        text(
            "INSERT INTO filings (tenant_id, engagement_id, work_item_id, form, filer_name, "
            "channel, due_on, extended_due_on) VALUES (:t, :e, :wi, 'form_5500', :filer, "
            "'efast2', :due, :ext) ON CONFLICT (tenant_id, work_item_id, form) DO NOTHING "
            "RETURNING id"
        ),
        {
            "t": tenant_id,
            "e": engagement_id,
            "wi": work_item_id,
            "filer": filer_name[:200] or "Plan sponsor",
            "due": due,
            "ext": extended,
        },
    )
    if made is None:
        return None
    filing_id = cast(UUID, made)
    tx.record(
        "filing.opened",
        target=Target("filing", filing_id),
        after=Ref(due_on=int(due.strftime("%Y%m%d"))),
        scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
    )
    return filing_id


async def update_filing(
    ctx: AuthContext,
    work_item_id: UUID,
    filing_id: UUID,
    *,
    status: str,
    filed_on: date | None,
    ack_evidence_version_id: UUID | None,
    seen_version: int,
) -> Filing:
    """After the caller's `filing.update` on the work item (AUD-24 f)."""
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT engagement_id, version FROM filings "
                    "WHERE id = :f AND work_item_id = :wi"
                ),
                {"f": filing_id, "wi": work_item_id},
            )
        ).first()
    if row is None:
        raise NotFound("filing")
    engagement_id = cast(UUID, row.engagement_id)
    if status == "filed":
        if filed_on is None or ack_evidence_version_id is None:
            raise FilingEvidenceRequired
        try:
            proof = await version_view(ctx.tenant, ack_evidence_version_id)
        except NotFound:
            raise FilingEvidenceRequired from None
        if proof.engagement_id != engagement_id:
            raise FilingEvidenceRequired  # another engagement's file is never this filing's proof
    else:
        filed_on, ack_evidence_version_id = None, None
    async with uow(ctx.tenant) as tx:
        moved = await tx.session.scalar(
            text(
                "UPDATE filings SET status = :status, filed_on = :filed, "
                "ack_evidence_version_id = :ack, version = version + 1, "
                "updated_at = clock_timestamp() WHERE id = :f AND version = :seen RETURNING id"
            ),
            {
                "status": status,
                "filed": filed_on,
                "ack": ack_evidence_version_id,
                "f": filing_id,
                "seen": seen_version,
            },
        )
        if moved is None:
            raise StaleVersion
        refs: dict[str, UUID | int] = {"version": seen_version + 1}
        if ack_evidence_version_id is not None:
            refs["ack_evidence_version_id"] = ack_evidence_version_id
        tx.record(
            "filing.updated",
            target=Target("filing", filing_id),
            after=Ref(**refs),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
        tx.emit(
            FilingUpdated(
                filing_id=filing_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                status=status,
            )
        )
    found = [f for f in await filings_of(ctx.tenant, work_item_id) if f.id == filing_id]
    return found[0]
