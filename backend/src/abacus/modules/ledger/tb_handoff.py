"""T-06-T20: the TB hand-off service (C12; SPEC-702 F6; T-06 §4.3; DEC-5631). PROTECTED (red):
the only writer of `tb_handoffs` and its children (HANDOFF-001).

A released (audit or review) or locked (CAS close) Final trial balance becomes a tax return's
starting TB:

- **Preview** (`preview`, pure): every account travels with last year's tax-line code
  (`prior_year`), a suggestion (`suggested`, adopted only by the person) or blank (`blank`,
  needs review); schedules carried from the leadsheets; book income from the Final layer; the
  tax-relevant items from C8's passed entries. Counts foot (prior + suggested + blank = total);
  `preview_hash` pins exactly what the person saw.
- **Create** (`create`): only when the source kind's registered gate says the source is
  released (`register_handoff_gate`; G8 for audit and review, a locked close for CAS; fail
  closed: an unregistered kind refuses, 409 `handoff_not_available`), and only for the preview
  the person saw (409 `preview_changed`). One unit of work writes one immutable version and its
  children; a previous version of the same target gains a supersession row (`rehandoff`).
- **Supersede** (`supersede_for_snapshot`): a new Final snapshot after release marks the latest
  hand-off superseded (`tb_changed_after_release`); the tax side shows the banner.

Outbox `tb_handoff.created` and `tb_handoff.superseded` carry identifiers only (DEC-60). Ledger
never imports identity: callers pass the tenant and the acting person's id.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import DomainEvent, Scope, Target, UnitOfWork, uow
from abacus.modules.ledger.handoff_errors import HandoffNotAvailable, PreviewChanged

SourceKind = Literal["audit_release", "review_release", "close_lock"]
Travel = Literal["prior_year", "suggested", "blank"]
TARGET: Final = "tb_handoff"
# (tenant, source work item) -> released? A source kind with no provider refuses (fail closed).
HandoffGate = Callable[[TenantContext, UUID], Awaitable[bool]]
_GATES: dict[str, HandoffGate] = {}


def register_handoff_gate(kind: SourceKind, gate: HandoffGate) -> None:
    known = _GATES.get(kind)
    if known is not None and (known.__module__, known.__qualname__) != (
        gate.__module__,
        gate.__qualname__,
    ):
        raise ValueError(f"handoff gate {kind!r} is already registered")
    _GATES[kind] = gate


async def source_released(tenant: TenantContext, kind: str, source_work_item_id: UUID) -> bool:
    gate = _GATES.get(kind)
    return gate is not None and await gate(tenant, source_work_item_id)


class TbHandoffCreated(DomainEvent):
    event_type = "tb_handoff.created"
    tb_handoff_id: Annotated[UUID, classified("internal")]
    tax_return_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]


class TbHandoffSuperseded(DomainEvent):
    event_type = "tb_handoff.superseded"
    tb_handoff_id: Annotated[UUID, classified("internal")]
    tax_return_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class AccountIn:
    account_no: str
    account_name: str
    balance: Decimal


@dataclass(frozen=True)
class AccountChoice:
    account_no: str
    account_name: str
    balance: Decimal
    travel: Travel
    tax_line_code: str | None
    suggestion_id: UUID | None
    needs_review: bool


# C-02-T39 (1017, DEC-5922): a December close's tax-relevant close item (`close_issue`).
ItemKind = Literal["passed_adjustment", "book_tax_expense", "close_issue"]
# The schedules a hand-off may carry (C-02-T39 adds a close's prepaid, deferred revenue and
# shareholder distributions to T-06's three).
ScheduleKind = Literal[
    "fixed_assets", "accrued_liabilities", "passed_adjustments", "prepaid_expenses",
    "deferred_revenue", "shareholder_distributions",
]  # fmt: skip


@dataclass(frozen=True)
class TaxItem:
    item_kind: ItemKind
    source_ref: Mapping[str, str]
    amount: Decimal
    create_issue: bool


@dataclass(frozen=True)
class Preview:
    accounts: tuple[AccountChoice, ...]
    counts: Mapping[str, int]
    book_income: Mapping[str, str]
    schedules: tuple[str, ...]
    tax_items: tuple[TaxItem, ...]
    preview_hash: str


@dataclass(frozen=True)
class Draft:
    client_id: UUID
    source_kind: SourceKind
    source_engagement_id: UUID
    source_work_item_id: UUID
    source_snapshot_id: UUID
    target_work_item_id: UUID
    preview: Preview
    schedule_facts: Mapping[str, Mapping[str, str]] = field(
        default_factory=dict[str, Mapping[str, str]]
    )


def preview(
    accounts: Sequence[AccountIn],
    *,
    prior_codes: Mapping[str, str],
    suggestions: Mapping[str, tuple[str, UUID]],
    book_income_before_tax: Decimal,
    income_tax_expense: Decimal,
    schedules: Sequence[str],
    tax_items: Sequence[TaxItem],
) -> Preview:
    """The hand-off as code builds it (pure): last year's code first, then a suggestion, else
    blank (a person decides). Book income is the Final layer's, less the tax expense."""
    rows: list[AccountChoice] = []
    for a in accounts:
        if a.account_no in prior_codes:
            rows.append(
                AccountChoice(
                    a.account_no,
                    a.account_name,
                    a.balance,
                    "prior_year",
                    prior_codes[a.account_no],
                    None,
                    False,
                )
            )
        elif a.account_no in suggestions:
            code, suggestion = suggestions[a.account_no]
            rows.append(
                AccountChoice(
                    a.account_no, a.account_name, a.balance, "suggested", code, suggestion, True
                )
            )
        else:
            rows.append(
                AccountChoice(a.account_no, a.account_name, a.balance, "blank", None, None, True)
            )
    counts = {
        "total": len(rows),
        "prior_year": sum(1 for r in rows if r.travel == "prior_year"),
        "suggested": sum(1 for r in rows if r.travel == "suggested"),
        "blank": sum(1 for r in rows if r.travel == "blank"),
    }
    book = {
        "before_tax": str(book_income_before_tax),
        "income_tax_expense": str(income_tax_expense),
        "net_income_per_books": str(book_income_before_tax - income_tax_expense),
    }
    body = {
        "accounts": [_jsonable(asdict(r)) for r in rows],
        "book": book,
        "schedules": sorted(schedules),
        "items": [_jsonable(asdict(i)) for i in tax_items],
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return Preview(tuple(rows), counts, book, tuple(sorted(schedules)), tuple(tax_items), digest)


def _jsonable(d: Mapping[str, object]) -> dict[str, object]:
    return {k: (str(v) if isinstance(v, Decimal | UUID) else v) for k, v in d.items()}


async def create(tenant: TenantContext, actor_user_id: UUID, draft: Draft, seen_hash: str) -> UUID:
    """One immutable hand-off version from a released source, for the preview the person saw."""
    if not await source_released(tenant, draft.source_kind, draft.source_work_item_id):
        raise HandoffNotAvailable(facts={"source_kind": draft.source_kind})
    if seen_hash != draft.preview.preview_hash:
        raise PreviewChanged(facts={"preview_hash": draft.preview.preview_hash})
    scope = Scope(engagement_id=draft.source_engagement_id, work_item_id=draft.source_work_item_id)
    async with uow(tenant) as tx:
        # The table is insert-only (no row locks): two hand-offs to one return serialise on a
        # transaction lock on the target, so the version numbers never race.
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"tb_handoff:{draft.target_work_item_id}"},
        )
        prior = (
            await tx.session.execute(
                text(
                    "SELECT id, version_no FROM tb_handoffs WHERE target_work_item_id = :t "
                    "ORDER BY version_no DESC LIMIT 1"
                ),
                {"t": draft.target_work_item_id},
            )
        ).first()
        version = 1 if prior is None else int(prior[1]) + 1
        new_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO tb_handoffs (tenant_id, client_id, source_kind, "
                    "source_engagement_id, source_work_item_id, source_snapshot_id, "
                    "target_work_item_id, version_no, preview_hash, book_income, counts, "
                    "handed_off_by) VALUES (:tenant, :client, :kind, :eng, :src, :snap, :target, "
                    ":v, :hash, CAST(:book AS jsonb), CAST(:counts AS jsonb), :by) RETURNING id"
                ),
                {
                    "tenant": tenant.tenant_id,
                    "client": draft.client_id,
                    "kind": draft.source_kind,
                    "eng": draft.source_engagement_id,
                    "src": draft.source_work_item_id,
                    "snap": draft.source_snapshot_id,
                    "target": draft.target_work_item_id,
                    "v": version,
                    "hash": draft.preview.preview_hash,
                    "book": json.dumps(dict(draft.preview.book_income)),
                    "counts": json.dumps(dict(draft.preview.counts)),
                    "by": actor_user_id,
                },
            )
        ).scalar_one()
        for a in draft.preview.accounts:
            await tx.session.execute(
                text(
                    "INSERT INTO tb_handoff_account_choices (tenant_id, handoff_id, account_no, "
                    "account_name, balance, tax_line_code, source, suggestion_id, needs_review) "
                    "VALUES (:t, :h, :no, :name, :bal, :code, :src, :sug, :review)"
                ),
                {
                    "t": tenant.tenant_id,
                    "h": new_id,
                    "no": a.account_no,
                    "name": a.account_name,
                    "bal": a.balance,
                    "code": a.tax_line_code,
                    "src": a.travel,
                    "sug": a.suggestion_id,
                    "review": a.needs_review,
                },
            )
        for kind in draft.preview.schedules:
            await tx.session.execute(
                text(
                    "INSERT INTO tb_handoff_schedules (tenant_id, handoff_id, kind, carried, "
                    "facts) "
                    "VALUES (:t, :h, :k, true, CAST(:f AS jsonb))"
                ),
                {
                    "t": tenant.tenant_id,
                    "h": new_id,
                    "k": kind,
                    "f": json.dumps(dict(draft.schedule_facts.get(kind, {}))),
                },
            )
        for item in draft.preview.tax_items:
            await tx.session.execute(
                text(
                    "INSERT INTO tb_handoff_tax_items (tenant_id, handoff_id, item_kind, "
                    "source_ref, amount, create_issue) VALUES (:t, :h, :k, CAST(:r AS jsonb), "
                    ":a, :c)"
                ),
                {
                    "t": tenant.tenant_id,
                    "h": new_id,
                    "k": item.item_kind,
                    "r": json.dumps(dict(item.source_ref)),
                    "a": item.amount,
                    "c": item.create_issue,
                },
            )
        if prior is not None:
            await _supersede(tx, tenant, UUID(str(prior[0])), new_id, "rehandoff", None)
            tx.emit(
                TbHandoffSuperseded(
                    tb_handoff_id=UUID(str(prior[0])), tax_return_id=draft.target_work_item_id
                )
            )
        tx.emit(
            TbHandoffCreated(
                tb_handoff_id=UUID(str(new_id)),
                tax_return_id=draft.target_work_item_id,
                version_no=version,
            )
        )
        tx.record("tb_handoff.created", target=Target(TARGET, UUID(str(new_id))), scope=scope)
    return UUID(str(new_id))


