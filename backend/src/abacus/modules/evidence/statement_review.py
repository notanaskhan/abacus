"""Reviewing and approving a statement's transactions (SPEC-312 phase 2-3; TASK-324).

The server always reads the transactions again from the stored file (in the isolated child);
the reviewer only sends decisions: lines to exclude with a reason, a sign flip for an export
whose convention code inferred, and the balances the file doesn't print. Code reconciles
(opening + included lines = closing); only a reconciled statement can be approved, and only by
a person (ADR-005; the matrix and a database CHECK agree). An approval is kept as it was made.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Literal, cast
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import lock_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.extraction import CSV, PDF, extract
from abacus.modules.evidence.service import version_view
from abacus.modules.evidence.statement_repository import (
    dataset_for_version,
    insert_dataset,
    insert_transactions,
    transactions_of,
)
from abacus.modules.evidence.statements import (
    Box,
    ParsedStatement,
    Reconciliation,
    Source,
    StatementLine,
    from_pages,
    from_text_file,
    reconcile,
)
from abacus.modules.evidence.uploads import item_resource, uploads_for
from abacus.modules.identity.api import AuthContext, authorise, names_of
from abacus.modules.requests.api import read_item

_CENTS: Final = Decimal("0.01")
BalanceSource = Literal["printed", "entered"]


class NoTransactions(DomainConflict):
    """Code found no statement lines in this file."""

    code = "no_transactions"


class NotReconciled(DomainConflict):
    code = "statement_not_reconciled"


class AlreadyApproved(DomainConflict):
    code = "statement_already_approved"


class ReviewInvalid(DomainInvalid):
    code = "statement_review_invalid"


class BalancePrinted(DomainInvalid):
    """A balance the statement prints can't be replaced by a typed one."""

    code = "statement_balance_printed"


@dataclass(frozen=True)
class Decisions:
    excluded: dict[int, str]  # position -> reason
    flip_signs: bool
    opening: Decimal | None  # only when the file doesn't print it
    closing: Decimal | None


@dataclass(frozen=True)
class ReviewLine:
    position: int
    posted_on: date | None
    description: str
    amount: Decimal
    page: int | None
    excluded: bool
    exclusion_reason: str | None
    box: Box | None = None  # TASK-334: where the line was printed on its page


@dataclass(frozen=True)
class StatementView:
    status: Literal["draft", "approved"]
    format: str
    account_kind: str
    issuer: str | None
    last4: str | None
    period_start: date | None
    period_end: date | None
    opening: Decimal | None
    closing: Decimal | None
    opening_source: BalanceSource | None
    closing_source: BalanceSource | None
    printed_opening: bool
    printed_closing: bool
    signs_inferred: bool
    signs_flipped: bool
    truncated: bool
    lines: list[ReviewLine]
    reconciliation: Reconciliation
    approved_by_name: str | None
    approved_at: datetime | None
    sources: dict[str, Source] | None = None  # TASK-334: where summary values were printed


def read_statement(content: bytes, media_type: str) -> ParsedStatement | None:
    """In the isolated child: the file's statement lines, or None."""
    if media_type == PDF:
        found = extract(content, PDF)
        if found.status != "extracted":
            return None
        lines = [[(line.text, line.box) for line in page] for page in found.page_lines]
        return from_pages(found.pages, lines)
    if media_type == CSV:
        return from_text_file(content)
    return None


def _money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return value.quantize(_CENTS)
    except InvalidOperation as exc:
        raise ReviewInvalid("amount") from exc


def apply(parsed: ParsedStatement, decisions: Decisions) -> StatementView:
    """The draft with the reviewer's decisions applied and reconciled, by code."""
    for position, reason in decisions.excluded.items():
        if not 1 <= len(reason.strip()) <= 200 or not 1 <= position <= len(parsed.lines):
            raise ReviewInvalid("excluded")
    if decisions.opening is not None and parsed.opening is not None:
        raise BalancePrinted("opening")
    if decisions.closing is not None and parsed.closing is not None:
        raise BalancePrinted("closing")
    if decisions.flip_signs and not parsed.signs_inferred:
        raise ReviewInvalid("flip")
    lines: list[StatementLine] = [
        replace(line, amount=-line.amount) if decisions.flip_signs else line
        for line in parsed.lines
    ]
    review = [
        ReviewLine(
            line.position,
            line.posted_on,
            line.description,
            line.amount,
            line.page,
            line.position in decisions.excluded,
            decisions.excluded[line.position].strip()
            if line.position in decisions.excluded
            else None,
            line.box,
        )
        for line in lines
    ]
    opening = parsed.opening if parsed.opening is not None else _money(decisions.opening)
    closing = parsed.closing if parsed.closing is not None else _money(decisions.closing)
    included = [line for line in lines if line.position not in decisions.excluded]
    return StatementView(
        "draft",
        parsed.format,
        parsed.account_kind,
        parsed.issuer,
        parsed.last4,
        parsed.period_start,
        parsed.period_end,
        opening,
        closing,
        None if opening is None else ("printed" if parsed.opening is not None else "entered"),
        None if closing is None else ("printed" if parsed.closing is not None else "entered"),
        parsed.opening is not None,
        parsed.closing is not None,
        parsed.signs_inferred,
        decisions.flip_signs,
        parsed.truncated,
        review,
        reconcile(opening, included, closing),
        None,
        None,
        parsed.sources,
    )


def _box(raw: list[float] | None) -> Box | None:
    if raw is None or len(raw) != 4:
        return None
    return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))


