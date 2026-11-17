"""The close's reconciliations (C-01-T23; C-01 §3 F5; SPEC-655 AC-39 to AC-42; CLS-05; DEC-5410;
amber).

- **Compute**: on a run step (`close_reconcile_statement`) and on `ledger_snapshot.recorded` for
  the close's entity and month. A version is new only when its inputs change; open items carry to
  it (each with `carried_from_item_id`), so a resolution stays with the item it was made on.
- **VM** (CLS-05): both sides to the cent, the items with their resolution, the statement lines
  and their match state, the L1 sign-off and why it is blocked or stale.
- **Resolution** (a person's, insert-only): carry forward or cleared, with a note.
- **Sign-off**: `reconciliation` is a reviewable; its content hash is the version's, so a new
  version (a changed book balance) leaves L1 stale, and an L1 waits while items are open
  (`reconciling_items_open`, the count of them).
- **Propose AJE** from an item: a person's entry through `adjustments.api.propose_entry`, which
  classifies it against the firm's threshold policy (Review required, its policy version).
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.closes import procedures as p
from abacus.modules.closes import repository as repo
from abacus.modules.closes.events import ReconciliationComputed, ReconcilingItemResolved
from abacus.modules.identity.api import AuthContext, Forbidden, authorise

TARGET: Final = "reconciliation"
BLOCKED: Final = "reconciling_items_open"

_LATEST: Final = text(
    "SELECT id, version, statement_evidence_version_id, balance_per_bank, adjusted_bank, "
    "book_balance, adjusted_book, difference, tally, engine_version, inputs_hash, content_hash "
    "FROM reconciliations WHERE close_id = :c AND account_external_id = :a "
    "ORDER BY version DESC LIMIT 1"
)
_ONE: Final = text(
    "SELECT r.id, r.close_id, r.account_external_id, r.version, r.content_hash, c.engagement_id "
    "FROM reconciliations r JOIN closes c ON c.work_item_id = r.close_id WHERE r.id = :r"
)
_ITEMS: Final = text(
    "SELECT i.id, i.side, i.kind, i.ref, i.txn_date, i.days_at_period_end, i.amount, i.stale, "
    "i.register_line_ref, i.issue_id, i.proposed_entry_id, i.statement_line_id, "
    "x.resolution FROM reconciling_items i LEFT JOIN reconciling_item_resolutions x "
    "ON x.item_id = i.id WHERE i.reconciliation_id = :r ORDER BY i.txn_date, i.id"
)
_INSERT_REC: Final = text(
    "INSERT INTO reconciliations (tenant_id, close_id, account_external_id, period, version, "
    "statement_evidence_version_id, balance_per_bank, adjusted_bank, book_balance, adjusted_book, "
    "difference, tally, engine_version, inputs_hash, content_hash) VALUES (:t, :c, :a, :period, "
    ":version, :stmt, :bank, :abank, :book, :abook, :diff, :tally, :engine, :ih, :ch) RETURNING id"
)
_CARRY: Final = text(
    "INSERT INTO reconciling_items (tenant_id, reconciliation_id, side, kind, ref, txn_date, "
    "days_at_period_end, amount, stale, statement_line_id, register_line_ref, issue_id, "
    "proposed_entry_id, carried_from_item_id) SELECT i.tenant_id, :new, i.side, i.kind, i.ref, "
    "i.txn_date, i.days_at_period_end, i.amount, i.stale, i.statement_line_id, "
    "i.register_line_ref, i.issue_id, i.proposed_entry_id, i.id FROM reconciling_items i "
    "LEFT JOIN reconciling_item_resolutions x ON x.item_id = i.id "
    "WHERE i.reconciliation_id = :old AND (x.resolution IS NULL OR x.resolution = 'carry_forward')"
)
_RESOLVE: Final = text(
    "INSERT INTO reconciling_item_resolutions (tenant_id, item_id, resolution, note, actor_id, "
    "actor_kind) VALUES (:t, :i, :res, :note, :by, 'human') ON CONFLICT (item_id) DO NOTHING "
    "RETURNING id"
)
_OPEN: Final = text(
    "SELECT count(*) FROM reconciling_items i LEFT JOIN reconciling_item_resolutions x "
    "ON x.item_id = i.id WHERE i.reconciliation_id = :r AND x.id IS NULL"
)
_OF_CLOSE: Final = text(
    "SELECT DISTINCT ON (account_external_id) id, account_external_id FROM reconciliations "
    "WHERE close_id = :c ORDER BY account_external_id, version DESC"
)
_CLOSES_OF: Final = text(
    "SELECT work_item_id FROM closes WHERE client_entity_id = :e AND locked_at IS NULL"
)
_ITEM: Final = text(
    "SELECT i.id, i.side, i.kind, i.amount, i.ref, r.close_id, r.account_external_id "
    "FROM reconciling_items i JOIN reconciliations r ON r.id = i.reconciliation_id "
    "WHERE i.id = :i AND i.reconciliation_id = :r"
)


class ItemResolved(DomainConflict):
    code = "reconciling_item_resolved"


def _sha(*parts: object) -> str:
    return hashlib.sha256("|".join(str(x) for x in parts).encode()).hexdigest()


async def _balance(tenant: TenantContext, close: repo.CloseRow, account: str) -> Decimal:
    from abacus.modules.ledger.api import account_tree

    if close.client_entity_id is None:
        raise NotFound("client_entity")
    tree = await account_tree(tenant, close.client_entity_id, close.period)
    found = next((b.balance for b in tree.balances if b.external_id == account), None)
    if found is None:
        raise NotFound("account")
    return found


async def recompute(tenant: TenantContext, close_id: UUID, account: str) -> UUID | None:
    """A new version when the inputs changed; open and carried items move to it. None when
    nothing changed (no version, no event)."""
    from abacus.modules.ledger.api import month_bounds

    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        raise NotFound("close")
    book = await _balance(tenant, close, account)
    _, period_end = month_bounds(close.period)
    async with tenant_session(tenant) as session:
        latest = (await session.execute(_LATEST, {"c": close_id, "a": account})).mappings().first()
        items = (
            []
            if latest is None
            else [
                p.OutstandingItem(
                    r["side"], r["kind"], r["ref"], Decimal(r["amount"]), r["txn_date"]
                )
                for r in (await session.execute(_ITEMS, {"r": latest["id"]})).mappings()
                if r["resolution"] in (None, "carry_forward")
            ]
        )
    bank = (
        None
        if latest is None or latest["balance_per_bank"] is None
        else Decimal(latest["balance_per_bank"])
    )
    inputs = {"book": book, "bank": bank, "items": [asdict(i) for i in items], "end": period_end}
    ih = p.inputs_hash(inputs)
    if latest is not None and latest["inputs_hash"] == ih:
        return None
    if bank is None:
        values: dict[str, object] = {
            "bank": None, "abank": None, "abook": book, "diff": None, "tally": "pending",
        }  # fmt: skip
    else:
        rec = p.reconcile_statement(bank, book, items, period_end)
        values = {
            "bank": rec.balance_per_bank,
            "abank": rec.adjusted_bank,
            "abook": rec.adjusted_book,
            "diff": rec.difference,
            "tally": rec.tally,
        }
    version = 1 if latest is None else int(cast(int, latest["version"])) + 1
    async with uow(tenant) as tx:
        made = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_REC,
                {
                    "t": tenant.tenant_id,
                    "c": close_id,
                    "a": account,
                    "period": close.period,
                    "version": version,
                    "stmt": None if latest is None else latest["statement_evidence_version_id"],
                    "book": book,
                    "engine": p.ENGINE_VERSION,
                    "ih": ih,
                    "ch": _sha(ih, values["tally"]),
                    **values,
                },
            ),
        )
        if latest is not None:
            await tx.session.execute(_CARRY, {"new": made, "old": latest["id"]})
        tx.record(
            "reconciliation.computed",
            target=Target(TARGET, made),
            after=Ref(close_id=close_id, version=version, inputs_hash=ih),
        )
        tx.emit(
            ReconciliationComputed(
                reconciliation_id=made, close_id=close_id, engagement_id=close.engagement_id
            )
        )
    return made


async def on_ledger_snapshot_recorded(event: OutboxEvent) -> None:
    """A new ledger snapshot for an entity recomputes each open close's reconciliations; a changed
    book balance is a new version (L1 goes stale); unchanged inputs make none."""
    entity = event.payload.get("client_entity_id")
    if entity is None:
        return
    tenant = TenantContext(event.tenant_id, "system", "closes:reconciliation")
    async with tenant_session(tenant) as session:
        closes = [r[0] for r in await session.execute(_CLOSES_OF, {"e": UUID(str(entity))})]
    for close_id in closes:
        async with tenant_session(tenant) as session:
            accounts = [
                r.account_external_id for r in await session.execute(_OF_CLOSE, {"c": close_id})
            ]
        for account in accounts:
            try:
                await recompute(tenant, close_id, account)
            except NotFound:
                continue


# --- the VM, resolution and entries --------------------------------------------------------------


async def view(ctx: AuthContext, close_id: UUID, account: str) -> dict[str, object]:
    """CLS-05's VM facts (the route maps them to `CloseReconciliationOut`)."""
    from abacus.modules.ledger.api import account_tree, month_bounds
    from abacus.modules.review.api import sign_off_states

    async with tenant_session(ctx.tenant) as session:
        close = await repo.close_row(session, close_id)
        if close is None:
            raise NotFound("close")
        latest = (await session.execute(_LATEST, {"c": close_id, "a": account})).mappings().first()
        if latest is None:
            raise NotFound("reconciliation")
        items = list((await session.execute(_ITEMS, {"r": latest["id"]})).mappings())
        open_count = int(await session.scalar(_OPEN, {"r": latest["id"]}) or 0)
    from abacus.modules.engagements.api import get_ref

    await authorise(ctx, "close.read", (await get_ref(ctx, close.engagement_id)).resource())
    name = ""
    if close.client_entity_id is not None:
        tree = await account_tree(ctx.tenant, close.client_entity_id, close.period)
        name = next((a.name for a in tree.accounts if a.external_id == account), "")
    states = await sign_off_states(
        ctx.tenant,
        TARGET,
        [cast(UUID, latest["id"])],
        {cast(UUID, latest["id"]): str(latest["content_hash"])},
    )
    state = states.get(cast(UUID, latest["id"]))
    _, period_end = month_bounds(close.period)
    return {
        "row": dict(latest),
        "items": [dict(i) for i in items],
        "account_name": name,
        "period_end": period_end,
        "open_count": open_count,
        "state": state,
    }