async def _supersede(
    tx: UnitOfWork,
    tenant: TenantContext,
    handoff_id: UUID,
    by: UUID | None,
    reason: Literal["tb_changed_after_release", "rehandoff"],
    snapshot_id: UUID | None,
) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO tb_handoff_supersessions (tenant_id, handoff_id, "
            "superseded_by_handoff_id, "
            "reason, detected_snapshot_id) VALUES (:t, :h, :by, :r, :s) "
            "ON CONFLICT (tenant_id, handoff_id) DO NOTHING"
        ),
        {"t": tenant.tenant_id, "h": handoff_id, "by": by, "r": reason, "s": snapshot_id},
    )


async def supersede_for_snapshot(
    tenant: TenantContext, source_work_item_id: UUID, snapshot_id: UUID
) -> list[UUID]:
    """A new Final snapshot after release: each target's latest hand-off from this source is
    marked superseded once (the ON CONFLICT keeps it idempotent)."""
    async with uow(tenant) as tx:
        rows = (
            await tx.session.execute(
                text(
                    "SELECT DISTINCT ON (target_work_item_id) id, target_work_item_id, "
                    "source_snapshot_id FROM tb_handoffs WHERE source_work_item_id = :s "
                    "ORDER BY target_work_item_id, version_no DESC"
                ),
                {"s": source_work_item_id},
            )
        ).all()
        marked: list[UUID] = []
        for handoff_id, target, snap in rows:
            if snap == snapshot_id:
                continue
            await _supersede(tx, tenant, handoff_id, None, "tb_changed_after_release", snapshot_id)
            tx.emit(TbHandoffSuperseded(tb_handoff_id=handoff_id, tax_return_id=target))
            marked.append(UUID(str(handoff_id)))
    return marked


