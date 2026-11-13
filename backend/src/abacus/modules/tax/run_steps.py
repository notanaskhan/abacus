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

Part 2 (T-05-T40; DEC-4703, DEC-4704): `depreciation_register` and `bonus_eligibility` read 02
(the firm's imported or keyed depreciation report), `interim_closing_706d` writes 04's segments
under the run's convention answer, `apportionment_ptet` and `state_k1s_k3s` read 08's imported
state schedule; with nothing to read a step stops at Needs attention with one issue (its failure
class in `FAILURE_CLASSES`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date
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


# --- part 2 (T-05-T40; DEC-4703, DEC-4704) ----------------------------------------------------
#
# Import mode: the firm's own depreciation report and state schedule arrive through
# `POST …/workbook/imports` (`workbook_imports.py`) or as keyed cells; each step reads what is
# there. With nothing there, the step stops at Needs attention (`failed` with a failure class)
# and raises one issue per return and step, deduplicated on its `source_ref`.

FAILURE_CLASSES: Final = {
    "import_required": "Import or key the firm's report",
    "convention_required": "Answer the §706(d) convention question",
    "closing_amounts_required": "Key the interim closing amounts on 04 Allocation",
    "apportionment_missing": "Import the state apportionment schedule",
    "return_missing": "The run names no return",
}
_ISSUE_TITLES: Final = {
    "depreciation_register": "Depreciation report not imported",
    "bonus_eligibility": "Bonus depreciation needs the depreciation report",
    "interim_closing_706d": "Interim closing amounts are missing",
    "apportionment_ptet": "State apportionment schedule not imported",
    "state_k1s_k3s": "State K-1 amounts need the apportionment schedule",
}
STATE_ROWS: Final = ("F", "G", "H")  # 08: state, apportionment %, PTET (workbook_imports)
HUNDRED: Final = Decimal(100)


async def _needs_attention(
    agent: AgentContext, facts: RunStepFacts, return_id: UUID, code: str
) -> RunStepResult:
    """`failed` with the class, and the step's issue on the return (once per return and step)."""
    from abacus.modules.review.api import create_issue

    await create_issue(
        agent,
        record_type="tax_return",
        record_id=return_id,
        kind="action_required",
        priority="high",
        title=_ISSUE_TITLES.get(facts.step_key, FAILURE_CLASSES.get(code, code)),
        internal_note=None,
        client_wording=None,
        client_contact_id=None,
        assignee_user_id=None,
        assignee_agent=False,
        blocks=("final_approval",),
        source_ref=f"run_step:{facts.step_key}:{code}",
        work_item_id=return_id,
    )
    return RunStepResult("failed", code)


def _rows_of(values: Mapping[str, Mapping[str, object]], sheet: str, col: str) -> list[int]:
    out: list[int] = []
    n = 2
    while f"{sheet}!{col}{n}" in values:
        out.append(n)
        n += 1
    return out


async def depreciation_register(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    """02's imported or keyed assets: succeeded with their count; none, Needs attention."""
    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    values = await current_values(agent.tenant, WORKBOOK, return_id)
    assets = [
        n for n in _rows_of(values, "02", "A") if str(values[f"02!A{n}"].get("v")) != "Total"
    ]
    if not assets:
        return await _needs_attention(agent, facts, return_id, "import_required")
    return RunStepResult("succeeded", records_read=len(assets))


async def bonus_eligibility(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    """The bonus column of the same report (02!G); eligibility judgments are T-06's (E3)."""
    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    values = await current_values(agent.tenant, WORKBOOK, return_id)
    assets = [
        n for n in _rows_of(values, "02", "A") if str(values[f"02!A{n}"].get("v")) != "Total"
    ]
    if not assets:
        return await _needs_attention(agent, facts, return_id, "import_required")
    with_bonus = sum(1 for n in assets if _dec(values.get(f"02!G{n}")) != ZERO)
    return RunStepResult("succeeded", records_read=with_bonus)


async def interim_closing_706d(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    """The segments of the year at each interest transfer under the convention (the run's
    `convention_706d` answer, else the settled structure's), written to 04 Allocation from row 2
    (A period, B start, C end, D amount). Interim closing keeps the closed-books amounts keyed or
    imported in D (none: Needs attention); proration splits the structure's income by days."""
    from abacus.modules.agents.api import run_step_answers
    from abacus.modules.tax.allocation_structure import ownership_of, versions
    from abacus.modules.tax.compute.entity.allocation import AllocationInvalid, segments
    from abacus.modules.tax.overview import tax_year_of

    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    answers = await run_step_answers(agent.tenant, facts.run_id)
    found = await versions(agent.tenant, return_id)
    newest = found[0] if found else None
    convention = answers.get("convention_706d") or (None if newest is None else newest.convention)
    if convention not in ("calendar_day", "semi_monthly", "monthly"):
        return await _needs_attention(agent, facts, return_id, "convention_required")
    method = "interim_closing" if newest is None else newest.method
    if method == "proration" and convention != "calendar_day":
        return await _needs_attention(agent, facts, return_id, "convention_required")
    periods, transfers = await ownership_of(agent.tenant, return_id)
    year = await tax_year_of(agent.tenant, return_id)
    starts = sorted({p.starts_on for p in periods})
    by_transfer: list[tuple[object, Mapping[str, Decimal]]] = [
        (None if n == 0 else transfers[n - 1] if n - 1 < len(transfers) else None,
         {str(p.partner_id): p.profit_pct for p in periods if p.starts_on == start})
        for n, start in enumerate(starts)
    ]  # fmt: skip
    if not by_transfer:
        by_transfer = [(None, {"partnership": HUNDRED})]
    try:
        segs = segments(date(year, 1, 1), date(year, 12, 31), by_transfer, convention)  # type: ignore[arg-type] -- the run's context reads as its initiator
    except AllocationInvalid as error:
        return RunStepResult("failed", error.code)
    values = await current_values(agent.tenant, WORKBOOK, return_id)
    writes: list[CellWrite] = []
    for n, seg in enumerate(segs, start=2):
        writes += [
            CellWrite(f"04!A{n}", f"p{n - 1}", "formula"),
            CellWrite(f"04!B{n}", seg.start.isoformat(), "formula"),
            CellWrite(f"04!C{n}", seg.end.isoformat(), "formula"),
        ]
    if method == "proration":
        income = None if newest is None else newest.income
        if income is None:
            return await _needs_attention(agent, facts, return_id, "closing_amounts_required")
        from abacus.kernel.numeric import allocate

        amounts = allocate(income, [Decimal(s.days) for s in segs], places=0)
        writes += [CellWrite(f"04!D{n}", a, "formula") for n, a in enumerate(amounts, start=2)]
    elif any(f"04!D{n}" not in values for n in range(2, len(segs) + 2)):
        await _write(agent, facts, return_id, writes)
        return await _needs_attention(agent, facts, return_id, "closing_amounts_required")
    await _write(agent, facts, return_id, writes)
    if transfers:  # T-05-T52 (DEC-4906): the §754 card, once per return, for the partner
        from abacus.modules.tax.entity_decisions import ensure_section_754_card

        await ensure_section_754_card(agent, facts.engagement_id, return_id)
    return RunStepResult("succeeded", records_read=len(segs))


def _states(values: Mapping[str, Mapping[str, object]]) -> list[tuple[str, Decimal, Decimal]]:
    out: list[tuple[str, Decimal, Decimal]] = []
    for n in _rows_of(values, "08", "F"):
        state = str(values[f"08!F{n}"].get("v") or "")
        if state:
            out.append((state, _dec(values.get(f"08!G{n}")), _dec(values.get(f"08!H{n}"))))
    return out


async def apportionment_ptet(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    """06's state column (D) for the first state on 08's schedule: each Schedule K line times its
    apportionment percentage, as a formula (code computes; ADR-050). Sourcing and PTET credit
    splits are T-06's engines (E9); the PTET paid stays as imported."""
    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    values = await current_values(agent.tenant, WORKBOOK, return_id)
    states = _states(values)
    if not states:
        return await _needs_attention(agent, facts, return_id, "import_required")
    _state, pct, _ptet = states[0]
    writes: list[CellWrite] = []
    for n in _rows_of(values, "06", "A"):
        federal = _dec(values.get(f"06!C{n}"))
        figure = (federal * pct / HUNDRED).quantize(Decimal("1"))
        writes.append(
            CellWrite(f"06!D{n}", figure, "formula", formula=f"=ROUND(C{n}*'08'!G2/100,0)")
        )
    await _write(agent, facts, return_id, writes)
    return RunStepResult("succeeded", records_read=len(states))


async def state_k1s_k3s(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
    """Per recipient (09's columns from B) the state share of each line: its federal share times
    the first state's apportionment, written to 08 from column J (J recipient, K line, L state
    amount). K-3 applicability is not decided in T-05."""
    return_id = _return_of(facts)
    if return_id is None:
        return RunStepResult("failed", "return_missing")
    values = await current_values(agent.tenant, WORKBOOK, return_id)
    states = _states(values)
    if not states:
        return await _needs_attention(agent, facts, return_id, "import_required")
    _state, pct, _ptet = states[0]
    lines = _rows_of(values, "06", "A")
    writes: list[CellWrite] = []
    row = 2
    col_index = 0
    while f"09!{chr(ord('B') + col_index)}1" in values:
        col = chr(ord("B") + col_index)
        name = str(values[f"09!{col}1"].get("v") or "")
        for n in lines:
            share = _dec(values.get(f"09!{col}{n}"))
            writes += [
                CellWrite(f"08!J{row}", name, "tb_linked"),
                CellWrite(f"08!K{row}", str(values[f"06!A{n}"].get("v") or ""), "tb_linked"),
                CellWrite(
                    f"08!L{row}",
                    (share * pct / HUNDRED).quantize(Decimal("1")),
                    "formula",
                    formula=f"=ROUND('09'!{col}{n}*G2/100,0)",
                ),
            ]
            row += 1
        col_index += 1
    if not col_index:
        return RunStepResult("failed", "recipients_missing")
    await _write(agent, facts, return_id, writes)
    return RunStepResult("succeeded", records_read=col_index)


PART_TWO_HANDLERS: Final = {
    "depreciation_register": depreciation_register,
    "bonus_eligibility": bonus_eligibility,
    "interim_closing_706d": interim_closing_706d,
    "apportionment_ptet": apportionment_ptet,
    "state_k1s_k3s": state_k1s_k3s,
}


def register() -> None:
    register_run_step("import_trial_balance", import_trial_balance)
    register_run_step("map_lines", map_lines)
    register_run_step("contributions_distributions", contributions_distributions)
    register_run_step("capital_m2", capital_m2)
    register_run_step("federal_k1s", federal_k1s)
    for kind in PART_TWO:
        register_run_step(kind, PART_TWO_HANDLERS[kind])


__all__ = ["FAILURE_CLASSES", "PART_TWO", "PART_TWO_HANDLERS", "register", "share_of"]
