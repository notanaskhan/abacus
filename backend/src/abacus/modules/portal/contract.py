"""C5 v1.1, the portal half: the POR-02 home and preferences (P-08-T01 stub; ADR P-36, ADR-163).
Contract: `docs/contracts/portal-identity.md`; spec: SPEC-320.

Behind `portal.home_v2`: off, both routes answer 404; on, 501 `not_implemented` until P-08-T13
(the home read model over `home_sources`). The Brightwater Hale portal slice (`stub_from_seed`)
arrives with P-08-T08, so the stubs return no fixtures yet.

The home is a client's view. No field carries a firm status code, an amount, materiality, an agent
name or a confidence: stages and pills are client stage codes (`stages.py`, P-08-T12), team members
carry client-facing role codes, and the words come from the frontend copy registry (ADR P-36
code to words). Every aggregate is filtered by the grant that covers its own target scope, so role
union never leaks one scope into another (INV-4).

`GET /v1/portal/branding` and `GET /v1/portal/branding/logo` are live (P-08-T05; ADR-163 §6): the
two routes on ADR-152's public-route list, under the `PORTAL_PUBLIC` marker. They answer anyone,
Public fields only, the same shape for an unknown host, and never a tenant id.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import PORTAL_HOME_V2
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    PORTAL_PUBLIC,
    AbacusRouter,
    AuthContext,
    ScopeKind,
    current_member,
)
from abacus.modules.portal.branding import branding_for_host, logo_for_host

# A portal person themself, never a break-glass support context.
Member = Annotated[AuthContext, Depends(current_member)]
# `PortalHomeEarlierOut` has a field named `date`, which would shadow the type in its own body.
Day = date
# Identifier-only facts (ADR-139): codes, identifiers, counts and flags; never prose.
Facts = dict[str, str | int | bool]

# The kinds of to-do POR-02 shows (a to h). A kind whose source module has not shipped is hidden in
# production and rendered in fixture builds (P-08 §2.2). New kinds are additive.
TodoKind = Literal[
    "upload",
    "answer",
    "sign",
    "deliverables",
    "approve",
    "reconnect",
    "review_statements",
    "control_requests",
    "exceptions",
    "description_approved",
]
TodoState = Literal["open", "none", "overdue"]
# The screen a to-do or row opens: manifest IDs, never URLs.
PortalScreen = Literal[
    "POR-03",
    "POR-04",
    "POR-05",
    "POR-06",
    "POR-07",
    "POR-08",
    "POR-09",
    "POR-11",
    "POR-12",
    "POR-13",
    "POR-16",
    "POR-21",
]
# Client stage codes (P-08-T12 `stages.py` over C2), never firm statuses (POR-02 Copy table).
StageCode = Literal[
    "gather_documents",
    "prepare",
    "review",
    "sign_form_8879",
    "file",
    "requests",
    "reconcile",
    "statements",
    "planning",
    "fieldwork",
    "statements_review",
    "report",
    "scoping",
    "system_description",
    "testing",
    "exceptions",
]
StageState = Literal["done", "current", "upcoming"]
PillCode = Literal[
    "getting_started",
    "preparing_return",
    "reviewing_return",
    "reconciling_accounts",
    "filed_and_accepted",
    "finishing_audit",
    "testing_under_way",
]
PillVariant = Literal["state", "success", "neutral"]
NoteCode = Literal["waiting_on_k1", "waiting_on_your_k1"]
# Client-facing team roles (OQ-5: the day-to-day contact is derived per work-item kind).
TeamRoleCode = Literal[
    "partner_signs_return",
    "partner",
    "engagement_partner",
    "manager_reviews_return",
    "manager",
    "preparer_day_to_day",
    "preparer",
    "close_preparer",
    "day_to_day_contact",
    "client_service",
]
EarlierKind = Literal[
    "return_filed", "extension_filed", "engagement_letter_signed", "deliverable_released"
]
NoticeCode = Literal["agency_notice_in_review"]


class PortalHomeScopeOut(BaseModel):
    """The scope the home is for (one grant's target; `?scope_id=`)."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[ScopeKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]  # "Jonah & Claire Feld"
    sub: Annotated[str | None, classified("confidential")] = None  # "Household · Brooklyn, NY"
    role_label: Annotated[str, classified("internal")]  # the grant role's client label


class PortalHomeTargetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    screen: Annotated[PortalScreen, classified("internal")]
    params: Annotated[dict[str, str], classified("internal")] = {}


class PortalHomeTodoOut(BaseModel):
    """A to-do card. `detail` is the source's client-safe line (request titles, the person who
    asked), already in the client's words; it never holds a firm status word."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[TodoKind, classified("internal")]
    count: Annotated[int, Field(ge=0), classified("internal")]
    state: Annotated[TodoState, classified("internal")]
    due_date: Annotated[date | None, classified("internal")] = None
    detail: Annotated[str | None, classified("confidential")] = None
    facts: Annotated[Facts, classified("internal")] = {}
    target: Annotated[PortalHomeTargetOut | None, classified("internal")] = None


class PortalHomePillOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[PillCode, classified("internal")]
    variant: Annotated[PillVariant, classified("internal")]


class PortalHomeStageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[StageCode, classified("internal")]
    state: Annotated[StageState, classified("internal")]
    facts: Annotated[Facts, classified("internal")] = {}  # {"done": 7, "total": 9}


class PortalHomeWorkCardOut(BaseModel):
    """A work item as the client sees it: its client-safe display fields and its stage."""

    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    kind: Annotated[str, Field(max_length=60), classified("internal")]  # C1 registered kind
    title: Annotated[str, classified("confidential")]  # "2025 Tax Return · Form 1040"
    sub: Annotated[str | None, classified("confidential")] = None  # "Extended to Oct 15, 2026"
    pill: Annotated[PortalHomePillOut, classified("internal")]
    stages: Annotated[list[PortalHomeStageOut], classified("internal")] = []
    note_code: Annotated[NoteCode | None, classified("internal")] = None
    # The counterparty a note names (the partnership on a K-1), and its date.
    note_subject: Annotated[str | None, classified("confidential")] = None
    note_date: Annotated[date | None, classified("internal")] = None


class PortalHomeBinderOut(BaseModel):
    """Binder progress: "19 of 21 requests done · Brightwater Hale sorted 37 of your files". The
    sorted count is firm-attributed; the agent is never named (INV-5, DEC-19)."""

    model_config = ConfigDict(frozen=True)

    binder_id: Annotated[UUID, classified("internal")]
    done: Annotated[int, Field(ge=0), classified("internal")]
    total: Annotated[int, Field(ge=0), classified("internal")]
    sorted_count: Annotated[int, Field(ge=0), classified("internal")]


class PortalHomeTeamMemberOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    role_code: Annotated[TeamRoleCode, classified("internal")]


class PortalHomeEarlierOut(BaseModel):
    """An Earlier row: "2024 Form 1040 filed and accepted"."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[EarlierKind, classified("internal")]
    date: Annotated[Day | None, classified("internal")] = None
    facts: Annotated[Facts, classified("internal")] = {}  # {"tax_year": 2024, "form": "1040"}
    target: Annotated[PortalHomeTargetOut | None, classified("internal")] = None


class PortalHomeK1Out(BaseModel):
    """A My K-1s row (T-02 registers the source). `released` only: the firm's package status
    ("Draft K-1 · pre-release") never reaches the portal."""

    model_config = ConfigDict(frozen=True)

    k1_package_id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]
    released: Annotated[bool, classified("internal")]
    expected_by: Annotated[date | None, classified("internal")] = None


