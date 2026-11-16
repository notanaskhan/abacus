"""The confirmations lifecycle (A-08-T18; A-08 §3 F5; SPEC-657 F5; AUD-14; AU-C 505; DEC-5308;
amber).

Status: draft → (authorization_requested) → sent → responded → closed, with exception and
alternative_procedures on the way. Every act is a person's (INV-1) and audited; the events table
keeps the timeline AUD-14 shows.

- **Send** (`confirmation.send`): the address must be verified independently (`check_sendable`,
  409 `address_not_verified`). An `accrued_link` confirmation mints one link principal (purpose
  `confirmation`, 30 days) and records the link; a network or mail send is recorded as sent.
- **Second request**: once, while sent and unanswered. **No response after the second request**
  moves the confirmation to `alternative_procedures` (C4), never to Closed (`follow_up`).
- **Recorded response** (a network or mail reply): its confirmed total, agreement and the
  evidence it came in; `responded`.
- **Reconcile**: the reconciling items a person lists; code computes what is unreconciled
  (books + items - respondent; `compute.reconciliation`). A difference at or above clearly
  trivial is an `exception`; below it is noted and the confirmation can still close.
- **Accept the reconciliation** (`confirmation.accept_reconciliation`, a Manager): never the
  person who reconciled (409 `reconciler_cannot_accept`), against the seen content hash.
- **Alternative procedures**: what a person did instead, with citations.
- **Close** (`confirmation.close`): a responded confirmation closes only once a manager other
  than the reconciler accepted its reconciliation (C3); an alternative-procedures one only with a
  procedure recorded (C4). 409 `not_closable` otherwise.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import now as clock_now
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.assurance.compute.reconciliation import reconcile as compute_reconcile
from abacus.modules.assurance.confirmations_service import (
    LINK_PURPOSE,
    _of,  # pyright: ignore[reportPrivateUsage] -- the module's own scope check
    _person,  # pyright: ignore[reportPrivateUsage] -- the module's own person check
    check_sendable,
)
from abacus.modules.assurance.events import ConfirmationLinkRequested
from abacus.modules.communications.api import RespondentFacts
from abacus.modules.identity.api import AuthContext

LINK_DAYS: Final = 30
SECOND_REQUEST_AFTER: Final = timedelta(days=7)
ALTERNATIVE_AFTER: Final = timedelta(days=7)  # after the second request, still no answer
_AAD_ADDRESS: Final = "assurance.confirmation.address"
_AAD_NAME: Final = "assurance.confirmation.respondent"
_AAD_PROCEDURE: Final = "assurance.confirmation.alternative"
ZERO: Final = Decimal("0.00")


class NotInStatus(DomainConflict):
    code = "transition_not_available"


class ReconcilerCannotAccept(DomainConflict):
    code = "reconciler_cannot_accept"


class ContentChanged(DomainConflict):
    code = "content_changed"


class NotClosable(DomainConflict):
    code = "not_closable"


class SecondRequestSent(DomainConflict):
    code = "second_request_already_sent"


_ROW: Final = text(
    "SELECT id, engagement_id, work_item_id, channel, status, address_sealed, row_version "
    "FROM confirmations WHERE id = :c FOR UPDATE"
)
_STATUS: Final = text(
    "UPDATE confirmations SET status = :s, row_version = row_version + 1 WHERE id = :c"
)
_EVENT: Final = text(
    "INSERT INTO confirmation_events (tenant_id, confirmation_id, kind, actor_kind, actor_id) "
    "VALUES (:t, :c, :k, :ak, :a)"
)
_EVENTS: Final = text(
    "SELECT kind, at FROM confirmation_events WHERE confirmation_id = :c ORDER BY at"
)
_LINK: Final = text(
    "INSERT INTO confirmation_links (confirmation_id, tenant_id, principal_id) VALUES (:c, :t, :p)"
)
_BOOKS: Final = text(
    "SELECT coalesce(sum(book_amount), 0) FROM confirmation_lines WHERE confirmation_id = :c"
)
_RESPONSE: Final = text(
    "SELECT confirmed_total, agrees FROM confirmation_responses WHERE confirmation_id = :c"
)
_RECORD_RESPONSE: Final = text(
    "INSERT INTO confirmation_responses (tenant_id, confirmation_id, via, agrees, "
    "respondent_name_sealed, confirmed_total, explanation_sealed, attested, "
    "attachment_version_ids) VALUES (:t, :c, 'recorded', :agrees, :name, :total, NULL, false, "
    ":files)"
)
_RESPONDENT: Final = text("SELECT respondent_name_sealed FROM confirmations WHERE id = :c")
_ITEM: Final = text(
    "INSERT INTO reconciliation_items (tenant_id, confirmation_id, kind, amount, citation_ids, "
    "created_by) VALUES (:t, :c, :k, :a, :cites, :u)"
)
_ITEMS: Final = text(
    "SELECT kind, amount, created_by FROM reconciliation_items WHERE confirmation_id = :c "
    "ORDER BY created_at, id"
)
_DECIDE: Final = text(
    "INSERT INTO confirmation_decisions (tenant_id, confirmation_id, decision, decided_by, "
    "actor_kind, content_hash) VALUES (:t, :c, :d, :u, 'human', :h)"
)
_DECISIONS: Final = text(
    "SELECT decision, decided_by, content_hash FROM confirmation_decisions "
    "WHERE confirmation_id = :c ORDER BY decided_at"
)
_ALTERNATIVE: Final = text(
    "INSERT INTO alternative_procedures (tenant_id, confirmation_id, procedure_sealed, "
    "citation_ids, performed_by) VALUES (:t, :c, :p, :cites, :u)"
)
_ALTERNATIVES: Final = text(
    "SELECT count(*) FROM alternative_procedures WHERE confirmation_id = :c"
)
_CT: Final = text(
    "SELECT ct FROM materiality_versions WHERE engagement_id = :e AND status = 'decided' "
    "ORDER BY version_no DESC LIMIT 1"
)


async def _locked(tx: UnitOfWork, confirmation_id: UUID) -> dict[str, object]:
    row = (await tx.session.execute(_ROW, {"c": confirmation_id})).mappings().first()
    if row is None:
        raise NotFound("confirmation")
    return dict(row)


def _need(row: dict[str, object], *statuses: str) -> None:
    if row["status"] not in statuses:
        raise NotInStatus(facts={"status": str(row["status"])})


async def _event(tx: UnitOfWork, ctx: AuthContext, confirmation_id: UUID, kind: str) -> None:
    await tx.session.execute(
        _EVENT,
        {
            "t": ctx.tenant_id,
            "c": confirmation_id,
            "k": kind,
            "ak": "human",
            "a": str(ctx.user_id),
        },
    )


async def _move(tx: UnitOfWork, confirmation_id: UUID, status: str) -> None:
    await tx.session.execute(_STATUS, {"s": status, "c": confirmation_id})
    tx.record("confirmation.status_changed", target=Target("confirmation", confirmation_id))


async def send(ctx: AuthContext, confirmation_id: UUID) -> UUID:
    _person(ctx, "confirmation.send")
    await _of(ctx, confirmation_id, "confirmation.send")
    await check_sendable(ctx, confirmation_id)
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, confirmation_id)
        # A-08-T18 (DEC-5324): one awaiting its client's authorization sends once it completes.
        _need(row, "draft")
        if row["channel"] == "accrued_link":
            # The link is minted and emailed at delivery (communications), its token never
            # stored: `link_at_delivery` below.
            tx.emit(ConfirmationLinkRequested(confirmation_id=confirmation_id))
        await _event(tx, ctx, confirmation_id, "sent")
        await _move(tx, confirmation_id, "sent")
        tx.record("confirmation.sent", target=Target("confirmation", confirmation_id))
    return confirmation_id


async def second_request(ctx: AuthContext, confirmation_id: UUID) -> UUID:
    _person(ctx, "confirmation.send")
    await _of(ctx, confirmation_id, "confirmation.send")
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, confirmation_id)
        _need(row, "sent")
        kinds = [k for k, _ in (await tx.session.execute(_EVENTS, {"c": confirmation_id})).all()]
        if "second_request" in kinds:
            raise SecondRequestSent(facts={"confirmation": str(confirmation_id)})
        await _event(tx, ctx, confirmation_id, "second_request")
        tx.record("confirmation.second_request", target=Target("confirmation", confirmation_id))
    return confirmation_id


def follow_up_step(events: list[tuple[str, datetime]], status: str, now: datetime) -> str | None:
    """The follow-up's next step, by code: `second_request` 7 days after sending, then
    `alternative_procedures` 7 days after the second request; None when nothing is due (C4 never
    closes by itself)."""
    if status != "sent":
        return None
    sent = [at for k, at in events if k == "sent"]
    second = [at for k, at in events if k == "second_request"]
    if any(k == "responded" for k, _ in events) or not sent:
        return None
    if not second:
        return "second_request" if now - sent[-1] >= SECOND_REQUEST_AFTER else None
    return "alternative_procedures" if now - second[-1] >= ALTERNATIVE_AFTER else None


async def follow_up(
    ctx: AuthContext, confirmation_id: UUID, now: datetime | None = None
) -> str | None:
    """Apply the follow-up's due step (the person's act or the follow-up workflow's tick)."""
    at = now or await clock_now(ctx.tenant)
    async with tenant_session(ctx.tenant) as session:
        status = await session.scalar(
            text("SELECT status FROM confirmations WHERE id = :c"), {"c": confirmation_id}
        )
        events = [
            (str(k), cast(datetime, a))
            for k, a in (await session.execute(_EVENTS, {"c": confirmation_id})).all()
        ]
    step = follow_up_step(events, str(status), at)
    if step == "second_request":
        await second_request(ctx, confirmation_id)
    elif step == "alternative_procedures":
        _person(ctx, "confirmation.record_alternative")
        await _of(ctx, confirmation_id, "confirmation.record_alternative")
        async with uow(ctx.tenant) as tx:
            row = await _locked(tx, confirmation_id)
            _need(row, "sent")
            await _move(tx, confirmation_id, "alternative_procedures")
    return step


