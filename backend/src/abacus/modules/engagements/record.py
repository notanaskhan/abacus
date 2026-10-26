"""ENG-02's engagement record, its gates and the interim recorded letter, live (P-07-T15; SPEC-321
AC-17; engagements-v2 contract §3; DEC-224).

- The record projection: subbar facts, rail bands (Details always; Review and Delivery's partner;
  the Client Portal band only for a caller who reads content), the contacts block (designations,
  for a caller holding `client_contact.read`), letter summary, gates, tab counts, why it is read
  only and the row's version. A walled engagement answers 404 (the wall layer), a client
  principal 404: this is a firm surface.
- Gates: the gates the type requires (G1 to G9) from the registered providers, each met (with
  when and, for G1, by whom where known), blocked (object-reference blockers with a reason code),
  or not started. An unregistered gate's provider is "no_gate_provider", so G4 to G9 read blocked
  until A-04, A-06 and A-07 register.
- The interim recorded letter (G3 until C7): a person with `letter.record`, G1 met, both
  signature dates on or after the G1 decision (409 `letter_before_acceptance`), never on an
  archived engagement (409 `engagement_archived`). It writes the letter, moves an Accepted
  engagement to Contracted (the system move on the fact), one `letter.recorded` audit event and
  `gate.met` (G3) in one unit of work. "Not required this year" is the engagement partner's, and
  only while the firm setting `allow_letter_exceptions` is on; that setting is not registered
  yet, so the exception answers 409 `letter_exceptions_off` (fail closed, DEC-224).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Annotated, ClassVar, Final, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._statuses import EngagementStatus
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.engagements.acceptance_tables import g1_decision
from abacus.modules.engagements.gate_policy import required_gates
from abacus.modules.engagements.index import PARTNER_ROLES, LetterSummary, letter_summary
from abacus.modules.engagements.models import (
    Engagement,
    EngagementLetter,
    WorkItem,
)
from abacus.modules.engagements.repository import get_letter, latest_acceptance, put_letter
from abacus.modules.engagements.service import get_ref, lock_ref
from abacus.modules.engagements.slots import gate_fact
from abacus.modules.engagements.transitions import transition
from abacus.modules.identity.api import (
    AuthContext,
    allowed_actions,
    authorise,
    engagement_team_query,
)
from abacus.modules.organisations.api import (
    client_name_column,
    client_names,
    contact_facts,
    office_name_column,
)

READ: Final = "engagement.read_metadata"
_RECORD_ACTIONS: Final = (
    "engagement.read_metadata",
    "engagement.read",
    "letter.record",
    "client_contact.read",
    "engagement.update",
    "engagement.hold",  # ENG-02's status pill menu (DEC-344)
)


class LetterBeforeAcceptance(DomainConflict):
    """The letter's date is before the acceptance decision (G1 < letter, R-06)."""

    code = "letter_before_acceptance"


class GateUnmet(DomainConflict):
    """A gate the step or the create requires is not met (C1 gate providers; `facts.gate`)."""

    code = "gate_unmet"


class EngagementArchived(DomainConflict):
    """The engagement is archived: it is read-only (`archived_write: deny`)."""

    code = "engagement_archived"


class LetterExceptionsOff(DomainConflict):
    """ "Not required this year" needs the engagement partner and the firm setting
    `allow_letter_exceptions` on."""

    code = "letter_exceptions_off"


class GateMet(DomainEvent):
    """A gate became met (G1, G2 or the interim G3): identifiers and the gate code only."""

    event_type: ClassVar[str] = "gate.met"

    engagement_id: Annotated[UUID, classified("internal")]
    gate: Annotated[str, classified("internal")]


# --- gates --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GateBlocker:
    type: str
    id: UUID
    reason_code: str


@dataclass(frozen=True)
class GateView:
    gate: str
    met: bool
    blockers: list[GateBlocker] = field(default_factory=list[GateBlocker])
    met_at: datetime | None = None
    met_by_user_id: UUID | None = None


