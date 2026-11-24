"""TAX-15's planning service (T-08-T19; TASK-8914; SPEC-710 AC-27; T-08 §3.5; DEC-5916; amber).

**Screens** run on a return's final approval (`tax_return.approved`), its acceptance
(`filing.acknowledged` accepted) and a completed consent set (`envelope.completed` on a
`consent_set`), as the system, and only while `tax.planning` is on (OQ-6: event-driven, no
batch). A screen reads the return's approved engine summary and filing status, runs the code
rules (`planning.rules`) over the CPA-reviewed parameters, applies the **§7216 consent filter**
and upserts one opportunity per (return, rule):

- a tax service to the same client needs no separate consent (§301.7216-2(h)); the
  `planning_screen` narrative needs both `use` and `ai_disclosure` in force for the filing unit
  (C19 counts a joint unit's consent in force only when both spouses signed). Without them the
  opportunity is **Not screened**: code's figures are kept, no model is called, no outreach is
  offered and the open consent envelope is named (TAX-15 d);
- a non-tax product also needs `other_services_use` in force; without it no row is written.

Nothing a person moved is moved back: a re-screen refreshes only Open and Not screened rows.

**People decide.** Raise is the owner's or the relationship partner's send through
`message.send` from the firm's "Planning conversation" template (DEC-79: no model text reaches a
client; an agent draft prefills only under P-25, which is not accepted), and the opportunity
becomes Raised only after the send. "Create advisory project…" answers ENG-03's prefill with a
`planning_opportunity:<id>` source; the opportunity becomes Accepted when `engagement.created`
carries it back. Decline, dismiss (reason required) and restore are insert-only events; restore
returns the previous status. Manual opportunities come from TXT-03's "Add to planning" and the
TXP-01 memo (`rule_key = manual.<source>`; no model). Every status change writes one
`planning_opportunity_events` row and one audit event with identifiers only (DEC-60).

The portfolio (the strip) and the queue tie by code over the viewer's visible returns (walls:
`visible()` through `work_item_facts`).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.tax.planning import calculators as calc
from abacus.modules.tax.planning import rules as planning_rules
from abacus.modules.tax.practice_tools_errors import (
    OpportunityStateInvalid,
    PlanningTemplateMissing,
    RecipientNotClient,
)

_log = get_logger(__name__)

READ: Final = "planning.read"
RAISE: Final = "planning.raise"
CREATE_PROJECT: Final = "planning.create_project"
DISMISS: Final = "planning.dismiss"
CREATE: Final = "planning.create"
TEMPLATE_KEY: Final = "planning_conversation"
SOURCE_PREFIX: Final = "planning_opportunity:"
Status = Literal["open", "raised", "accepted", "declined", "not_screened", "dismissed"]
Trigger = Literal["return_approved", "return_accepted", "consent_completed", "manual"]
# A re-screen refreshes these; every other status is a person's (or the engagement's) and stays.
SCREENABLE: Final = frozenset({"open", "not_screened"})
# Counted on the strip: dismissed rows are hidden (Show dismissed), declined ones are closed.
LIVE: Final = frozenset({"open", "raised", "accepted", "not_screened"})
_STATUS_OF_FILING: Final[dict[str, calc.FilingStatus]] = {
    "mfj": "mfj", "single": "single", "hoh": "hoh", "mfs": "mfs", "qss": "mfj",
}  # fmt: skip


# --- the model step's slot (T-08-T26 registers `tax.return_analyst` mode `planning_screen`) ------

Narrator = Callable[[TenantContext, UUID, Sequence[UUID]], Awaitable[None]]
_NARRATOR: list[Narrator] = []


def register_planning_narrator(narrator: Narrator) -> None:
    """T-08-T26: the `planning_screen` run, started for a consented return's Open opportunities
    after the screen commits. Until it registers, the rationale is code's template (DF-04)."""
    _NARRATOR[:] = [narrator]


# --- rows ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Opportunity:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID
    client_id: UUID
    client_name: str
    source_kind: str
    rule_key: str
    category: str
    product_kind: str
    title: str
    status: Status
    previous_status: Status | None
    est_savings: Decimal | None
    rationale: str | None
    rationale_source: Literal["agent", "template"] | None
    consent_basis: str
    owner_user_id: UUID | None
    project_engagement_id: UUID | None
    raised_message_id: UUID | None
    raised_at: datetime | None
    row_version: int
    tax_year: int | None


