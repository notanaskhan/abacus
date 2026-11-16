"""Accounts and schedules (C-01-T21; C-01 §3 F6; CLS-04 a to e; SPEC-655 AC-35 to AC-37; amber).

- **The tree** (`account_tree`): the close month's ledger (C9 v2.1, `ledger.account_tree`) as
  classification, then account type, then account; balances roll up in code (`compute.schedules
  .rollup`) and contra balances render in parentheses on the screen. Each account carries its
  reconciliation word: a bank account its newest reconciliation's tally, a scheduled account its
  schedule's tie. Zero balances hide unless asked.
- **The register** (`register`): the month's rows, 200 a page, each citable as a `ledger_line`.
- **Arrangements** (`create_arrangement`, `update_arrangement`): a prepaid, fixed asset, accrual or
  deferred revenue; every edit is a new version (insert-only), audited
  `arrangement.created/updated`; only a person edits (INV-1).
- **The workpaper** (`workpaper`): the schedule computed by code and tied to the GL: `tie`,
  `off`, `ties_once_posted` while the proposed entry that closes the difference is pending
  ("Ties once posted", AJE-02), or `recorded` once a sync found the entry recorded in QuickBooks
  (`close_entry_recordings`: "Recorded in QuickBooks · JE 48214"). A result is kept per
  (close, arrangement, period) when it changes (`close_schedule_results`). An `off` account raises
  one `close_exception` (class `schedule`, deduplicated by its source).
- **workpaper.xlsx** goes through `evidence.render_close_workpaper` (strings never formulas).
- **Recategorisation** (AC-36): a register row's new category is a reclass proposal (C8's
  `propose_entry`, kind `aje`, a person the proposer) reviewed on SHL-10; the transaction is never
  changed (CONN-001: closes writes nothing to QuickBooks).
- **The recording matcher** (`match_recordings`): an approved close entry is recorded when the
  month's register holds one journal entry (one QuickBooks transaction id) whose rows carry each
  of the entry's lines (account and amount); found once per snapshot, audited
  `close_entry.recorded_matched`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.adjustments.api import NewEntry, NewLine, entries_of, propose_entry
from abacus.modules.closes import repository as repo
from abacus.modules.closes.compute import schedules as calc
from abacus.modules.closes.contract_work import (
    AccountNodeOut,
    AccountTreeOut,
    ArrangementIn,
    ArrangementOut,
    CloseRegisterOut,
    CloseWorkpaperOut,
    EntryRecordingOut,
    ProposalRefOut,
    RecategorizationIn,
    RegisterLineOut,
    ScheduleLineOut,
    TallyWord,
)
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.ledger.api import PeriodNotAvailable
from abacus.modules.ledger.api import account_tree as ledger_tree
from abacus.modules.ledger.api import register_lines as ledger_register

ZERO: Final = Decimal("0.00")
EDIT: Final = "arrangement.edit"
_ORDER: Final = ("asset", "liability", "equity", "income", "expense")
_PENDING: Final = frozenset({"proposed", "within_threshold", "review_required"})
_RECORDED: Final = frozenset({"approved", "client_approved"})
_JOURNAL: Final = ("journal", "journalentry")


class ArrangementStale(DomainConflict):
    code = "stale_arrangement"


class NoLedgerMonth(DomainConflict):
    code = "period_not_synced"


@dataclass(frozen=True)
class _Version:
    arrangement_id: UUID
    client_entity_id: UUID
    account_external_id: str
    kind: calc.Kind
    version: int
    description: str
    expense_account_ref: str | None
    scheduled_total: Decimal
    starting_balance: Decimal
    frequency: calc.Frequency
    start_on: date
    finish_on: date
    source_citation_id: UUID | None


_LATEST: Final = text(
    "SELECT DISTINCT ON (a.id) a.id AS arrangement_id, a.client_entity_id, "
    "a.account_external_id, a.kind, v.version, v.description, v.expense_account_ref, "
    "v.scheduled_total, v.starting_balance, v.frequency, v.start_on, v.finish_on, "
    "v.source_citation_id FROM arrangements a JOIN arrangement_versions v "
    "ON v.arrangement_id = a.id WHERE a.client_entity_id = :e "
    "AND (CAST(:acct AS text) IS NULL OR a.account_external_id = CAST(:acct AS text)) "
    "ORDER BY a.id, v.version DESC"
)
_ONE: Final = text(
    "SELECT a.id AS arrangement_id, a.client_entity_id, a.account_external_id, a.kind, "
    "v.version, v.description, v.expense_account_ref, v.scheduled_total, v.starting_balance, "
    "v.frequency, v.start_on, v.finish_on, v.source_citation_id FROM arrangements a "
    "JOIN arrangement_versions v ON v.arrangement_id = a.id WHERE a.id = :a "
    "ORDER BY v.version DESC LIMIT 1"
)
_NEW: Final = text(
    "INSERT INTO arrangements (tenant_id, client_entity_id, account_external_id, kind, "
    "created_by) VALUES (:t, :e, :acct, :k, :u) RETURNING id"
)
_NEW_VERSION: Final = text(
    "INSERT INTO arrangement_versions (tenant_id, arrangement_id, version, description, "
    "expense_account_ref, scheduled_total, frequency, start_on, finish_on, source_citation_id, "
    "actor_id) VALUES (:t, :a, :n, :d, :x, :total, :f, :s, :fin, :c, :u)"
)
_LAST_RESULT: Final = text(
    "SELECT tie, ending_balance, gl_balance, inputs_hash FROM close_schedule_results "
    "WHERE close_id = :c AND arrangement_id = :a AND period = :p "
    "ORDER BY computed_at DESC, id DESC LIMIT 1"
)
_KEEP_RESULT: Final = text(
    "INSERT INTO close_schedule_results (tenant_id, close_id, arrangement_id, period, inflows, "
    "aje, ending_balance, gl_balance, tie, engine_version, inputs_hash) VALUES (:t, :c, :a, :p, "
    ":i, :aje, :end, :gl, :tie, :ev, :h)"
)
_RECORDINGS: Final = text(
    "SELECT proposed_entry_id, external_txn_id, at, confirmed_by FROM close_entry_recordings "
    "WHERE close_id = :c ORDER BY at"
)
_RECORD: Final = text(
    "INSERT INTO close_entry_recordings (tenant_id, close_id, proposed_entry_id, "
    "ledger_snapshot_id, external_txn_id, match_rule) VALUES (:t, :c, :p, :s, :x, :r) "
    "ON CONFLICT (proposed_entry_id, ledger_snapshot_id) DO NOTHING RETURNING id"
)
_REC_TALLY: Final = text(
    "SELECT DISTINCT ON (account_external_id) account_external_id, tally, difference "
    "FROM reconciliations WHERE close_id = :c ORDER BY account_external_id, version DESC"
)


def _version(row: object) -> _Version:
    m = cast("dict[str, object]", getattr(row, "_mapping", row))
    return _Version(
        arrangement_id=cast(UUID, m["arrangement_id"]),
        client_entity_id=cast(UUID, m["client_entity_id"]),
        account_external_id=cast(str, m["account_external_id"]),
        kind=cast(calc.Kind, m["kind"]),
        version=cast(int, m["version"]),
        description=cast(str, m["description"]),
        expense_account_ref=cast("str | None", m["expense_account_ref"]),
        scheduled_total=cast(Decimal, m["scheduled_total"]),
        starting_balance=cast(Decimal, m["starting_balance"]),
        frequency=cast(calc.Frequency, m["frequency"]),
        start_on=cast(date, m["start_on"]),
        finish_on=cast(date, m["finish_on"]),
        source_citation_id=cast("UUID | None", m["source_citation_id"]),
    )


def _arrangement(v: _Version) -> calc.Arrangement:
    return calc.Arrangement(
        kind=v.kind,
        scheduled_total=v.scheduled_total,
        start_on=v.start_on,
        finish_on=v.finish_on,
        frequency=v.frequency,
        starting_balance=v.starting_balance,
    )


def _out(v: _Version) -> ArrangementOut:
    return ArrangementOut(
        arrangement_id=v.arrangement_id,
        version=v.version,
        kind=v.kind,
        description=v.description,
        expense_account_ref=v.expense_account_ref or "",
        scheduled_total=v.scheduled_total,
        frequency=v.frequency,
        start_on=v.start_on,
        finish_on=v.finish_on,
        source_citation_id=v.source_citation_id,
    )


async def _close(ctx: AuthContext, close_id: UUID) -> tuple[repo.CloseRow, UUID]:
    from abacus.modules.closes.service import visible_close

    close = await visible_close(ctx, close_id)
    if close.client_entity_id is None:
        raise NotFound("close")
    return close, close.client_entity_id


async def _authorise_entity(ctx: AuthContext, entity: UUID) -> None:
    """`arrangement.edit` on the engagement of a close of the entity the person may read (walls
    and independence as for the close; an entity with no close the person sees reads 404)."""
    from abacus.modules.closes.service import visible_close

    async with tenant_session(ctx.tenant) as session:
        ids = [
            cast(UUID, r[0])
            for r in await session.execute(
                text("SELECT work_item_id FROM closes WHERE client_entity_id = :e"), {"e": entity}
            )
        ]
    for close_id in ids:
        try:
            close = await visible_close(ctx, close_id)
        except NotFound:
            continue
        await authorise(ctx, EDIT, await engagement_resource_of(ctx.tenant, close.engagement_id))
        return
    raise NotFound("arrangement")


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


# --- the tree and the register -------------------------------------------------------------------


async def _tallies(tenant: TenantContext, close: repo.CloseRow) -> dict[str, tuple[str, Decimal]]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_REC_TALLY, {"c": close.work_item_id})).all()
    return {str(r[0]): (str(r[1]), Decimal(r[2] or 0)) for r in rows}


async def account_tree(
    ctx: AuthContext, close_id: UUID, *, show_zero: bool = False
) -> AccountTreeOut:
    close, entity = await _close(ctx, close_id)
    try:
        month = await ledger_tree(ctx.tenant, entity, close.period)
    except PeriodNotAvailable:
        raise NoLedgerMonth(facts={"period": close.period}) from None
    balances = {b.external_id: b.balance for b in month.balances}
    recs = await _tallies(ctx.tenant, close)
    words: dict[str, tuple[TallyWord | None, Decimal | None]] = {
        acct: (cast(TallyWord, word), diff) for acct, (word, diff) in recs.items()
    }
    for result in await _schedule_words(ctx, close, entity, balances):
        words.setdefault(result[0], (result[1], result[2]))
    by_class: dict[str, dict[str, list[AccountNodeOut]]] = {}
    leaves: list[tuple[str, str, Decimal]] = []
    for account in month.accounts:
        balance = balances.get(account.external_id, ZERO)
        if balance == 0 and not show_zero:
            continue
        word, off = words.get(account.external_id, (None, None))
        leaves.append((account.classification, account.account_type, balance))
        by_class.setdefault(account.classification, {}).setdefault(
            account.account_type, []
        ).append(
            AccountNodeOut(
                node_id=f"a:{account.external_id}"[:80],
                kind="account",
                name=account.name,
                account_external_id=account.external_id,
                number=account.number,
                mask=account.mask,
                classification=account.classification,
                is_contra=account.is_contra,
                balance=balance,
                tally=word,
                off_by=off if word in ("off", "ties_once_posted") else None,
            )
        )
    sums = calc.rollup(leaves)
    nodes: list[AccountNodeOut] = []
    for classification in _ORDER:
        types = by_class.get(classification)
        if not types:
            continue
        nodes.append(
            AccountNodeOut(
                node_id=f"c:{classification}",
                kind="classification",
                name=classification.title(),
                classification=classification,
                balance=sums[classification][""],
                children=[
                    AccountNodeOut(
                        node_id=f"t:{classification}:{name}"[:80],
                        kind="account_type",
                        name=name,
                        classification=classification,
                        balance=sums[classification][name],
                        children=children,
                    )
                    for name, children in types.items()
                ],
            )
        )
    return AccountTreeOut(
        close_id=close_id,
        snapshot_id=month.snapshot_id,
        totals={k: month.totals.get(k, ZERO) for k in month.totals},
        nodes=nodes,
    )


async def register(
    ctx: AuthContext, close_id: UUID, account_ref: str, *, cursor: str | None = None
) -> CloseRegisterOut:
    close, entity = await _close(ctx, close_id)
    try:
        rows, following = await ledger_register(
            ctx.tenant, entity, account_ref, close.period, cursor=cursor
        )
    except PeriodNotAvailable:
        raise NoLedgerMonth(facts={"period": close.period}) from None
    return CloseRegisterOut(
        account_external_id=account_ref,
        items=[
            RegisterLineOut(
                line_ref=r.line_ref,
                txn_date=r.txn_date,
                txn_type=r.txn_type,
                category=r.offset_account_ref,
                payee=r.payee,
                memo=r.memo,
                amount=r.amount,
            )
            for r in rows
        ],
        next_cursor=following,
    )


# --- arrangements --------------------------------------------------------------------------------


async def _latest(
    tenant: TenantContext, entity: UUID, account: str | None = None
) -> list[_Version]:
    async with tenant_session(tenant) as session:
        return [
            _version(r) for r in await session.execute(_LATEST, {"e": entity, "acct": account})
        ]


async def create_arrangement(
    ctx: AuthContext, close_id: UUID, account_ref: str, body: ArrangementIn
) -> ArrangementOut:
    _human(ctx, EDIT)
    close, entity = await _close(ctx, close_id)
    await authorise(ctx, EDIT, await engagement_resource_of(ctx.tenant, close.engagement_id))
    try:
        calc.periods_of(_from_body(body))
    except calc.ScheduleInvalid as exc:
        raise ArrangementStale(facts={"reason": str(exc)}) from None
    async with uow(ctx.tenant) as tx:
        arrangement = cast(
            UUID,
            await tx.session.scalar(
                _NEW,
                {
                    "t": ctx.tenant_id,
                    "e": entity,
                    "acct": account_ref,
                    "k": body.kind,
                    "u": ctx.user_id,
                },
            ),
        )
        await tx.session.execute(_NEW_VERSION, _version_params(ctx, arrangement, 1, body))
        tx.record(
            "arrangement.created", target=Target("arrangement", arrangement), after=Ref(version=1)
        )
    return await _read(ctx.tenant, arrangement)


def _from_body(body: ArrangementIn) -> calc.Arrangement:
    return calc.Arrangement(
        kind=body.kind,
        scheduled_total=body.scheduled_total,
        start_on=body.start_on,
        finish_on=body.finish_on,
        frequency=body.frequency,
    )


def _version_params(
    ctx: AuthContext, arrangement: UUID, n: int, body: ArrangementIn
) -> dict[str, object]:
    return {
        "t": ctx.tenant_id,
        "a": arrangement,
        "n": n,
        "d": body.description,
        "x": body.expense_account_ref,
        "total": body.scheduled_total,
        "f": body.frequency,
        "s": body.start_on,
        "fin": body.finish_on,
        "c": body.source_citation_id,
        "u": ctx.user_id,
    }


async def _read(tenant: TenantContext, arrangement_id: UUID) -> ArrangementOut:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_ONE, {"a": arrangement_id})).first()
    if row is None:
        raise NotFound("arrangement")
    return _out(_version(row))


async def update_arrangement(
    ctx: AuthContext, arrangement_id: UUID, body: ArrangementIn, if_match: str
) -> ArrangementOut:
    """A new version per edit; `If-Match` is the version the person saw."""
    _human(ctx, EDIT)
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_ONE, {"a": arrangement_id})).first()
    if row is None:
        raise NotFound("arrangement")
    current = _version(row)
    await _authorise_entity(ctx, current.client_entity_id)
    if if_match.strip('"') != str(current.version):
        raise ArrangementStale(facts={"version": str(current.version)})
    try:
        calc.periods_of(_from_body(body))
    except calc.ScheduleInvalid as exc:
        raise ArrangementStale(facts={"reason": str(exc)}) from None
    n = current.version + 1
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_NEW_VERSION, _version_params(ctx, arrangement_id, n, body))
        tx.record(
            "arrangement.updated",
            target=Target("arrangement", arrangement_id),
            after=Ref(version=n),
        )
    return await _read(ctx.tenant, arrangement_id)


# --- the workpaper and its tie -------------------------------------------------------------------


def _effect(
    entry_lines: Sequence[tuple[str, Decimal, Decimal]], account: str, debit_natural: bool
) -> Decimal:
    net = sum(((d - c) for code, d, c in entry_lines if code == account), ZERO)
    return net if debit_natural else -net


async def _entries(
    ctx: AuthContext, close_id: UUID
) -> list[tuple[UUID, str, str, list[tuple[str, Decimal, Decimal]]]]:
    return [
        (e.id, e.ref, e.status, [(line.account_code, line.debit, line.credit) for line in e.lines])
        for e in await entries_of(ctx, close_id, "aje")
    ]


async def _recordings(tenant: TenantContext, close_id: UUID) -> dict[UUID, tuple[str, datetime]]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_RECORDINGS, {"c": close_id})).all()
    return {cast(UUID, r[0]): (str(r[1]), cast(datetime, r[2])) for r in rows}


async def _schedule_words(
    ctx: AuthContext, close: repo.CloseRow, entity: UUID, balances: dict[str, Decimal]
) -> list[tuple[str, TallyWord, Decimal | None]]:
    out: list[tuple[str, TallyWord, Decimal | None]] = []
    versions = await _latest(ctx.tenant, entity)
    if not versions:
        return out
    entries = await _entries(ctx, close.work_item_id)
    recorded = await _recordings(ctx.tenant, close.work_item_id)
    for account in sorted({v.account_external_id for v in versions}):
        result, _, _ = _tie_account(
            account,
            [v for v in versions if v.account_external_id == account],
            close.period,
            balances.get(account, ZERO),
            entries,
            recorded,
        )
        out.append((account, result.tie, result.off_by))
    return out


def _tie_account(
    account: str,
    versions: Sequence[_Version],
    period: str,
    gl: Decimal,
    entries: Sequence[tuple[UUID, str, str, list[tuple[str, Decimal, Decimal]]]],
    recorded: dict[UUID, tuple[str, datetime]],
) -> tuple[calc.TieResult, UUID | None, str | None]:
    """The account's tie, the pending entry that closes it (or the recorded one that did)."""
    sched = sum((calc.balance_at(_arrangement(v), period) for v in versions), ZERO)
    debit_natural = versions[0].kind in ("prepaid", "fixed_asset")
    pending: list[calc.PendingEntry] = []
    numbers: dict[str, UUID] = {}
    touched_recorded: UUID | None = None
    for entry_id, number, status, lines in entries:
        effect = _effect(lines, account, debit_natural)
        if effect == 0:
            continue
        if entry_id in recorded:
            touched_recorded = entry_id
        elif status in _PENDING or status in _RECORDED:
            pending.append(calc.PendingEntry(number, effect))
            numbers[number] = entry_id
    result = calc.tie(gl, sched, pending, recorded=touched_recorded is not None)
    entry_id = numbers.get(result.pending_entry_number or "") or touched_recorded
    return result, entry_id, result.pending_entry_number


