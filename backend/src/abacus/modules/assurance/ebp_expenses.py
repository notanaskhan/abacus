"""EBP-09: administrative expenses and operational compliance (A-05-T43; A-05 F8; DEC-2307).

Figures foot by code (`compute.ebp.expenses`). A compliance test's exemption (QACA ADP/ACP, top
heavy) stays a proposal until a person accepts it: an unaccepted `exempt` reads as `proposed`. An
expense with no 408(b)(2) disclosure is an exception a person raises through P-04's issues. Request
TPA support prefills SHL-14 (POR-14), never sending anything. Limits are the plan year's only. The
routes have authorised the action and the flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.assurance.compute.ebp import expenses as engine

_ZERO: Final = Decimal(0)
JsonRow = dict[str, Any]  # Any: rows from the database
PROVIDER_REQUEST_KIND: Final = "tpa_support"


@dataclass(frozen=True)
class ExpensesView:
    rows: tuple[JsonRow, ...]
    tie: engine.ExpenseTie


async def plan_expenses(tenant: TenantContext, work_item_id: UUID) -> ExpensesView:
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT id, provider_id, line_key, description, disclosure_citation_id, "
                        "citation_id, invoiced, credits, paid_from_plan, schedule_h_line, result, "
                        "issue_id FROM ebp_plan_expenses WHERE work_item_id = :w ORDER BY line_key"
                    ),
                    {"w": work_item_id},
                )
            )
            .mappings()
            .all()
        )
    found = tuple(dict(r) for r in rows)
    return ExpensesView(
        found,
        engine.tie(
            [
                engine.Expense(
                    r["line_key"],
                    r["invoiced"],
                    r["credits"],
                    r["paid_from_plan"],
                    r["schedule_h_line"],
                    r["disclosure_citation_id"] is not None,
                )
                for r in found
            ]
        ),
    )


async def budget_account(tenant: TenantContext, work_item_id: UUID) -> engine.BudgetRoll:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT kind, amount FROM ebp_erisa_budget_lines WHERE work_item_id = :w "
                    "ORDER BY line_key"
                ),
                {"w": work_item_id},
            )
        ).all()
    return engine.budget_account([(r.kind, r.amount) for r in rows])


@dataclass(frozen=True)
class ComplianceRow:
    id: UUID
    test_key: str
    plan_year: int
    limit: Decimal | None
    limit_ref: str | None
    result: str  # pass, exception, exempt, or proposed (an exemption nobody accepted)
    accepted_at: date | None
    finding_ref: JsonRow | None


async def compliance_tests(
    tenant: TenantContext, work_item_id: UUID, plan_year: int
) -> tuple[ComplianceRow, ...]:
    """Rows for this plan year only, each limit re-read from the file (prior years are refused)."""
    limits = engine.limits_for(plan_year)
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT id, test_key, plan_year, limit_ref, result, accepted_at, "
                        "finding_ref FROM ebp_compliance_tests "
                        "WHERE work_item_id = :w AND plan_year = :y ORDER BY test_key"
                    ),
                    {"w": work_item_id, "y": plan_year},
                )
            )
            .mappings()
            .all()
        )
    return tuple(
        ComplianceRow(
            r["id"],
            r["test_key"],
            r["plan_year"],
            limits.get(r["limit_ref"] or ""),
            r["limit_ref"],
            "proposed" if r["result"] == "exempt" and r["accepted_at"] is None else r["result"],
            r["accepted_at"],
            r["finding_ref"],
        )
        for r in rows
    )


async def qualification(tenant: TenantContext, work_item_id: UUID) -> tuple[JsonRow, ...]:
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT id, fact_key, value, result, citation_id, proposed_by_kind, "
                        "accepted_by, accepted_at FROM ebp_qualification_facts "
                        "WHERE work_item_id = :w ORDER BY fact_key"
                    ),
                    {"w": work_item_id},
                )
            )
            .mappings()
            .all()
        )
    return tuple(dict(r) for r in rows)


@dataclass(frozen=True)
class SupportPrefill:
    """What SHL-14 opens with; a person edits and sends it (identifiers only)."""

    provider_id: UUID | None
    expense_line_key: str
    request_kind: str


async def support_prefill(
    tenant: TenantContext, work_item_id: UUID, expense_id: UUID
) -> SupportPrefill:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT provider_id, line_key FROM ebp_plan_expenses "
                    "WHERE work_item_id = :w AND id = :i"
                ),
                {"w": work_item_id, "i": expense_id},
            )
        ).one_or_none()
    if row is None:
        raise NotFound("ebp_plan_expense")
    return SupportPrefill(row.provider_id, row.line_key, PROVIDER_REQUEST_KIND)