# End pass (SQL-001): one literal query; every filter is a bound parameter, NULL when unused.
_ROWS: Final = text(
    "SELECT o.id, o.engagement_id, o.work_item_id, o.client_id, o.source_kind, o.rule_key, "
    "o.category, o.product_kind, o.title, o.body, o.status, o.previous_status, o.est_savings, "
    "o.rationale_suggestion_id, o.consent_basis, o.owner_user_id, o.project_engagement_id, "
    "o.raised_message_id, o.row_version, r.tax_year, "
    "(SELECT max(e.at) FROM planning_opportunity_events e WHERE e.opportunity_id = o.id "
    " AND e.to_status = 'raised') AS raised_at "
    "FROM planning_opportunities o JOIN tax_returns r ON r.work_item_id = o.work_item_id "
    "WHERE o.work_item_id = ANY(:visible) "
    "AND (CAST(:id AS uuid) IS NULL OR o.id = :id) "
    "AND (CAST(:year AS integer) IS NULL OR r.tax_year = :year) "
    "AND (CAST(:partner AS uuid) IS NULL OR o.owner_user_id = :partner) "
    "AND (CAST(:status AS text) IS NULL OR o.status = :status) "
    "AND (CAST(:work AS uuid) IS NULL OR o.work_item_id = :work) "
    "AND (CAST(:rule AS text) IS NULL OR o.rule_key = :rule) "
    "AND (CAST(:dismissed AS boolean) IS NULL OR CAST(:dismissed AS boolean) "
    "OR o.status <> 'dismissed') "
    "ORDER BY o.created_at, o.id"
)
_NO_FILTER: Final[Mapping[str, object]] = dict.fromkeys(
    ("id", "year", "partner", "status", "work", "rule", "dismissed")
)


def _body_text(body: object) -> str | None:
    parts = [
        str(cast("dict[str, object]", seg).get("text", ""))
        for seg in cast("list[object]", body or [])
        if isinstance(seg, dict)
    ]
    found = " ".join(p.strip() for p in parts if p.strip())
    return found or None


def _source(rationale: str | None, suggestion: object) -> Literal["agent", "template"] | None:
    if rationale is None:
        return None
    return "agent" if suggestion else "template"


def _row(row: Mapping[str, object], clients: Mapping[UUID, tuple[UUID, str]]) -> Opportunity:
    work_item = cast(UUID, row["work_item_id"])
    client_id, client_name = clients[work_item]
    rationale = _body_text(row["body"])
    return Opportunity(
        id=cast(UUID, row["id"]),
        engagement_id=cast(UUID, row["engagement_id"]),
        work_item_id=work_item,
        client_id=cast("UUID | None", row["client_id"]) or client_id,
        client_name=client_name,
        source_kind=str(row["source_kind"]),
        rule_key=str(row["rule_key"] or f"memo.{row['id']}"[:60]),
        category=str(row["category"] or "advisory"),
        product_kind=str(row["product_kind"]),
        title=str(row["title"]),
        status=cast(Status, row["status"]),
        previous_status=cast("Status | None", row["previous_status"]),
        est_savings=cast("Decimal | None", row["est_savings"]),
        rationale=rationale,
        rationale_source=_source(rationale, row["rationale_suggestion_id"]),
        consent_basis=str(row["consent_basis"]),
        owner_user_id=cast("UUID | None", row["owner_user_id"]),
        project_engagement_id=cast("UUID | None", row["project_engagement_id"]),
        raised_message_id=cast("UUID | None", row["raised_message_id"]),
        raised_at=cast("datetime | None", row["raised_at"]),
        row_version=int(cast(int, row["row_version"])),
        tax_year=cast("int | None", row["tax_year"]),
    )


async def _visible_returns(ctx: AuthContext) -> dict[UUID, tuple[UUID, str]]:
    """The returns the viewer may read planning on (walls; INV-3): work item → client."""
    from abacus.modules.engagements.api import work_item_facts

    return {
        f.work_item_id: (f.client_id, f.client_name)
        for f in await work_item_facts(ctx, "tax_return", READ)
    }


async def _rows(ctx: AuthContext, params: Mapping[str, object]) -> list[Opportunity]:
    clients = await _visible_returns(ctx)
    if not clients:
        return []
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(_ROWS, {**_NO_FILTER, "visible": list(clients), **params})
        ).mappings()
        return [_row(cast("Mapping[str, object]", r), clients) for r in rows]


# --- reads ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Summary:
    tax_year: int
    clients_to_contact: int
    est_savings: Decimal
    talking_points: Literal["drafted", "template", "none"]
    consent_blocked: int
    opportunities: int
    clients: int