class PortalHomeThreadOut(BaseModel):
    """A Recent messages row (N-03 registers the source)."""

    model_config = ConfigDict(frozen=True)

    thread_id: Annotated[UUID, classified("internal")]
    subject: Annotated[str, classified("confidential")]
    from_name: Annotated[str, classified("confidential")]
    at: Annotated[datetime, classified("internal")]
    unread: Annotated[bool, classified("internal")]


class PortalHomeNoticeOut(BaseModel):
    """An information row ("… notice — Brightwater Hale is reviewing it. Nothing needed from
    you."); N-04 registers the source."""

    model_config = ConfigDict(frozen=True)

    notice_id: Annotated[UUID, classified("internal")]
    code: Annotated[NoticeCode, classified("internal")]
    subject: Annotated[str, classified("confidential")]


class PortalHomeOut(BaseModel):
    """POR-02 for one scope: what the firm needs now, where the work stands, who the team is."""

    model_config = ConfigDict(frozen=True)

    scope: Annotated[PortalHomeScopeOut, classified("internal")]
    todos: Annotated[list[PortalHomeTodoOut], classified("internal")] = []
    work_cards: Annotated[list[PortalHomeWorkCardOut], classified("internal")] = []
    binder: Annotated[PortalHomeBinderOut | None, classified("internal")] = None
    team: Annotated[list[PortalHomeTeamMemberOut], classified("internal")] = []
    earlier: Annotated[list[PortalHomeEarlierOut], classified("internal")] = []
    # Empty until T-02, N-03 and N-04 register their home sources.
    my_k1s: Annotated[list[PortalHomeK1Out], classified("internal")] = []
    recent_threads: Annotated[list[PortalHomeThreadOut], classified("internal")] = []
    notices_info: Annotated[list[PortalHomeNoticeOut], classified("internal")] = []
    first_visit: Annotated[bool, classified("internal")]
    welcome_dismissed: Annotated[bool, classified("internal")]
    all_done: Annotated[bool, classified("internal")]


