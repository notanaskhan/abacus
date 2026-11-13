"""The tax module's contribution to the Today brief's facts (I-02-T07; I-02 §6; DEC-4719): for each
entity return on the engagement, the off tie-outs' differences (T-05-T42's code) and the §754
placeholder (the transfer's price less the capital the transferee took on, 28,595 for Ridgeline),
as registered facts; the partnership as its §7216 subject (TRI); and the workbook cells the facts
rest on as candidate citations. Registered with `agents.register_briefing_source` at import."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

if TYPE_CHECKING:
    from abacus.modules.agents.api import BriefingContribution

_RETURNS: Final = text(
    "SELECT work_item_id FROM tax_returns WHERE engagement_id = :e AND form IN "
    "('1065', '1120-S', '1120', '990') ORDER BY work_item_id"
)
_TRANSFER: Final = text(
    "SELECT t.price, p.display_name FROM interest_transfers t JOIN partners p ON "
    "p.id = t.to_partner_id WHERE t.work_item_id = :r AND t.price IS NOT NULL "
    "ORDER BY t.transfer_date LIMIT 1"
)


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal(1)), "f")


async def entity_briefing(tenant: TenantContext, engagement_id: UUID) -> BriefingContribution:
    from abacus.modules.agents.api import (
        AgentFact as Fact,
    )
    from abacus.modules.agents.api import (
        BriefingCandidate,
        BriefingContribution,
        BriefingSubject,
    )
    from abacus.modules.agents.api import (
        briefing_fact_id as fact_id,
    )
    from abacus.modules.tax.entity_schedules import capital_rows, workbook_values
    from abacus.modules.tax.entity_sections import tie_outs
    from abacus.modules.tax.entity_tri import entity_return_subjects

    async with tenant_session(tenant) as session:
        returns = list((await session.execute(_RETURNS, {"e": engagement_id})).scalars())
    facts: list[Fact] = []
    subjects: list[BriefingSubject] = []
    citations: list[BriefingCandidate] = []
    for return_id in returns:
        values = await workbook_values(tenant, return_id)
        for t in tie_outs(values):
            if t.state == "off" and t.difference is not None:
                facts.append(
                    Fact(
                        id=fact_id("tie_out", t.key),
                        kind="money" if t.key == "item_l_m2" else "count",
                        value=_money(abs(t.difference)),
                        basis=f"T-05-T42 tie-out {t.key}",
                    )
                )
                citations += [
                    BriefingCandidate(
                        "workpaper_cell",
                        f"tax_workbook:{return_id}:{link['sheet']}!{link['range']}",
                    )
                    for link in t.links
                ]
        async with tenant_session(tenant) as session:
            transfer = (await session.execute(_TRANSFER, {"r": return_id})).first()
        if transfer is not None:
            moved = next(
                (
                    r.beginning
                    for r in capital_rows(values, return_id, {})
                    if r.name == transfer.display_name
                ),
                None,
            )
            if moved is not None and moved > 0:
                facts.append(
                    Fact(
                        id="section_754_placeholder",
                        kind="money",
                        value=_money(Decimal(transfer.price) - moved),
                        basis="§743(b) placeholder: price less capital moved (code)",
                    )
                )
        for s in await entity_return_subjects(tenant, return_id):
            if s.entity_id is not None:
                subjects.append(BriefingSubject(s.entity_id, True, s.tax_year))
    return BriefingContribution(facts=facts, subjects=subjects, citations=citations)


__all__ = ["entity_briefing"]