async def gate_views(ctx: AuthContext, engagement: Engagement) -> list[GateView]:
    """The type's gates from their providers; G1 and G3 carry when they were met."""
    async with tenant_session(ctx.tenant) as session:
        decided = await g1_decision(session, engagement.id)
        acceptance = await latest_acceptance(session, engagement.id)
        letter = await get_letter(session, engagement.id)
    views: list[GateView] = []
    for gate in required_gates(engagement.type):
        fact = await gate_fact(ctx.tenant, engagement.id, gate)
        if fact.met:
            met_at = None
            met_by = None
            if gate == "G1" and decided is not None:
                met_at, met_by = decided.decided_at, decided.decided_by
            elif gate == "G2" and acceptance is not None:
                met_at = acceptance.independence_concluded_at
            elif gate == "G3" and letter is not None:
                met_at = letter.recorded_at
                met_by = letter.recorded_by_user_id
            views.append(GateView(gate, True, met_at=met_at, met_by_user_id=met_by))
        else:
            views.append(
                GateView(
                    gate,
                    False,
                    [GateBlocker("engagement", engagement.id, code) for code in fact.blockers],
                )
            )
    return views


async def _readable(ctx: AuthContext, engagement_id: UUID) -> Engagement:
    if ctx.client:
        raise NotFound("engagement")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, READ, ref.resource())
    async with tenant_session(ctx.tenant) as session:
        found = await session.get(Engagement, engagement_id)
    if found is None:
        raise NotFound("engagement")
    return found


async def engagement_gates_v2(ctx: AuthContext, engagement_id: UUID) -> list[GateView]:
    return await gate_views(ctx, await _readable(ctx, engagement_id))


# --- the record projection ----------------------------------------------------------------------


@dataclass(frozen=True)
class RailRow:
    key: str
    text: str | None = None
    user_id: UUID | None = None
    on: date | None = None
    pill_object: str | None = None
    pill_code: str | None = None


@dataclass(frozen=True)
class RailBand:
    band: Literal["details", "review_delivery", "client_portal"]
    rows: list[RailRow]


@dataclass(frozen=True)
class Designation:
    designation: str
    contact_id: UUID
    name: str


@dataclass(frozen=True)
class RecordView:
    engagement: Engagement
    client_name: str
    client_entity_name: str
    bands: list[RailBand]
    contacts: list[Designation]
    letter: LetterSummary
    gates: list[GateView]
    work_item_count: int
    team_count: int
    read_only_reason: Literal["archived"] | None
    allowed_actions: list[str]


async def engagement_record(ctx: AuthContext, engagement_id: UUID) -> RecordView:
    from abacus.modules.engagements.contacts import designations_of  # contacts imports service

    engagement = await _readable(ctx, engagement_id)
    resource = (await get_ref(ctx, engagement_id)).resource()
    actions = sorted(await allowed_actions(ctx, resource, _RECORD_ACTIONS))
    team = engagement_team_query().subquery("team")
    async with tenant_session(ctx.tenant) as session:
        names = (
            await session.execute(
                select(
                    client_name_column(Engagement.client_id),
                    office_name_column(Engagement.office_id),
                ).where(Engagement.id == engagement_id)
            )
        ).one()
        entity_names = await _entity_name(session, engagement.client_entity_id)
        letter = await get_letter(session, engagement_id)
        work_items = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(WorkItem)
                    .where(WorkItem.engagement_id == engagement_id, WorkItem.archived_at.is_(None))
                )
            ).scalar_one()
        )
        members = (
            await session.execute(
                select(team.c.user_id, team.c.role)
                .where(team.c.engagement_id == engagement_id)
                .order_by(team.c.role, team.c.user_id)
            )
        ).all()
        designations = (
            await designations_of(session, engagement_id)
            if "client_contact.read" in actions
            else []
        )
        contact_names = (
            await contact_facts(session, [d.contact_id for d in designations])
            if designations
            else {}
        )
    summary = letter_summary(letter)
    details = [
        RailRow("client", text=names[0]),
        RailRow("entity", text=entity_names),
        RailRow("period", text=engagement.period_label),
        RailRow("office", text=names[1]),
        RailRow(
            "letter",
            on=summary.signed_on,
            pill_object="letter_record",
            pill_code=summary.status,
        ),
    ]
    partners = [user for user, role in members if role in PARTNER_ROLES]
    bands = [
        RailBand("details", [r for r in details if r.text is not None or r.key == "letter"]),
        RailBand("review_delivery", [RailRow("partner", user_id=u) for u in partners]),
    ]
    if "engagement.read" in actions:
        bands.append(RailBand("client_portal", [RailRow("contacts", text=None)]))
    return RecordView(
        engagement=engagement,
        client_name=names[0],
        client_entity_name=entity_names,
        bands=bands,
        contacts=[
            Designation(d.designation, d.contact_id, contact_names[d.contact_id].display_name)
            for d in designations
            if d.contact_id in contact_names
        ],
        letter=summary,
        gates=await gate_views(ctx, engagement),
        work_item_count=work_items,
        team_count=len({u for u, _ in members}),
        read_only_reason="archived" if engagement.status == "archived" else None,
        allowed_actions=actions,
    )