async def resolve_item(
    ctx: AuthContext, reconciliation_id: UUID, item_id: UUID, resolution: str, note: str
) -> dict[str, object]:
    """A person's carry forward or cleared, with a note (insert-only; once per item)."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("reconciliation.resolve_item", "role")
    async with tenant_session(ctx.tenant) as session:
        rec = (await session.execute(_ONE, {"r": reconciliation_id})).mappings().first()
        found = (
            (await session.execute(_ITEM, {"i": item_id, "r": reconciliation_id}))
            .mappings()
            .first()
        )
    if rec is None or found is None:
        raise NotFound("reconciling_item")
    from abacus.modules.engagements.api import get_ref

    await authorise(
        ctx,
        "reconciliation.resolve_item",
        (await get_ref(ctx, cast(UUID, rec["engagement_id"]))).resource(),
    )
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(
            _RESOLVE,
            {
                "t": ctx.tenant_id,
                "i": item_id,
                "res": resolution,
                "note": note.strip(),
                "by": ctx.user_id,
            },
        )
        if done is None:
            raise ItemResolved(facts={"item": str(item_id)})
        tx.record(
            f"reconciling_item.{resolution}",
            target=Target(TARGET, reconciliation_id),
            after=Ref(item=item_id),
        )
        tx.emit(
            ReconcilingItemResolved(
                reconciliation_id=reconciliation_id,
                close_id=cast(UUID, rec["close_id"]),
                engagement_id=cast(UUID, rec["engagement_id"]),
            )
        )
    out: dict[str, object] = {str(k): v for k, v in dict(found).items()}
    out["resolution"] = resolution
    return out


async def item_for_draft(
    ctx: AuthContext, reconciliation_id: UUID, item_id: UUID
) -> dict[str, object]:
    async with tenant_session(ctx.tenant) as session:
        rec = (await session.execute(_ONE, {"r": reconciliation_id})).mappings().first()
        found = (
            (await session.execute(_ITEM, {"i": item_id, "r": reconciliation_id}))
            .mappings()
            .first()
        )
    if rec is None or found is None:
        raise NotFound("reconciling_item")
    from abacus.modules.engagements.api import get_ref

    await authorise(
        ctx, "close.read", (await get_ref(ctx, cast(UUID, rec["engagement_id"]))).resource()
    )
    return {str(k): v for k, v in dict(found).items()}


def entry_lines(
    item: dict[str, object], cash_account: str, offset_account: str
) -> list[tuple[str, Decimal, Decimal]]:
    """Code's draft of the AJE an unrecorded or book-error item needs: the cash account against
    the offset, the item's amount (a deposit debits cash; a withdrawal credits it)."""
    amount = abs(Decimal(str(item["amount"])))
    inflow = str(item["kind"]) in ("unrecorded_deposit",) or (
        str(item["kind"]) == "book_error" and Decimal(str(item["amount"])) > 0
    )
    if inflow:
        return [(cash_account, amount, Decimal(0)), (offset_account, Decimal(0), amount)]
    return [(offset_account, amount, Decimal(0)), (cash_account, Decimal(0), amount)]


