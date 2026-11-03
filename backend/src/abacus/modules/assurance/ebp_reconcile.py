"""A-05-T27: mode `ebp_reconcile` (A-05 §3 F5; EBP-04 a; DEC-2219). PROTECTED (red).

EBP-04 reconciles contributions payroll → trust → financial statements. The model reads the
payroll register, the trustee's receipts, the W-3, the loan reports and the account statements
(masked page text) and drafts the totals each document prints, with region citations; it never
adds or subtracts. **Code** supplies the facts it cites: the imported payroll register's totals
(`ebp_payrolls`) and the waterfall's steps (`compute.ebp.remittance.waterfall`), so a drafted
total that differs from code's is visible as a difference, never reconciled by a model
(ADR-050). The agent's exceptions are drafts; a person raises them (SHL-15).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.agents.api import ModeInputs, SourcePaper
from abacus.modules.assurance.draft_mappings import documents_for_areas
from abacus.modules.identity.api import AgentContext

MODE: Final = "ebp_reconcile"
RECONCILE_AREAS: Final = frozenset({"contributions", "payroll", "trust", "participant_loans"})
_TOTALS = text(
    "SELECT coalesce(sum(deferrals_pretax), 0) AS pretax, "
    "coalesce(sum(deferrals_roth), 0) AS roth, "
    "coalesce(sum(match), 0) AS match, count(*) AS payrolls, "
    "coalesce(sum(CASE WHEN deposit_date > make_date(date_part('year', pay_date)::int, 12, 31) "
    "THEN deferrals_pretax + deferrals_roth + match ELSE 0 END), 0) AS after_year_end "
    "FROM ebp_payrolls WHERE work_item_id = :w"
)


def _fact(name: str, value: Decimal | int) -> tuple[str, dict[str, object]]:
    return (name, {"t": "decimal", "v": str(value)})


async def payroll_facts(
    tenant: TenantContext, work_item_id: UUID
) -> tuple[tuple[str, dict[str, object]], ...]:
    """Code's register totals as facts (amounts as decimal strings; no participant data)."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_TOTALS, {"w": work_item_id})).mappings().one()
    deferrals = cast(Decimal, row["pretax"]) + cast(Decimal, row["roth"])
    return (
        _fact("payrolls_imported", int(cast(int, row["payrolls"]))),
        _fact("register_deferrals", deferrals),
        _fact("register_match", cast(Decimal, row["match"])),
        _fact("register_deferrals_and_match", deferrals + cast(Decimal, row["match"])),
        _fact("deposited_after_year_end", cast(Decimal, row["after_year_end"])),
    )


async def reconcile_inputs(actor: AgentContext, paper: SourcePaper) -> ModeInputs:
    """`ebp_reconcile`'s inputs: the contribution documents (masked) and code's totals."""
    documents = await documents_for_areas(actor, paper, RECONCILE_AREAS)
    facts = await payroll_facts(actor.tenant, paper.work_item_id)
    return ModeInputs(documents=documents.documents, facts=facts)