async def workpaper(ctx: AuthContext, close_id: UUID, account_ref: str) -> CloseWorkpaperOut:
    close, entity = await _close(ctx, close_id)
    versions = await _latest(ctx.tenant, entity, account_ref)
    if not versions:
        raise NotFound("arrangement")
    try:
        month = await ledger_tree(ctx.tenant, entity, close.period)
    except PeriodNotAvailable:
        raise NoLedgerMonth(facts={"period": close.period}) from None
    account = next((a for a in month.accounts if a.external_id == account_ref), None)
    if account is None:
        raise NotFound("account")
    gl = next((b.balance for b in month.balances if b.external_id == account_ref), ZERO)
    entries = await _entries(ctx, close_id)
    recorded = await _recordings(ctx.tenant, close_id)
    result, entry_id, number = _tie_account(
        account_ref, versions, close.period, gl, entries, recorded
    )
    lines: list[ScheduleLineOut] = []
    for v in versions:
        lines.extend(
            ScheduleLineOut(
                period=line.period,
                inflows=line.inflows,
                aje=line.aje,
                ending_balance=line.ending_balance,
            )
            for line in calc.schedule(_arrangement(v), close.period)
        )
    recording = None
    if result.tie == "recorded" and entry_id is not None and entry_id in recorded:
        found = recorded[entry_id]
        recording = EntryRecordingOut(
            proposed_entry_id=entry_id,
            entry_number=next((n for i, n, _, _ in entries if i == entry_id), ""),
            external_txn_id=found[0],
            found_at=found[1],
        )
    await _keep(ctx, close, versions, gl, result)
    if result.tie == "off":
        from abacus.modules.closes.issues import raise_exception

        await raise_exception(
            ctx,
            close_id,
            severity="medium",
            issue_class="schedule",
            title=f"{account.name} does not tie to its schedule",
            account_ref=account_ref,
        )
    return CloseWorkpaperOut(
        account_external_id=account_ref,
        account_name=account.name,
        gl_balance=result.gl_balance,
        schedule_balance=result.schedule_balance,
        tally=result.tie,
        off_by=result.off_by,
        pending_entry_number=number,
        recording=recording,
        arrangements=[_out(v) for v in versions],
        lines=lines,
    )


