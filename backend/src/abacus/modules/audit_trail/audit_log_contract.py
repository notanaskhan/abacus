"""The audit-log contract, v1: ADM-07 (G-02-T04 stub; SPEC-349 §8; ADR-139, P-36). Contract:
`docs/contracts/audit-log.md`.

Behind `audit_log.explorer`: off, every route here answers 404; on, 501 `not_implemented` until
G-02-T08 (list and detail) and G-02-T17 (export). The legacy explorer (`GET
/v1/firm/audit-events`, SPEC-304) is unchanged until ADM-07 replaces it.

Rules the shapes carry (DEC-60, DEC-43, INV-1, INV-5):

- **Codes and facts, never labels.** A row carries its action code, its catalogue `category` and
  `mark`, the actor grammar's facts and the target's identifiers; the SPA composes "Report
  prepared by Hannah Leclerc via Agent" from them. Names are facts (`display_name`), not titles.
- **The actor grammar** is `person`, `via_agent` (an agent event with the person it acted for),
  `policy` (dormant, ADR-187), `system` or `support`. No shape can name the agent as an actor of
  its own: a `via_agent` actor always carries `on_behalf_of`.
- **Walls** omit events; nothing here counts or flags what was left out (DEC-43).
- **Values** are resolved at read time for viewers with the target's content read, masked by
  classification, and never stored (`values.status`: `resolved`, `withheld`, `unavailable`).
- **Facts are codes and identifiers only** (security review M4): counts, booleans, codes and
  ids, never a value, an amount or free text. Anything that carries a value lives under the
  detail's `values`, resolved per viewer and masked (ADR-024, DEC-60). `labels` names the ids in
  the row (people, policies, agents) as their owners' labelers give them, never above
  Confidential. `q` searches actor, target and fact labels only, never a value, for every reader.
- **Request context** (`ip`, `user_agent_family`, `device_label`, `session`) is personal data,
  null on agent and system events (G-02-T06), and shown only to `REQUEST_CONTEXT_READERS`
  (`firm_admin`, `security_admin`, `quality_partner`); every other reader gets it null (DEC-420,
  security review M2). The projection lands in G-02-T08.
- **Authorisation comes first** (security review L1): a client principal gets 404 (INV-4), and
  the agent, the system and anyone refused an export action get 403, before the flag is read. A
  person's read is narrowed per event by `visible()` in the live route.
- **No route changes or removes an event.** Corrections are new events.
- **`since_seq`** lists events with a higher `seq`, oldest first, for the F-04 harness.
"""

from __future__ import annotations

from datetime import date, datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Final, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AUDIT_LOG_EXPLORER
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

# The Actor filter (ADM-07 "All · People · via Agent · Policy principal · System") and the
# grammar each row carries. `support` is a support engineer under SPEC-012.
ActorKind = Literal["person", "via_agent", "policy", "system", "support"]
# Activity catalogue v1 (G-02-T08): what kind of event a row is, and its marker. `ok` marks a
# named person's (or, dormant, a named policy's) approval or sign-off, never agent output; `no` a
# reversal or removal; `pl` a neutral event.
Category = Literal["decision", "change", "access", "run", "sign_in", "communication", "export"]
Mark = Literal["ok", "no", "pl"]
LinkKind = Literal["run", "none"]
ValuesStatus = Literal["resolved", "withheld", "unavailable"]
WithheldReason = Literal["need_to_know", "walled", "not_enabled"]
AuthMethod = Literal["sso", "email_code", "passkey", "totp", "support", "service"]
ExportStatus = Literal["requested", "building", "ready", "downloaded", "expired", "failed"]
Fact = str | int | bool | None
# DEC-420: who sees a person's request context (IP, device, session); everyone else gets null.
REQUEST_CONTEXT_READERS: Final = frozenset({"firm_admin", "security_admin", "quality_partner"})
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class AuditPersonOut(BaseModel):
    """A person named on an event; the id links to the ADM-02 user drawer."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    # Membership level and office, for the drawer's Actor line ("Senior, Denver").
    level: Annotated[str | None, classified("internal")] = None
    office_id: Annotated[UUID | None, classified("internal")] = None


class AuditActorOut(BaseModel):
    """The actor grammar's facts (INV-5): `person` and `support` name `person`; `via_agent` names
    `on_behalf_of` (and the agent by id only); `policy` names `policy_ref`; `system` names
    nothing."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[ActorKind, classified("internal")]
    person: Annotated[AuditPersonOut | None, classified("internal")] = None
    on_behalf_of: Annotated[AuditPersonOut | None, classified("internal")] = None
    agent_id: Annotated[str | None, classified("internal")] = None
    policy_ref: Annotated[str | None, classified("internal")] = None


