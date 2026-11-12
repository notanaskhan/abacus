"""The entity workbook run's step handlers, part 1 (T-05-T32; T-05 F2, F3, F6, F7; TXP-00, TXP-02,
TXP-05, TXP-07; ADR-050; DEC-4617). Amber. Registered through `agents.register_run_step` at the
tax api's import; each runs under the run's AgentContext and writes cells only through
`workbook_service.write_cells` in its own unit of work (audited `workbook.step_written`).

Code computes every figure (ADR-050); no model is called here. Every write skips a cell whose
current value a person wrote (`engine_may_write`, the run's `keep_human`).

- `import_trial_balance`: the engagement's newest trial balance (C9) into sheet 01: per account
  the code, the name, UTB, AJE, RJE and ATB (`tb_linked`), and the column totals as formulas. No
  trial balance answers `failed` `trial_balance_missing`; a connection whose token expired
  answers `failed` `token_expired` (the TXP-00 e failure class).
- `map_lines`: the trial balance's mapped lines (C9, `mapped_trial_balance`) into sheet 03, one
  row per line with its key, label and net; unmapped accounts are counted, not written (they close
  the export gate, TXP-02 tallies). Mapper suggestions arrive as proposals through the mapper's own
  flow, never as cells.
- `contributions_distributions`: per partner row of sheet 05 the contributions and distributions
  (columns C and D) totalled into the M-2 (sheet 07 rows 2 and 6) as formulas.
- `capital_m2`: per partner ending capital = beginning + contributions - distributions + income
  share (05!F, a formula with its computed value), and the M-2's ending capital (07!B9) footing to
  the sum of the partners'.
- `federal_k1s`: sheet 09, one row per K-1 recipient with its share of each Schedule K line from
  sheet 06 (percentages from the recipient's ownership note), written as draft figures. The drafts
  are cells on the return's workbook: no K-1 package is created or released here, and nothing is
  portal-visible.

Part 2 (T-05-T40): `depreciation_register`, `bonus_eligibility`, `interim_closing_706d`,
`apportionment_ptet`, `state_k1s_k3s` answer `failed` `import_required` (Needs attention) until
their import-mode handlers land, so a full run completes every code step and names what waits.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.api import RunStepFacts, RunStepResult, register_run_step
from abacus.modules.identity.api import AgentContext
from abacus.modules.ledger.api import (
    engagement_trial_balances,
    mapped_trial_balance,
    trial_balance_view,
)
from abacus.modules.review.api import current_values, latest_sources
from abacus.modules.tax.workbook_service import (
    WORKBOOK,
    CellWrite,
    address,
    engine_may_write,
    write_cells,
)

ZERO: Final = Decimal("0")
_PCT: Final = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
PART_TWO: Final = (
    "depreciation_register",
    "bonus_eligibility",
    "interim_closing_706d",
    "apportionment_ptet",
    "state_k1s_k3s",
)
_RECIPIENTS: Final = text(
    "SELECT display_name, ownership_note FROM k1_recipients WHERE work_item_id = :r "
    "ORDER BY display_name"
)


def _return_of(facts: RunStepFacts) -> UUID | None:
    raw = facts.arguments.get("return_id")
    return None if raw is None else UUID(str(raw))


def _dec(cell: Mapping[str, object] | None) -> Decimal:
    if cell is None or cell.get("v") in (None, ""):
        return ZERO
    try:
        return Decimal(str(cell["v"]))
    except ArithmeticError:
        return ZERO


async def _kept(
    tenant: TenantContext, return_id: UUID, writes: Sequence[CellWrite]
) -> list[CellWrite]:
    """The writes whose cells no person wrote (a re-run keeps human-edited cells)."""
    sources = await latest_sources(tenant, WORKBOOK, [return_id])
    out: list[CellWrite] = []
    for w in writes:
        current = sources.get((return_id, address(w.address).key))
        if engine_may_write(None if current is None else current[0]):
            out.append(w)
    return out


async def _write(
    agent: AgentContext, facts: RunStepFacts, return_id: UUID, writes: Sequence[CellWrite]
) -> int:
    kept = await _kept(agent.tenant, return_id, writes)
    if not kept:
        return 0
    async with uow(agent.tenant) as tx:
        written = await write_cells(
            tx, engagement_id=facts.engagement_id, return_id=return_id, writes=kept
        )
        tx.record(
            "workbook.step_written",
            target=Target(WORKBOOK, return_id),
            after=Ref(step=facts.step_key, cells=written, run=facts.run_id),
        )
    return written


# --- part 1 -------------------------------------------------------------------------------------


async def import_trial_balance(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    balances = await engagement_trial_balances(agent.tenant, facts.engagement_id)
    if not balances:
        return RunStepResult("failed", "trial_balance_missing")
    newest = max(balances, key=lambda b: (b.period_end, b.current_version_no))
    try:
        view = await trial_balance_view(agent.tenant, facts.engagement_id, newest.id)
    except PermissionError:  # a connection's refresh token expired upstream (TXP-00 e)
        return RunStepResult("failed", "token_expired")
    writes: list[CellWrite] = []
    for n, line in enumerate(view.lines, start=2):
        aje = line.aje or ZERO
        rje = line.rje or ZERO
        atb = line.final if line.final is not None else line.eoy + aje + rje
        writes += [
            CellWrite(f"01!A{n}", line.account_code, "tb_linked"),
            CellWrite(f"01!B{n}", line.account_name, "tb_linked"),
            CellWrite(f"01!C{n}", line.eoy, "tb_linked"),
            CellWrite(f"01!D{n}", aje, "tb_linked"),
            CellWrite(f"01!E{n}", rje, "tb_linked"),
            CellWrite(f"01!F{n}", atb, "formula", formula=f"=C{n}+D{n}+E{n}"),
        ]
    last = len(view.lines) + 1
    if view.lines:
        total = last + 1
        for col in "CDEF":
            column_sum = sum(
                (Decimal(str(w.value)) for w in writes if w.address.startswith(f"01!{col}")),
                ZERO,
            )
            writes.append(
                CellWrite(
                    f"01!{col}{total}", column_sum, "formula", formula=f"=SUM({col}2:{col}{last})"
                )
            )
    await _write(agent, facts, return_id, writes)
    return RunStepResult("succeeded", records_read=len(view.lines))


async def map_lines(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    balances = await engagement_trial_balances(agent.tenant, facts.engagement_id)
    if not balances:
        return RunStepResult("failed", "trial_balance_missing")
    newest = max(balances, key=lambda b: (b.period_end, b.current_version_no))
    mapped = await mapped_trial_balance(agent.tenant, facts.engagement_id, newest.id)
    if mapped is None:
        return RunStepResult("failed", "mapping_missing")
    writes: list[CellWrite] = []
    for row, line in enumerate(mapped.lines, start=2):
        writes += [
            CellWrite(f"03!A{row}", line.fs_line_key, "tb_linked"),
            CellWrite(f"03!B{row}", line.fs_line_label, "tb_linked"),
            CellWrite(f"03!C{row}", line.net, "tb_linked"),
        ]
    await _write(agent, facts, return_id, writes)
    # Unmapped accounts close the export gate (TXP-02); the step itself succeeds.
    return RunStepResult("succeeded", records_read=len(mapped.lines) + mapped.unmapped)


async def _partner_rows(
    tenant: TenantContext, return_id: UUID
) -> tuple[dict[str, dict[str, object]], list[int]]:
    """Sheet 05's partner rows (row 2 onward while column A holds a name)."""
    values = await current_values(tenant, WORKBOOK, return_id)
    rows: list[int] = []
    n = 2
    while f"05!A{n}" in values and values[f"05!A{n}"].get("v"):
        rows.append(n)
        n += 1
    return values, rows