async def propose_from_item(
    ctx: AuthContext,
    close_id: UUID,
    item_id: UUID | None,
    description: str,
    lines: list[tuple[str, Decimal, Decimal]],
) -> tuple[UUID, str]:
    """A person's AJE through adjustments (classified against the firm's threshold policy):
    its id and number ("AJE-06")."""
    from abacus.modules.adjustments.api import NewEntry, NewLine, propose_entry

    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("proposed_entry.create", "role")
    entry = await propose_entry(
        ctx,
        close_id,
        NewEntry(
            kind="aje",
            description=description.strip(),
            misstatement_id=None,
            lines=tuple(NewLine(code, debit, credit) for code, debit, credit in lines),
        ),
    )
    entry_id = entry.id
    if item_id is not None:
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                text(
                    "UPDATE reconciling_items SET proposed_entry_id = :e WHERE id = :i "
                    "AND proposed_entry_id IS NULL"
                ),
                {"i": item_id, "e": entry_id},
            )
            tx.record(
                "reconciling_item.entry_proposed",
                target=Target(TARGET, item_id),
                after=Ref(entry=entry_id),
            )
    return entry_id, entry.ref


# --- the reviewable ------------------------------------------------------------------------------


async def reconciliation_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[object]:
    from abacus.modules.review.api import Reviewable

    async with tenant_session(tenant) as session:
        closes = [
            r[0]
            for r in await session.execute(
                text("SELECT work_item_id FROM closes WHERE engagement_id = :e"),
                {"e": engagement_id},
            )
        ]
        out: list[object] = []
        for close_id in closes:
            for r in await session.execute(
                text(
                    "SELECT DISTINCT ON (account_external_id) id, account_external_id, "
                    "content_hash FROM reconciliations WHERE close_id = :c "
                    "ORDER BY account_external_id, version DESC"
                ),
                {"c": close_id},
            ):
                out.append(
                    Reviewable(
                        TARGET,
                        r.id,
                        str(r.account_external_id),
                        f"Reconciliation {r.account_external_id}",
                        str(r.content_hash),
                        True,
                    )
                )
    return out


