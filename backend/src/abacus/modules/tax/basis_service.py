"""Basis and §754 (T-06-T35; TASK-8833; T-06 F3; SPEC-702; TXP-08 a to e, POR-08; ADR-005,
ADR-050; DEC-4906, DEC-5835). Amber.

- **Views.** `basis` (each partner's inside share, outside basis and the difference; 4 of 5
  reconcile) and `s752` (each partner's share of qualified nonrecourse and other nonrecourse
  liabilities) from `basis_schedules` and `liability_shares`, figures as E8 stored them.
- **The §754 card** (`basis_adjustment_election`, C3, reserved to the engagement partner,
  DEC-4906) is raised by a person on the return (`decision.raise`); code computes its options.
- **Send to the client** (`decision.send_to_client`): the election is the partnership's, so the
  partner sends the question to the client's owner as a C18 client decision (POR-08, kind
  `section_754`, decider rule: the owner grant only). One send per card: a second answers 409
  `decision_already_sent`. The request links the return's existing waiting-on-client issue (none
  is created). The agent can neither send nor decide (the routes are a live person's; the C18
  decide is a client human's).
- **The client's answer** is recorded as the client's decision (`tax_decision_answers`: the
  contact, the grant, the decider basis), E8 recomputes the subject partner's basis with the
  §743(b) step-up when the client elects, and TAX-11's statement flag follows; the partner then
  records it on the card (the §754 statement stays pending until the card is decided, T-06-T37).
  Only the contact the request names sees it in the portal.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.tax.entity_depth_errors import DecisionAlreadySent

READ: Final = "basis.read"
RAISE: Final = "decision.raise"
SEND: Final = "decision.send_to_client"
KIND: Final = "section_754"
TARGET: Final = "tax_decision_request"
ZERO: Final = Decimal(0)
Section754 = Literal["open", "sent_to_client", "decided"]


class DecisionCardUnknown(DomainConflict):
    code = "decision_card_unknown"


@dataclass(frozen=True)
class PartnerBasis:
    partner_id: UUID
    name: str
    inside: Decimal
    outside: Decimal
    reconciled: bool
    qualified_nonrecourse: Decimal | None
    other_nonrecourse: Decimal | None


@dataclass(frozen=True)
class BasisView:
    partners: tuple[PartnerBasis, ...]
    reconciled: int
    inside_total: Decimal
    outside_total: Decimal
    section_754: Section754


_BASIS: Final = text(
    "SELECT b.partner_id, coalesce(p.display_name, 'Partner') AS name, b.inside_share, "
    "b.outside_basis, b.status FROM basis_schedules b LEFT JOIN partners p ON p.id = b.partner_id "
    "WHERE b.work_item_id = :r ORDER BY p.ord, p.display_name"
)
_SHARES: Final = text(
    "SELECT partner_id, liability_kind, share_eop FROM liability_shares WHERE work_item_id = :r"
)
_REQUEST_OF_CARD: Final = text(
    "SELECT q.id, a.id AS answered FROM tax_decision_requests q LEFT JOIN tax_decision_answers a "
    "ON a.request_id = q.id WHERE q.card_id = :c"
)


async def _loaded(ctx: AuthContext, return_id: UUID) -> tuple[UUID, object]:
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    return loaded.facts.engagement_id, await return_resource(ctx, loaded)


async def section_754_state(tenant: TenantContext, return_id: UUID) -> Section754:
    from abacus.modules.review.api import awaiting_cards
    from abacus.modules.tax.entity_decisions import SECTION_754

    awaiting = await awaiting_cards(tenant, return_id, [SECTION_754])
    if not awaiting:
        async with tenant_session(tenant) as session:
            sent = await session.scalar(
                text("SELECT count(*) FROM tax_decision_requests WHERE work_item_id = :r"),
                {"r": return_id},
            )
        return "decided" if sent else "open"
    async with tenant_session(tenant) as session:
        found = (await session.execute(_REQUEST_OF_CARD, {"c": awaiting[0].card_id})).first()
    return "open" if found is None else "sent_to_client"


async def basis(ctx: AuthContext, return_id: UUID, partner: UUID | None = None) -> BasisView:
    _engagement, resource = await _loaded(ctx, return_id)
    await authorise(ctx, READ, cast(Any, resource))
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_BASIS, {"r": return_id})).all()
        shares = (await session.execute(_SHARES, {"r": return_id})).all()
    by_partner: dict[UUID, dict[str, Decimal]] = {}
    for s in shares:
        by_partner.setdefault(UUID(str(s.partner_id)), {})[str(s.liability_kind)] = Decimal(
            s.share_eop
        )
    partners = tuple(
        PartnerBasis(
            UUID(str(r.partner_id)),
            str(r.name),
            Decimal(r.inside_share),
            Decimal(r.outside_basis),
            str(r.status) == "reconciled",
            by_partner.get(UUID(str(r.partner_id)), {}).get("qualified_nonrecourse"),
            by_partner.get(UUID(str(r.partner_id)), {}).get("nonrecourse"),
        )
        for r in rows
        if partner is None or UUID(str(r.partner_id)) == partner
    )
    return BasisView(
        partners,
        sum(1 for p in partners if p.reconciled),
        sum((p.inside for p in partners), ZERO),
        sum((p.outside for p in partners), ZERO),
        await section_754_state(ctx.tenant, return_id),
    )


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.client or ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")  # the agent never raises, sends or decides here


async def raise_card(ctx: AuthContext, return_id: UUID) -> UUID:
    """A person raises the §754 card on the return (options by code, DEC-4906)."""
    from abacus.modules.review.api import awaiting_cards, raise_decision_card
    from abacus.modules.tax.entity_decisions import QUESTION_754, SECTION_754

    _human(ctx, RAISE)
    engagement_id, resource = await _loaded(ctx, return_id)
    await authorise(ctx, RAISE, cast(Any, resource))
    awaiting = await awaiting_cards(ctx.tenant, return_id, [SECTION_754])
    if awaiting:
        return awaiting[0].card_id  # one card per return: the open one answers
    return await raise_decision_card(
        ctx, engagement_id=engagement_id, kind=SECTION_754, question_key=QUESTION_754,
        work_item_id=return_id, raised_under=RAISE,
    )  # fmt: skip


async def _waiting_issue(ctx: AuthContext, return_id: UUID) -> UUID | None:
    """The return's existing waiting-on-client issue the request links (never a new one)."""
    from abacus.modules.review.api import issue_awaits_client, list_issues

    page = await list_issues(
        ctx, record_type="tax_return", record_id=return_id, engagement_id=None, status=None,
        kind=None, limit=200,
    )  # fmt: skip
    for row in page.rows:
        if await issue_awaits_client(ctx.tenant, row.id):
            return UUID(str(row.id))
    return None


