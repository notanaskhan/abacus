"""The clients family contract, v1: CLI-01 and CLI-02 (P-07-T04 stub; ADR-139, P-36). Contract:
`docs/contracts/clients.md`; spec: SPEC-321.

Every route is live for every firm since P-07-T59 retired `clients.v2` (P-07-T08 the
index, P-07-T09 the record, overview, relationships and PATCH, P-07-T10 the TIN reveal). The
live client picker (`GET /v1/firm/clients/search`) stays
where it is.

Walls: a walled client is absent from every row, count, facet and total, and answers 404 by id
(INV-3, DEC-43). No model here has a hidden-by-wall field, a walled client's name or a TIN. A
taxpayer ID appears only masked (`MaskedTinOut`, last four digits, Restricted) on the record,
never in a list, and in plain text only in the one reveal response (DEC-141).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import ClientStatus, EngagementStatus, InvitationStatus
from abacus.kernel.classification import classified
from abacus.kernel.listing import ListPage
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context, mask_tins_for
from abacus.modules.organisations import live, tin

Ctx = Annotated[AuthContext, Depends(current_context)]

# Codes from the database CHECKs (migration 0082, F-03-T25) and P-07 §4.2 M1 (P-07-T07).
ClientKind = Literal["household", "business", "plan_sponsor", "nonprofit", "trust_family"]
EntityType = Literal[
    "individual",
    "household_mfj",
    "c_corp",
    "s_corp",
    "llc",
    "partnership",
    "trust",
    "estate",
    "ebp_plan",
    "exempt_org",
]
ServiceLine = Literal["audit", "tax", "cas", "advisory"]
RiskTier = Literal["low", "moderate", "high"]
ClientSort = Literal["last_activity", "name"]
RelationshipKind = Literal[
    "spouse",
    "owner_of",
    "trustee_of",
    "beneficiary_of",
    "sponsor_of",
    "upper_tier_of",
    "executor_of",
    "gp_of",
    "lp_of",
    "estate_of",
]
TinKind = Literal["ssn", "ein", "itin"]
# `client_entities.tin_status` minus `none` (no TIN: the field is null).
TinPresence = Literal["on_file", "applied_for"]
# Why a person reveals a TIN (P-07 §4.3: a registry code, never free text). DEC-141.
TinRevealReason = Literal[
    "prepare_return",
    "review_return",
    "file_or_correct_filing",
    "respond_to_notice",
    "verify_identity",
]
# The kind profile CLI-02's overview renders (business a, household b, plan sponsor c, empty e).
OverviewProfile = Literal["business", "household", "plan_sponsor", "empty"]
OverviewSectionKind = Literal["stats", "details", "table", "key_dates", "activity"]


# --- CLI-01 index -------------------------------------------------------------------------------


class ClientRowOut(BaseModel):
    """A CLI-01 row: metadata only, after `visible(scope=client)` (INV-3). No TIN, no hidden
    count; a walled client is simply not a row."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]  # the client's own display name (DEC-62)
    descriptor: Annotated[str | None, classified("confidential")] = None  # the row's sub-line
    kind: Annotated[ClientKind | None, classified("internal")]
    status: Annotated[ClientStatus, classified("internal")]  # C2 `client` (P-07-T03)
    entity_count: Annotated[int, classified("internal")]
    service_lines: Annotated[list[ServiceLine], classified("internal")]
    is_attest_client: Annotated[bool, classified("internal")]  # derived (DEC-128): "Attest"
    office_id: Annotated[UUID | None, classified("internal")] = None
    office_name: Annotated[str | None, classified("internal")] = None
    relationship_partner_id: Annotated[UUID | None, classified("internal")] = None
    relationship_partner_initials: Annotated[str | None, classified("internal")] = None
    portal_status: Annotated[InvitationStatus, classified("internal")]  # the rollup (DF-31)
    # Open client requests (C5), registered by requests; null when no provider answers ("—").
    open_request_count: Annotated[int | None, classified("internal")] = None
    binder_draft_only: Annotated[bool, classified("internal")] = False  # "Binder draft"
    last_activity_at: Annotated[datetime | None, classified("internal")] = None
    # An audit event type the UI words ("Sep 11 · …"); identifiers only, never prose.
    last_activity_event_type: Annotated[str | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


# --- CLI-02 record ------------------------------------------------------------------------------


class MaskedTinOut(BaseModel):
    """A taxpayer ID as every payload but the reveal carries it: kind and last four digits
    (`XX-XXX0287`, `•••-••-2208`). Restricted; never in a list (ADR-031, P-12)."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[TinKind, classified("internal")]
    presence: Annotated[TinPresence, classified("internal")]
    last4: Annotated[
        str | None, Field(pattern=r"^[0-9]{4}$"), classified("restricted", pii_kind="tin")
    ] = None


class ClientEntityBriefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    entity_type: Annotated[EntityType | None, classified("internal")] = None
    fye_month_day: Annotated[str | None, classified("internal")] = None
    state_of_formation: Annotated[str | None, classified("internal")] = None
    plan_number: Annotated[str | None, classified("internal")] = None
    tin: Annotated[MaskedTinOut | None, classified("restricted")] = None


class ClientTabCountsOut(BaseModel):
    """CLI-02 tab counts; null where the tab's owner registers no count (the tab shows none)."""

    model_config = ConfigDict(frozen=True)

    engagements: Annotated[int, classified("internal")]
    relationships: Annotated[int, classified("internal")]
    contacts: Annotated[int | None, classified("internal")] = None
    messages: Annotated[int | None, classified("internal")] = None


class ClientEngagementBriefOut(BaseModel):
    """The "2 active engagements ⌄" menu: visible engagements only."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    status: Annotated[EngagementStatus, classified("internal")]  # C2
    service_line: Annotated[ServiceLine, classified("internal")]


class ClientRecordOut(BaseModel):
    """CLI-02's subbar facts, rail Details and Team, and tab counts. The Team band's Partner is
    the stored relationship partner; Manager and Preparer are derived (DEC-62, DEC-138)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    descriptor: Annotated[str | None, classified("confidential")] = None
    kind: Annotated[ClientKind | None, classified("internal")]
    status: Annotated[ClientStatus, classified("internal")]  # C2 `client`
    is_attest_client: Annotated[bool, classified("internal")]
    risk_tier: Annotated[RiskTier | None, classified("internal")] = None
    primary_office_id: Annotated[UUID | None, classified("internal")] = None
    office_name: Annotated[str | None, classified("internal")] = None
    relationship_partner_id: Annotated[UUID | None, classified("internal")] = None
    manager_user_ids: Annotated[list[UUID], classified("internal")] = []
    preparer_user_ids: Annotated[list[UUID], classified("internal")] = []
    portal_status: Annotated[InvitationStatus, classified("internal")]
    entities: Annotated[list[ClientEntityBriefOut], classified("restricted")]
    active_engagements: Annotated[list[ClientEngagementBriefOut], classified("confidential")] = []
    tab_counts: Annotated[ClientTabCountsOut, classified("internal")]
    version: Annotated[int, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")] = []


class ClientObjectRefOut(BaseModel):
    """An opaque reference an overview row links to (an engagement, a work item, a binder)."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[str, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class ClientOverviewItemOut(BaseModel):
    """One stat, KV row, table row, key date or activity line. Numbers are decimal strings
    computed in code (ADR-050); `pill_object` and `pill_code` name a C2 status the UI words."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]  # the provider's row code
    text: Annotated[str | None, classified("confidential")] = None
    figure: Annotated[str | None, classified("confidential")] = None
    on: Annotated[date | None, classified("internal")] = None
    at: Annotated[datetime | None, classified("internal")] = None
    pill_object: Annotated[str | None, classified("internal")] = None
    pill_code: Annotated[str | None, classified("internal")] = None
    ref: Annotated[ClientObjectRefOut | None, classified("internal")] = None


class ClientOverviewSectionOut(BaseModel):
    """A section from one registered provider, present only when the caller holds the
    provider's own read action (a metadata-only role gets metadata sections; ADR-024)."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]  # the registered section code
    kind: Annotated[OverviewSectionKind, classified("internal")]
    read_action: Annotated[str, classified("internal")]
    items: Annotated[list[ClientOverviewItemOut], classified("confidential")]
    total: Annotated[int | None, classified("internal")] = None  # "View all {n}"


class ClientOverviewOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_id: Annotated[UUID, classified("internal")]
    profile: Annotated[OverviewProfile, classified("internal")]
    sections: Annotated[list[ClientOverviewSectionOut], classified("confidential")]


class ClientRelationshipOut(BaseModel):
    """One `entity_relationships` edge. An edge into a walled client is omitted, never
    redacted (INV-3)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[RelationshipKind, classified("internal")]
    from_entity_id: Annotated[UUID, classified("internal")]
    from_entity_name: Annotated[str, classified("confidential")]
    to_entity_id: Annotated[UUID, classified("internal")]
    to_entity_name: Annotated[str, classified("confidential")]
    to_client_id: Annotated[UUID, classified("internal")]
    percent: Annotated[str | None, classified("confidential")] = None  # decimal string
    effective_from: Annotated[date | None, classified("internal")] = None
    effective_to: Annotated[date | None, classified("internal")] = None


class ClientStatusChangeIn(BaseModel):
    """A person may move a client to inactive or former, and back to active; prospect to active
    is a system transition (409 `illegal_transition`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Annotated[ClientStatus, classified("internal")]  # C2 `client`


class ClientPatchIn(BaseModel):
    """Absent fields are unchanged; `status_change` is absent unless the status moves."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    seen_version: Annotated[int, Field(ge=0), classified("internal")]
    descriptor: Annotated[
        SingleLineText | None,
        Field(default=None, min_length=1, max_length=120),
        classified("confidential"),
    ]
    primary_office_id: Annotated[UUID | None, classified("internal")] = None
    relationship_partner_id: Annotated[UUID | None, classified("internal")] = None
    status_change: Annotated[ClientStatusChangeIn | None, classified("internal")] = None


class TinRevealIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[TinRevealReason, classified("internal")]


class TinRevealOut(BaseModel):
    """The plain value, once, `Cache-Control: no-store`, for the 10-second reveal. The only
    payload that carries a TIN; one `tin.revealed` audit event names the reason, never the
    value (P-07 Story 1.3; DEC-141)."""

    model_config = ConfigDict(frozen=True)

    entity_id: Annotated[UUID, classified("internal")]
    kind: Annotated[TinKind, classified("internal")]
    value: Annotated[str, classified("restricted", pii_kind="tin")]
    remask_after_seconds: Annotated[int, classified("internal")] = 10


def _row(r: live.ClientRow) -> ClientRowOut:
    return ClientRowOut.model_validate(r, from_attributes=True)


def _record(v: live.ClientRecordView) -> ClientRecordOut:
    c = v.client
    return ClientRecordOut(
        id=c.id,
        name=c.name,
        descriptor=c.descriptor,
        kind=cast(ClientKind | None, c.kind),
        status=ClientStatus(c.status),
        is_attest_client=c.is_attest_client,
        risk_tier=cast(RiskTier | None, c.risk_tier),
        primary_office_id=c.primary_office_id,
        office_name=v.office_name,
        relationship_partner_id=c.relationship_partner_id,
        manager_user_ids=v.manager_user_ids,
        preparer_user_ids=v.preparer_user_ids,
        portal_status=InvitationStatus(c.portal_status),
        entities=[
            ClientEntityBriefOut(
                id=e.id,
                name=e.name,
                entity_type=cast(EntityType | None, e.entity_type),
                fye_month_day=e.fye_month_day,
                state_of_formation=e.state_of_formation,
                plan_number=e.plan_number,
                tin=(
                    None
                    if e.tin_kind is None
                    else MaskedTinOut(
                        kind=cast(TinKind, e.tin_kind),
                        presence=cast(TinPresence, e.tin_presence),
                        last4=e.tin_last4,
                    )
                ),
            )
            for e in v.entities
        ],
        active_engagements=[
            ClientEngagementBriefOut(
                id=b.id,
                name=b.name,
                status=EngagementStatus(b.status),
                service_line=cast(ServiceLine, b.service_line),
            )
            for b in v.active_engagements
        ],
        tab_counts=ClientTabCountsOut.model_validate(v.tab_counts),
        version=c.version,
        allowed_actions=v.allowed_actions,
    )


clients_router = AbacusRouter(prefix="/v1/clients", tags=["clients"])
client_entities_router = AbacusRouter(prefix="/v1/client-entities", tags=["clients"])


@clients_router.get("", action="client.read", response_model=ListPage[ClientRowOut])
async def list_clients_route(
    ctx: Ctx,
    kind: Annotated[ClientKind | None, Query()] = None,
    office_id: Annotated[UUID | None, Query()] = None,
    partner_id: Annotated[UUID | None, Query()] = None,
    service_line: Annotated[ServiceLine | None, Query()] = None,
    status: Annotated[ClientStatus | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[ClientSort, Query()] = "last_activity",
    facets: Annotated[bool, Query()] = False,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ListPage[ClientRowOut]:
    """CLI-01: rows, `counts` per client status and, on request, `facets` (kind, office,
    partner, service line), after `visible(scope=client)`. `total` is exact (DEC-47); `q` is
    never logged."""
    found = await live.list_clients(
        ctx,
        live.ClientFilters(
            kind=kind,
            office_id=office_id,
            partner_id=partner_id,
            service_line=service_line,
            status=None if status is None else status.value,
            q=q,
        ),
        sort=sort,
        facets=facets,
        cursor=cursor,
        limit=limit,
    )
    return ListPage[ClientRowOut](
        items=[_row(r) for r in found.items],
        next_cursor=found.next_cursor,
        total=found.total,
        total_capped=found.total_capped,
        counts=found.counts,
        facets=found.facets,
    )


@clients_router.get("/{client_id}", action="client.read", response_model=ClientRecordOut)
async def get_client_route(client_id: UUID, ctx: Ctx) -> ClientRecordOut:
    return await mask_tins_for(ctx, _record(await live.client_record(ctx, client_id)))


@clients_router.get(
    "/{client_id}/overview", action="client.read", response_model=ClientOverviewOut
)
async def client_overview_route(client_id: UUID, ctx: Ctx) -> ClientOverviewOut:
    """Per-kind profile from registered section providers, each filtered by its own read action;
    an unregistered section is absent and an unregistered column renders "—" (fail closed)."""
    profile, sections = await live.client_overview(ctx, client_id)
    return ClientOverviewOut(
        client_id=client_id,
        profile=profile,
        sections=[
            ClientOverviewSectionOut(
                code=s.code,
                kind=cast(OverviewSectionKind, s.kind),
                read_action=s.read_action,
                items=[
                    ClientOverviewItemOut(
                        key=i.key,
                        text=i.text,
                        figure=i.figure,
                        on=i.on,
                        at=i.at,
                        pill_object=i.pill_object,
                        pill_code=i.pill_code,
                        ref=(
                            None
                            if i.ref_type is None or i.ref_id is None
                            else ClientObjectRefOut(type=i.ref_type, id=i.ref_id)
                        ),
                    )
                    for i in s.rows.items
                ],
                total=s.rows.total,
            )
            for s in sections
        ],
    )


@clients_router.patch(
    "/{client_id}", action="client.update", response_model=ClientRecordOut, errors=(409,)
)
async def update_client_route(client_id: UUID, body: ClientPatchIn, ctx: Ctx) -> ClientRecordOut:
    """Descriptor, office, relationship partner and status; 409 `stale_version`, 409
    `illegal_transition`; one `client.updated` audit event."""
    await live.update_client(
        ctx,
        client_id,
        live.ClientPatch(
            seen_version=body.seen_version,
            descriptor=body.descriptor,
            primary_office_id=body.primary_office_id,
            relationship_partner_id=body.relationship_partner_id,
            status=None if body.status_change is None else body.status_change.status.value,
        ),
    )
    return await mask_tins_for(ctx, _record(await live.client_record(ctx, client_id)))


@clients_router.get(
    "/{client_id}/relationships",
    action="client.read",
    response_model=ListPage[ClientRelationshipOut],
)
async def client_relationships_route(
    client_id: UUID, ctx: Ctx, cursor: Annotated[str | None, Query(max_length=512)] = None
) -> ListPage[ClientRelationshipOut]:
    found = await live.client_relationships(ctx, client_id, cursor)
    return ListPage[ClientRelationshipOut](
        items=[ClientRelationshipOut.model_validate(r, from_attributes=True) for r in found.items],
        next_cursor=found.next_cursor,
        total=found.total,
        total_capped=found.total_capped,
    )


@client_entities_router.post(
    "/{entity_id}/tin/reveal", action="tin.reveal", response_model=TinRevealOut, errors=(429,)
)
async def reveal_tin_route(
    entity_id: UUID, body: TinRevealIn, ctx: Ctx, response: Response
) -> TinRevealOut:
    """Human-only: a live, onshore person with recent MFA and a reason, holding `tin.reveal` on
    one of the client's open engagements (P-07-T10, DEC-223); 403 otherwise, 404 for a walled or
    unknown entity or no TIN on file; 403 `mfa_step_up_required` when only MFA is stale; 429
    `tin_reveal_rate_limited` past 20 reveals an hour (DEC-232). One `tin_reveals` row and one
    `tin.revealed` audit event in the same unit of work (the reason, never the value);
    `Cache-Control: no-store`."""
    revealed = await tin.reveal_tin(ctx, entity_id, body.reason)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TinRevealOut(entity_id=revealed.entity_id, kind=revealed.kind, value=revealed.value)
