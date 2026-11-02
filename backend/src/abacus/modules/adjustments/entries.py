"""A-06-T09: the adjustments service, part 1 (C8; A-06 §4.3; SPEC-642; DEC-2061). PROTECTED (red).

Proposed entries (AJE, RJE, PAJE, TJE, elimination) on an audit work item:

- **Propose** (from a misstatement or by hand): lines with one side each; the entry must balance
  (debits = credits, 422 `unbalanced_entry`); its amount is the debits' total. The threshold is
  code's: `methodology.api.aje_classification_for` under the firm's AJE thresholds in effect
  (account class = the area of the entry's largest line on the trial balance). An attest
  client's entry is always Review required (here, and 0643's `pe_attest_review_required`); a firm
  without thresholds in effect gets Review required too (fail closed).
- **Adjusted TB** (`adjusted_tb`): never stored. The ledger computes each layer (Unadjusted, AJE,
  RJE, Final) over the C9 snapshot from the entries this module offers through
  `ledger.api.register_adjustment_source`: approved AJEs and RJEs only (and the client's approved
  ones); PAJEs, TJEs and eliminations are never in a layer; proposed entries are a count.
- **C8 reads** for EBP-06, T-05 and A-09: `entries_of`, `recorded_entries`.

Nothing here posts, books or writes to any client system (ADR-040; `pe_posting_dormant`).
Approving, sending and recording the client's decision are A-06-T10.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import attest_of, get_ref, lock_ref, work_item_engagement
from abacus.modules.identity.api import AuthContext, allowed_actions
from abacus.modules.ledger.api import (
    AdjustmentEntry,
    EntryLine,
    EntrySet,
    engagement_trial_balances,
    trial_balance_view,
)
from abacus.modules.methodology.api import aje_classification_for

EntryKind = Literal["aje", "rje", "paje", "tje", "elimination"]
TARGET: Final = "proposed_entry"
_PREFIX: Final = {"aje": "AJE", "rje": "RJE", "paje": "PAJE", "tje": "TJE", "elimination": "ELIM"}
# What the ledger's layers take: a person approved it, or the client approved it.
RECORDED: Final = frozenset({"approved", "client_approved"})
PENDING: Final = frozenset({"proposed", "within_threshold", "review_required"})
LAYERED: Final = frozenset({"aje", "rje"})
_ACTIONS: Final = (
    "proposed_entry.update",
    "proposed_entry.send_to_client",
    "proposed_entry.reject",
    "proposed_entry.record_client_decision",
    "approval_batch.create",
)


class UnbalancedEntry(DomainInvalid):
    """An entry's debits and credits differ (or a line has both or neither side)."""

    code = "unbalanced_entry"


@dataclass(frozen=True)
class NewLine:
    account_code: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class NewEntry:
    kind: EntryKind
    description: str | None
    misstatement_id: UUID | None
    lines: tuple[NewLine, ...]


@dataclass(frozen=True)
class Line:
    line_no: int
    account_code: str
    account_name: str | None
    fs_line_key: str | None
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class Entry:
    id: UUID
    ref: str
    kind: EntryKind
    description: str | None
    amount: Decimal
    status: str
    threshold_result: Literal["within_threshold", "review_required"]
    is_attest_client: bool
    lines: tuple[Line, ...]
    approval_label: str | None
    version: int
    allowed_actions: tuple[str, ...]


def balance(lines: Sequence[NewLine]) -> Decimal:
    """The entry's amount: its debits' total, once it balances (422 `unbalanced_entry`)."""
    if len(lines) < 2:
        raise UnbalancedEntry(facts={"field": "lines"})
    debits = sum((ln.debit for ln in lines), Decimal(0))
    credits = sum((ln.credit for ln in lines), Decimal(0))
    for ln in lines:
        if (ln.debit == 0) == (ln.credit == 0) or ln.debit < 0 or ln.credit < 0:
            raise UnbalancedEntry(facts={"field": "lines"})
    if debits != credits:
        raise UnbalancedEntry(facts={"debits": str(debits), "credits": str(credits)})
    return debits


async def _engagement_of(tenant: TenantContext, work_item_id: UUID) -> UUID:
    found = await work_item_engagement(tenant, work_item_id)
    if found is None:
        raise NotFound("work_item")
    return found


async def _accounts(
    tenant: TenantContext, engagement_id: UUID
) -> dict[str, tuple[str, str | None]]:
    """The current trial balance's accounts: code -> (name, area)."""
    tbs = await engagement_trial_balances(tenant, engagement_id)
    if not tbs:
        return {}
    current = max(tbs, key=lambda t: t.period_end)
    view = await trial_balance_view(tenant, engagement_id, current.id)
    return {ln.account_code: (ln.account_name, ln.area) for ln in view.lines}