async def send_to_client(
    ctx: AuthContext,
    card_id: UUID,
    *,
    contact_id: UUID,
    subject_partner_id: UUID | None = None,
) -> UUID:
    """One send per card (module docstring); the contact must be a client user of the return's
    client (the C18 decider rule then admits only the owner)."""
    from abacus.modules.organisations.api import contact_portal_facts
    from abacus.modules.review.api import card_decision, card_subject
    from abacus.modules.tax.entity_decisions import SECTION_754

    _human(ctx, SEND)
    subject = await card_subject(ctx.tenant, card_id)
    if subject is None or subject[0] != SECTION_754 or subject[1] is None:
        raise DecisionCardUnknown(facts={"card_id": str(card_id)})
    return_id = subject[1]
    engagement_id, resource = await _loaded(ctx, return_id)
    await authorise(ctx, SEND, cast(Any, resource))
    if await card_decision(ctx.tenant, card_id) is not None:
        raise DecisionAlreadySent(facts={"card_id": str(card_id), "decided": True})
    portal = await contact_portal_facts(ctx.tenant, contact_id)
    user_id = None if portal is None else portal[1]
    if user_id is None:
        raise NotFound("client_contact")  # no portal person: nothing can reach the client
    async with tenant_session(ctx.tenant) as session:
        if (await session.execute(_REQUEST_OF_CARD, {"c": card_id})).first() is not None:
            raise DecisionAlreadySent(facts={"card_id": str(card_id)})
    issue_id = await _waiting_issue(ctx, return_id)
    async with uow(ctx.tenant) as tx:
        request_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO tax_decision_requests (tenant_id, engagement_id, work_item_id, "
                    "card_id, kind, subject_partner_id, contact_id, contact_user_id, issue_id, "
                    "sent_by) VALUES (:t, :e, :r, :c, :k, :p, :ct, :u, :i, :by) "
                    "ON CONFLICT (tenant_id, card_id) DO NOTHING RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "r": return_id,
                    "c": card_id,
                    "k": KIND,
                    "p": subject_partner_id,
                    "ct": contact_id,
                    "u": user_id,
                    "i": issue_id,
                    "by": ctx.user_id,
                },
            )
        ).scalar_one_or_none()
        if request_id is None:  # a concurrent second send lost the race
            raise DecisionAlreadySent(facts={"card_id": str(card_id)})
        tx.record(
            "decision_request.sent",
            target=Target(TARGET, UUID(str(request_id))),
            after=Ref(card=card_id, issue=issue_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    return UUID(str(request_id))


# --- C18 `section_754`: the client's answer in POR-08 ------------------------------------------


@dataclass(frozen=True)
class _Request:
    id: UUID
    engagement_id: UUID
    return_id: UUID
    card_id: UUID
    subject_partner_id: UUID | None
    contact_user_id: UUID
    sent_by: UUID
    sent_at: object
    answer: str | None
    answered_at: object | None


_REQUEST: Final = text(
    "SELECT q.id, q.engagement_id, q.work_item_id, q.card_id, q.subject_partner_id, "
    "q.contact_user_id, q.sent_by, q.sent_at, a.decision, a.answered_at FROM "
    "tax_decision_requests q LEFT JOIN tax_decision_answers a ON a.request_id = q.id "
)


def _request(r: object) -> _Request:
    row = cast(Any, r)
    return _Request(
        UUID(str(row.id)), UUID(str(row.engagement_id)), UUID(str(row.work_item_id)),
        UUID(str(row.card_id)),
        None if row.subject_partner_id is None else UUID(str(row.subject_partner_id)),
        UUID(str(row.contact_user_id)), UUID(str(row.sent_by)), row.sent_at, row.decision,
        row.answered_at,
    )  # fmt: skip


def _seen(r: _Request) -> str:
    import hashlib

    return hashlib.sha256(f"section_754:{r.id}:{r.card_id}".encode()).hexdigest()


def _viewer_is_contact(tenant: TenantContext, r: _Request) -> bool:
    """Only the contact the request names sees it (the portal's own session is the reader)."""
    return tenant.actor_kind != "human" or tenant.actor_id == str(r.contact_user_id)


class Section754Approvals:
    """C18 provider for kind `section_754` (owner grant decides; DEC-5835)."""

    def _item(self, r: _Request) -> object:
        from abacus.modules.engagements.api import ApprovalItem

        state = (
            "waiting" if r.answer is None else ("accepted" if r.answer == "accept" else "declined")
        )
        return ApprovalItem(
            kind=cast(Any, KIND), item_id=r.id, scope_kind="work_item", scope_id=r.return_id,
            sent_to_client=True, title="Elect under section 754?", state=cast(Any, state),
            seen_hash=_seen(r),
            legend="Your answer is recorded as the partnership's decision.",
            released_by_user_id=r.sent_by, released_at=cast(Any, r.sent_at),
            decided_at=cast(Any, r.answered_at),
        )  # fmt: skip

    async def items(self, tenant: TenantContext, scope_id: UUID) -> list[object]:
        async with tenant_session(tenant) as session:
            rows = (
                await session.execute(
                    text(_REQUEST.text + "WHERE q.work_item_id = :s ORDER BY q.sent_at"),
                    {"s": scope_id},
                )
            ).all()
        found = [_request(r) for r in rows]
        return [self._item(r) for r in found if _viewer_is_contact(tenant, r)]

    async def item(self, tenant: TenantContext, item_id: UUID) -> object | None:
        async with tenant_session(tenant) as session:
            row = (
                await session.execute(text(_REQUEST.text + "WHERE q.id = :i"), {"i": item_id})
            ).first()
        if row is None:
            return None
        r = _request(row)
        return self._item(r) if _viewer_is_contact(tenant, r) else None

    async def decide(
        self, tx: UnitOfWork, item_id: UUID, decision: object, context: object
    ) -> object:
        from abacus.modules.engagements.api import ItemChanged

        row = (
            await tx.session.execute(text(_REQUEST.text + "WHERE q.id = :i"), {"i": item_id})
        ).first()
        if row is None:
            raise NotFound(TARGET)
        r = _request(row)
        if decision.seen_hash != _seen(r) or r.answer is not None:
            raise ItemChanged
        word = str(decision.decision)
        answer = "accept" if word in ("accept", "approve") else "decline"
        ctx = cast(Any, context)
        await tx.session.execute(
            text(
                "INSERT INTO tax_decision_answers (tenant_id, request_id, decision, contact_id, "
                "user_id, grant_id, designation_basis) VALUES (:t, :q, :d, :c, :u, :g, :b)"
            ),
            {
                "t": tx.tenant.tenant_id,
                "q": item_id,
                "d": answer,
                "c": ctx.contact_id,
                "u": ctx.user_id,
                "g": ctx.grant_id,
                "b": ctx.designation_basis,
            },
        )
        if answer == "accept" and r.subject_partner_id is not None:
            await recompute_basis(tx, r.return_id, r.subject_partner_id)
        tx.record(
            "decision_request.answered",
            target=Target(TARGET, item_id),
            after=Ref(card=r.card_id, decision=answer),
            scope=Scope(engagement_id=r.engagement_id, work_item_id=r.return_id),
        )
        return self._item(replace_answer(r, answer))

    async def facts(self, tenant: TenantContext, item_id: UUID) -> object:
        from abacus.modules.engagements.api import ApprovalFacts

        async with tenant_session(tenant) as session:
            row = (
                await session.execute(text(_REQUEST.text + "WHERE q.id = :i"), {"i": item_id})
            ).first()
        if row is None:
            raise NotFound(TARGET)
        return ApprovalFacts(False, _request(row).return_id)


def replace_answer(r: _Request, answer: str) -> _Request:
    from dataclasses import replace

    return replace(r, answer=answer)


async def recompute_basis(tx: UnitOfWork, return_id: UUID, partner_id: UUID) -> None:
    """E8 for the subject partner once the client elects: the §743(b) step-up joins the partner's
    inside share; the difference and the status follow by code (the table's CHECKs hold)."""
    from abacus.modules.tax.compute import basis as e8

    row = (
        await tx.session.execute(
            text(
                "SELECT inside_share, outside_basis, s743b_placeholder FROM basis_schedules "
                "WHERE work_item_id = :r AND partner_id = :p"
            ),
            {"r": return_id, "p": partner_id},
        )
    ).first()
    if row is None:
        return
    inside = Decimal(row.inside_share) + Decimal(row.s743b_placeholder)
    difference = Decimal(row.outside_basis) - inside
    await tx.session.execute(
        text(
            "UPDATE basis_schedules SET inside_share = :i, difference = :d, status = :s, "
            "s743b_placeholder = 0, engine_name = 'E8', engine_version = :v, "
            "computed_at = clock_timestamp() WHERE work_item_id = :r AND partner_id = :p"
        ),
        {
            "i": inside, "d": difference, "s": "reconciled" if difference == 0 else "off",
            "v": getattr(e8, "ENGINE_VERSION", "e8.1"), "r": return_id, "p": partner_id,
        },
    )  # fmt: skip


async def answered(tenant: TenantContext, return_id: UUID) -> str | None:
    """TAX-11's statement flag: the client's answer on the return's §754 request, if any."""
    async with tenant_session(tenant) as session:
        return await session.scalar(
            text(
                "SELECT a.decision FROM tax_decision_requests q JOIN tax_decision_answers a "
                "ON a.request_id = q.id WHERE q.work_item_id = :r ORDER BY a.answered_at DESC "
                "LIMIT 1"
            ),
            {"r": return_id},
        )


PROVIDER: Final = Section754Approvals()


def register() -> None:
    from abacus.modules.engagements.api import register_client_approval_kind

    register_client_approval_kind(KIND, PROVIDER)  # type: ignore[arg-type] -- C18 provider


__all__ = [
    "PROVIDER",
    "BasisView",
    "PartnerBasis",
    "Section754Approvals",
    "answered",
    "basis",
    "raise_card",
    "recompute_basis",
    "register",
    "section_754_state",
    "send_to_client",
]