async def reconciliation_facts(tenant: TenantContext, reconciliation_id: UUID) -> object | None:
    """L1 waits while items are open; the version's hash is what an L1 names (a new version is
    stale)."""
    from abacus.modules.review.api import ReviewableFacts

    async with tenant_session(tenant) as session:
        r = (await session.execute(_ONE, {"r": reconciliation_id})).mappings().first()
        if r is None:
            return None
        open_count = int(await session.scalar(_OPEN, {"r": reconciliation_id}) or 0)
    return ReviewableFacts(
        target_type=TARGET,
        target_id=reconciliation_id,
        engagement_id=cast(UUID, r["engagement_id"]),
        content_hash=str(r["content_hash"]),
        version_no=int(cast(int, r["version"])),
        preparer_user_ids=frozenset(),
        label=f"Reconciliation {r['account_external_id']}",
        work_item_id=cast(UUID, r["close_id"]),
        blocked_code=BLOCKED if open_count else None,
        blocked_count=open_count,
    )


def register() -> None:
    from abacus.modules.review.api import register_reviewable, register_reviewable_facts

    register_reviewable(TARGET, reconciliation_reviewables)  # type: ignore[arg-type] -- Reviewable rows
    register_reviewable_facts(TARGET, reconciliation_facts)  # type: ignore[arg-type] -- ReviewableFacts


SUBSCRIPTIONS: Final = {"ledger_snapshot.recorded": on_ledger_snapshot_recorded}
__all__ = ["recompute", "register", "resolve_item", "view"]