class AuditTargetOut(BaseModel):
    """The object chip: type and id always; a label when its owner's labeler names it."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[str, classified("internal")]
    id: Annotated[str, classified("internal")]
    label: Annotated[str | None, classified("confidential")] = None
    engagement_id: Annotated[UUID | None, classified("internal")] = None
    client_id: Annotated[UUID | None, classified("internal")] = None


class AuditEventRow(BaseModel):
    """One row of the feed (ADM-07 a, b): newest first, its own date over its time."""

    model_config = ConfigDict(frozen=True)

    seq: Annotated[int, Field(ge=1), classified("internal")]
    effective_at: Annotated[datetime, classified("internal")]
    action: Annotated[str, classified("internal")]
    category: Annotated[Category, classified("internal")]
    mark: Annotated[Mark, classified("internal")]
    actor: Annotated[AuditActorOut, classified("internal")]
    target: Annotated[AuditTargetOut, classified("internal")]
    # The detail line's facts, keyed by the catalogue's fact names: codes, counts, booleans and
    # ids only, never a value (M4). Values are the detail's `values`.
    detail_facts: Annotated[dict[str, Fact], classified("internal")] = Field(
        default_factory=dict[str, Fact]
    )
    # Display labels for the ids in `detail_facts`, keyed by the id (labelers; ≤ Confidential).
    labels: Annotated[dict[str, str], classified("confidential")] = Field(
        default_factory=dict[str, str]
    )
    office_id: Annotated[UUID | None, classified("internal")] = None
    # Null for agent and system events, and for readers outside REQUEST_CONTEXT_READERS.
    ip: Annotated[str | None, classified("confidential")] = None
    run_id: Annotated[UUID | None, classified("internal")] = None
    link_kind: Annotated[LinkKind, classified("internal")] = "none"


class AuditEventPageOut(ListPage[AuditEventRow]):
    """The P-36 envelope. `counts` holds `all`, `person`, `via_agent`, `policy` and `system`
    over the other filters (capped like `total`); walled events are in none of them."""


class AuditSessionOut(BaseModel):
    """The drawer's Session line ("SSO · MFA 9:01 AM")."""

    model_config = ConfigDict(frozen=True)

    session_id: Annotated[UUID | None, classified("internal")] = None
    auth_method: Annotated[AuthMethod | None, classified("internal")] = None
    mfa_at: Annotated[datetime | None, classified("internal")] = None