# --- reads (T-06-T39, DEC-5832): the tax side's landing and C12's read routes -------------------


@dataclass(frozen=True)
class HandoffRow:
    id: UUID
    client_id: UUID
    source_kind: SourceKind
    source_engagement_id: UUID
    source_work_item_id: UUID
    source_snapshot_id: UUID
    target_work_item_id: UUID
    version_no: int
    book_income: Mapping[str, str]
    counts: Mapping[str, int]
    handed_off_by: UUID
    handed_off_at: datetime
    superseded: bool
    superseded_by: UUID | None


@dataclass(frozen=True)
class ChoiceRow:
    account_no: str
    account_name: str
    balance: Decimal
    tax_line_code: str | None
    travel: Travel
    suggestion_id: UUID | None
    needs_review: bool


@dataclass(frozen=True)
class TaxItemRow:
    item_kind: str
    source_ref: Mapping[str, str]
    amount: Decimal
    create_issue: bool


_HANDOFF_COLUMNS: Final = (
    "h.id, h.client_id, h.source_kind, h.source_engagement_id, h.source_work_item_id, "
    "h.source_snapshot_id, h.target_work_item_id, h.version_no, h.book_income, h.counts, "
    "h.handed_off_by, h.handed_off_at, s.handoff_id IS NOT NULL AS superseded, "
    "s.superseded_by_handoff_id FROM tb_handoffs h LEFT JOIN tb_handoff_supersessions s "
    "ON s.tenant_id = h.tenant_id AND s.handoff_id = h.id"
)
# Fixed statements, composed once from constants (SQL-001).
_HANDOFF_BY_ID: Final = "SELECT " + _HANDOFF_COLUMNS + " WHERE h.id = :h"
_HANDOFF_LATEST: Final = (
    "SELECT " + _HANDOFF_COLUMNS + " WHERE h.target_work_item_id = :t "
    "ORDER BY h.version_no DESC LIMIT 1"
)