async def contributions_distributions(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    values, rows = await _partner_rows(agent.tenant, return_id)
    if not rows:
        return RunStepResult("failed", "capital_inputs_missing")
    contributions = sum((_dec(values.get(f"05!C{n}")) for n in rows), ZERO)
    distributions = sum((_dec(values.get(f"05!D{n}")) for n in rows), ZERO)
    first, last = rows[0], rows[-1]
    await _write(
        agent,
        facts,
        return_id,
        [
            CellWrite("07!B2", contributions, "formula", formula=f"=SUM('05'!C{first}:C{last})"),
            CellWrite("07!B6", distributions, "formula", formula=f"=SUM('05'!D{first}:D{last})"),
        ],
    )
    return RunStepResult("succeeded", records_read=len(rows))


async def capital_m2(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    values, rows = await _partner_rows(agent.tenant, return_id)
    if not rows:
        return RunStepResult("failed", "capital_inputs_missing")
    writes: list[CellWrite] = []
    ending_total = ZERO
    for n in rows:
        ending = (
            _dec(values.get(f"05!B{n}"))
            + _dec(values.get(f"05!C{n}"))
            - _dec(values.get(f"05!D{n}"))
            + _dec(values.get(f"05!E{n}"))
        )
        ending_total += ending
        writes.append(CellWrite(f"05!F{n}", ending, "formula", formula=f"=B{n}+C{n}-D{n}+E{n}"))
    first, last = rows[0], rows[-1]
    writes.append(
        CellWrite("07!B9", ending_total, "formula", formula=f"=SUM('05'!F{first}:F{last})")
    )
    await _write(agent, facts, return_id, writes)
    return RunStepResult("succeeded", records_read=len(rows))


def share_of(note: object) -> Decimal | None:
    """A recipient's percentage from its ownership note ("limited partner 25%" → 0.25)."""
    found = _PCT.search(str(note or ""))
    return None if found is None else Decimal(found.group(1)) / Decimal(100)


async def federal_k1s(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    async with tenant_session(agent.tenant) as session:
        recipients = (await session.execute(_RECIPIENTS, {"r": return_id})).mappings().all()
    if not recipients:
        return RunStepResult("failed", "recipients_missing")
    values = await current_values(agent.tenant, WORKBOOK, return_id)
    lines: list[tuple[int, Decimal]] = []
    n = 2
    while f"06!A{n}" in values:
        lines.append((n, _dec(values.get(f"06!C{n}"))))
        n += 1
    writes: list[CellWrite] = []
    for col_index, r in enumerate(recipients):
        share = share_of(r["ownership_note"])
        if share is None:
            return RunStepResult("failed", "ownership_missing")
        col = chr(ord("B") + col_index)
        writes.append(CellWrite(f"09!{col}1", str(r["display_name"]), "tb_linked"))
        for row, amount in lines:
            figure = (amount * share).quantize(Decimal("1"))
            writes.append(
                CellWrite(
                    f"09!{col}{row}",
                    figure,
                    "formula",
                    formula=f"=ROUND('06'!C{row}*{share},0)",
                )
            )
    await _write(agent, facts, return_id, writes)
    return RunStepResult("succeeded", records_read=len(recipients))


# --- part 2 (T-05-T40) ------------------------------------------------------------------------


def _import_required(kind: str):  # noqa: ANN202 -- a handler factory
    async def handler(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
        del agent, facts
        return RunStepResult("failed", "import_required")

    handler.__name__ = f"{kind}_import_required"
    return handler


def register() -> None:
    register_run_step("import_trial_balance", import_trial_balance)
    register_run_step("map_lines", map_lines)
    register_run_step("contributions_distributions", contributions_distributions)
    register_run_step("capital_m2", capital_m2)
    register_run_step("federal_k1s", federal_k1s)
    for kind in PART_TWO:
        register_run_step(kind, _import_required(kind))


__all__ = ["PART_TWO", "register", "share_of"]
