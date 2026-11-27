"""Amendments (T-08-T30; TASK-9005; SPEC-710 §3.6 AC6.1 to AC6.4; TAX-16 a, b, d, f; ADR-004;
DEC-77; DEC-6011; amber). Dark behind `tax.amendments`.

- **Create** (`create`, `POST /v1/tax-returns/{id}/amendments`, `amendment.create`): only from an
  Accepted return, one open amendment each (409 `amendment_exists`). A new linked return (form
  `1040x` for a 1040; `amends_return_id` the original) on the original's engagement, and an
  `amendments` row naming the original's **approved checkpoint as the as-filed baseline** (409
  `baseline_unavailable` without one). The original is never written: not its row, its lines or
  its checkpoint.
- **Read** (`view`): as filed is the original's approved engine summary, as amended the new
  return's newest (an engine import; until one exists the lines show no change), per jurisdiction,
  computed by code (`compute.amendment`, ADR-050). Each line is labelled with its source (DEC-77:
  `engine`). The Part II explanation is its newest version.
- **Part II** (`explain`): a person's insert-only version at the row version they saw (409
  `version_conflict`); an agent's draft arrives as a suggestion (T-08-T34), never here.
- **Route for approval** (`route_for_approval`): the amendment's signer is asked (C16
  `amendment.approval_requested`, HOME-02's `amendment_approval` gate); the approval itself is the
  amendment return's final approval through `tax/approval.py` (T-08-T33's red path), and its 8879
  is the amendment's own, so the original's signed 8879 never covers it.
- **Supersession** (`on_filing_acknowledged`): when the amendment's federal transmission is
  accepted, one insert-only `return_supersessions` row marks the original Superseded; nothing
  before that ack does.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import Row, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.tax.compute import amendment as calc

TARGET: Final = "amendment"
AMENDED_FORM: Final = {"1040": "1040x"}
_JURISDICTION_TAG: Final = {"federal": "US", "il": "IL"}


class AmendmentExists(DomainConflict):
    code = "amendment_exists"


class BaselineUnavailable(DomainConflict):
    code = "baseline_unavailable"


class NotAccepted(DomainConflict):
    code = "return_not_accepted"


class VersionConflict(DomainConflict):
    code = "version_conflict"


class AmendmentApprovalRequested(DomainEvent):
    event_type: ClassVar[str] = "amendment.approval_requested"
    tax_return_id: UUID
    amendment_id: UUID
    recipient_user_ids: list[UUID]
    by_user: UUID


@dataclass(frozen=True)
class AmendmentView:
    amendment_id: UUID
    kind: str
    work_item_id: UUID
    original_work_item_id: UUID
    jurisdictions: tuple[str, ...]
    amended: calc.Amended
    explanation: str | None
    explanation_author: UUID | None
    status: str
    original_superseded: bool
    row_version: int


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


_RETURN: Final = text(
    "SELECT work_item_id, engagement_id, client_entity_id, form, tax_year, status, "
    "amends_return_id FROM tax_returns WHERE work_item_id = :id"
)


async def _authorised(ctx: AuthContext, return_id: UUID, action: str) -> Row[Any]:
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_RETURN, {"id": return_id})).first()
    if row is None:
        raise NotFound("tax_return")
    resource = await engagement_resource_of(ctx.tenant, cast(UUID, row.engagement_id))
    try:
        await authorise(ctx, action, replace(resource, work_item_id=return_id))
    except Forbidden:
        if action == "tax_return.read":
            raise NotFound("tax_return") from None  # a walled return answers 404 (INV-3)
        raise
    return row


# --- create --------------------------------------------------------------------------------------

_OPEN: Final = text("SELECT id FROM amendments WHERE original_work_item_id = :o")
_NEW: Final = text(
    "INSERT INTO amendments (tenant_id, engagement_id, work_item_id, original_work_item_id, "
    "kind, jurisdictions, baseline_checkpoint_id, created_by) VALUES (:t, :e, :w, :o, :k, :j, "
    ":b, :by) RETURNING id"
)


async def create(
    ctx: AuthContext, original_id: UUID, *, kind: str, jurisdictions: list[str]
) -> UUID:
    from abacus.modules.engagements.api import create_work_item
    from abacus.modules.review.api import current_checkpoint

    _human(ctx, "amendment.create")
    row = await _authorised(ctx, original_id, "amendment.create")
    if row.status != "accepted":
        raise NotAccepted(facts={"status": str(row.status)})
    form = str(row.form)
    if form not in AMENDED_FORM:
        raise NotAccepted(facts={"form": form})
    async with tenant_session(ctx.tenant) as session:
        if await session.scalar(_OPEN, {"o": original_id}) is not None:
            raise AmendmentExists(facts={"original": str(original_id)})
    baseline = await current_checkpoint(ctx.tenant, "tax_return", original_id)
    if baseline is None:
        raise BaselineUnavailable(facts={"original": str(original_id)})
    year = int(row.tax_year)
    engagement_id = cast(UUID, row.engagement_id)
    work_item_id = await create_work_item(
        ctx,
        engagement_id,
        "tax_return",
        name=f"{year} Form {AMENDED_FORM[form].upper().replace('X', '-X')}"[:200],
        client_entity_id=cast(UUID, row.client_entity_id),
        details={
            "form": AMENDED_FORM[form],
            "tax_year": year,
            "amends_return_id": str(original_id),
        },
        authorised_under="amendment.create",
    )
    async with uow(ctx.tenant) as tx:
        amendment_id = cast(
            UUID,
            await tx.session.scalar(
                _NEW,
                {"t": ctx.tenant_id, "e": engagement_id, "w": work_item_id, "o": original_id,
                 "k": kind, "j": [_JURISDICTION_TAG[j] for j in jurisdictions],
                 "b": baseline[0], "by": ctx.user_id},
            ),
        )  # fmt: skip
        tx.record(
            "amendment.created",
            target=Target(TARGET, amendment_id),
            after=Ref(original=original_id, amendment_return=work_item_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return amendment_id


# --- read ----------------------------------------------------------------------------------------

_AMENDMENT: Final = text(
    "SELECT a.id, a.kind, a.work_item_id, a.original_work_item_id, a.jurisdictions, "
    "a.row_version, t.status, t.engagement_id FROM amendments a JOIN tax_returns t "
    "ON t.work_item_id = a.work_item_id WHERE a.id = :a"
)
# The newest approved engine summary (approved_at is NOT NULL on every row, 0403).
_SUMMARY: Final = text(
    "SELECT lines FROM return_engine_summaries WHERE work_item_id = :id AND kind <> 'pro_forma' "
    "ORDER BY approved_at DESC LIMIT 1"
)
_EXPLANATION: Final = text(
    "SELECT text, created_by FROM amendment_explanation_versions WHERE amendment_id = :a "
    "ORDER BY version_no DESC LIMIT 1"
)
_SUPERSEDED: Final = text("SELECT 1 FROM return_supersessions WHERE original_work_item_id = :o")


def amounts(lines: object) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    raw = json.loads(lines) if isinstance(lines, str) else lines
    for item in cast(list[object], raw or []):
        if not isinstance(item, dict):
            continue
        line = cast(dict[str, object], item)
        key, amount = line.get("line_key"), line.get("amount")
        if isinstance(key, str) and amount is not None:
            try:
                out[key] = Decimal(str(amount))
            except InvalidOperation:
                continue
    return out


_STATUS_OF: Final = {"accepted": "filed", "filed": "filed", "approved": "approved"}


async def view(ctx: AuthContext, amendment_id: UUID, jurisdiction: str) -> AmendmentView:
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_AMENDMENT, {"a": amendment_id})).first()
    if row is None:
        raise NotFound(TARGET)
    await _authorised(ctx, row.work_item_id, "tax_return.read")
    async with tenant_session(ctx.tenant) as session:
        filed = await session.scalar(_SUMMARY, {"id": row.original_work_item_id})
        amended = await session.scalar(_SUMMARY, {"id": row.work_item_id})
        latest = (await session.execute(_EXPLANATION, {"a": amendment_id})).first()
        superseded = await session.scalar(_SUPERSEDED, {"o": row.original_work_item_id})
    found = calc.amend(
        cast(calc.Jurisdiction, jurisdiction),
        amounts(filed),
        None if amended is None else amounts(amended),
    )
    return AmendmentView(
        amendment_id=row.id,
        kind=str(row.kind),
        work_item_id=row.work_item_id,
        original_work_item_id=row.original_work_item_id,
        jurisdictions=tuple(
            {v: k for k, v in _JURISDICTION_TAG.items()}[j] for j in row.jurisdictions
        ),
        amended=found,
        explanation=None if latest is None else str(latest.text),
        explanation_author=None if latest is None else latest.created_by,
        status=_STATUS_OF.get(str(row.status), "draft"),
        original_superseded=superseded is not None,
        row_version=int(row.row_version),
    )


# --- Part II -------------------------------------------------------------------------------------

_NEXT: Final = text(
    "SELECT coalesce(max(version_no), 0) + 1 FROM amendment_explanation_versions "
    "WHERE amendment_id = :a"
)
_EXPLAIN: Final = text(
    "INSERT INTO amendment_explanation_versions (tenant_id, amendment_id, version_no, text, "
    "author_kind, created_by) VALUES (:t, :a, :n, :text, 'human', :by)"
)
_BUMP: Final = text(
    "UPDATE amendments SET row_version = row_version + 1 WHERE id = :a AND row_version = :seen "
    "RETURNING row_version"
)


async def explain(ctx: AuthContext, amendment_id: UUID, body: str, seen_version: int) -> None:
    _human(ctx, "amendment.edit")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_AMENDMENT, {"a": amendment_id})).first()
    if row is None:
        raise NotFound(TARGET)
    await _authorised(ctx, row.work_item_id, "amendment.edit")
    async with uow(ctx.tenant) as tx:
        if await tx.session.scalar(_BUMP, {"a": amendment_id, "seen": seen_version}) is None:
            raise VersionConflict(facts={"row_version": int(row.row_version)})
        n = int(await tx.session.scalar(_NEXT, {"a": amendment_id}) or 1)
        await tx.session.execute(
            _EXPLAIN,
            {"t": ctx.tenant_id, "a": amendment_id, "n": n, "text": body.strip()[:4000],
             "by": ctx.user_id},
        )  # fmt: skip
        tx.record(
            "amendment.explained",
            target=Target(TARGET, amendment_id),
            after=Ref(version=n),
            scope=Scope(engagement_id=row.engagement_id, work_item_id=row.work_item_id),
        )


# --- routing and supersession --------------------------------------------------------------------


async def route_for_approval(ctx: AuthContext, amendment_id: UUID) -> UUID:
    """Ask the amendment's signer for final approval (they approve the return through
    `tax/approval.py`); answers the signer."""
    from abacus.modules.tax.approval import signer_for

    _human(ctx, "amendment.edit")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_AMENDMENT, {"a": amendment_id})).first()
        client = None if row is None else await session.scalar(
            text("SELECT client_id FROM engagements WHERE id = :e"), {"e": row.engagement_id}
        )  # fmt: skip
    if row is None or client is None:
        raise NotFound(TARGET)
    await _authorised(ctx, row.work_item_id, "amendment.edit")
    signer = await signer_for(ctx.tenant_id, cast(UUID, client))
    if signer is None:
        raise NotFound("signer")
    async with uow(ctx.tenant) as tx:
        tx.record(
            "amendment.routed",
            target=Target(TARGET, amendment_id),
            after=Ref(signer=signer),
            scope=Scope(engagement_id=row.engagement_id, work_item_id=row.work_item_id),
        )
        tx.emit(
            AmendmentApprovalRequested(
                tax_return_id=row.work_item_id, amendment_id=amendment_id,
                recipient_user_ids=[signer], by_user=ctx.user_id,
            )
        )  # fmt: skip
    return signer


_ACCEPTED_ACK: Final = text(
    "SELECT id FROM efile_acks WHERE return_id = :w AND jurisdiction = :federal "
    "AND status = 'accepted' ORDER BY received_at DESC LIMIT 1"
)
_AMENDS: Final = text("SELECT amends_return_id FROM tax_returns WHERE work_item_id = :w")
_SUPERSEDE: Final = text(
    "INSERT INTO return_supersessions (tenant_id, original_work_item_id, "
    "superseded_by_work_item_id, ack_id) VALUES (:t, :o, :w, :ack) "
    "ON CONFLICT (tenant_id, original_work_item_id) DO NOTHING RETURNING id"
)


async def on_filing_acknowledged(event: OutboxEvent) -> None:
    """An amendment's accepted federal ack supersedes its original (once, insert-only)."""
    from abacus.kernel.uow import MissingAuditEvent
    from abacus.modules.tax.filing import FEDERAL

    if event.payload.get("status") != "accepted":
        return
    raw = event.payload.get("return_id")
    if raw is None:
        return
    return_id = UUID(str(raw))
    tenant = TenantContext(event.tenant_id, "system", "tax:amendments")
    async with tenant_session(tenant) as session:
        original = await session.scalar(_AMENDS, {"w": return_id})
        ack = (
            None
            if original is None
            else await session.scalar(_ACCEPTED_ACK, {"w": return_id, "federal": FEDERAL})
        )
    if original is None or ack is None:
        return
    try:
        async with uow(tenant) as tx:
            made = await tx.session.scalar(
                _SUPERSEDE, {"t": event.tenant_id, "o": original, "w": return_id, "ack": ack}
            )
            if made is None:
                raise MissingAuditEvent  # already superseded: nothing to record
            tx.record(
                "tax_return.superseded",
                target=Target("tax_return", cast(UUID, original)),
                after=Ref(by=return_id, ack=ack),
            )
    except MissingAuditEvent:
        return


__all__ = [
    "AmendmentExists",
    "AmendmentView",
    "BaselineUnavailable",
    "NotAccepted",
    "VersionConflict",
    "amounts",
    "create",
    "explain",
    "on_filing_acknowledged",
    "route_for_approval",
    "view",
]