def summarise(items: Sequence[Opportunity], tax_year: int) -> Summary:
    """The strip, by code (AC-27): live opportunities (dismissed and declined left out), their
    clients, the estimate summed over the ones still to win (Open, Raised, Not screened) and the
    consent-blocked clients (a Not screened row)."""
    live = [o for o in items if o.status in LIVE]
    clients = {o.client_id for o in live}
    to_contact = {o.client_id for o in live if o.status in ("open", "raised", "not_screened")}
    savings = sum(
        (o.est_savings or Decimal(0) for o in live if o.status in ("open", "raised")),
        Decimal(0),
    )
    blocked = {o.client_id for o in live if o.status == "not_screened"}
    sources = {o.rationale_source for o in live if o.rationale_source is not None}
    talking: Literal["drafted", "template", "none"] = (
        "drafted" if "agent" in sources else "template" if sources else "none"
    )
    return Summary(
        tax_year, len(to_contact), savings, talking, len(blocked), len(live), len(clients)
    )


async def summary(ctx: AuthContext, tax_year: int, partner_id: UUID | None) -> Summary:
    items = await _rows(ctx, {"year": tax_year, "partner": partner_id})
    return summarise(items, tax_year)


async def opportunities(
    ctx: AuthContext,
    *,
    status: Status | None = None,
    client_id: UUID | None = None,
    work_item_id: UUID | None = None,
    include_dismissed: bool = False,
) -> list[Opportunity]:
    """The queue: every visible opportunity, filtered; dismissed rows only when asked."""
    found = await _rows(
        ctx,
        {
            "status": status,
            "work": work_item_id,
            "dismissed": include_dismissed or status == "dismissed",
        },
    )
    return [o for o in found if client_id is None or o.client_id == client_id]


async def opportunity(ctx: AuthContext, opportunity_id: UUID) -> Opportunity:
    found = await _rows(ctx, {"id": opportunity_id})
    if not found:
        raise NotFound("planning_opportunity")
    return found[0]


async def consent_envelope(tenant: TenantContext, found: Opportunity) -> UUID | None:
    """TAX-15 d: the open consent envelope of a Not screened opportunity's taxpayer."""
    if found.status != "not_screened" or found.tax_year is None:
        return None
    from abacus.modules.organisations.api import open_consent_envelope

    entity = await _entity_of(tenant, found.work_item_id)
    return None if entity is None else await open_consent_envelope(tenant, entity, found.tax_year)


async def allowed(ctx: AuthContext, found: Opportunity) -> list[str]:
    """What the viewer may do on the row: no outreach on a consent-blocked row (TAX-15 d)."""
    from abacus.modules.identity.api import allowed_actions

    resource = await _resource(ctx.tenant, found.engagement_id, found.work_item_id)
    held = set(await allowed_actions(ctx, resource, (RAISE, CREATE_PROJECT, DISMISS)))
    out: list[str] = []
    if RAISE in held and found.status == "open" and await _owns(ctx, found):
        out.append(RAISE)
    if CREATE_PROJECT in held and found.status in ("open", "raised") and await _owns(ctx, found):
        out.append(CREATE_PROJECT)
    if DISMISS in held and found.status in ("open", "raised", "not_screened", "dismissed"):
        out.append(DISMISS)
    return out


# --- helpers -------------------------------------------------------------------------------------


async def _resource(tenant: TenantContext, engagement_id: UUID, work_item_id: UUID) -> Resource:
    from dataclasses import replace

    from abacus.modules.identity.api import engagement_resource

    return replace(await engagement_resource(tenant, engagement_id), work_item_id=work_item_id)