async def _keep(
    ctx: AuthContext,
    close: repo.CloseRow,
    versions: Sequence[_Version],
    gl: Decimal,
    result: calc.TieResult,
) -> None:
    """One result row per arrangement when its inputs or tie changed (a recompute that changes
    nothing writes nothing)."""
    async with uow(ctx.tenant) as tx:
        for v in versions:
            arrangement = _arrangement(v)
            digest = calc.inputs_hash(arrangement, close.period, gl)
            last = (
                await tx.session.execute(
                    _LAST_RESULT,
                    {"c": close.work_item_id, "a": v.arrangement_id, "p": close.period},
                )
            ).first()
            if last is not None and last[0] == result.tie and last[3] == digest:
                continue
            line = calc.schedule(arrangement, close.period)[-1]
            # A multi-arrangement account ties as one; each row keeps its own ending balance, so a
            # row reads `tie` only when its own balance is the GL's (the table's CHECK).
            word = result.tie
            if word == "tie" and line.ending_balance != gl:
                word = "off"
            await tx.session.execute(
                _KEEP_RESULT,
                {
                    "t": ctx.tenant_id,
                    "c": close.work_item_id,
                    "a": v.arrangement_id,
                    "p": close.period,
                    "i": line.inflows,
                    "aje": line.aje,
                    "end": line.ending_balance,
                    "gl": gl,
                    "tie": word,
                    "ev": calc.ENGINE_STAMP,
                    "h": digest,
                },
            )


