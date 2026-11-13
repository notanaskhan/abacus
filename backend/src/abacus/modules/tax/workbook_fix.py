"""The fix flow on an entity return's workbook (T-05-T50; TASK-7901; T-05 F8; TXP-10, TXP-11,
TXP-07; ADR-005, ADR-050, ADR-052; DEC-4901, DEC-4902). Amber.

A tie-out issue (T-05-T42) on an entity return carries a person's fix instructions (SHL-15 a,
"Add 6,200 to 07 M-2!B6"). Review seals them, moves the issue In progress and calls the tax fix
runner (`review.api.register_fix_runner('tax_return', …)`, T-04-T31); for a return whose form has
a workbook (`workbook_service.sheets_of`), the runner's activity hands the issue to `fix` here.

1. **Propose (the run, as the agent).** The person's sealed instructions, read back for this
   issue's own run, are parsed by code against a closed grammar (`parse_instructions`): add,
   subtract or set an amount on a `<sheet>!<cell>` address of the form's own sheets. No model is
   asked (DEC-4901): the amount is the person's own figure (number provenance) and code computes
   each new value from the cell's current one. One `workbook_cell_changes` proposal with a row per
   cell (before and after, `{t, v}`), named to the issue (`review.api.record_fix_proposal`). An
   instruction outside the grammar proposes nothing (`no_cell_named`); the run never writes a cell.
2. **Approve (a person, SHL-10).** The adapter (`apply_fix`, registered for the kind) runs after
   the decision commits: each row's value through `write_cells` → `record_value` as the
   approver's value (`human`, so a re-run keeps it), the cells' dependents recomputed (bounded, as
   T-05-T35's edit), audited `workbook.fix_applied`; then the approver's checkpoint "Fix approved
   by Daniel Reyes" and a group re-run (`selected('group', …)`: the groups owning the fixed
   sheets and their dependants), so approving the M-2 fix starts Run 3.
3. **Resolve.** The issue stays In progress: a tie-out issue is `system_resolved_only` and review
   never resolves it on the approval (DEC-4902); the re-run's terminal state runs the tie-outs
   (`entity_sections.on_run_state_changed`) and the system resolves it when the tie passes.
4. **Reject.** A person rejects the proposal in SHL-10 with a reason (the decision's reason
   code); nothing is written and the issue stays In progress for the person to act on.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.tax.workbook_service import (
    WORKBOOK,
    Address,
    CellAddressInvalid,
    CellWrite,
    address,
    sheets_of,
    write_cells,
)

KIND: Final = "workbook_cell_changes"
CAUSE: Final = "fix_instructions"
Op = Literal["add", "subtract", "set"]

# The groups whose steps write each sheet (`entity_run_plan.GROUPS`); a fix re-runs these and
# their dependants, never their dependencies.
SHEET_GROUPS: Final[Mapping[str, str]] = {
    "01": "map",
    "03": "map",
    "02": "compute",
    "04": "capital",
    "05": "capital",
    "07": "capital",
    "08": "apportionment",
    "06": "k1s",
    "09": "k1s",
}

# --- the closed grammar (code, never a model) ---------------------------------------------------

_AMOUNT: Final = r"(?P<amount>-?\(?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?)"
# `07 M-2!B6`, `05 Capital!F12`, `07!B9` or `07 B9`: two-digit sheet, an optional title, a cell.
_ADDR: Final = (
    r"(?P<sheet>\d{2})(?:[ ][A-Za-z][\w.&-]*)*\s*[!\s]\s*(?P<cell>[A-Za-z]{1,3}[1-9]\d{0,4})\b"
)
_CLAUSES: Final[tuple[tuple[Op, re.Pattern[str]], ...]] = (
    ("add", re.compile(rf"\b(?:add|increase)\s+{_AMOUNT}\s+(?:to|on|in)\s+{_ADDR}", re.I)),
    (
        "subtract",
        re.compile(rf"\b(?:subtract|deduct|reduce)\s+{_AMOUNT}\s+(?:from|on|in)\s+{_ADDR}", re.I),
    ),
    ("set", re.compile(rf"\b(?:set|change|update)\s+{_ADDR}\s+to\s+{_AMOUNT}", re.I)),
)
MAX_CELLS: Final = 20


@dataclass(frozen=True)
class PlannedCell:
    op: Op
    amount: Decimal
    at: Address


def _amount(raw: str) -> Decimal | None:
    negative = raw.startswith("-") or (raw.startswith("(") and raw.endswith(")"))
    digits = raw.strip("-()$").replace(",", "")
    try:
        value = Decimal(digits)
    except InvalidOperation:
        return None
    return -value if negative else value


def parse_instructions(instructions: str, form: str) -> tuple[PlannedCell, ...]:
    """Each add, subtract or set the person's words name on one of the form's sheets, in the order
    written; a later clause on the same cell wins. Words outside the grammar name nothing."""
    sheets = {n for n, _ in sheets_of(form)}
    found: list[tuple[int, PlannedCell]] = []
    for op, pattern in _CLAUSES:
        for m in pattern.finditer(instructions):
            amount = _amount(m.group("amount"))
            if amount is None or m.group("sheet") not in sheets:
                continue
            try:
                at = address(f"{m.group('sheet')}!{m.group('cell').upper()}")
            except CellAddressInvalid:
                continue
            found.append((m.start(), PlannedCell(op, amount, at)))
    by_cell: dict[str, PlannedCell] = {}
    for _, cell in sorted(found, key=lambda pair: pair[0]):
        by_cell.pop(cell.at.key, None)
        by_cell[cell.at.key] = cell
    return tuple(by_cell.values())[:MAX_CELLS]


def _decimal(cell: Mapping[str, object] | None) -> Decimal | None:
    if not cell or cell.get("v") is None:
        return None
    try:
        return Decimal(str(cell["v"]))
    except InvalidOperation:
        return None


def new_value(planned: PlannedCell, current: Decimal | None) -> Decimal:
    if planned.op == "set":
        return planned.amount
    base = current or Decimal(0)
    return base + planned.amount if planned.op == "add" else base - planned.amount


def _typed(value: Decimal | None) -> dict[str, object]:
    return {"t": "decimal", "v": None if value is None else format(value, "f")}


def label_of(form: str, at: Address) -> str:
    titles = dict(sheets_of(form))
    title = titles.get(at.sheet)
    return f"{at.sheet} {title}!{at.a1}" if title else at.key


@dataclass(frozen=True)
class FixResult:
    outcome: str  # proposed · nothing_to_propose · refused
    proposal_id: UUID | None = None
    rows: int = 0
    code: str | None = None


_FORM_OF: Final = text("SELECT form FROM tax_returns WHERE work_item_id = :r")


async def workbook_form(tenant: TenantContext, return_id: UUID) -> str | None:
    """The return's form when it has a workbook (an entity return), else None."""
    async with tenant_session(tenant) as session:
        form = await session.scalar(_FORM_OF, {"r": return_id})
    if form is None or not sheets_of(str(form)):
        return None
    return str(form)


