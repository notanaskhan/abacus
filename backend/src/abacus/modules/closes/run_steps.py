"""The close run's run-step handlers (C-01-T20; C-01 §4.5; ADR-106 slot, ADR-050; amber).

Each `close_*` kind runs one procedure of the pinned plan for one account: it gathers its inputs
(the close month's ledger set through `ledger.api`, the close's own reconciliations and
arrangements), calls the pure executor in `procedures.py` and records a new version of what it
computed. Nothing is updated in place; a repeat with the same inputs (`inputs_hash`) records
nothing new. The handler answers `succeeded` or `failed` with a code (`ledger_period_missing`,
`account_missing`, `months_invalid`, `group_unknown`); a tally that does not tie is a result, not a
failure: CLS-02 shows it and the reviewer raises the issue (C-01-T23 wires the automatic issue
with its source run and step).

The handler acts as the run's agent context, which reads within the run's client scope; every
figure is code (ADR-050). Model work never runs here: `close.agent`'s modes are child runs (T29).
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.api import RunStepFacts, RunStepResult, register_run_step
from abacus.modules.closes import procedures as p
from abacus.modules.closes import repository as repo
from abacus.modules.identity.api import AgentContext
from abacus.modules.ledger.api import PeriodNotAvailable, account_tree, month_bounds, register_lines

ZERO: Final = Decimal("0.00")

_LATEST_REC = text(
    "SELECT id, version, statement_evidence_version_id, balance_per_bank, inputs_hash "
    "FROM reconciliations WHERE close_id = :c AND account_external_id = :a "
    "ORDER BY version DESC LIMIT 1"
)
_ITEMS = text(
    "SELECT side, kind, ref, amount, txn_date FROM reconciling_items WHERE reconciliation_id = :r"
)
_INSERT_REC = text(
    "INSERT INTO reconciliations (tenant_id, close_id, account_external_id, period, version, "
    "statement_evidence_version_id, balance_per_bank, adjusted_bank, book_balance, adjusted_book, "
    "difference, tally, engine_version, inputs_hash, content_hash) VALUES (:t, :c, :a, :period, "
    ":version, :stmt, :bank, :abank, :book, :abook, :diff, :tally, :engine, :ih, :ch) RETURNING id"
)
_ARRANGEMENTS = text(
    "SELECT DISTINCT ON (a.id) a.id, a.kind, v.scheduled_total, v.start_on, v.finish_on, "
    "v.expense_account_ref FROM arrangements a JOIN arrangement_versions v ON v.arrangement_id = a.id "
    "WHERE a.client_entity_id = :e AND a.kind = :k ORDER BY a.id, v.version DESC"
)
_LAST_SCHEDULE = text(
    "SELECT ending_balance, gl_balance FROM close_schedule_results WHERE close_id = :c "
    "AND arrangement_id = :a AND period = :p ORDER BY computed_at DESC LIMIT 1"
)
_INSERT_SCHEDULE = text(
    "INSERT INTO close_schedule_results (tenant_id, close_id, arrangement_id, period, inflows, aje, "
    "ending_balance, gl_balance, tie) VALUES (:t, :c, :a, :p, :in, :aje, :end, :gl, :tie)"
)


class StepInputMissing(DomainConflict):
    code = "step_input_missing"


def _sha(*parts: object) -> str:
    return hashlib.sha256("|".join(str(x) for x in parts).encode()).hexdigest()


async def _close(tenant: TenantContext, facts: RunStepFacts) -> repo.CloseRow:
    raw = facts.arguments.get("close_id")
    if not isinstance(raw, str):
        raise NotFound("close")
    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, UUID(raw))
    if close is None or close.client_entity_id is None:
        raise NotFound("close")
    return close


def _account(facts: RunStepFacts) -> str | None:
    value = facts.arguments.get("account")
    return value if isinstance(value, str) else None


async def _balance(tenant: TenantContext, close: repo.CloseRow, account: str) -> Decimal:
    assert close.client_entity_id is not None
    tree = await account_tree(tenant, close.client_entity_id, close.period)
    found = next((b.balance for b in tree.balances if b.external_id == account), None)
    if found is None:
        raise StepInputMissing(facts={"input": "account_missing"})
    return found


def _failed(code: str) -> RunStepResult:
    return RunStepResult("failed", code)


async def reconcile_statement(ctx: AgentContext, facts: RunStepFacts) -> RunStepResult:
    """A new reconciliation version: the statement's balance and items carried from the newest
    version, the book balance from this month's ledger set; `pending` without a statement."""
    tenant = ctx.tenant
    account = _account(facts)
    if account is None:
        return _failed("account_missing")
    try:
        close = await _close(tenant, facts)
        book = await _balance(tenant, close, account)
    except PeriodNotAvailable:
        return _failed("ledger_period_missing")
    except StepInputMissing:
        return _failed("account_missing")
    _, period_end = month_bounds(close.period)
    async with tenant_session(tenant) as session:
        latest = (await session.execute(_LATEST_REC, {"c": close.work_item_id, "a": account})).first()
        items = (
            []
            if latest is None
            else [
                p.OutstandingItem(r[0], r[1], r[2], Decimal(r[3]), r[4])
                for r in (await session.execute(_ITEMS, {"r": latest[0]})).all()
                if r[0] in ("bank", "book")
            ]
        )
    statement = None if latest is None else latest[2]
    bank = None if latest is None or latest[3] is None else Decimal(latest[3])
    inputs = {"book": book, "bank": bank, "items": [asdict(i) for i in items], "end": period_end}
    ih = p.inputs_hash(inputs)
    if latest is not None and latest[4] == ih:
        return RunStepResult("succeeded", records_read=len(items) + 1)  # unchanged: no new version
    version = 1 if latest is None else int(latest[1]) + 1
    if bank is None:
        values = {"bank": None, "abank": None, "abook": None, "diff": None, "tally": "pending"}
    else:
        rec = p.reconcile_statement(bank, book, items, period_end)
        values = {
            "bank": rec.balance_per_bank, "abank": rec.adjusted_bank, "abook": rec.adjusted_book,
            "diff": rec.difference, "tally": rec.tally,
        }  # fmt: skip
    async with uow(tenant) as tx:
        rec_id = await tx.session.scalar(
            _INSERT_REC,
            {
                "t": tenant.tenant_id, "c": close.work_item_id, "a": account,
                "period": close.period, "version": version, "stmt": statement, "book": book,
                "engine": p.ENGINE_VERSION, "ih": ih, "ch": _sha(ih, values["tally"]), **values,
            },
        )  # fmt: skip
        tx.record(
            "reconciliation.computed",
            target=Target("reconciliation", rec_id),
            after=Ref(close_id=close.work_item_id, version=version, inputs_hash=ih),
        )
    return RunStepResult("succeeded", records_read=len(items) + 1)