def _handoff_row(r: object) -> HandoffRow:
    row = cast(Any, r)  # Any: a row value
    return HandoffRow(
        UUID(str(row.id)), UUID(str(row.client_id)), row.source_kind,
        UUID(str(row.source_engagement_id)), UUID(str(row.source_work_item_id)),
        UUID(str(row.source_snapshot_id)), UUID(str(row.target_work_item_id)),
        int(row.version_no), dict(row.book_income), dict(row.counts),
        UUID(str(row.handed_off_by)), row.handed_off_at, bool(row.superseded),
        None if row.superseded_by_handoff_id is None else UUID(str(row.superseded_by_handoff_id)),
    )  # fmt: skip


async def handoff_of(tenant: TenantContext, handoff_id: UUID) -> HandoffRow | None:
    async with tenant_session(tenant) as session:
        found = (await session.execute(text(_HANDOFF_BY_ID), {"h": handoff_id})).first()
    return None if found is None else _handoff_row(found)


async def latest_for_target(tenant: TenantContext, target_work_item_id: UUID) -> HandoffRow | None:
    """The target return's newest hand-off version (superseded or not)."""
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                text(_HANDOFF_LATEST),
                {"t": target_work_item_id},
            )
        ).first()
    return None if found is None else _handoff_row(found)


async def choices_of(tenant: TenantContext, handoff_id: UUID) -> list[ChoiceRow]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT account_no, account_name, balance, tax_line_code, source, "
                    "suggestion_id, needs_review FROM tb_handoff_account_choices "
                    "WHERE handoff_id = :h ORDER BY account_no"
                ),
                {"h": handoff_id},
            )
        ).all()
    return [
        ChoiceRow(
            r.account_no,
            r.account_name,
            Decimal(r.balance),
            r.tax_line_code,
            r.source,
            None if r.suggestion_id is None else UUID(str(r.suggestion_id)),
            bool(r.needs_review),
        )
        for r in rows
    ]


async def tax_items_of(tenant: TenantContext, handoff_id: UUID) -> list[TaxItemRow]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT item_kind, source_ref, amount, create_issue FROM tb_handoff_tax_items "
                    "WHERE handoff_id = :h ORDER BY item_kind, id"
                ),
                {"h": handoff_id},
            )
        ).all()
    return [
        TaxItemRow(r.item_kind, dict(r.source_ref), Decimal(r.amount), bool(r.create_issue))
        for r in rows
    ]