# --- 1. propose (the fix run, as the agent) ------------------------------------------------------


async def fix(agent: object, issue_id: UUID, return_id: UUID, form: str) -> FixResult:
    """The run's step for an entity return (module docstring, 1). `agent` is the run's
    `AgentContext` (typed loosely: identity is imported lazily, like the tax fix runner)."""
    from abacus.modules.agents.api import ProposedRow, create_proposal
    from abacus.modules.identity.api import AgentContext
    from abacus.modules.review.api import current_values, fix_instructions_of, record_fix_proposal

    if not isinstance(agent, AgentContext):
        raise TypeError("the fix runs as the agent")
    instructions = await fix_instructions_of(agent, issue_id)
    if not instructions:
        return FixResult("nothing_to_propose", code="no_instructions")
    if agent.engagement_id is None:
        return FixResult("refused", code="no_engagement")
    planned = parse_instructions(instructions, form)
    if not planned:
        return FixResult("nothing_to_propose", code="no_cell_named")
    values = await current_values(agent.tenant, WORKBOOK, return_id)
    rows: list[ProposedRow] = []
    for cell in planned:
        before = _decimal(values.get(cell.at.key))
        after = new_value(cell, before)
        if before == after:
            continue
        rows.append(
            ProposedRow(
                target_type=WORKBOOK,
                target_id=return_id,
                field_key=cell.at.key,
                label=label_of(form, cell.at),
                before=None if before is None else _typed(before),
                after=_typed(after),
                cause=CAUSE,
            )
        )
    if not rows:
        return FixResult("nothing_to_propose", code="no_change")
    first = planned[0].at
    proposal_id = await create_proposal(
        agent,
        engagement_id=agent.engagement_id,
        kind=KIND,
        title=f"Fix {label_of(form, first)}"
        + (f" and {len(rows) - 1} more" if len(rows) > 1 else ""),
        rows=rows,
        set_ref={"issue_id": str(issue_id), "return_id": str(return_id)},
    )
    await record_fix_proposal(agent, issue_id, proposal_id)
    return FixResult("proposed", proposal_id=proposal_id, rows=len(rows))


# --- 2. approve (the adapter, after the decision commits) ----------------------------------------


def rerun_groups(cells: Sequence[str]) -> tuple[str, ...]:
    """The groups owning the fixed sheets, in plan order (their dependants run with them)."""
    from abacus.modules.tax.entity_run_plan import GROUPS

    wanted = {
        SHEET_GROUPS[c.split("!", 1)[0]] for c in cells if c.split("!", 1)[0] in SHEET_GROUPS
    }
    return tuple(g for g in GROUPS if g in wanted)


def recompute(
    form: str, values: Mapping[str, Mapping[str, object]], fixed: Mapping[str, Decimal | None]
) -> dict[str, Decimal | None]:
    """The fixed cells' dependents, recomputed in code as T-05-T35's edit does (bounded); a fan
    out over `MAX_RECOMPUTE` or a formula error recomputes nothing here: the re-run does."""
    from abacus.kernel.errors import DomainInvalid
    from abacus.modules.tax.cell_edit import apply_edit, book_of

    book = book_of(form, values)
    out: dict[str, Decimal | None] = {}
    for key, value in fixed.items():
        try:
            figures, touched = apply_edit(book, address(key), value, None)
        except DomainInvalid:
            return {}
        out.update({k: figures[k] for k in touched})
    for key in fixed:
        out.pop(key, None)
    return out


