"""The close tools on C17 (C-01-T28; C-01 §5; ADR-233, ADR-049, ADR-050).

Declared as `ToolDecl` records and registered by `agents` (`agents.tools.catalogue`); every
description is a registry prompt (`tool.close.<name>@v1`). The run's close is named by the
model and checked: the close must sit on the run's engagement, or the tool reads 404.

- `close.read_checklist` (read): the close's pinned plan rows (account, procedure, method).
- `close.reconcile` (compute): one account's bank reconciliation by code.
- `close.read_upload_table` (compute): an uploaded table's row count and numeric column totals.
- `close.read_register` (read): the close month's register for one account (200 rows a page).
- `close.propose_aje` (propose): a suggestion of the AJE that clears one item; never an entry.
- `close.plan_history_profile` (compute): each account's last closes (tied, off, carried).

Code computes every figure (ADR-050): the AJE's amount and debit account come from the item and
its reconciliation, its threshold class from the firm's rules for bank adjustments (none is
within threshold, BH AJE thresholds v2), and the model chooses only the credit account from the
vendor's prior categorisations offered. Client text (payees, memos, cell text, account names) is
untrusted and declared so. `records_read` counts what each read touched.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.agent_tools import MAX_ROWS, ToolCaller, ToolDecl
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.closes import repository as repo
from abacus.modules.closes.compute import reconciliation as rec
from abacus.modules.identity.api import AgentContext

Int = classified("internal")
Conf = classified("confidential")
READ: Final = "close.read"
SUGGEST: Final = "suggestion.create"
AJE_TARGET: Final = "reconciling_item"
AJE_FIELD: Final = "aje_draft"
CENT: Final = Decimal("0.01")
ZERO: Final = Decimal("0.00")


def _cfg() -> ConfigDict:
    return ConfigDict(extra="forbid", frozen=True)


async def _close(caller: ToolCaller, close_id: UUID) -> repo.CloseRow:
    """The close, when it sits on the run's engagement (any other reads 404, INV-3)."""
    async with tenant_session(caller.tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None or close.engagement_id != caller.engagement_id:
        raise NotFound("close")
    return close


# --- close.read_checklist ------------------------------------------------------------------------


class CloseIn(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]


class ChecklistRow(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Int]
    position: Annotated[int, Int]
    account_external_id: Annotated[str | None, Int] = None
    account_name: Annotated[str, Conf]
    procedure: Annotated[str, Int]
    method: Annotated[str, Conf]
    source: Annotated[str, Int]
    review_level: Annotated[str, Int]


class ChecklistOut(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]
    period: Annotated[str, Int]
    plan_version_id: Annotated[UUID | None, Int] = None
    rows: Annotated[list[ChecklistRow], Field(max_length=MAX_ROWS), Int]


_ROWS: Final = text(
    "SELECT id, position, account_external_id, account_name, procedure, method, source, "
    "review_level FROM close_plan_rows WHERE version_id = :v ORDER BY position LIMIT 200"
)


async def read_checklist(caller: ToolCaller, args: CloseIn) -> ChecklistOut:
    close = await _close(caller, args.close_id)
    rows: list[ChecklistRow] = []
    if close.close_plan_version_id is not None:
        async with tenant_session(caller.tenant) as session:
            found = (await session.execute(_ROWS, {"v": close.close_plan_version_id})).mappings()
            rows = [ChecklistRow.model_validate(dict(r)) for r in found]
    return ChecklistOut(
        close_id=close.work_item_id,
        period=close.period,
        plan_version_id=close.close_plan_version_id,
        rows=rows,
    )


# --- close.reconcile -----------------------------------------------------------------------------


class ReconcileIn(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]
    account_external_id: Annotated[str, Field(min_length=1, max_length=64), Int]
    statement_evidence_version_id: Annotated[UUID | None, Int] = None


class ReconcilingItemRow(BaseModel):
    model_config = _cfg()

    id: Annotated[str, Int]  # the statement line or register line it comes from
    side: Annotated[Literal["bank", "book"], Int]
    kind: Annotated[str, Int]
    txn_date: Annotated[date, Int]
    amount: Annotated[Decimal, Conf]
    days_at_period_end: Annotated[int, Int]
    stale: Annotated[bool, Int]
    ref: Annotated[str | None, Conf] = None


class ReconcileOut(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]
    account_external_id: Annotated[str, Int]
    balance_per_bank: Annotated[Decimal | None, Conf] = None
    adjusted_bank: Annotated[Decimal | None, Conf] = None
    book_balance: Annotated[Decimal, Conf]
    adjusted_book: Annotated[Decimal, Conf]
    difference: Annotated[Decimal | None, Conf] = None
    tally: Annotated[Literal["pending", "tie", "off"], Int]
    items: Annotated[list[ReconcilingItemRow], Field(max_length=MAX_ROWS), Int]
    needs_review: Annotated[list[str], Int]
    engine_version: Annotated[str, Int]
    inputs_hash: Annotated[str, Int]


_STATEMENT: Final = text(
    "SELECT id, page_no, bbox, txn_date, description, withdrawal, deposit, running_balance, "
    "confidence FROM statement_lines WHERE evidence_version_id = :v "
    "ORDER BY txn_date, page_no, id LIMIT 2000"
)
_LAST_STATEMENT: Final = text(
    "SELECT statement_evidence_version_id FROM reconciliations WHERE close_id = :c "
    "AND account_external_id = :a AND statement_evidence_version_id IS NOT NULL "
    "ORDER BY version DESC LIMIT 1"
)
_PRIOR_ITEMS: Final = text(
    "SELECT i.id, i.side, i.kind, i.txn_date, i.amount, i.ref, i.register_line_ref "
    "FROM reconciling_items i JOIN reconciliations r ON r.id = i.reconciliation_id "
    "JOIN closes c ON c.work_item_id = r.close_id WHERE c.client_entity_id = :e "
    "AND c.period = :p AND r.account_external_id = :a AND r.version = ("
    "SELECT max(version) FROM reconciliations r2 WHERE r2.close_id = r.close_id "
    "AND r2.account_external_id = r.account_external_id) "
    "AND NOT EXISTS (SELECT 1 FROM reconciling_item_resolutions s WHERE s.item_id = i.id "
    "AND s.resolution = 'cleared')"
)


def _prior_period(period: str) -> str:
    year, month = int(period[:4]), int(period[5:])
    return f"{year - 1:04d}-12" if month == 1 else f"{year:04d}-{month - 1:02d}"


def _period_end(period: str) -> date:
    year, month = int(period[:4]), int(period[5:])
    following = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return date.fromordinal(following.toordinal() - 1)


async def _register_all(
    caller: ToolCaller, entity: UUID, account: str, period: str
) -> list[rec.RegisterLine]:
    from abacus.modules.ledger.api import register_lines

    out: list[rec.RegisterLine] = []
    cursor: str | None = None
    for _ in range(20):  # 4,000 rows at most: a bank register's month
        rows, cursor = await register_lines(caller.tenant, entity, account, period, cursor=cursor)
        out.extend(
            rec.RegisterLine(
                ref=r.line_ref, txn_date=r.txn_date, amount=r.amount, payee=r.payee, number=None
            )
            for r in rows
        )
        if cursor is None:
            break
    return out


async def reconcile(caller: ToolCaller, args: ReconcileIn) -> ReconcileOut:
    """The reconciliation by code; the statement is the one named, or the account's latest."""
    close = await _close(caller, args.close_id)
    if close.client_entity_id is None:
        raise NotFound("close")
    from abacus.modules.ledger.api import PeriodNotAvailable, account_tree

    try:
        month = await account_tree(caller.tenant, close.client_entity_id, close.period)
    except PeriodNotAvailable:
        raise NotFound("ledger_month") from None
    book = next(
        (b.balance for b in month.balances if b.external_id == args.account_external_id), None
    )
    if book is None:
        raise NotFound("account")
    async with tenant_session(caller.tenant) as session:
        version = args.statement_evidence_version_id or await session.scalar(
            _LAST_STATEMENT, {"c": close.work_item_id, "a": args.account_external_id}
        )
        statement = (
            []
            if version is None
            else list((await session.execute(_STATEMENT, {"v": version})).mappings())
        )
        prior = list(
            (
                await session.execute(
                    _PRIOR_ITEMS,
                    {
                        "e": close.client_entity_id,
                        "p": _prior_period(close.period),
                        "a": args.account_external_id,
                    },
                )
            ).mappings()
        )
    lines = tuple(
        rec.StatementLine(
            id=str(s["id"]),
            txn_date=s["txn_date"],
            description=str(s["description"]),
            withdrawal=s["withdrawal"],
            deposit=s["deposit"],
            page_no=int(s["page_no"]),
            confidence=Decimal(str(s["confidence"])),
        )
        for s in statement
    )
    balances = [s["running_balance"] for s in statement if s["running_balance"] is not None]
    bank = cast("Decimal | None", balances[-1]) if balances else None
    result = rec.reconcile(
        rec.Inputs(
            period_end=_period_end(close.period),
            book_balance=book,
            balance_per_bank=bank,
            statement_lines=lines,
            register_lines=tuple(
                await _register_all(
                    caller, close.client_entity_id, args.account_external_id, close.period
                )
            ),
            prior_items=tuple(
                rec.PriorItem(
                    id=str(p["id"]),
                    side=p["side"],
                    kind=p["kind"],
                    txn_date=p["txn_date"],
                    amount=Decimal(p["amount"]),
                    ref=p["ref"],
                    register_line_ref=p["register_line_ref"],
                )
                for p in prior
            ),
        )
    )
    return ReconcileOut(
        close_id=close.work_item_id,
        account_external_id=args.account_external_id,
        balance_per_bank=result.balance_per_bank,
        adjusted_bank=result.adjusted_bank,
        book_balance=result.book_balance,
        adjusted_book=result.adjusted_book,
        difference=result.difference,
        tally=result.tally,
        items=[
            ReconcilingItemRow(
                id=i.statement_line_id or i.register_line_ref or i.carried_from or "-",
                side=i.side,
                kind=i.kind,
                txn_date=i.txn_date,
                amount=i.amount,
                days_at_period_end=i.days_at_period_end,
                stale=i.stale,
                ref=i.ref,
            )
            for i in result.items[:MAX_ROWS]
        ],
        needs_review=list(result.needs_review),
        engine_version=result.engine_version,
        inputs_hash=result.inputs_hash,
    )


# --- close.read_upload_table ---------------------------------------------------------------------


class UploadTableIn(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]
    evidence_version_id: Annotated[UUID, Int]
    table_index: Annotated[int, Field(ge=0, le=99), Int] = 0
    header_row: Annotated[int, Field(ge=0, le=20), Int] = 0


class ColumnTotal(BaseModel):
    model_config = _cfg()

    column: Annotated[int, Int]
    header: Annotated[str, Conf]
    numeric_rows: Annotated[int, Int]
    total: Annotated[Decimal, Conf]


class UploadTableOut(BaseModel):
    model_config = _cfg()

    id: Annotated[UUID, Int]  # the extracted table
    page: Annotated[int, Int]
    rows: Annotated[int, Int]
    columns: Annotated[list[ColumnTotal], Field(max_length=MAX_ROWS), Int]


def _number(raw: str) -> Decimal | None:
    value = raw.strip().replace("$", "").replace(",", "").replace(" ", "")
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    if not value or not all(c.isdigit() or c in ".-" for c in value):
        return None
    try:
        number = Decimal(value).quantize(CENT)
    except InvalidOperation:
        return None
    return -number if negative else number


async def read_upload_table(caller: ToolCaller, args: UploadTableIn) -> UploadTableOut:
    """Totals by code of an uploaded table's numeric columns (cell text is never returned)."""
    await _close(caller, args.close_id)
    from abacus.modules.evidence.api import extracted_tables

    tables = await extracted_tables(caller, args.evidence_version_id, None)  # type: ignore[arg-type] -- the agent context is the caller
    if args.table_index >= len(tables):
        raise NotFound("extracted_table")
    table = tables[args.table_index]
    header = table.rows[args.header_row] if len(table.rows) > args.header_row else ()
    body = table.rows[args.header_row + 1 :]
    width = max((len(r) for r in table.rows), default=0)
    columns: list[ColumnTotal] = []
    for col in range(min(width, MAX_ROWS)):
        values = [_number(r[col].text) for r in body if col < len(r)]
        numbers = [v for v in values if v is not None]
        if not numbers:
            continue
        columns.append(
            ColumnTotal(
                column=col,
                header=(header[col].text[:80] if col < len(header) else ""),
                numeric_rows=len(numbers),
                total=sum(numbers, ZERO).quantize(CENT),
            )
        )
    return UploadTableOut(id=table.table_id, page=table.page, rows=len(body), columns=columns)


# --- close.read_register -------------------------------------------------------------------------


class RegisterIn(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]
    account_external_id: Annotated[str, Field(min_length=1, max_length=64), Int]
    cursor: Annotated[str | None, Field(max_length=20), Int] = None


class RegisterRow(BaseModel):
    model_config = _cfg()

    id: Annotated[str, Int]
    txn_date: Annotated[date, Int]
    txn_type: Annotated[str | None, Conf] = None
    payee: Annotated[str | None, Conf] = None
    memo: Annotated[str | None, Conf] = None
    category: Annotated[str | None, Int] = None
    amount: Annotated[Decimal, Conf]


class RegisterOut(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]
    account_external_id: Annotated[str, Int]
    lines: Annotated[list[RegisterRow], Field(max_length=200), Int]
    next_cursor: Annotated[str | None, Int] = None


async def read_register(caller: ToolCaller, args: RegisterIn) -> RegisterOut:
    close = await _close(caller, args.close_id)
    if close.client_entity_id is None:
        raise NotFound("close")
    from abacus.modules.ledger.api import register_lines

    rows, following = await register_lines(
        caller.tenant,
        close.client_entity_id,
        args.account_external_id,
        close.period,
        cursor=args.cursor,
    )
    return RegisterOut(
        close_id=close.work_item_id,
        account_external_id=args.account_external_id,
        lines=[
            RegisterRow(
                id=r.line_ref,
                txn_date=r.txn_date,
                txn_type=r.txn_type,
                payee=r.payee,
                memo=r.memo,
                category=r.offset_account_ref,
                amount=r.amount,
            )
            for r in rows
        ],
        next_cursor=following,
    )


# --- close.propose_aje ---------------------------------------------------------------------------


class ProposeAjeIn(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]
    reconciling_item_id: Annotated[UUID, Int]
    credit_account_ref: Annotated[str, Field(min_length=1, max_length=64), Int]
    rationale_ref: Annotated[str | None, Field(max_length=120), Int] = None

    def tool_targets(self, agent: AgentContext) -> object:
        """The run's engagement: the handler checks the close and its item sit on it."""
        from abacus.modules.agents.api import ToolTargets  # agents imports closes' tools

        return ToolTargets((agent.engagement_id,) if agent.engagement_id is not None else ())


class AjeLine(BaseModel):
    model_config = _cfg()

    account_ref: Annotated[str, Int]
    debit: Annotated[Decimal, Conf]
    credit: Annotated[Decimal, Conf]


class ProposeAjeOut(BaseModel):
    model_config = _cfg()

    suggestion_id: Annotated[UUID, Int]
    lines: Annotated[list[AjeLine], Int]
    amount: Annotated[Decimal, Conf]
    threshold_class: Annotated[Literal["within_threshold", "review_required"], Int]


_ITEM: Final = text(
    "SELECT i.id, i.kind, i.amount, r.account_external_id, r.close_id FROM reconciling_items i "
    "JOIN reconciliations r ON r.id = i.reconciliation_id WHERE i.id = :i"
)


def aje_lines(kind: str, bank_account: str, credit_account: str, amount: Decimal) -> list[AjeLine]:
    """The entry that clears a book-side item: an unrecorded deposit debits the bank, an
    unrecorded withdrawal credits it; the other side is the category chosen."""
    value = Decimal(amount).quantize(CENT)
    if kind == "unrecorded_deposit":
        return [AjeLine(account_ref=bank_account, debit=value, credit=ZERO),
                AjeLine(account_ref=credit_account, debit=ZERO, credit=value)]  # fmt: skip
    if kind == "unrecorded_withdrawal":
        return [AjeLine(account_ref=credit_account, debit=value, credit=ZERO),
                AjeLine(account_ref=bank_account, debit=ZERO, credit=value)]  # fmt: skip
    raise NotFound("reconciling_item")  # a bank-side item is not cleared by an entry


async def propose_aje(caller: ToolCaller, args: ProposeAjeIn) -> ProposeAjeOut:
    """A suggestion of the AJE (C-31 Adopt); a person proposes the entry (INV-1)."""
    close = await _close(caller, args.close_id)
    async with tenant_session(caller.tenant) as session:
        item = (await session.execute(_ITEM, {"i": args.reconciling_item_id})).mappings().first()
    if item is None or item["close_id"] != close.work_item_id:
        raise NotFound("reconciling_item")
    if args.credit_account_ref == item["account_external_id"]:
        raise NotFound("reconciling_item")
    lines = aje_lines(
        str(item["kind"]),
        str(item["account_external_id"]),
        args.credit_account_ref,
        item["amount"],
    )
    from abacus.modules.agents.api import create_suggestion

    suggestion = await create_suggestion(
        caller,  # type: ignore[arg-type] -- the agent context is the actor
        engagement_id=close.engagement_id,
        target_type=AJE_TARGET,
        target_id=args.reconciling_item_id,
        field_key=AJE_FIELD,
        proposed_value={
            "t": "json",
            "v": {
                "lines": [
                    {
                        "account_ref": ln.account_ref,
                        "debit": str(ln.debit),
                        "credit": str(ln.credit),
                    }
                    for ln in lines
                ]
            },
        },
        rationale_ref=args.rationale_ref,
    )
    return ProposeAjeOut(
        suggestion_id=suggestion,
        lines=lines,
        amount=Decimal(item["amount"]).quantize(CENT),
        # Bank adjustments have no within-threshold class under the firm's AJE thresholds (US-7.3).
        threshold_class="review_required",
    )


# --- close.plan_history_profile ------------------------------------------------------------------


class HistoryIn(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]
    months: Annotated[int, Field(ge=1, le=12), Int] = 6


class AccountHistory(BaseModel):
    model_config = _cfg()

    account_external_id: Annotated[str, Int]
    closes_seen: Annotated[int, Int]
    tied: Annotated[int, Int]
    off: Annotated[int, Int]
    items_carried: Annotated[int, Int]
    stale_items: Annotated[int, Int]


class HistoryOut(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Int]
    periods: Annotated[list[str], Int]
    accounts: Annotated[list[AccountHistory], Field(max_length=MAX_ROWS), Int]


_HISTORY: Final = text(
    "SELECT r.account_external_id, c.period, r.tally, "
    "(SELECT count(*) FROM reconciling_items i WHERE i.reconciliation_id = r.id) AS items, "
    "(SELECT count(*) FROM reconciling_items i WHERE i.reconciliation_id = r.id AND i.stale) "
    "AS stale FROM reconciliations r JOIN closes c ON c.work_item_id = r.close_id "
    "WHERE c.client_entity_id = :e AND c.period = ANY(:periods) AND r.version = ("
    "SELECT max(version) FROM reconciliations r2 WHERE r2.close_id = r.close_id "
    "AND r2.account_external_id = r.account_external_id)"
)


async def plan_history_profile(caller: ToolCaller, args: HistoryIn) -> HistoryOut:
    """Counts by code over the entity's previous closes (the Close Planner's profile)."""
    close = await _close(caller, args.close_id)
    periods: list[str] = []
    period = close.period
    for _ in range(args.months):
        period = _prior_period(period)
        periods.append(period)
    async with tenant_session(caller.tenant) as session:
        rows = list(
            (
                await session.execute(_HISTORY, {"e": close.client_entity_id, "periods": periods})
            ).mappings()
        )
    by_account: dict[str, AccountHistory] = {}
    for r in rows:
        account = str(r["account_external_id"])
        seen = by_account.get(account) or AccountHistory(
            account_external_id=account,
            closes_seen=0,
            tied=0,
            off=0,
            items_carried=0,
            stale_items=0,
        )
        by_account[account] = seen.model_copy(
            update={
                "closes_seen": seen.closes_seen + 1,
                "tied": seen.tied + int(r["tally"] == "tie"),
                "off": seen.off + int(r["tally"] == "off"),
                "items_carried": seen.items_carried + int(r["items"]),
                "stale_items": seen.stale_items + int(r["stale"]),
            }
        )
    return HistoryOut(
        close_id=close.work_item_id,
        periods=periods,
        accounts=[by_account[k] for k in sorted(by_account)][:MAX_ROWS],
    )


AGENT_TOOLS: Final = (
    ToolDecl("close.read_checklist", "read", READ, "confidential", CloseIn, ChecklistOut,
             read_checklist, untrusted=("rows",), records_read="close_plan_row"),
    ToolDecl("close.reconcile", "compute", READ, "confidential", ReconcileIn, ReconcileOut,
             reconcile, untrusted=("items",), records_read="statement_line"),
    ToolDecl("close.read_upload_table", "compute", READ, "confidential", UploadTableIn,
             UploadTableOut, read_upload_table, untrusted=("columns",),
             records_read="extracted_table"),
    ToolDecl("close.read_register", "read", READ, "confidential", RegisterIn, RegisterOut,
             read_register, untrusted=("lines",), records_read="gl_entry"),
    ToolDecl("close.propose_aje", "propose", SUGGEST, "confidential", ProposeAjeIn,
             ProposeAjeOut, propose_aje),
    ToolDecl("close.plan_history_profile", "compute", READ, "confidential", HistoryIn,
             HistoryOut, plan_history_profile, records_read="reconciliation"),
)  # fmt: skip