async def _entity_name(session: AsyncSession, entity_id: UUID) -> str:
    found = await client_names(session, [entity_id])
    named = found.get(entity_id)
    return "" if named is None else named.client_entity_name


# --- the interim recorded letter ----------------------------------------------------------------


@dataclass(frozen=True)
class RecordedLetterIn:
    mode: Literal["signed", "not_required_this_year"]
    client_signed_on: date | None = None
    firm_signed_on: date | None = None
    client_signer_contact_id: UUID | None = None
    firm_signer_user_id: UUID | None = None
    signed_copy_version_id: UUID | None = None
    not_required_reason: str | None = None


@dataclass(frozen=True)
class RecordedLetter:
    engagement_id: UUID
    letter: EngagementLetter
    acceptance_decided_at: datetime
    engagement_status: str


async def record_letter_v2(
    ctx: AuthContext, engagement_id: UUID, given: RecordedLetterIn
) -> RecordedLetter:
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        if ref.archived:
            raise EngagementArchived(facts={"engagement_id": str(engagement_id)})
        await authorise(ctx, "letter.record", ref.resource())
        if given.mode == "not_required_this_year":
            raise LetterExceptionsOff(facts={"engagement_id": str(engagement_id)})
        acceptance = await g1_decision(tx.session, engagement_id)
        if acceptance is None or not acceptance.accepted:
            raise GateUnmet(facts={"gate": "G1", "engagement_id": str(engagement_id)})
        if given.client_signed_on is None or given.firm_signed_on is None:
            raise GateUnmet(facts={"gate": "G3", "engagement_id": str(engagement_id)})
        decided_on = acceptance.decided_at.date()
        if min(given.client_signed_on, given.firm_signed_on) < decided_on:
            raise LetterBeforeAcceptance(facts={"engagement_id": str(engagement_id)})
        previous = await get_letter(tx.session, engagement_id)
        await put_letter(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "status": "signed",
                "letter_date": max(given.client_signed_on, given.firm_signed_on),
                "reason": None,
                "link": None,
                "recorded_by": str(ctx.user_id),
                "recorded_by_user_id": ctx.user_id,
                "client_signed_on": given.client_signed_on,
                "firm_signed_on": given.firm_signed_on,
                "client_signer_contact_id": given.client_signer_contact_id,
                "firm_signer_user_id": given.firm_signer_user_id,
                "signed_copy_version_id": given.signed_copy_version_id,
                **(
                    {}
                    if previous is None
                    else {
                        "file_key": previous.file_key,
                        "file_version_id": previous.file_version_id,
                        "file_fingerprint": previous.file_fingerprint,
                        "file_size": previous.file_size,
                        "file_media_type": previous.file_media_type,
                        "file_name": previous.file_name,
                    }
                ),
            },
        )
        status = (
            await tx.session.execute(
                select(Engagement.status).where(Engagement.id == engagement_id)
            )
        ).scalar_one()
        if status == EngagementStatus.ACCEPTED:
            await transition(tx, engagement_id, "contracted", by="system")
            status = "contracted"
        tx.record(
            "letter.recorded",
            target=Target("engagement", engagement_id),
            after=Ref(signed=1),
        )
        if previous is None or previous.status not in ("signed", "not_required_this_year"):
            tx.emit(GateMet(engagement_id=engagement_id, gate="G3"))
    async with tenant_session(ctx.tenant) as session:
        stored = await get_letter(session, engagement_id)
    if stored is None:  # written in the unit of work just committed
        raise NotFound("engagement_letter")
    return RecordedLetter(engagement_id, stored, acceptance.decided_at, status)