async def record_response(
    ctx: AuthContext,
    confirmation_id: UUID,
    *,
    agrees: bool,
    confirmed_amounts: list[Decimal],
    evidence_version_ids: list[UUID],
) -> UUID:
    _person(ctx, "confirmation.record_response")
    await _of(ctx, confirmation_id, "confirmation.record_response")
    total = sum((Decimal(a) for a in confirmed_amounts), ZERO).quantize(Decimal("0.01"))
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, confirmation_id)
        _need(row, "sent", "alternative_procedures")
        name = await tx.session.scalar(_RESPONDENT, {"c": confirmation_id})
        await tx.session.execute(
            _RECORD_RESPONSE,
            {
                "t": ctx.tenant_id,
                "c": confirmation_id,
                "agrees": agrees,
                "name": name,
                "total": total,
                "files": list(evidence_version_ids),
            },
        )
        await _event(tx, ctx, confirmation_id, "responded")
        await _move(tx, confirmation_id, "responded")
    return confirmation_id


async def _ct(ctx: AuthContext, engagement_id: UUID) -> Decimal:
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(_CT, {"e": engagement_id})
    return Decimal(found) if found is not None else ZERO


def content_hash(books: Decimal, respondent: Decimal, items: list[tuple[str, Decimal]]) -> str:
    body = json.dumps(
        {"b": str(books), "r": str(respondent), "i": [[k, str(a)] for k, a in items]},
        sort_keys=True,
    )
    return hashlib.sha256(body.encode()).hexdigest()