def _stored_sources(raw: dict[str, Any] | None) -> dict[str, Source] | None:  # Any: JSON
    if not raw:
        return None
    out: dict[str, Source] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            entry = cast(dict[str, object], value)
            box = _box(cast(list[float] | None, entry.get("box")))
            page = entry.get("page")
            if box is not None and isinstance(page, int):
                out[key] = Source(page, box)
    return out


async def _authorised_upload(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID
) -> str:
    """The upload's media type, after `evidence.read` on the item (in `uploads_for`)."""
    found = next(
        (
            u
            for u in await uploads_for(ctx, engagement_id, item_id)
            if u.evidence_version_id == version_id
        ),
        None,
    )
    if found is None:
        raise NotFound("evidence_version")
    return found.media_type


async def _parsed(ctx: AuthContext, version_id: UUID, media_type: str) -> ParsedStatement:
    view = await version_view(ctx.tenant, version_id)
    content = await storage.get(ctx.tenant_id, view.stored)
    try:
        parsed = await asyncio.to_thread(run_isolated, read_statement, content, media_type)
    except IsolationFailed as exc:
        raise NoTransactions("crashed") from exc
    if parsed is None or not parsed.lines:
        raise NoTransactions(str(version_id))
    return parsed


async def _approved(ctx: AuthContext, version_id: UUID) -> StatementView | None:
    async with tenant_session(ctx.tenant) as session:
        ds = await dataset_for_version(session, version_id)
        if ds is None:
            return None
        rows = await transactions_of(session, ds.id)
    names = await names_of([ds.approved_by])
    included = [
        StatementLine(r.position, r.posted_on, r.description, r.amount, r.page)
        for r in rows
        if not r.excluded
    ]
    return StatementView(
        "approved",
        ds.format,
        ds.account_kind,
        ds.issuer,
        ds.last4,
        ds.period_start,
        ds.period_end,
        ds.opening,
        ds.closing,
        "printed" if ds.opening_source == "printed" else "entered",
        "printed" if ds.closing_source == "printed" else "entered",
        ds.opening_source == "printed",
        ds.closing_source == "printed",
        False,
        ds.signs_flipped,
        False,
        [
            ReviewLine(
                r.position,
                r.posted_on,
                r.description,
                r.amount,
                r.page,
                r.excluded,
                r.exclusion_reason,
                _box(r.box),
            )
            for r in rows
        ],
        reconcile(ds.opening, included, ds.closing),
        names.get(ds.approved_by, ""),
        ds.created_at,
        _stored_sources(ds.field_sources),
    )


async def statement_for(
    ctx: AuthContext,
    engagement_id: UUID,
    item_id: UUID,
    version_id: UUID,
    decisions: Decisions | None = None,
) -> StatementView:
    """The approved transactions, or the draft read from the file (with decisions applied)."""
    media_type = await _authorised_upload(ctx, engagement_id, item_id, version_id)
    approved = await _approved(ctx, version_id)
    if approved is not None:
        return approved
    parsed = await _parsed(ctx, version_id, media_type)
    return apply(parsed, decisions or Decisions({}, False, None, None))


async def approve_statement(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID, decisions: Decisions
) -> StatementView:
    """A person approves the reconciled transactions; kept as approved."""
    media_type = await _authorised_upload(ctx, engagement_id, item_id, version_id)
    view = apply(await _parsed(ctx, version_id, media_type), decisions)
    if not view.reconciliation.reconciled:
        raise NotReconciled(str(view.reconciliation.difference))
    included = [line for line in view.lines if not line.excluded]
    if not included or view.opening is None or view.closing is None:
        raise NotReconciled("empty")
    async with uow(ctx.tenant) as tx:
        engagement = await lock_ref(tx, engagement_id)
        item = await read_item(ctx.tenant, engagement_id, item_id)
        await authorise(ctx, "statement.approve", item_resource(item, engagement.resource()))
        if await dataset_for_version(tx.session, version_id) is not None:
            raise AlreadyApproved(str(version_id))
        dataset_id = await insert_dataset(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            request_item_id=item_id,
            evidence_version_id=version_id,
            format=view.format,
            account_kind=view.account_kind,
            issuer=view.issuer,
            last4=view.last4,
            period_start=view.period_start,
            period_end=view.period_end,
            opening=view.opening,
            closing=view.closing,
            opening_source=view.opening_source,
            closing_source=view.closing_source,
            included_total=view.reconciliation.lines_total,
            line_count=len(view.lines),
            excluded_count=len(view.lines) - len(included),
            signs_flipped=view.signs_flipped,
            field_sources=(
                {k: {"page": v.page, "box": list(v.box)} for k, v in view.sources.items()}
                if view.sources
                else None
            ),
            approved_by=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
        )
        await insert_transactions(
            tx.session,
            [
                {
                    "tenant_id": ctx.tenant_id,
                    "dataset_id": dataset_id,
                    "position": line.position,
                    "posted_on": line.posted_on,
                    "description": line.description,
                    "amount": line.amount,
                    "page": line.page,
                    "excluded": line.excluded,
                    "exclusion_reason": line.exclusion_reason,
                    "box": list(line.box) if line.box is not None else None,
                }
                for line in view.lines
            ],
        )
        tx.record(
            "statement.approved",
            target=Target("statement_dataset", dataset_id),
            after=Ref(evidence_version=version_id, lines=len(included)),
        )
    found = await _approved(ctx, version_id)
    if found is None:
        raise NotFound("statement_dataset")
    return found