async def workpaper_xlsx(ctx: AuthContext, close_id: UUID, account_ref: str) -> bytes:
    from abacus.modules.evidence.api import CloseWorkpaperSheet, render_close_workpaper

    paper = await workpaper(ctx, close_id, account_ref)
    close, _ = await _close(ctx, close_id)
    return render_close_workpaper(
        CloseWorkpaperSheet(
            title=f"{paper.account_name} · {close.period}",
            gl_balance=paper.gl_balance,
            schedule_balance=paper.schedule_balance,
            tally=paper.tally,
            rows=tuple(
                (line.period, line.inflows, line.aje, line.ending_balance) for line in paper.lines
            ),
        )
    )


# --- recategorisation and the recording matcher --------------------------------------------------


_CLOSE_OF: Final = text(
    "SELECT work_item_id FROM closes WHERE client_entity_id = :e AND period = :p"
)


async def recategorize(
    ctx: AuthContext, line_ref: str, body: RecategorizationIn
) -> ProposalRefOut:
    """A reclass proposal for one register row: Dr the new category, Cr the old, for the row's
    amount (code facts only), on the row's month's close; the person is the proposer; nothing is
    written to QuickBooks."""
    _human(ctx, "proposed_entry.create")
    from abacus.modules.ledger.api import register_row

    snapshot, _, number = line_ref.partition(":")
    if not number.isdigit() or len(number) > 9:
        raise NotFound("register_line")
    try:
        snapshot_id = UUID(snapshot)
    except ValueError:
        raise NotFound("register_line") from None
    async with tenant_session(ctx.tenant) as session:
        found = await register_row(session, snapshot_id, int(number))
        row = found[1] if found is not None else None
        close_id = (
            None
            if row is None or row.period is None
            else await session.scalar(_CLOSE_OF, {"e": row.client_entity_id, "p": row.period})
        )
    if row is None or not isinstance(close_id, UUID):
        raise NotFound("register_line")
    close, _ = await _close(ctx, close_id)  # walls: the row's close must be visible (INV-3)
    if row.offset_account_ref is None or row.offset_account_ref == body.to_account_ref:
        raise NotFound("register_line")
    amount = abs(row.debit - row.credit)
    out_of_account = row.credit > row.debit  # money out: the category was debited
    to_line = NewLine(
        body.to_account_ref, amount if out_of_account else ZERO, ZERO if out_of_account else amount
    )
    from_line = NewLine(
        row.offset_account_ref,
        ZERO if out_of_account else amount,
        amount if out_of_account else ZERO,
    )
    entry = await propose_entry(
        ctx,
        close.work_item_id,
        NewEntry(
            kind="aje",
            description=body.note or "Recategorize register row",
            misstatement_id=None,
            lines=(to_line, from_line),
        ),
    )
    async with uow(ctx.tenant) as tx:
        tx.record(
            "recategorization.proposed",
            target=Target("proposed_entry", entry.id),
            after=Ref(close_id=close.work_item_id),
        )
    return ProposalRefOut(
        proposed_entry_id=entry.id,
        entry_number=entry.ref,
        review_href=f"?ov=approve:{entry.id}",
    )