class AuditAuthorityOut(BaseModel):
    """Why the actor could do it: a code and identifier facts ("within BH AJE thresholds v2,
    approval limit Senior"), composed by the SPA."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    facts: Annotated[dict[str, Fact], classified("internal")] = Field(default_factory=dict)


class ValueRow(BaseModel):
    """One changed item, as the viewer may see it. A Restricted value is only ever masked
    (`•••-••-2208`, `masked: true`). Amounts are decimal strings, never floats."""

    model_config = ConfigDict(frozen=True)

    item_label: Annotated[str, classified("confidential")]
    field: Annotated[str, classified("internal")]
    amount: Annotated[str | None, Field(pattern=r"^-?\d+\.\d{2}$"), classified("confidential")] = (
        None
    )
    before: Annotated[str | None, classified("confidential")] = None
    after: Annotated[str | None, classified("confidential")] = None
    masked: Annotated[bool, classified("internal")] = False


class NotIncludedRow(BaseModel):
    """An item left out of the change ("Accrued expenses 14,900.00 · Review required → Priya
    Raman")."""

    model_config = ConfigDict(frozen=True)

    item_label: Annotated[str, classified("confidential")]
    amount: Annotated[str | None, Field(pattern=r"^-?\d+\.\d{2}$"), classified("confidential")] = (
        None
    )
    reason_code: Annotated[str, classified("internal")]
    routed_to: Annotated[AuditPersonOut | None, classified("internal")] = None


class AuditValuesOut(BaseModel):
    """`resolved` with rows; `withheld` with a reason ("Values are visible to partners in
    scope."); `unavailable` when the owner cannot resolve them ("Values not available")."""

    model_config = ConfigDict(frozen=True)

    status: Annotated[ValuesStatus, classified("internal")]
    reason: Annotated[WithheldReason | None, classified("internal")] = None
    rows: Annotated[list[ValueRow], classified("confidential")] = Field(
        default_factory=list[ValueRow]
    )
    not_included: Annotated[list[NotIncludedRow], classified("confidential")] = Field(
        default_factory=list[NotIncludedRow]
    )


class AuditSourceOut(BaseModel):
    """The run behind an event ("Proposed by Raj Malhotra via Agent · Close run 2 · started 9:06
    AM"); `run_id` links to WB-09, a planned link until P-09."""

    model_config = ConfigDict(frozen=True)

    run_id: Annotated[UUID, classified("internal")]
    agent_id: Annotated[str | None, classified("internal")] = None
    run_no: Annotated[int | None, classified("internal")] = None
    started_at: Annotated[datetime | None, classified("internal")] = None
    initiator: Annotated[AuditPersonOut | None, classified("internal")] = None


class AuditEventDetail(AuditEventRow):
    """The O2 480 drawer (ADM-07 c): the row plus authority, time to the second, request
    context, content hash, values and source. The footer reads "Immutable. Corrections are new
    events."."""

    occurred_at: Annotated[datetime, classified("internal")]
    # Request context: null for agent and system events and outside REQUEST_CONTEXT_READERS.
    authority: Annotated[AuditAuthorityOut | None, classified("internal")] = None
    device_label: Annotated[str | None, classified("confidential")] = None
    user_agent_family: Annotated[str | None, classified("internal")] = None
    session: Annotated[AuditSessionOut | None, classified("internal")] = None
    # SHA-256 of the event's canonical form (the hash chain's leaf, P-43).
    content_hash: Annotated[Sha256, classified("internal")]
    values: Annotated[AuditValuesOut, classified("internal")]
    source: Annotated[AuditSourceOut | None, classified("internal")] = None


class AuditExportFilterIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_kind: Annotated[ActorKind | None, classified("internal")] = None
    object_type: Annotated[str | None, Field(max_length=64), classified("internal")] = None
    action: Annotated[str | None, Field(max_length=80), classified("internal")] = None
    office_id: Annotated[UUID | None, classified("internal")] = None


class AuditExportRequestIn(BaseModel):
    """ADM-07 e: a date range in the firm's time zone, at most 92 days (422 otherwise)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_date: Annotated[date, classified("internal")]
    to_date: Annotated[date, classified("internal")]
    filter: Annotated[AuditExportFilterIn, classified("internal")] = AuditExportFilterIn()
    include_values: Annotated[bool, classified("internal")] = False


class AuditExport(BaseModel):
    """An export job (ADM-07 e, g): CSV plus `manifest.json` and `manifest.sig` (format
    `accrued.audit-log-export` v1)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    status: Annotated[ExportStatus, classified("internal")]
    from_date: Annotated[date, classified("internal")]
    to_date: Annotated[date, classified("internal")]
    filter: Annotated[dict[str, Fact], classified("internal")] = Field(default_factory=dict)
    include_values: Annotated[bool, classified("internal")]
    requested_by: Annotated[AuditPersonOut, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]
    file_name: Annotated[str | None, classified("internal")] = None
    row_count: Annotated[int | None, Field(ge=0), classified("internal")] = None
    seq_from: Annotated[int | None, classified("internal")] = None
    seq_to: Annotated[int | None, classified("internal")] = None
    manifest_sha256: Annotated[Sha256 | None, classified("internal")] = None
    expires_at: Annotated[datetime | None, classified("internal")] = None


class AuditExportLinkOut(BaseModel):
    """A 15-minute presigned link; Restricted (it opens the firm's log) and never logged."""

    model_config = ConfigDict(frozen=True)

    url: Annotated[str, classified("restricted")]
    expires_at: Annotated[datetime, classified("internal")]
    manifest_sha256: Annotated[Sha256, classified("internal")]


router = AbacusRouter(prefix="/v1/audit-events", tags=["audit log"])


async def _gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, AUDIT_LOG_EXPLORER):
        raise NotFound("audit_log.explorer")