async def propose(ctx: AuthContext, work_item_id: UUID, new: NewEntry) -> Entry:
    """`POST …/proposed-entries` (the route authorised `proposed_entry.create`)."""
    amount = balance(new.lines)
    engagement_id = await _engagement_of(ctx.tenant, work_item_id)
    attest = bool(await attest_of(ctx.tenant, engagement_id))
    accounts = await _accounts(ctx.tenant, engagement_id)
    largest = max(new.lines, key=lambda ln: max(ln.debit, ln.credit))
    account_class = (accounts.get(largest.account_code, ("", None))[1] or "unclassified")[:60]
    classified = await aje_classification_for(
        ctx.tenant_id,
        account_class=account_class,
        amount_usd=int(amount),
        attest_client=attest,
        as_of=await today(ctx.tenant),
    )
    result: Literal["within_threshold", "review_required"] = (
        "review_required"
        if attest or classified is None or classified.outcome != "within_threshold"
        else "within_threshold"
    )
    policy = None if classified is None else classified.policy.version_id
    agent = ctx.tenant.actor_kind == "agent"
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        number = (
            await tx.session.execute(
                text(
                    "SELECT coalesce(max(number), 0) + 1 FROM proposed_entries "
                    "WHERE work_item_id = :w AND kind = :k"
                ),
                {"w": work_item_id, "k": new.kind},
            )
        ).scalar_one()
        entry_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO proposed_entries (tenant_id, engagement_id, work_item_id, kind, "
                    "number, ref, description, misstatement_id, amount, account_class, "
                    "threshold_policy_version_id, threshold_result, is_attest_client, status, "
                    "created_by_kind, created_by_id, on_behalf_of_user_id) VALUES (:t, :e, :w, "
                    ":k, :n, :ref, :d, :m, :a, :c, :p, :r, :att, :s, :ck, :cid, :obo) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "k": new.kind,
                    "n": number,
                    "ref": f"{_PREFIX[new.kind]}-{number}",
                    "d": (new.description or "").strip() or None,
                    "m": new.misstatement_id,
                    "a": amount,
                    "c": account_class,
                    "p": policy,
                    "r": result,
                    "att": attest,
                    "s": result,
                    "ck": "agent" if agent else "human",
                    "cid": ctx.tenant.actor_id,
                    "obo": ctx.user_id if agent else None,
                },
            )
        ).scalar_one()
        for n, ln in enumerate(new.lines, start=1):
            name, area = accounts.get(ln.account_code, (None, None))
            await tx.session.execute(
                text(
                    "INSERT INTO proposed_entry_lines (tenant_id, engagement_id, work_item_id, "
                    "entry_id, line_no, account_code, account_name, fs_line_key, debit, credit) "
                    "VALUES (:t, :e, :w, :id, :n, :code, :name, :fs, :dr, :cr)"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "id": entry_id,
                    "n": n,
                    "code": ln.account_code.strip(),
                    "name": name,
                    "fs": area,
                    "dr": ln.debit,
                    "cr": ln.credit,
                },
            )
        tx.record(
            "proposed_entry.proposed",
            target=Target(TARGET, entry_id),
            after=Ref(threshold=result, attest=attest),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return await entry(ctx, entry_id)


_COLUMNS = (
    "SELECT id, engagement_id, work_item_id, ref, kind, description, amount, status, "
    "threshold_result, is_attest_client, version FROM proposed_entries "
)
_ENTRY_BY_ID: Final = _COLUMNS + "WHERE id = :id"
_ENTRIES_OF: Final = (
    _COLUMNS + "WHERE work_item_id = :w AND (CAST(:k AS text) IS NULL OR kind = :k) "
    "ORDER BY kind, number"
)


async def _lines(tenant: TenantContext, ids: Sequence[UUID]) -> dict[UUID, list[Line]]:
    out: dict[UUID, list[Line]] = {i: [] for i in ids}
    if not ids:
        return out
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT entry_id, line_no, account_code, account_name, fs_line_key, debit, "
                    "credit FROM proposed_entry_lines WHERE entry_id = ANY(:ids) "
                    "ORDER BY entry_id, line_no"
                ),
                {"ids": list(ids)},
            )
        ).mappings()
        for r in rows:
            out[r["entry_id"]].append(
                Line(r["line_no"], r["account_code"], r["account_name"], r["fs_line_key"],
                     r["debit"], r["credit"])
            )  # fmt: skip
    return out