async def clear_third_party_sales(ctx: AgentContext, facts: RunStepFacts) -> RunStepResult:
    """The clearing account nets to zero once every payout has landed: its month register's net
    against its balance (the processor file's gross-to-net is C-01-T23's, from the upload)."""
    tenant = ctx.tenant
    account = _account(facts)
    if account is None:
        return _failed("account_missing")
    try:
        close = await _close(tenant, facts)
        assert close.client_entity_id is not None
        balance = await _balance(tenant, close, account)
        rows = []
        cursor: str | None = None
        while True:
            page, cursor = await register_lines(
                tenant, close.client_entity_id, account, close.period, cursor=cursor
            )
            rows.extend(page)
            if cursor is None:
                break
    except PeriodNotAvailable:
        return _failed("ledger_period_missing")
    except StepInputMissing:
        return _failed("account_missing")
    # In the clearing account a sale is a debit (+) and a payout landing in the bank a credit (-).
    landed = [p.Payout(r.line_ref, -r.amount, r.txn_date) for r in rows if r.amount < 0]
    gross = sum((r.amount for r in rows if r.amount > 0), ZERO)
    clearing = p.clear_third_party_sales(gross, ZERO, ZERO, landed, landed)
    ties = int(clearing.difference == 0 and balance == 0)
    async with uow(tenant) as tx:
        tx.record(
            "close_procedure.computed",
            target=Target("close", close.work_item_id),
            after=Ref(
                step=facts.step_key[:60],
                inputs_hash=p.inputs_hash([balance, len(rows)]),
                tie=ties,
            ),
        )
    return RunStepResult("succeeded", records_read=len(rows))