async def match_recordings(ctx: AuthContext, close_id: UUID) -> list[UUID]:
    """Approved close entries the month's register now records (one journal entry per entry,
    every line's account and amount); each found once per snapshot."""
    close, entity = await _close(ctx, close_id)
    try:
        month = await ledger_tree(ctx.tenant, entity, close.period)
    except PeriodNotAvailable:
        return []
    found: list[UUID] = []
    seen = await _recordings(ctx.tenant, close_id)
    for entry_id, _number, status, lines in await _entries(ctx, close_id):
        if status not in _RECORDED or entry_id in seen or not lines:
            continue
        candidates: dict[str, set[int]] | None = None
        for index, (code, debit, credit) in enumerate(lines):
            rows, _ = await ledger_register(ctx.tenant, entity, code, close.period)
            amount = abs(debit - credit)
            ids = {
                r.external_txn_id
                for r in rows
                if r.external_txn_id
                and (r.txn_type or "").replace(" ", "").lower().startswith(_JOURNAL)
                and abs(r.amount) == amount
            }
            if candidates is None:
                candidates = {i: {index} for i in ids if i}
            else:
                candidates = {i: s | {index} for i, s in candidates.items() if i in ids}
        matched = sorted(i for i, s in (candidates or {}).items() if len(s) == len(lines))
        if len(matched) != 1:
            continue
        async with uow(ctx.tenant) as tx:
            made = await tx.session.scalar(
                _RECORD,
                {
                    "t": ctx.tenant_id,
                    "c": close_id,
                    "p": entry_id,
                    "s": month.snapshot_id,
                    "x": matched[0],
                    "r": "journal_lines",
                },
            )
            if made is not None:
                tx.record(
                    "close_entry.recorded_matched",
                    target=Target("proposed_entry", entry_id),
                    after=Ref(close_id=close_id),
                )
                found.append(entry_id)
    return found