async def _approval_labels(tenant: TenantContext, ids: Sequence[UUID]) -> dict[UUID, str]:
    """ "Approved by Hannah Leclerc under BH AJE thresholds v2" is T10's batch label."""
    if not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT e.id, b.label FROM proposed_entries e JOIN approval_batches b "
                    "ON e.id = ANY(b.entry_ids) WHERE e.id = ANY(:ids)"
                ),
                {"ids": list(ids)},
            )
        ).all()
    return {r[0]: r[1] for r in rows}


def _entry(r: RowMapping, lines: list[Line], label: str | None, actions: tuple[str, ...]) -> Entry:
    return Entry(
        id=r["id"],
        ref=r["ref"],
        kind=cast(EntryKind, r["kind"]),
        description=r["description"],
        amount=r["amount"],
        status=r["status"],
        threshold_result=r["threshold_result"],
        is_attest_client=r["is_attest_client"],
        lines=tuple(lines),
        approval_label=label,
        version=r["version"],
        allowed_actions=actions,
    )


async def _actions(ctx: AuthContext, engagement_id: UUID) -> tuple[str, ...]:
    ref = await get_ref(ctx, engagement_id)
    can = await allowed_actions(ctx, ref.resource(), _ACTIONS)
    return tuple(a for a in _ACTIONS if a in can)


async def entry(ctx: AuthContext, entry_id: UUID) -> Entry:
    async with tenant_session(ctx.tenant) as session:
        r = (await session.execute(text(_ENTRY_BY_ID), {"id": entry_id})).mappings().first()
    if r is None:
        raise NotFound(TARGET)
    lines = await _lines(ctx.tenant, [entry_id])
    labels = await _approval_labels(ctx.tenant, [entry_id])
    return _entry(
        r, lines[entry_id], labels.get(entry_id), await _actions(ctx, r["engagement_id"])
    )


async def entries_of(
    ctx: AuthContext, work_item_id: UUID, kind: EntryKind | None = None
) -> list[Entry]:
    """`GET …/proposed-entries` (the route authorised `proposed_entry.read`) and C8's read."""
    engagement_id = await _engagement_of(ctx.tenant, work_item_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (
            (
                await session.execute(
                    text(_ENTRIES_OF),
                    {"w": work_item_id, "k": kind},
                )
            )
            .mappings()
            .all()
        )
    ids = [r["id"] for r in rows]
    lines = await _lines(ctx.tenant, ids)
    labels = await _approval_labels(ctx.tenant, ids)
    actions = await _actions(ctx, engagement_id)
    return [_entry(r, lines[r["id"]], labels.get(r["id"]), actions) for r in rows]


async def recorded_entries(tenant: TenantContext, engagement_id: UUID) -> EntrySet:
    """The ledger's adjustment source (C9 layers): approved AJEs and RJEs; the rest pending."""
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT id, ref, kind, status FROM proposed_entries "
                        "WHERE engagement_id = :e ORDER BY kind, number"
                    ),
                    {"e": engagement_id},
                )
            )
            .mappings()
            .all()
        )
    recorded = [r for r in rows if r["status"] in RECORDED and r["kind"] in LAYERED]
    lines = await _lines(tenant, [r["id"] for r in recorded])
    return EntrySet(
        tuple(
            AdjustmentEntry(
                r["ref"],
                cast(Literal["aje", "rje"], r["kind"]),
                tuple(EntryLine(ln.account_code, ln.debit, ln.credit) for ln in lines[r["id"]]),
            )
            for r in recorded
        ),
        sum(1 for r in rows if r["status"] in PENDING),
    )


async def adjusted_tb(ctx: AuthContext, work_item_id: UUID, layer: str) -> object:
    """`GET …/adjusted-tb` (the route authorised `adjusted_tb.read`): the current trial balance's
    `layer` from the ledger, never stored. The caller shapes the view (C8's `AdjustedTbOut`)."""
    engagement_id = await _engagement_of(ctx.tenant, work_item_id)
    tbs = await engagement_trial_balances(ctx.tenant, engagement_id)
    if not tbs:
        raise NotFound("trial_balance")
    current = max(tbs, key=lambda t: t.period_end)
    return await trial_balance_view(ctx.tenant, engagement_id, current.id, layer=layer)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `proposed_entry` rows an audit event names: id -> the owning engagement."""
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text("SELECT id, engagement_id FROM proposed_entries WHERE id = ANY(:ids)"),
            {"ids": list(ids)},
        )
        return {found: owned for found, owned in rows}


AUDIT_KINDS: Final = frozenset({TARGET})