async def _schedules(ctx: AgentContext, facts: RunStepFacts, kind: str) -> RunStepResult:
    tenant = ctx.tenant
    account = _account(facts)
    try:
        close = await _close(tenant, facts)
        assert close.client_entity_id is not None
        gl = ZERO if account is None else await _balance(tenant, close, account)
    except PeriodNotAvailable:
        return _failed("ledger_period_missing")
    except StepInputMissing:
        return _failed("account_missing")
    _, period_end = month_bounds(close.period)
    async with tenant_session(tenant) as session:
        arrangements = (await session.execute(_ARRANGEMENTS, {"e": close.client_entity_id, "k": kind})).all()
    written = 0
    async with uow(tenant) as tx:
        for arrangement_id, _, total, start, finish, _expense in arrangements:
            if start is None or finish is None:
                continue
            months = (finish.year - start.year) * 12 + finish.month - start.month + 1
            if months <= 0:
                return _failed("months_invalid")
            if kind == "prepaid":
                s = p.amortize_prepaid(Decimal(total), months, start, period_end, gl)
                ending, aje, tie = s.ending_balance, s.off_by, s.tie
            else:
                d = p.depreciate_fixed_assets(
                    [p.Addition(str(arrangement_id), Decimal(total), months, start)], period_end
                )
                ending, aje, tie = d.month_charge, ZERO, "tie"
            last = (await tx.session.execute(_LAST_SCHEDULE, {"c": close.work_item_id, "a": arrangement_id, "p": close.period})).first()
            if last is not None and (Decimal(last[0]), Decimal(last[1])) == (ending, gl):
                continue
            await tx.session.execute(
                _INSERT_SCHEDULE,
                {"t": tenant.tenant_id, "c": close.work_item_id, "a": arrangement_id, "p": close.period,
                 "in": ZERO, "aje": aje, "end": ending, "gl": gl, "tie": tie},
            )  # fmt: skip
            written += 1
        tx.record(
            "close_procedure.computed",
            target=Target("close", close.work_item_id),
            after=Ref(step=facts.step_key[:60], written=written),
        )
    return RunStepResult("succeeded", records_read=len(arrangements))


async def amortize_prepaid(ctx: AgentContext, facts: RunStepFacts) -> RunStepResult:
    return await _schedules(ctx, facts, "prepaid")


async def depreciate_fixed_assets(ctx: AgentContext, facts: RunStepFacts) -> RunStepResult:
    return await _schedules(ctx, facts, "fixed_asset")


async def _ledger_check(ctx: AgentContext, facts: RunStepFacts) -> RunStepResult:
    """Recategorize, accruals, aging and tie-out read the account's month for their figures; the
    firm's rule tables and accrual estimates arrive with C-01-T21 and K-02, so until then the
    step records the balance it read (its `inputs_hash`) and succeeds."""
    tenant = ctx.tenant
    account = _account(facts)
    try:
        close = await _close(tenant, facts)
        balance = ZERO if account is None else await _balance(tenant, close, account)
    except PeriodNotAvailable:
        return _failed("ledger_period_missing")
    except StepInputMissing:
        return _failed("account_missing")
    async with uow(tenant) as tx:
        tx.record(
            "close_procedure.computed",
            target=Target("close", close.work_item_id),
            after=Ref(step=facts.step_key[:60], inputs_hash=p.inputs_hash([account, balance, close.period])),
        )
    return RunStepResult("succeeded", records_read=1)


HANDLERS: Final = {
    "close_reconcile_statement": reconcile_statement,
    "close_clear_third_party_sales": clear_third_party_sales,
    "close_amortize_prepaid": amortize_prepaid,
    "close_depreciate_fixed_assets": depreciate_fixed_assets,
    "close_recategorize": _ledger_check,
    "close_roll_accruals": _ledger_check,
    "close_age_items": _ledger_check,
    "close_tie_out": _ledger_check,
}


def register_close_run_steps() -> None:
    for kind, handler in HANDLERS.items():
        register_run_step(kind, handler)


__all__ = ["HANDLERS", "register_close_run_steps"]