async def reconcile(
    ctx: AuthContext, confirmation_id: UUID, items: list[tuple[str, Decimal, list[UUID]]]
) -> dict[str, object]:
    """The person's items; code computes the unreconciled amount and whether it is below CT."""
    _person(ctx, "confirmation.reconcile")
    _, engagement_id = await _of(ctx, confirmation_id, "confirmation.reconcile")
    ct = await _ct(ctx, engagement_id)
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, confirmation_id)
        _need(row, "responded", "exception")
        response = (await tx.session.execute(_RESPONSE, {"c": confirmation_id})).first()
        if response is None:
            raise NotInStatus(facts={"status": "no_response"})
        for kind, amount, cites in items:
            await tx.session.execute(
                _ITEM,
                {
                    "t": ctx.tenant_id,
                    "c": confirmation_id,
                    "k": kind[:60],
                    "a": amount,
                    "cites": list(cites),
                    "u": ctx.user_id,
                },
            )
        books = Decimal(await tx.session.scalar(_BOOKS, {"c": confirmation_id}) or 0)
        listed = [
            (str(k), Decimal(a))
            for k, a, _ in (await tx.session.execute(_ITEMS, {"c": confirmation_id})).all()
        ]
        result = compute_reconcile(books, Decimal(response[0]), [a for _, a in listed], ct or None)
        exception = not result.ties and not bool(result.below_clearly_trivial)
        if exception:
            await _move(tx, confirmation_id, "exception")
        tx.record(
            "confirmation.reconciled",
            target=Target("confirmation", confirmation_id),
            after=Ref(items=len(listed), ties=int(result.ties)),
        )
    return {
        "books": books,
        "respondent": Decimal(response[0]),
        "unreconciled": result.unreconciled,
        "ties": result.ties,
        "below_clearly_trivial": result.below_clearly_trivial,
        "exception": exception,
        "content_hash": content_hash(books, Decimal(response[0]), listed),
    }