async def _entity_of(tenant: TenantContext, work_item_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        return await session.scalar(
            text("SELECT client_entity_id FROM tax_returns WHERE work_item_id = :r"),
            {"r": work_item_id},
        )


async def _owns(ctx: AuthContext, found: Opportunity) -> bool:
    """The opportunity's owner, or the client's relationship partner (T-08 §4.7)."""
    from abacus.modules.organisations.api import client_partner_of

    if found.owner_user_id == ctx.user_id:
        return True
    partner = await client_partner_of(ctx.tenant, found.client_id)
    return isinstance(partner, UUID) and partner == ctx.user_id


_EVENT: Final = text(
    "INSERT INTO planning_opportunity_events (tenant_id, opportunity_id, from_status, to_status, "
    "event, reason, note, actor_id) VALUES (:t, :o, :f, :to, :ev, :reason, :note, :actor)"
)


async def _move(
    tenant: TenantContext,
    found: Opportunity,
    to: Status,
    event: str,
    *,
    actor_id: UUID | None,
    previous: Status | None,
    reason: str | None = None,
    note: str | None = None,
    raised_message_id: UUID | None = None,
) -> None:
    """One status change: the row (optimistic on its version), its event and its audit."""
    async with uow(tenant) as tx:
        moved = await tx.session.scalar(
            text(
                "UPDATE planning_opportunities SET status = :to, previous_status = :prev, "
                "raised_message_id = COALESCE(CAST(:message AS uuid), raised_message_id), "
                "row_version = row_version + 1, updated_at = clock_timestamp() "
                "WHERE id = :id AND status = :from AND row_version = :v RETURNING row_version"
            ),
            {"to": to, "prev": previous, "message": raised_message_id, "id": found.id,
             "from": found.status, "v": found.row_version},
        )  # fmt: skip
        if moved is None:
            raise OpportunityStateInvalid(facts={"status": found.status})
        await tx.session.execute(
            _EVENT,
            {"t": tenant.tenant_id, "o": found.id, "f": found.status, "to": to, "ev": event,
             "reason": reason, "note": note, "actor": actor_id},
        )  # fmt: skip
        tx.record(
            f"planning_opportunity.{event}",
            target=Target("planning_opportunity", found.id),
            after=Ref(row_version=int(moved)),
            scope=Scope(engagement_id=found.engagement_id, work_item_id=found.work_item_id),
        )


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _authorised(ctx: AuthContext, opportunity_id: UUID, action: str) -> Opportunity:
    _human(ctx, action)
    found = await opportunity(ctx, opportunity_id)
    await authorise(
        ctx, action, await _resource(ctx.tenant, found.engagement_id, found.work_item_id)
    )
    return found


# --- people's moves ------------------------------------------------------------------------------


@dataclass(frozen=True)
class RaiseSheet:
    template_version_id: UUID
    subject: str
    body: str
    recipients: tuple[tuple[UUID, str], ...]  # (contact, name)


async def _recipients(tenant: TenantContext, found: Opportunity) -> tuple[tuple[UUID, str], ...]:
    """The filing unit's taxpayers (both spouses on a joint unit) as the default recipients."""
    from abacus.modules.organisations.api import unit_signer_contacts

    entity = await _entity_of(tenant, found.work_item_id)
    if entity is None:
        return ()
    return tuple(await unit_signer_contacts(tenant, entity))


async def prepare_raise(ctx: AuthContext, opportunity_id: UUID) -> RaiseSheet:
    """The send sheet (TAX-15 b): the firm's "Planning conversation" version filled with code's
    values for the opportunity; nothing is sent or changed."""
    from abacus.modules.communications.api import template_draft
    from abacus.modules.identity.api import firm_name, names_of

    found = await _authorised(ctx, opportunity_id, RAISE)
    if found.status != "open":
        raise OpportunityStateInvalid(facts={"status": found.status})
    if not await _owns(ctx, found):
        raise Forbidden(RAISE, "relationship")
    recipients = await _recipients(ctx.tenant, found)
    first = recipients[0][1].split(" ")[0] if recipients else found.client_name.split(" ")[0]
    me = (await names_of([ctx.user_id])).get(ctx.user_id) or ""
    draft = await template_draft(
        ctx.tenant,
        TEMPLATE_KEY,
        {"client_first_name": first, "firm_name": await firm_name(ctx.tenant_id),
         "work_item": found.title, "staff_name": me},
    )  # fmt: skip
    if draft is None:
        raise PlanningTemplateMissing(facts={"key": TEMPLATE_KEY})
    return RaiseSheet(draft.version_id, draft.subject, draft.body, recipients)


async def raise_with_client(
    ctx: AuthContext,
    opportunity_id: UUID,
    *,
    subject: str,
    body: str,
    recipient_contact_ids: Sequence[UUID],
) -> Opportunity:
    """A person's send through `message.send` (the outbound scope check runs there); Raised only
    after it is sent (AC5.3). A retried raise of a Raised row answers it as it is."""
    from abacus.modules.communications.api import Draft, send
    from abacus.modules.organisations.api import signer_contacts

    found = await _authorised(ctx, opportunity_id, RAISE)
    if found.status == "raised" and found.raised_message_id is not None:
        return found
    if found.status != "open":
        raise OpportunityStateInvalid(facts={"status": found.status})
    if not await _owns(ctx, found):
        raise Forbidden(RAISE, "relationship")
    contacts = await signer_contacts(ctx.tenant, list(recipient_contact_ids))
    if len(contacts) != len(set(recipient_contact_ids)) or any(
        c.client_id != found.client_id for c in contacts.values()
    ):
        raise RecipientNotClient(facts={"count": len(recipient_contact_ids)})
    message_ids: list[UUID] = []
    for contact_id in sorted(set(recipient_contact_ids), key=str):
        view = await send(
            ctx,
            found.engagement_id,
            Draft(channel="portal", recipient_ref=f"contact:{contact_id}",
                  body=f"{subject.strip()}\n\n{body.strip()}"),
        )  # fmt: skip
        message_ids.append(view.id)
    await _move(
        ctx.tenant, found, "raised", "raised", actor_id=ctx.user_id, previous=found.status,
        raised_message_id=message_ids[0],
    )  # fmt: skip
    async with uow(ctx.tenant) as tx:
        # The message's consent basis (§301.7216-2(h), or the other-services consent) is the
        # opportunity's `consent_basis`; the audit names the message and the opportunity only.
        tx.record(
            "planning_message.sent",
            target=Target("planning_opportunity", found.id),
            after=Ref(message=message_ids[0], recipients=len(message_ids)),
            scope=Scope(engagement_id=found.engagement_id, work_item_id=found.work_item_id),
        )
    return await opportunity(ctx, opportunity_id)


@dataclass(frozen=True)
class ProjectPrefill:
    engagement_name: str
    owner_user_id: UUID
    client_id: UUID
    source_ref: str


async def create_project(ctx: AuthContext, opportunity_id: UUID) -> ProjectPrefill:
    """ENG-03's prefill (TAX-15 c). T-08 creates no engagement; `engagement.created` carrying
    the source reference makes the opportunity Accepted (AC5.4)."""
    found = await _authorised(ctx, opportunity_id, CREATE_PROJECT)
    if found.status not in ("open", "raised"):
        raise OpportunityStateInvalid(facts={"status": found.status})
    if not await _owns(ctx, found):
        raise Forbidden(CREATE_PROJECT, "relationship")
    owner = found.owner_user_id or ctx.user_id
    name = f"{found.client_name.split(',')[0]} {found.title[:1].lower()}{found.title[1:]}"[:200]
    async with uow(ctx.tenant) as tx:
        tx.record(
            "planning_opportunity.project_prefilled",
            target=Target("planning_opportunity", found.id),
            after=Ref(owner=owner),
            scope=Scope(engagement_id=found.engagement_id, work_item_id=found.work_item_id),
        )
    return ProjectPrefill(name, owner, found.client_id, f"{SOURCE_PREFIX}{found.id}")


async def decline(ctx: AuthContext, opportunity_id: UUID) -> Opportunity:
    """The client declined (Open or Raised → Declined)."""
    found = await _authorised(ctx, opportunity_id, DISMISS)
    if found.status not in ("open", "raised"):
        raise OpportunityStateInvalid(facts={"status": found.status})
    await _move(
        ctx.tenant, found, "declined", "declined", actor_id=ctx.user_id, previous=found.status,
        reason="client_declined",
    )  # fmt: skip
    return await opportunity(ctx, opportunity_id)


async def dismiss(
    ctx: AuthContext, opportunity_id: UUID, reason: str, note: str | None
) -> Opportunity:
    """Dismiss with a reason (TAX-15 e; insert-only event; the previous status is kept)."""
    found = await _authorised(ctx, opportunity_id, DISMISS)
    if found.status not in ("open", "raised", "not_screened"):
        raise OpportunityStateInvalid(facts={"status": found.status})
    await _move(
        ctx.tenant, found, "dismissed", "dismissed", actor_id=ctx.user_id,
        previous=found.status, reason=reason, note=note,
    )  # fmt: skip
    return await opportunity(ctx, opportunity_id)


async def restore(ctx: AuthContext, opportunity_id: UUID) -> Opportunity:
    """Restore returns a dismissed opportunity to the status it had (AC5.5)."""
    found = await _authorised(ctx, opportunity_id, DISMISS)
    if found.status != "dismissed" or found.previous_status is None:
        raise OpportunityStateInvalid(facts={"status": found.status})
    await _move(
        ctx.tenant, found, found.previous_status, "restored", actor_id=ctx.user_id,
        previous=None,
    )  # fmt: skip
    return await opportunity(ctx, opportunity_id)


_MANUAL: Final = text(
    "INSERT INTO planning_opportunities (tenant_id, engagement_id, work_item_id, memo_id, "
    "source_kind, title, body, client_id, rule_key, category, owner_user_id) VALUES "
    "(:t, :e, :r, NULL, 'manual', :title, CAST(:body AS jsonb), :client, :rule, 'manual', :owner) "
    "ON CONFLICT (work_item_id, rule_key) WHERE rule_key IS NOT NULL DO NOTHING RETURNING id"
)


class _Nothing(Exception):
    """Leave the unit of work without a commit (nothing changed)."""


async def create_manual(
    ctx: AuthContext, work_item_id: UUID, title: str, source: str, source_ref: str
) -> Opportunity:
    """TXT-03's "Add to planning" or a TXP-01 memo item (AC5.7): an Open opportunity with
    `rule_key = manual.<source>.<ref>`, no model and no estimate. One per source item."""
    import hashlib

    _human(ctx, CREATE)
    clients = await _visible_returns(ctx)
    if work_item_id not in clients:
        raise NotFound("tax_return")
    from abacus.modules.engagements.api import work_item_scope

    scope = await work_item_scope(ctx.tenant, work_item_id)
    if scope is None or scope.engagement_id is None:
        raise NotFound("tax_return")
    await authorise(ctx, CREATE, await _resource(ctx.tenant, scope.engagement_id, work_item_id))
    ref = hashlib.sha256(source_ref.encode()).hexdigest()[:16]
    rule_key = f"manual.{source}.{ref}"[:60]
    try:
        async with uow(ctx.tenant) as tx:
            new_id = await tx.session.scalar(
                _MANUAL,
                {"t": ctx.tenant_id, "e": scope.engagement_id, "r": work_item_id, "title": title,
                 "body": json.dumps([]), "client": clients[work_item_id][0], "rule": rule_key,
                 "owner": ctx.user_id},
            )  # fmt: skip
            if new_id is None:
                raise _Nothing  # added before from the same source item: answer that one
            await tx.session.execute(
                _EVENT,
                {"t": ctx.tenant_id, "o": new_id, "f": None, "to": "open", "ev": "created",
                 "reason": None, "note": None, "actor": ctx.user_id},
            )  # fmt: skip
            tx.record(
                "planning_opportunity.created",
                target=Target("planning_opportunity", new_id),
                scope=Scope(engagement_id=scope.engagement_id, work_item_id=work_item_id),
            )
    except _Nothing:
        pass
    existing = await _rows(ctx, {"work": work_item_id, "rule": rule_key})
    return existing[0]


# --- screens (the system) ------------------------------------------------------------------------


@dataclass(frozen=True)
class ScreenResult:
    screen_id: UUID | None
    opportunity_ids: tuple[UUID, ...]
    consented: bool


_RETURN: Final = text(
    "SELECT form, tax_year, filing_status, client_entity_id FROM tax_returns "
    "WHERE work_item_id = :r"
)
_SUMMARY: Final = text(
    "SELECT lines FROM return_engine_summaries WHERE work_item_id = :r AND kind <> 'pro_forma' "
    "ORDER BY approved_at DESC LIMIT 1"
)
_SCREEN: Final = text(
    "INSERT INTO planning_screens (tenant_id, work_item_id, partner_user_id, trigger, "
    "rules_version, agent_run_id) VALUES (:t, :r, :partner, :trigger, :version, NULL) "
    "RETURNING id"
)
_EXISTING: Final = text(
    "SELECT id, status, row_version FROM planning_opportunities "
    "WHERE work_item_id = :r AND rule_key = :k"
)
_INSERT: Final = text(
    "INSERT INTO planning_opportunities (tenant_id, engagement_id, work_item_id, source_kind, "
    "title, body, client_id, screen_id, rule_key, category, product_kind, est_savings, "
    "savings_basis, consent_basis, consent_id, owner_user_id) VALUES (:t, :e, :r, 'rule', "
    ":title, CAST(:body AS jsonb), :client, :screen, :rule, :category, :product, :savings, "
    "CAST(:basis AS jsonb), :consent_basis, :consent, :owner) RETURNING id"
)
# A new row is inserted Open (the column's default; status is not an insert column) and moved.
_BLOCK: Final = text("UPDATE planning_opportunities SET status = 'not_screened' WHERE id = :id")
_REFRESH: Final = text(
    "UPDATE planning_opportunities SET title = :title, body = CAST(:body AS jsonb), "
    "status = :status, est_savings = :savings, savings_basis = CAST(:basis AS jsonb), "
    "row_version = row_version + 1, updated_at = clock_timestamp() "
    "WHERE id = :id AND row_version = :v"
)


def consent_status(product_kind: str, tri_valid: bool, other_services: bool) -> Status | None:
    """The §7216 filter (module docstring): Open when the model may narrate, Not screened when
    it may not, None (never written) for another product without its consent."""
    if product_kind == "non_tax_product" and not other_services:
        return None
    return "open" if tri_valid else "not_screened"


def filing_status(raw: str | None, entity_type: str | None) -> calc.FilingStatus:
    if raw in _STATUS_OF_FILING:
        return _STATUS_OF_FILING[raw]
    return "mfj" if entity_type == "household_mfj" else "single"


async def _owner(tenant: TenantContext, work_item_id: UUID, client_id: UUID) -> UUID | None:
    """The return's signer (its tax partner), else the client's relationship partner."""
    from abacus.modules.engagements.api import holders_of
    from abacus.modules.organisations.api import client_partner_of

    signers = await holders_of(tenant, work_item_id, "signer")
    if signers:
        return signers[0]
    partner = await client_partner_of(tenant, client_id)
    return partner if isinstance(partner, UUID) else None


async def screen_return(tenant: TenantContext, return_id: UUID, trigger: Trigger) -> ScreenResult:
    """Screen one return (module docstring). Without an approved engine summary, a parameter
    file for its year or an owner there is nothing to screen."""
    from abacus.kernel.clock import now
    from abacus.modules.engagements.api import work_item_scope
    from abacus.modules.organisations.api import (
        consent_state,
        entity_type_of,
        tri_consent_verdict,
    )

    scope = await work_item_scope(tenant, return_id)
    async with tenant_session(tenant) as session:
        ret = (await session.execute(_RETURN, {"r": return_id})).first()
        lines = await session.scalar(_SUMMARY, {"r": return_id})
    if scope is None or scope.engagement_id is None or ret is None or lines is None:
        return ScreenResult(None, (), False)
    try:
        params = calc.parameters(int(ret.tax_year))
    except LookupError:
        return ScreenResult(None, (), False)
    owner = await _owner(tenant, return_id, scope.client_id)
    if owner is None:
        return ScreenResult(None, (), False)
    entity = cast(UUID, ret.client_entity_id)
    status = filing_status(ret.filing_status, await entity_type_of(tenant, entity))
    facts = planning_rules.facts_from_lines(str(ret.form), int(ret.tax_year), status, lines)
    candidates = planning_rules.screen(facts, params)
    at = await now(tenant)
    verdict = await tri_consent_verdict(tenant, [entity], at, tax_year=int(ret.tax_year))
    other = await consent_state(tenant, [entity], "other_services_use", int(ret.tax_year))
    other_id = other[0].consent_id if other and other[0].status == "signed" else None
    kept: list[UUID] = []
    async with uow(tenant) as tx:
        screen_id = await tx.session.scalar(
            _SCREEN,
            {"t": tenant.tenant_id, "r": return_id, "partner": owner, "trigger": trigger,
             "version": params.version_ref},
        )  # fmt: skip
        for c in candidates:
            decided = consent_status(c.product_kind, verdict.valid, other_id is not None)
            if decided is None:
                continue  # §301.7216-3: another product needs the other-services consent
            to: Status = decided
            body = json.dumps([{"kind": "text", "text": planning_rules.rationale(c)}])
            basis = json.dumps(c.estimate.basis()) if c.estimate.savings is not None else None
            row = (await tx.session.execute(_EXISTING, {"r": return_id, "k": c.rule_key})).first()
            if row is None:
                new_id = await tx.session.scalar(
                    _INSERT,
                    {"t": tenant.tenant_id, "e": scope.engagement_id, "r": return_id,
                     "title": c.title, "body": body, "client": scope.client_id,
                     "screen": screen_id, "rule": c.rule_key, "category": c.category,
                     "product": c.product_kind, "savings": c.estimate.savings, "basis": basis,
                     "consent_basis": "301_7216_2h" if c.product_kind == "tax_service"
                     else "other_services_use",
                     "consent": None if c.product_kind == "tax_service" else other_id,
                     "owner": owner},
                )  # fmt: skip
                if to == "not_screened":
                    await tx.session.execute(_BLOCK, {"id": new_id})
                await tx.session.execute(
                    _EVENT,
                    {"t": tenant.tenant_id, "o": new_id, "f": None, "to": to, "ev": "screened",
                     "reason": None, "note": None, "actor": None},
                )  # fmt: skip
                kept.append(cast(UUID, new_id))
            elif row.status in SCREENABLE:
                await tx.session.execute(
                    _REFRESH,
                    {"title": c.title, "body": body, "status": to, "savings": c.estimate.savings,
                     "basis": basis, "id": row.id, "v": row.row_version},
                )  # fmt: skip
                if row.status != to:
                    await tx.session.execute(
                        _EVENT,
                        {"t": tenant.tenant_id, "o": row.id, "f": row.status, "to": to,
                         "ev": "screened", "reason": None, "note": None, "actor": None},
                    )  # fmt: skip
                kept.append(cast(UUID, row.id))
        tx.record(
            "planning_opportunity.screened",
            target=Target("tax_return", return_id),
            after=Ref(screen=cast(UUID, screen_id), opportunities=len(kept)),
            scope=Scope(engagement_id=scope.engagement_id, work_item_id=return_id),
        )
    if verdict.valid and kept and _NARRATOR:
        try:
            await _NARRATOR[0](tenant, return_id, kept)
        except Exception as exc:  # the template rationale stands (DF-04)
            _log.warning("planning.narrator_failed", error=type(exc).__name__)
    return ScreenResult(cast(UUID, screen_id), tuple(kept), verdict.valid)


async def _planning_on(tenant: TenantContext) -> bool:
    from abacus.kernel._flags import TAX_PLANNING
    from abacus.kernel.flags import flag_enabled

    return await flag_enabled(tenant, TAX_PLANNING)


def _system(tenant_id: UUID, what: str) -> TenantContext:
    return TenantContext(tenant_id, "system", f"planning:{what}")


async def on_return_approved(event: OutboxEvent) -> None:
    """`tax_return.approved`: screen the return (trigger `return_approved`)."""
    e = event
    tenant = _system(e.tenant_id, "return_approved")
    if await _planning_on(tenant):
        await screen_return(tenant, UUID(str(e.payload["work_item_id"])), "return_approved")


async def on_filing_acknowledged(event: OutboxEvent) -> None:
    """`filing.acknowledged` accepted (not an extension's): screen it (`return_accepted`)."""
    e = event
    if e.payload.get("status") != "accepted" or e.payload.get("extension_id"):
        return
    tenant = _system(e.tenant_id, "return_accepted")
    if await _planning_on(tenant):
        await screen_return(tenant, UUID(str(e.payload["return_id"])), "return_accepted")


_RETURNS_OF_ENTITIES: Final = text(
    "SELECT work_item_id FROM tax_returns WHERE client_entity_id = ANY(:entities) "
    "AND status IN ('approved', 'filed', 'accepted') ORDER BY work_item_id"
)


async def on_consent_completed(event: OutboxEvent) -> None:
    """`envelope.completed` on a `consent_set`, after its consents are signed: re-screen the
    taxpayer's approved returns (`consent_completed`), so Not screened rows can open."""
    from abacus.modules.organisations.api import client_entity_names

    e = event
    if e.payload.get("source_kind") != "consent_set":
        return
    tenant = _system(e.tenant_id, "consent_completed")
    if not await _planning_on(tenant):
        return
    client = e.payload.get("client_id")
    if not isinstance(client, str):
        return
    async with tenant_session(tenant) as session:
        entities = list(await client_entity_names(session, UUID(client)))
        returns = list(await session.scalars(_RETURNS_OF_ENTITIES, {"entities": entities}))
    for return_id in returns:
        await screen_return(tenant, return_id, "consent_completed")


_BY_SOURCE: Final = text(
    "SELECT id, status, row_version, client_id, engagement_id, work_item_id "
    "FROM planning_opportunities WHERE id = :id"
)


async def on_engagement_created(event: OutboxEvent) -> None:
    """`engagement.created` carrying `planning_opportunity:<id>`: the opportunity becomes
    Accepted with the engagement as its project (AC5.4), when the engagement is the same
    client's and the opportunity is still Open or Raised."""
    from abacus.modules.engagements.api import client_of

    e = event
    ref = e.payload.get("source_ref")
    if not isinstance(ref, str) or not ref.startswith(SOURCE_PREFIX):
        return
    try:
        opportunity_id = UUID(ref[len(SOURCE_PREFIX) :])
    except ValueError:
        return
    tenant = _system(e.tenant_id, "engagement_created")
    engagement_id = UUID(str(e.payload["engagement_id"]))
    async with tenant_session(tenant) as session:
        row = (await session.execute(_BY_SOURCE, {"id": opportunity_id})).first()
    if row is None or row.status not in ("open", "raised"):
        return
    if await client_of(tenant, engagement_id) != row.client_id:
        return
    async with uow(tenant) as tx:
        moved = await tx.session.scalar(
            text(
                "UPDATE planning_opportunities SET status = 'accepted', previous_status = NULL, "
                "project_engagement_id = :eng, row_version = row_version + 1, "
                "updated_at = clock_timestamp() WHERE id = :id AND row_version = :v "
                "RETURNING row_version"
            ),
            {"eng": engagement_id, "id": opportunity_id, "v": row.row_version},
        )
        if moved is None:
            return
        await tx.session.execute(
            _EVENT,
            {"t": tenant.tenant_id, "o": opportunity_id, "f": row.status, "to": "accepted",
             "ev": "accepted", "reason": None, "note": None, "actor": None},
        )  # fmt: skip
        tx.record(
            "planning_opportunity.accepted",
            target=Target("planning_opportunity", opportunity_id),
            after=Ref(engagement=engagement_id),
            scope=Scope(engagement_id=row.engagement_id, work_item_id=row.work_item_id),
        )


SUBSCRIPTIONS: Final = {
    "tax_return.approved": on_return_approved,
    "engagement.created": on_engagement_created,
}


__all__ = [
    "SUBSCRIPTIONS",
    "Opportunity",
    "ProjectPrefill",
    "RaiseSheet",
    "ScreenResult",
    "Summary",
    "allowed",
    "consent_envelope",
    "consent_status",
    "create_manual",
    "create_project",
    "decline",
    "dismiss",
    "filing_status",
    "on_consent_completed",
    "on_engagement_created",
    "on_filing_acknowledged",
    "on_return_approved",
    "opportunities",
    "opportunity",
    "prepare_raise",
    "raise_with_client",
    "register_planning_narrator",
    "restore",
    "screen_return",
    "summarise",
    "summary",
]