# The read actions are answered per event by `visible()` (engagement roles, `in_scope`); the
# export family is firm-level and authorised as such.
_READS: Final = frozenset({"audit_event.read"})


async def _authorised(ctx: AuthContext, action: str) -> None:
    """L1: the matrix first. A client principal gets 404 (INV-4). The agent, the system and any
    other non-person principal are authorised at the firm and refused (403). A person asking
    for a read passes here: the live route narrows each event with `visible()`, so someone who
    holds no right sees an empty list, never another firm's or another team's events. Export
    actions are authorised at the firm for everyone."""
    if ctx.client:
        raise NotFound("audit_log")
    if action in _READS and ctx.tenant.actor_kind == "human":
        return
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    await _authorised(ctx, action)
    await _gate(ctx)
    raise NotImplementedYet


Text = Annotated[str | None, Query(max_length=200)]


@router.get("", action="audit_event.read", response_model=AuditEventPageOut, errors=(501,))
async def list_audit_events_route(
    ctx: Ctx,
    actor_kind: Annotated[ActorKind | None, Query()] = None,
    actor_id: Annotated[UUID | None, Query()] = None,
    object_type: Annotated[str | None, Query(max_length=64)] = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    office_id: Annotated[UUID | None, Query()] = None,
    ip: Annotated[IPv4Address | IPv6Address | None, Query()] = None,
    q: Text = None,
    since_seq: Annotated[int | None, Query(ge=0)] = None,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditEventPageOut:
    """ADM-07 a, b, f: newest first by `seq` (oldest first after `since_seq`). Dates filter on
    `effective_at` in the firm's time zone; `office_id` is the object's office, else the actor's
    (DEC-415 Q9); `q` searches actor, target and fact labels only, never a value (M4)."""
    await _stub(ctx, "audit_event.read")


@router.get(
    "/exports/{export_id}", action="audit_export.read", response_model=AuditExport, errors=(501,)
)
async def audit_export_route(export_id: UUID, ctx: Ctx) -> AuditExport:
    """ADM-07 g: the requester's export; anyone else's answers 404. A status read needs no fresh
    second factor (L5); the request and the link do."""
    await _stub(ctx, "audit_export.read")


@router.get("/{seq}", action="audit_event.read", response_model=AuditEventDetail, errors=(501,))
async def audit_event_route(seq: Annotated[int, Path(ge=1)], ctx: Ctx) -> AuditEventDetail:
    """ADM-07 c: one event; a walled or invisible one answers 404 (DEC-43)."""
    await _stub(ctx, "audit_event.read")


@router.post(
    "/exports",
    action="audit_event.export",
    response_model=AuditExport,
    status_code=202,
    errors=(501,),
)
async def request_audit_export_route(
    body: AuditExportRequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AuditExport:
    """ADM-07 e: one person with a fresh second factor (DEC-415 Q8); 202 `requested`. Audited
    `audit_export.requested`; values only as the requester may see them on screen."""
    await _stub(ctx, "audit_event.export")


@router.post(
    "/exports/{export_id}/link",
    action="audit_event.export",
    response_model=AuditExportLinkOut,
    errors=(409, 410, 501),
)
async def link_audit_export_route(export_id: UUID, ctx: Ctx) -> AuditExportLinkOut:
    """ADM-07 g: a 15-minute link for the requester while `ready` or `downloaded` (409
    `export_not_ready` before), 410 `export_expired` after 7 days. Audited
    `audit_export.downloaded`."""
    await _stub(ctx, "audit_event.export")