async def accept_reconciliation(ctx: AuthContext, confirmation_id: UUID, seen_hash: str) -> UUID:
    """A Manager accepts; never the person who listed the items (C3)."""
    _person(ctx, "confirmation.accept_reconciliation")
    await _of(ctx, confirmation_id, "confirmation.accept_reconciliation")
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, confirmation_id)
        _need(row, "responded", "exception")
        rows = (await tx.session.execute(_ITEMS, {"c": confirmation_id})).all()
        reconcilers = {cast(UUID, r[2]) for r in rows}
        if ctx.user_id in reconcilers:
            raise ReconcilerCannotAccept(facts={"confirmation": str(confirmation_id)})
        books = Decimal(await tx.session.scalar(_BOOKS, {"c": confirmation_id}) or 0)
        response = (await tx.session.execute(_RESPONSE, {"c": confirmation_id})).first()
        if response is None:
            raise NotInStatus(facts={"status": "no_response"})
        digest = content_hash(
            books, Decimal(response[0]), [(str(r[0]), Decimal(r[1])) for r in rows]
        )
        if digest != seen_hash:
            raise ContentChanged(facts={"confirmation": str(confirmation_id)})
        await tx.session.execute(
            _DECIDE,
            {
                "t": ctx.tenant_id,
                "c": confirmation_id,
                "d": "accept_reconciliation",
                "u": ctx.user_id,
                "h": digest,
            },
        )
        tx.record(
            "confirmation.reconciliation_accepted", target=Target("confirmation", confirmation_id)
        )
    return confirmation_id


async def record_alternative(
    ctx: AuthContext, confirmation_id: UUID, description: str, citation_ids: list[UUID]
) -> UUID:
    _person(ctx, "confirmation.record_alternative")
    await _of(ctx, confirmation_id, "confirmation.record_alternative")
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, confirmation_id)
        _need(row, "sent", "alternative_procedures", "exception")
        await tx.session.execute(
            _ALTERNATIVE,
            {
                "t": ctx.tenant_id,
                "c": confirmation_id,
                "p": await seal(ctx.tenant_id, description.encode(), _AAD_PROCEDURE),
                "cites": list(citation_ids),
                "u": ctx.user_id,
            },
        )
        if row["status"] == "sent":
            await _move(tx, confirmation_id, "alternative_procedures")
        tx.record(
            "confirmation.alternative_recorded", target=Target("confirmation", confirmation_id)
        )
    return confirmation_id


async def close(ctx: AuthContext, confirmation_id: UUID) -> UUID:
    """C3: responded closes only after a manager (not the reconciler) accepted; C4: an
    alternative-procedures confirmation only with a procedure recorded."""
    _person(ctx, "confirmation.close")
    await _of(ctx, confirmation_id, "confirmation.close")
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, confirmation_id)
        _need(row, "responded", "alternative_procedures", "exception")
        decisions = (await tx.session.execute(_DECISIONS, {"c": confirmation_id})).all()
        accepted = [d for d in decisions if d[0] == "accept_reconciliation"]
        alternatives = int(await tx.session.scalar(_ALTERNATIVES, {"c": confirmation_id}) or 0)
        if row["status"] == "alternative_procedures":
            if alternatives == 0:
                raise NotClosable(facts={"reason": "alternative_procedure_required"})
        elif not accepted:
            raise NotClosable(facts={"reason": "reconciliation_not_accepted"})
        digest = (
            accepted[-1][2]
            if accepted
            else hashlib.sha256(str(confirmation_id).encode()).hexdigest()
        )
        await tx.session.execute(
            _DECIDE,
            {
                "t": ctx.tenant_id,
                "c": confirmation_id,
                "d": "close",
                "u": ctx.user_id,
                "h": digest,
            },
        )
        await _move(tx, confirmation_id, "closed")
        tx.record("confirmation.closed", target=Target("confirmation", confirmation_id))
    return confirmation_id


# --- the respondent's link at delivery (A-08-T18; DEC-5324) --------------------------------------

_LINK_FACTS: Final = text(
    "SELECT c.status, c.channel, c.respondent_org, c.address_sealed, c.engagement_id, "
    "(SELECT e.actor_id FROM confirmation_events e WHERE e.confirmation_id = c.id "
    "AND e.kind = 'sent' AND e.actor_kind = 'human' ORDER BY e.at DESC LIMIT 1) AS sent_by "
    "FROM confirmations c WHERE c.id = :c"
)


