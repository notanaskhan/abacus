"""The confirmations core (A-08-T16; SPEC-657 F6; AU-C 505; AUD-14; amber).

- **Create** (`confirmation.create`): a draft, positive form only, numbered C1, C2… per work item,
  with the address it will go to (sealed; its SHA-256 kept) and the book amounts it asks about.
- **The log and summary** (AUD-14): rows with their status and facts; the status tiles count the
  log (they always sum to it) and the AR coverage line is code: sent over the population, to one
  decimal place, with what was confirmed and the differences (897,950 of 5,860,000 is 15.3%).
- **Address verification** (`confirmation.verify_address`, a person's): the method, the sources and
  at least one citation; `independent` only with a non-client source. **Sending to an address no
  independent verification covers is refused** with 409 `address_not_verified` (AU-C 505 §A2,
  R-17), before anything else about the send.
- **Isolation** (I-CONFIRMATION-ISOLATION): every read here refuses a client context first; a
  client principal never reaches a confirmation, a response or its id.

The link a sent confirmation carries is a link principal (A-08-T15, purpose `confirmation`); its
respondent view is built here. Sends, responses and reconciliation are A-08-T18's.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.controls import control_active
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.safe_xlsx import Sheet, workbook
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.assurance import confirmations_fixtures as fx
from abacus.modules.assurance.confirmations_contract_models import (
    AddressVerificationIn,
    AddressVerificationOut,
    ConfirmationCoverageOut,
    ConfirmationCreateIn,
    ConfirmationDetailOut,
    ConfirmationLineOut,
    ConfirmationLogOut,
    ConfirmationRowOut,
    ConfirmationSummaryOut,
    ConfirmationType,
    RespondentAccountOut,
    RespondentRequestOut,
    RespondentViewOut,
    StatusTileOut,
)
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    LinkPrincipal,
    authorise,
    names_of,
    register_link_purpose,
)
from abacus.modules.ledger.api import entity_snapshots, snapshot_line

_AAD_NAME: Final = "assurance.confirmation.respondent"
_AAD_ADDRESS: Final = "assurance.confirmation.address"
_INDEPENDENT: Final = frozenset(
    {"prior_year", "website", "phone", "public_register", "bank_published"}
)
_ORDER: Final = (
    "draft",
    "authorization_requested",
    "sent",
    "responded",
    "exception",
    "alternative_procedures",
    "closed",
)
LINK_PURPOSE: Final = "confirmation"


class AddressNotVerified(DomainConflict):
    """AU-C 505: the address must be verified independently of the client before sending."""

    code = "address_not_verified"


def _key(address: str) -> bytes:
    return hashlib.sha256(address.strip().casefold().encode()).digest()


def _no_client(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("confirmation")


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _scope(ctx: AuthContext, work_item_id: UUID, action: str) -> UUID:
    _no_client(ctx)
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    await authorise(ctx, action, (await get_ref(ctx, engagement_id)).resource())
    return engagement_id


async def _of(ctx: AuthContext, confirmation_id: UUID, action: str) -> tuple[UUID, UUID]:
    _no_client(ctx)
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text("SELECT work_item_id, engagement_id FROM confirmations WHERE id = :c"),
                {"c": confirmation_id},
            )
        ).first()
    if row is None:
        raise NotFound("confirmation")
    await _scope(ctx, row[0], action)
    return row[0], row[1]


_ROWS: Final = text(
    "SELECT c.id, c.number, c.type, c.respondent_org, c.channel, c.status, c.sample_item_ref, "
    "coalesce((SELECT sum(l.book_amount) FROM confirmation_lines l WHERE l.confirmation_id = "
    "c.id), 0), "
    "EXISTS (SELECT 1 FROM address_verifications v WHERE v.confirmation_id = c.id AND "
    "v.independent "
    "AND v.address_sha256 = c.address_sha256), "
    "(SELECT max(at) FROM confirmation_events e WHERE e.confirmation_id = c.id AND e.kind = "
    "'sent'), "
    "(SELECT max(at) FROM confirmation_events e WHERE e.confirmation_id = c.id AND e.kind = "
    "'viewed'), "
    "(SELECT max(at) FROM confirmation_events e WHERE e.confirmation_id = c.id AND e.kind = "
    "'second_request'), "
    "(SELECT submitted_at FROM confirmation_responses r WHERE r.confirmation_id = c.id), "
    "c.tb_account_refs, "
    "(SELECT confirmed_total FROM confirmation_responses r WHERE r.confirmation_id = c.id) "
    "FROM confirmations c WHERE c.work_item_id = :w ORDER BY c.number"
)


def _row_out(r: tuple[object, ...]) -> ConfirmationRowOut:
    status = str(r[5])
    actions: list[str] = []
    if status == "draft":
        actions = [
            "confirmation.verify_address",
            "confirmation.request_authorization",
            "confirmation.send",
        ]
    elif status == "sent":
        actions = ["confirmation.record_response", "confirmation.record_alternative"]
    elif status == "responded":
        actions = ["confirmation.reconcile", "confirmation.accept_reconciliation"]
    return ConfirmationRowOut(
        id=cast(UUID, r[0]),
        number=f"C{r[1]}",
        type=cast(ConfirmationType, r[2]),
        respondent_org=str(r[3]),
        channel=r[4],  # pyright: ignore[reportArgumentType] -- CHECKed words
        status=status,  # pyright: ignore[reportArgumentType] -- a confirmation word
        book_total=Decimal(str(r[7])),
        address_independent=bool(r[8]),
        authorization_on_file=False,
        sent_at=cast(datetime | None, r[9]),
        viewed_at=cast(datetime | None, r[10]),
        second_request_at=cast(datetime | None, r[11]),
        responded_at=cast(datetime | None, r[12]),
        sample_item_ref=cast(str | None, r[6]),
        allowed_actions=actions,  # pyright: ignore[reportArgumentType] -- matrix action words
    )


async def confirmation_list(ctx: AuthContext, work_item_id: UUID) -> ConfirmationLogOut:
    await _scope(ctx, work_item_id, "confirmation.read")
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_ROWS, {"w": work_item_id})).all()
    return ConfirmationLogOut(
        items=[_row_out(tuple(r)) for r in rows],
        links_paused=await control_active("confirmation_links", ctx.tenant_id),
        allowed_actions=["confirmation.create", "confirmation.export"],
    )


async def _population(ctx: AuthContext, engagement_id: UUID, codes: list[str]) -> Decimal:
    """The AR population: the newest year snapshot's balances on the accounts the AR
    confirmations name (the AR control account), through `ledger.api`."""
    if not codes:
        return Decimal(0)
    entity = (await get_ref(ctx, engagement_id)).client_entity_id
    snapshots = [
        s
        for s in await entity_snapshots(ctx.tenant, entity)
        if (s.period_end - s.period_start).days > 40
    ]
    if not snapshots:
        return Decimal(0)
    newest = max(snapshots, key=lambda s: (s.period_end, s.pulled_at))
    total = Decimal(0)
    async with tenant_session(ctx.tenant) as session:
        for code in codes:
            found = await snapshot_line(session, newest.id, code)
            if found is not None and found[1] is not None:
                total += found[1].debit - found[1].credit
    return total


def coverage_of(
    population: Decimal, sent: Decimal, confirmed: Decimal, differences: Decimal, trivial: Decimal
) -> ConfirmationCoverageOut:
    """The AR coverage line, by code: sent over the population to one decimal place (15.3%)."""
    pct = (
        Decimal(0)
        if population == 0
        else (sent * 100 / population).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    )
    return ConfirmationCoverageOut(
        population_total=population,
        sent_total=sent,
        sent_pct=pct,
        confirmed_total=confirmed,
        differences_total=differences,
        clearly_trivial=trivial,
    )


async def summary(ctx: AuthContext, work_item_id: UUID) -> ConfirmationSummaryOut:
    engagement = await _scope(ctx, work_item_id, "confirmation.read")
    async with tenant_session(ctx.tenant) as session:
        rows = [tuple(r) for r in (await session.execute(_ROWS, {"w": work_item_id})).all()]
        ar = [r for r in rows if r[2] == "accounts_receivable"]
        codes = sorted({c for r in ar for c in cast(list[str], r[13] or [])})
    population = await _population(ctx, engagement, codes)
    counts = Counter(str(r[5]) for r in rows)
    tiles = [StatusTileOut(status=s, count=counts[s]) for s in _ORDER if counts[s]]  # pyright: ignore[reportArgumentType] -- a confirmation word
    sent = sum((Decimal(str(r[7])) for r in ar if r[5] != "draft"), Decimal(0))
    confirmed = sum((Decimal(str(r[14])) for r in ar if r[14] is not None), Decimal(0))
    differences = sum(
        (Decimal(str(r[7])) - Decimal(str(r[14])) for r in ar if r[14] is not None), Decimal(0)
    )
    return ConfirmationSummaryOut(
        tiles=tiles,
        total=len(rows),
        coverage=coverage_of(population, sent, confirmed, abs(differences), Decimal(0))
        if ar
        else None,
    )


async def create(
    ctx: AuthContext, work_item_id: UUID, body: ConfirmationCreateIn
) -> ConfirmationRowOut:
    _person(ctx, "confirmation.create")
    engagement = await _scope(ctx, work_item_id, "confirmation.create")
    async with uow(ctx.tenant) as tx:
        number = int(
            await tx.session.scalar(
                text(
                    "SELECT coalesce(max(number), 0) + 1 FROM confirmations WHERE work_item_id = "
                    ":w"
                ),
                {"w": work_item_id},
            )
            or 1
        )
        cid = await tx.session.scalar(
            text(
                "INSERT INTO confirmations (tenant_id, engagement_id, work_item_id, number, "
                "type, channel, "
                "respondent_name_sealed, respondent_org, address_sealed, address_sha256, "
                "sample_item_ref, "
                "tb_account_refs, created_by) VALUES (:t, :e, :w, :n, :ty, :ch, :rn, :ro, :ad, "
                ":ah, :si, :tb, :u) "
                "RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "e": engagement,
                "w": work_item_id,
                "n": number,
                "ty": body.type,
                "ch": body.channel,
                "rn": await seal(ctx.tenant_id, body.respondent_name.encode(), _AAD_NAME),
                "ro": body.respondent_org,
                "ad": await seal(ctx.tenant_id, body.address_value.encode(), _AAD_ADDRESS),
                "ah": _key(body.address_value),
                "si": body.sample_item_ref,
                "tb": list(body.tb_account_refs),
                "u": ctx.user_id,
            },
        )
        for n, line in enumerate(body.lines, start=1):
            await tx.session.execute(
                text(
                    "INSERT INTO confirmation_lines (tenant_id, confirmation_id, position, "
                    "description, account_last4, book_amount) VALUES (:t, :c, :p, :d, :a, :b)"
                ),
                {
                    "t": ctx.tenant_id,
                    "c": cid,
                    "p": n,
                    "d": line.description,
                    "a": line.account_last4,
                    "b": line.book_amount,
                },
            )
        tx.record(
            "confirmation.created",
            target=Target("confirmation", cast(UUID, cid)),
            after=Ref(number=number),
            scope=Scope(engagement_id=engagement, work_item_id=work_item_id),
        )
    return next(r for r in (await confirmation_list(ctx, work_item_id)).items if r.id == cid)


async def verify_address(
    ctx: AuthContext, confirmation_id: UUID, body: AddressVerificationIn
) -> AddressVerificationOut:
    _person(ctx, "confirmation.verify_address")
    work_item, engagement = await _of(ctx, confirmation_id, "confirmation.verify_address")
    independent = bool(set(body.sources) & _INDEPENDENT)
    async with uow(ctx.tenant) as tx:
        found = (
            await tx.session.execute(
                text("SELECT address_sha256 FROM confirmations WHERE id = :c"),
                {"c": confirmation_id},
            )
        ).first()
        if found is None:
            raise NotFound("confirmation")
        vid = await tx.session.scalar(
            text(
                "INSERT INTO address_verifications (tenant_id, confirmation_id, method, sources, "
                "independent, citation_ids, address_sha256, verified_by, actor_kind) VALUES (:t, "
                ":c, :m, :s, :i, :ci, :ah, :u, 'human') RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "c": confirmation_id,
                "m": body.method,
                "s": list(body.sources),
                "i": independent,
                "ci": list(body.citation_ids),
                "ah": found[0],
                "u": ctx.user_id,
            },
        )
        tx.record(
            "confirmation.address_verified",
            target=Target("confirmation", confirmation_id),
            after=Ref(independent=int(independent)),
            scope=Scope(engagement_id=engagement, work_item_id=work_item),
        )
    name = (await names_of([ctx.user_id])).get(ctx.user_id, "")
    from abacus.kernel.clock import today

    return AddressVerificationOut(
        id=cast(UUID, vid),
        method=body.method,
        sources=list(body.sources),
        independent=independent,
        citation_ids=list(body.citation_ids),
        verified_by_name=name or "—",
        verified_on=await today(ctx.tenant),
    )


async def check_sendable(ctx: AuthContext, confirmation_id: UUID) -> None:
    """The send's first gate (A-08-T18 sends): 409 `address_not_verified` unless an independent
    verification covers the address the confirmation goes to now."""
    await _of(ctx, confirmation_id, "confirmation.send")
    async with tenant_session(ctx.tenant) as session:
        ok = await session.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM confirmations c JOIN address_verifications v ON "
                "v.confirmation_id = c.id WHERE c.id = :c AND v.independent AND v.address_sha256 "
                "= c.address_sha256)"
            ),
            {"c": confirmation_id},
        )
    if not ok:
        raise AddressNotVerified(facts={"confirmation_id": str(confirmation_id)})


async def detail(ctx: AuthContext, confirmation_id: UUID) -> ConfirmationDetailOut:
    work_item, _ = await _of(ctx, confirmation_id, "confirmation.read")
    row = next(
        r for r in (await confirmation_list(ctx, work_item)).items if r.id == confirmation_id
    )
    async with tenant_session(ctx.tenant) as session:
        lines = (
            await session.execute(
                text(
                    "SELECT position, description, account_last4, book_amount FROM "
                    "confirmation_lines WHERE confirmation_id = :c ORDER BY position"
                ),
                {"c": confirmation_id},
            )
        ).all()
        checks = (
            await session.execute(
                text(
                    "SELECT id, method, sources, independent, citation_ids, verified_by, "
                    "verified_at FROM address_verifications WHERE confirmation_id = :c ORDER BY "
                    "verified_at"
                ),
                {"c": confirmation_id},
            )
        ).all()
    names = await names_of(sorted({c[5] for c in checks}, key=str)) if checks else {}
    return ConfirmationDetailOut(
        row=row,
        lines=[
            ConfirmationLineOut(
                position=n,
                description=d,
                account_last4=a,
                book_amount=Decimal(b),
                confirmed_amount=None,
                difference=None,
            )
            for n, d, a, b in lines
        ],
        address_verifications=[
            AddressVerificationOut(
                id=c[0],
                method=c[1],
                sources=list(c[2]),
                independent=c[3],
                citation_ids=list(c[4]),
                verified_by_name=names.get(c[5], "—"),
                verified_on=c[6].date(),
            )
            for c in checks
        ],
        response=None,
        reconciliation=None,
        why_surfaced_suggestion_id=None,
        finding_id=None,
        misstatement_id=None,
    )


async def workbook_of(ctx: AuthContext, work_item_id: UUID) -> bytes:
    rows = (await confirmation_list(ctx, work_item_id)).items
    table: list[list[str | Decimal | None]] = [
        ["Number", "Type", "Respondent", "Channel", "Status", "Book total", "Address independent"]
    ]
    table += [
        [
            r.number,
            r.type,
            r.respondent_org,
            r.channel,
            r.status,
            r.book_total,
            "yes" if r.address_independent else "no",
        ]
        for r in rows
    ]
    return workbook([Sheet("Confirmations", table)])


# --- the link purpose (A-08-T15)
# ------------------------------------------------------------------


async def _live(tenant: TenantContext, confirmation_id: UUID) -> bool:
    """A link stays live while its confirmation is sent and unanswered."""
    async with tenant_session(tenant) as session:
        status = await session.scalar(
            text("SELECT status FROM confirmations WHERE id = :c"), {"c": confirmation_id}
        )
    return status == "sent"


# The respondent's statement of the client's authorization: the handoff's POR-17 words, with
# the firm, the client's fiscal year end and nothing else (AC-7.1, INV-4).
_AUTHORIZATION_TEXT: Final = (
    "Our auditors, {firm}, are auditing our financial statements for the year ended {year_end}. "
    "Please confirm directly to them the balance you owed us at that date. This is not a "
    "request for payment."
)
_VIEW: Final = text(
    "SELECT c.id, c.number, c.type, c.status, c.respondent_org, c.engagement_id, "
    "a.signer_contact_id, a.completed_at FROM confirmations c "
    "JOIN confirmation_authorization_items i ON i.confirmation_id = c.id "
    "JOIN confirmation_authorizations a ON a.id = i.authorization_id "
    "AND a.completed_at IS NOT NULL "
    "WHERE c.id = :c ORDER BY a.completed_at DESC LIMIT 1"
)
_VIEW_LINES: Final = text(
    "SELECT description, book_amount FROM confirmation_lines WHERE confirmation_id = :c "
    "ORDER BY position"
)


async def respondent_view_of(principal: LinkPrincipal) -> RespondentViewOut:
    """POR-17's view of a live link (A-08-T19; DEC-5325): `answered` once the one answer is in,
    `open` with this confirmation's render data while it is Sent under a completed client
    authorization, otherwise the uniform expired view. Nothing about the engagement, another
    customer or the firm's people leaves (AC-7.1, INV-4)."""
    from abacus.modules.assurance import confirmations_respondent as respondent
    from abacus.modules.engagements.api import engagement_label
    from abacus.modules.identity.api import firm_name
    from abacus.modules.organisations.api import contact_facts

    tenant = TenantContext(principal.tenant_id, "system", "confirmation.respondent")
    answered = await respondent.original_receipt(principal)
    if answered is not None:
        return RespondentViewOut(state="answered", answered_on=answered.submitted_at.date())
    async with tenant_session(tenant) as session:
        row = (await session.execute(_VIEW, {"c": principal.subject_id})).mappings().first()
        lines: list[tuple[str, Decimal]] = (
            []
            if row is None
            else [
                (str(d), Decimal(a))
                for d, a in (await session.execute(_VIEW_LINES, {"c": row["id"]})).all()
            ]
        )
        signer = (
            {}
            if row is None
            else await contact_facts(session, [cast(UUID, row["signer_contact_id"])])
        )
    if row is None or row["status"] != "sent":
        return fx.EXPIRED
    label = await engagement_label(tenant, cast(UUID, row["engagement_id"]))
    if label is None or label.fiscal_period_end is None:
        return fx.EXPIRED
    firm = await firm_name(principal.tenant_id)
    end = label.fiscal_period_end
    person = signer.get(cast(UUID, row["signer_contact_id"]))
    bank = row["type"] == "bank"
    total = sum((a for _, a in lines), Decimal("0.00"))
    return RespondentViewOut(
        state="open",
        request=RespondentRequestOut(
            reference=f"C{row['number']}",
            type=row["type"],
            firm_name=firm,
            client_name=label.client_name,
            respondent_org=str(row["respondent_org"]),
            as_of=end,
            authorization_text=_AUTHORIZATION_TEXT.format(
                firm=firm, year_end=f"{end:%B} {end.day}, {end.year}"
            ),
            authorized_by=label.client_name if person is None else person.display_name,
            authorized_on=cast(datetime, row["completed_at"]).date(),
            balance_per_client=None if bank else total,
            invoices=[],
            client_accounts=[
                RespondentAccountOut(description=d, balance_per_client=a) for d, a in lines
            ]
            if bank
            else [],
            list_every_account=bank,
        ),
    )


def register() -> None:
    register_link_purpose(LINK_PURPOSE, _live)


__all__ = [
    "AddressNotVerified",
    "check_sendable",
    "confirmation_list",
    "coverage_of",
    "create",
    "detail",
    "register",
    "respondent_view_of",
    "summary",
    "verify_address",
    "workbook_of",
]