async def apply_fix(tenant: TenantContext, proposal_id: UUID) -> None:
    """An approved `workbook_cell_changes` proposal (module docstring, 2)."""
    from abacus.modules.agents.api import approved_proposal_rows, proposal_approver
    from abacus.modules.engagements.api import function_holders
    from abacus.modules.identity.api import display_names, member_context
    from abacus.modules.tax.entity_decisions import WorkbookFixApplied

    async with tenant_session(tenant) as session:
        found = await approved_proposal_rows(session, proposal_id)
        approver = await proposal_approver(session, proposal_id)
    if found is None or approver is None:
        return
    engagement_id, rows = found
    if engagement_id is None:
        return
    fixed: dict[str, Decimal | None] = {}
    return_id: UUID | None = None
    for row in rows:
        ref = row.field_ref
        if ref.get("target_type") != WORKBOOK or row.after is None:
            continue
        target = UUID(str(ref["target_id"]))
        if return_id is not None and target != return_id:
            continue  # one return per fix
        return_id = target
        fixed[str(ref["field_key"])] = _decimal(row.after)
    if return_id is None or not fixed:
        return
    system = TenantContext(tenant.tenant_id, "system", f"proposal:{proposal_id}")
    form = await workbook_form(system, return_id)
    if form is None:
        return
    from abacus.modules.review.api import current_values

    names = await display_names([approver])
    person_name = names.get(approver, "A person")
    note = f"Fix approved by {person_name}"
    values = await current_values(system, WORKBOOK, return_id)
    dependents = recompute(form, values, fixed)
    writes = [
        CellWrite(key, value, "human", citation_note=note) for key, value in fixed.items()
    ] + [
        CellWrite(key, value, "formula", formula=str(values[f"{key}:f"]["v"]))
        for key, value in dependents.items()
        if values.get(f"{key}:f", {}).get("v")
    ]
    async with uow(system) as tx:
        await write_cells(
            tx,
            engagement_id=engagement_id,
            return_id=return_id,
            writes=writes,
            on_behalf_of_user_id=approver,
        )
        tx.emit(
            WorkbookFixApplied(
                work_item_id=return_id,
                engagement_id=engagement_id,
                cells=len(fixed),
                by_user=approver,
                recipient_user_ids=sorted(
                    {u for users in (await function_holders(system, return_id)).values()
                     for u in users}
                ),
            )
        )  # fmt: skip
        tx.record(
            "workbook.fix_applied",
            target=Target(WORKBOOK, return_id),
            after=Ref(proposal=str(proposal_id), cells=len(fixed), recomputed=len(dependents)),
            scope=Scope(engagement_id=engagement_id),
        )
    person = await member_context(tenant.tenant_id, approver)
    if person is None:  # the approver left the firm since: the values stand, no re-run
        return
    await _checkpoint_and_rerun(person, engagement_id, return_id, note, tuple(fixed))


async def _checkpoint_and_rerun(
    person: object, engagement_id: UUID, return_id: UUID, name: str, cells: tuple[str, ...]
) -> UUID | None:
    """The approver's checkpoint, then the group re-run (skipped while a run is open: the open
    run's terminal state runs the tie-outs anyway)."""
    from abacus.modules.agents.api import PlanRequest, start_engagement_run, work_item_runs
    from abacus.modules.identity.api import AuthContext
    from abacus.modules.review.api import save_checkpoint
    from abacus.modules.tax.entity_run_plan import PROVIDER

    if not isinstance(person, AuthContext):
        raise TypeError("the re-run starts as a person")
    with contextlib.suppress(Exception):  # a refused checkpoint never undoes the approved values
        await save_checkpoint(person, WORKBOOK, return_id, name)
    groups = rerun_groups(cells)
    ref = f"tax_return:{return_id}"
    if not groups or any(r.active for r in await work_item_runs(person.tenant, ref, 5)):
        return None
    started = await start_engagement_run(
        person,
        engagement_id,
        work_item_ref=ref,
        provider=PROVIDER,
        request=PlanRequest(return_id, "group", groups),
    )
    return started.run_id


def register() -> None:
    """At the tax api's import: the workbook as a suggestion target and the kind's adapter."""
    from abacus.modules.agents.api import register_proposal_adapter, register_suggestion_target
    from abacus.modules.engagements.api import work_item_engagement

    register_suggestion_target(WORKBOOK, engagement_of=work_item_engagement)
    register_proposal_adapter(KIND, apply_fix)


__all__ = [
    "CAUSE",
    "KIND",
    "SHEET_GROUPS",
    "FixResult",
    "PlannedCell",
    "apply_fix",
    "fix",
    "label_of",
    "new_value",
    "parse_instructions",
    "recompute",
    "register",
    "rerun_groups",
    "workbook_form",
]