class PortalPreferencesIn(BaseModel):
    """The person's own per-scope preferences (Story 6.2). `version` is the row's, for the 409."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_id: Annotated[UUID, classified("internal")]
    welcome_dismissed: Annotated[bool, classified("internal")]
    version: Annotated[int, Field(ge=0), classified("internal")]


class PortalPreferencesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    scope_id: Annotated[UUID, classified("internal")]
    welcome_dismissed: Annotated[bool, classified("internal")]
    welcome_dismissed_at: Annotated[datetime | None, classified("internal")] = None
    version: Annotated[int, classified("internal")]


# --- Branding before sign-in (P-08-T05) --------------------------------------------------------


class PortalSignInPolicyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    methods: Annotated[list[Literal["email_code"]], classified("public")]
    mfa_floor: Annotated[list[Literal["owner", "signer", "approver"]], classified("public")]


class PortalBrandingOut(BaseModel):
    """Public fields only, the same shape for an unknown host (neutral values), and no tenant
    identifier on any host (ADR-163 §5, §6)."""

    model_config = ConfigDict(frozen=True)

    firm_name: Annotated[str | None, classified("public")]
    portal_name: Annotated[str | None, classified("public")]
    logo_url: Annotated[str | None, classified("public")]  # same-origin /v1/portal/branding/logo
    address_line: Annotated[str | None, classified("public")]
    help_url: Annotated[str | None, classified("public")]
    privacy_url: Annotated[str | None, classified("public")]
    support_contact_name: Annotated[str | None, classified("public")]
    secured_footer: Annotated[bool, classified("public")] = False
    sign_in: Annotated[PortalSignInPolicyOut, classified("public")]
    maintenance_banner: Annotated[str | None, classified("public")] = None


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, PORTAL_HOME_V2):
        raise NotFound("portal.home_v2")
    raise NotImplementedYet


router = AbacusRouter(prefix="/v1/portal", tags=["portal"])


@router.get("/home", action="portal_home.read", response_model=PortalHomeOut, errors=(501,))
async def get_portal_home_route(
    ctx: Member, scope_id: Annotated[UUID | None, Query()] = None
) -> PortalHomeOut:
    """POR-02 for one scope (default: the person's first full-client scope). A scope no grant
    covers, or a person with no full-client grant (third party, K-1 only), answers 404 (INV-4)."""
    await _stub(ctx)


@router.put(
    "/preferences",
    action="portal_preferences.update",
    response_model=PortalPreferencesOut,
    errors=(409, 501),
)
async def update_portal_preferences_route(
    body: PortalPreferencesIn, ctx: Member
) -> PortalPreferencesOut:
    """Per user and scope; 409 `portal_preferences_stale` on a version mismatch; a scope no grant
    covers answers 404. Audited as `portal_preferences.updated`."""
    await _stub(ctx)


# The sign-in policy every portal shows today (DEC-58 email codes; MFA for owners, signers and
# approvers, P-08 §3).
_SIGN_IN = PortalSignInPolicyOut(methods=["email_code"], mfa_floor=["owner", "signer", "approver"])


@router.get("/branding", action=PORTAL_PUBLIC, response_model=PortalBrandingOut)
async def get_portal_branding_route(
    response: Response, host: Annotated[str | None, Header()] = None
) -> PortalBrandingOut:
    """POR-01's branding for the request's host: Public slots, or the same shape with neutral
    values. Cached per host at the edge for a minute."""
    found = await branding_for_host(host)
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["Vary"] = "Host"
    return PortalBrandingOut(**asdict(found), sign_in=_SIGN_IN)


@router.get("/branding/logo", action=PORTAL_PUBLIC, response_model=str)
async def get_portal_logo_route(host: Annotated[str | None, Header()] = None) -> Response:
    """The firm's logo, re-encoded as PNG on upload, served same-origin; 404 for any host
    without one. The body is `image/png` (the model is only the generator's placeholder)."""
    png = await logo_for_host(host)
    return Response(
        png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=300",
            "Vary": "Host",
            "X-Content-Type-Options": "nosniff",
        },
    )