async def _link_row(tenant: TenantContext, confirmation_id: UUID) -> dict[str, object] | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_LINK_FACTS, {"c": confirmation_id})).mappings().first()
    if row is None or row["status"] != "sent" or row["channel"] != "accrued_link":
        return None
    return dict(row)


async def link_facts(tenant: TenantContext, confirmation_id: UUID) -> RespondentFacts | None:
    """What the request email needs: the address (opened here, for communications only), the
    respondent's organisation, the client and the link's last day."""
    from abacus.modules.engagements.api import engagement_label

    row = await _link_row(tenant, confirmation_id)
    if row is None:
        return None
    address = (
        await open_sealed(tenant.tenant_id, cast(bytes, row["address_sealed"]), _AAD_ADDRESS)
    ).decode()
    label = await engagement_label(tenant, cast(UUID, row["engagement_id"]))
    last_day = (await clock_now(tenant) + timedelta(days=LINK_DAYS)).date()
    return RespondentFacts(
        address=address,
        respondent_org=str(row["respondent_org"]),
        organisation_name="" if label is None else label.client_name,
        due_date=f"{last_day:%B} {last_day.day}, {last_day.year}",
    )


async def link_at_delivery(tenant: TenantContext, confirmation_id: UUID) -> str | None:
    """The link principal for a sent confirmation, minted now (its hash stored, the raw token
    returned to the deliverer only) and named on `confirmation_links`."""
    from abacus.modules.identity.api import live_principal, mint_link

    row = await _link_row(tenant, confirmation_id)
    if row is None or row["sent_by"] is None:
        return None
    address = (
        await open_sealed(tenant.tenant_id, cast(bytes, row["address_sealed"]), _AAD_ADDRESS)
    ).decode()
    async with uow(tenant) as tx:
        token = await mint_link(
            tx,
            tenant_id=tenant.tenant_id,
            purpose=LINK_PURPOSE,
            subject_id=confirmation_id,
            email=address,
            created_by=UUID(str(row["sent_by"])),
            valid_for=timedelta(days=LINK_DAYS),
        )
        principal = await live_principal(tx, LINK_PURPOSE, confirmation_id)
        await tx.session.execute(
            _LINK, {"c": confirmation_id, "t": tenant.tenant_id, "p": principal}
        )
    return token


# --- revoke the link and the exception prefill (A-08-T18; DEC-5324) ------------------------------

_LIVE_LINKS: Final = text(
    "SELECT l.principal_id FROM confirmation_links l WHERE l.confirmation_id = :c "
    "AND l.principal_id IS NOT NULL"
)


async def revoke(ctx: AuthContext, confirmation_id: UUID) -> UUID:
    """A person ends a sent confirmation's link (a wrong address, a replaced respondent): every
    link principal it issued is revoked and the page reads expired; the status is unchanged and
    a new send issues a new link. 409 `not_in_status` unless Sent."""
    _person(ctx, "confirmation.send")
    await _of(ctx, confirmation_id, "confirmation.send")
    from abacus.modules.identity.api import revoke_link

    async with uow(ctx.tenant) as tx:
        row = await _locked(tx, confirmation_id)
        _need(row, "sent")
        principals = [
            cast(UUID, r[0])
            for r in (await tx.session.execute(_LIVE_LINKS, {"c": confirmation_id}))
        ]
        for principal in principals:
            await revoke_link(tx, principal)
        await _event(tx, ctx, confirmation_id, "revoked")
        tx.record(
            "confirmation.link_revoked",
            target=Target("confirmation", confirmation_id),
            after=Ref(n=len(principals)),
        )
    return confirmation_id


async def exception_prefill(ctx: AuthContext, confirmation_id: UUID) -> dict[str, object]:
    """SHL-15's prefill from the reconciliation as recorded (read only): the unreconciled amount
    by code and where it goes, a finding at or above clearly trivial, else a misstatement."""
    _, engagement_id = await _of(ctx, confirmation_id, "finding.create")
    ct = await _ct(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        response = (await session.execute(_RESPONSE, {"c": confirmation_id})).first()
        if response is None:
            raise NotInStatus(facts={"status": "no_response"})
        books = Decimal(await session.scalar(_BOOKS, {"c": confirmation_id}) or 0)
        items = [Decimal(a) for _, a, _ in (await session.execute(_ITEMS, {"c": confirmation_id}))]
    result = compute_reconcile(books, Decimal(response[0]), items, ct or None)
    below = bool(result.below_clearly_trivial)
    return {
        "difference": result.unreconciled,
        "below_clearly_trivial": below,
        "route": "misstatement" if below else "finding",
    }
