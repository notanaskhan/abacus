"""CLI-05's tax profile, organisations' half (T-01-T43; T-01 §3.6, §4.3; DEC-1651). RED.

The profile's own records (authorizations, elections, transcripts and their comparisons) are
tax's: filing a transcript as evidence, reading the return as filed from review and the
transcript compute are tax's, and organisations imports only identity. Tax registers them here
(`register_tax_profile_backend`); unregistered, the routes answer 501 (fail closed). What stays
here is what organisations owns: the order of checks every tax-profile route keeps (a client
principal 404, the entity's client or 404, the matrix on that client, the flag), the entity's
§7216 consents and the masked identity band (last four only; DEC-52). No route ever serves a
full TIN or CAF number: TINs leave as `MaskedTinOut`, CAF numbers as their last four.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Path, Query, Request
from sqlalchemy import RowMapping, text

from abacus.kernel._flags import CLIENTS_TAX_PROFILE
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    allowed_actions,
    authorise,
    current_context,
    mask_tins_for,
)
from abacus.modules.organisations.consents_contract import (
    ConsentOut,
    ConsentRecipientOut,
    ConsentSignerOut,
    TaxAuthorizationIn,
    TaxAuthorizationOut,
    TaxElectionIn,
    TaxElectionOut,
    TaxProfileFileOut,
    TaxProfileIdentityOut,
    TaxProfileOut,
    TranscriptComparisonIn,
    TranscriptComparisonOut,
    TranscriptOut,
    TranscriptUploadIn,
    consents_router,
)
from abacus.modules.organisations.contract import MaskedTinOut, TinKind
from abacus.modules.organisations.service import client_of_entity

# The profile's actions a caller may hold (ADR-024: the UI hides what it can't do).
PROFILE_ACTIONS = (
    "tax_election.manage",
    "tax_authorization.manage",
    "transcript.upload",
    "transcript.compare",
)


@dataclass(frozen=True)
class TaxProfileBackend:
    """Tax's half of the tax profile. Every callable takes the caller's context (already checked
    by `live_entity` where it names an entity) and returns C19 models."""

    authorizations: Callable[[AuthContext, UUID], Awaitable[list[TaxAuthorizationOut]]]
    add_authorization: Callable[
        [AuthContext, UUID, UUID, TaxAuthorizationIn], Awaitable[TaxAuthorizationOut]
    ]
    elections: Callable[[AuthContext, UUID], Awaitable[list[TaxElectionOut]]]
    put_election: Callable[[AuthContext, UUID, str, TaxElectionIn], Awaitable[TaxElectionOut]]
    stage_file: Callable[[AuthContext, UUID, str, bytes], Awaitable[TaxProfileFileOut]]
    upload_transcript: Callable[
        [AuthContext, UUID, UUID, TranscriptUploadIn], Awaitable[TranscriptOut]
    ]
    transcripts: Callable[[AuthContext, UUID], Awaitable[list[TranscriptOut]]]
    compare: Callable[
        [AuthContext, UUID, TranscriptComparisonIn], Awaitable[TranscriptComparisonOut]
    ]
    comparison: Callable[[AuthContext, UUID], Awaitable[TranscriptComparisonOut]]
    transcript_entity: Callable[[AuthContext, UUID], Awaitable[UUID | None]]


_BACKEND: list[TaxProfileBackend] = []


def register_tax_profile_backend(backend: TaxProfileBackend) -> None:
    """Tax registers once, at import; a reload replaces itself."""
    _BACKEND[:] = [backend]


def backend() -> TaxProfileBackend:
    if not _BACKEND:
        raise NotImplementedYet  # fail closed: tax registers at import
    return _BACKEND[0]


async def live_entity(ctx: AuthContext, entity_id: UUID, action: str) -> UUID:
    """The order of checks for a live tax-profile route; returns the entity's client. A client
    principal and an entity outside the firm (or behind a wall) answer 404."""
    if ctx.client:
        raise NotFound("client_entity")
    client_id = await client_of_entity(ctx.tenant, entity_id)
    if client_id is None:
        raise NotFound("client_entity")
    await authorise(ctx, action, Resource.client(ctx.tenant_id, client_id))
    if not await flag_enabled(ctx.tenant, CLIENTS_TAX_PROFILE):
        raise NotFound(CLIENTS_TAX_PROFILE.name)
    return client_id


async def live_transcript(ctx: AuthContext, transcript_id: UUID, action: str) -> UUID:
    """A transcript route's checks, through the transcript's entity; returns that entity."""
    if ctx.client:
        raise NotFound("transcript")
    entity_id = await backend().transcript_entity(ctx, transcript_id)
    if entity_id is None:
        raise NotFound("transcript")
    await live_entity(ctx, entity_id, action)
    return entity_id


_ENTITY = text(
    "SELECT e.id, e.name, e.entity_type, e.tin_kind, e.tin_last4, e.tin_status, "
    "c.id AS client_id, c.name AS client_name, c.kind AS client_kind "
    "FROM client_entities e JOIN clients c ON c.id = e.client_id WHERE e.id = :id"
)
_HOUSEHOLD = text(
    "SELECT id, name, tin_kind, tin_last4, tin_status FROM client_entities "
    "WHERE client_id = :client AND entity_type = 'individual' ORDER BY created_at, id"
)
_CONSENTS = text(
    "SELECT k.id, k.client_id, k.client_entity_id, k.consent_set_id, k.purpose, k.tax_years, "
    "k.scope, k.recipients, k.provider_terms_version, k.template_version_id, k.source, "
    "k.envelope_id, k.status, k.requested_at, k.signed_at, k.expires_at, k.renewal_of_id, "
    "k.declined_at, k.revoked_at FROM consents k WHERE k.client_entity_id = :entity "
    "ORDER BY k.requested_at, k.id"
)
_SIGNERS = text(
    "SELECT s.consent_id, s.contact_id, coalesce(t.display_name, '') AS name, s.signer_role, "
    "s.required, s.signed_at, s.method FROM consent_signers s "
    "LEFT JOIN contacts t ON t.id = s.contact_id WHERE s.consent_id = ANY(:ids) "
    "ORDER BY s.consent_id, s.signer_role, s.id"
)


def _masked(kind: object, last4: object, status: object) -> MaskedTinOut | None:
    """Kind and last four only (DEC-52); none when no TIN is on file or applied for."""
    if kind is None or status not in ("on_file", "applied_for"):
        return None
    return MaskedTinOut(kind=cast(TinKind, kind), presence=status, last4=cast(str | None, last4))


async def _consents(ctx: AuthContext, entity_id: UUID, client_name: str) -> list[ConsentOut]:
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_CONSENTS, {"entity": entity_id})).mappings().all()
        ids = [r["id"] for r in rows]
        signers: Sequence[RowMapping] = (
            (await session.execute(_SIGNERS, {"ids": ids})).mappings().all() if ids else ()
        )
    by_consent: dict[UUID, list[ConsentSignerOut]] = {}
    for s in signers:
        by_consent.setdefault(s["consent_id"], []).append(
            ConsentSignerOut(
                contact_id=s["contact_id"],
                name=str(s["name"]),
                role=s["signer_role"],
                required=bool(s["required"]),
                signed_at=s["signed_at"],
                method=s["method"],
            )
        )
    out: list[ConsentOut] = []
    for r in rows:
        people = by_consent.get(r["id"], [])
        required = [p for p in people if p.required]
        out.append(
            ConsentOut(
                id=r["id"],
                client_id=r["client_id"],
                client_entity_id=r["client_entity_id"],
                client_name=client_name,
                consent_set_id=r["consent_set_id"],
                purpose=r["purpose"],
                tax_years=list(r["tax_years"]),
                scope={str(k): str(v) for k, v in dict(r["scope"]).items()},
                recipients=[ConsentRecipientOut.model_validate(x) for x in r["recipients"]],
                provider_terms_version=str(r["provider_terms_version"]),
                template_version_id=r["template_version_id"],
                source=r["source"],
                envelope_id=r["envelope_id"],
                status=r["status"],
                signed_count=sum(1 for p in required if p.signed_at is not None),
                signer_count=len(required),
                requested_at=r["requested_at"],
                signed_at=r["signed_at"],
                expires_at=r["expires_at"],
                renewal_of_id=r["renewal_of_id"],
                offshore=r["purpose"] == "offshore_disclosure",
                allowed_actions=[],
                declined_at=r["declined_at"],
                revoked_at=r["revoked_at"],
                signers=people,
            )
        )
    return out


async def profile(ctx: AuthContext, entity_id: UUID) -> TaxProfileOut:
    """CLI-05's rail: the entity's consents, authorizations and elections, the household's
    identity band by masked TIN, and what the caller may do (open notices are N-04's: None)."""
    client_id = await live_entity(ctx, entity_id, "tax_profile.read")
    async with tenant_session(ctx.tenant) as session:
        entity = (await session.execute(_ENTITY, {"id": entity_id})).mappings().one()
        household = (await session.execute(_HOUSEHOLD, {"client": client_id})).mappings().all()
    resource = Resource.client(ctx.tenant_id, client_id)
    held = sorted(await allowed_actions(ctx, resource, PROFILE_ACTIONS))
    identity = [
        TaxProfileIdentityOut(
            role="taxpayer" if n == 0 else "spouse",
            client_entity_id=row["id"],
            name=str(row["name"]),
            masked_tin=_masked(row["tin_kind"], row["tin_last4"], row["tin_status"]),
        )
        for n, row in enumerate(household[:2])
    ]
    tax = backend()
    return TaxProfileOut(
        client_entity_id=entity_id,
        taxpayer_tin=_masked(entity["tin_kind"], entity["tin_last4"], entity["tin_status"]),
        consents=await _consents(ctx, entity_id, str(entity["client_name"])),
        authorizations=await tax.authorizations(ctx, entity_id),
        elections=await tax.elections(ctx, entity_id),
        open_notices=None,
        allowed_actions=held,
        client_name=str(entity["client_name"]),
        client_kind="Household" if entity["client_kind"] == "household" else None,
        identity=identity,
    )


# --- routes (on C19's router; the stub's order of checks, then the backend) --------------------

Ctx = Annotated[AuthContext, Depends(current_context)]
EntityId = Annotated[UUID, Path()]
TranscriptId = Annotated[UUID, Path()]
FileName = Annotated[str, Query(min_length=1, max_length=255)]


@consents_router.get(
    "/client-entities/{client_entity_id}/tax-profile",
    action="tax_profile.read",
    response_model=TaxProfileOut,
    errors=(501,),
)
async def tax_profile_route(client_entity_id: EntityId, ctx: Ctx) -> TaxProfileOut:
    # The answer carries the masked TIN, so it goes out through the offshore mask (AC9.4).
    return await mask_tins_for(ctx, await profile(ctx, client_entity_id))


@consents_router.put(
    "/client-entities/{client_entity_id}/elections/{kind}",
    action="tax_election.manage",
    response_model=TaxElectionOut,
    errors=(409, 501),
)
async def put_election_route(
    client_entity_id: EntityId,
    kind: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{1,59}$")],
    body: TaxElectionIn,
    ctx: Ctx,
) -> TaxElectionOut:
    """Upsert one election; 409 `stale_version` when `seen_version` moved."""
    await live_entity(ctx, client_entity_id, "tax_election.manage")
    return await backend().put_election(ctx, client_entity_id, kind, body)


@consents_router.get(
    "/client-entities/{client_entity_id}/authorizations",
    action="tax_authorization.manage",
    response_model=list[TaxAuthorizationOut],
    errors=(501,),
)
async def list_authorizations_route(
    client_entity_id: EntityId, ctx: Ctx
) -> list[TaxAuthorizationOut]:
    await live_entity(ctx, client_entity_id, "tax_authorization.manage")
    return await backend().authorizations(ctx, client_entity_id)


@consents_router.post(
    "/client-entities/{client_entity_id}/authorizations/files",
    action="tax_authorization.manage",
    response_model=TaxProfileFileOut,
    status_code=201,
    errors=(413, 503),
)
async def stage_authorization_file_route(
    request: Request, client_entity_id: EntityId, ctx: Ctx, filename: FileName
) -> TaxProfileFileOut:
    """The scanned 8821, 2848 or state form, the raw bytes as the body: scanned before storage,
    refused closed (SPEC-029 AC-1); named by `upload_id` when the form is added."""
    await live_entity(ctx, client_entity_id, "tax_authorization.manage")
    return await backend().stage_file(ctx, client_entity_id, filename, await request.body())


@consents_router.post(
    "/client-entities/{client_entity_id}/authorizations",
    action="tax_authorization.manage",
    response_model=TaxAuthorizationOut,
    status_code=201,
    errors=(409, 501),
)
async def add_authorization_route(
    client_entity_id: EntityId, body: TaxAuthorizationIn, ctx: Ctx
) -> TaxAuthorizationOut:
    """An authorization already on file; CAF numbers sealed, only their last four served."""
    client_id = await live_entity(ctx, client_entity_id, "tax_authorization.manage")
    return await backend().add_authorization(ctx, client_entity_id, client_id, body)


@consents_router.get(
    "/client-entities/{client_entity_id}/transcripts",
    action="tax_profile.read",
    response_model=list[TranscriptOut],
    errors=(501,),
)
async def list_transcripts_route(client_entity_id: EntityId, ctx: Ctx) -> list[TranscriptOut]:
    """CLI-05 a's register, newest pull first, each with its latest result."""
    await live_entity(ctx, client_entity_id, "tax_profile.read")
    return await backend().transcripts(ctx, client_entity_id)


@consents_router.post(
    "/client-entities/{client_entity_id}/transcripts/files",
    action="transcript.upload",
    response_model=TaxProfileFileOut,
    status_code=201,
    errors=(413, 503),
)
async def stage_transcript_file_route(
    request: Request, client_entity_id: EntityId, ctx: Ctx, filename: FileName
) -> TaxProfileFileOut:
    """A transcript a practitioner pulled from IRS e-Services, the raw bytes as the body: scanned
    before storage, refused closed (SPEC-029 AC-1)."""
    await live_entity(ctx, client_entity_id, "transcript.upload")
    return await backend().stage_file(ctx, client_entity_id, filename, await request.body())


@consents_router.post(
    "/client-entities/{client_entity_id}/transcripts",
    action="transcript.upload",
    response_model=TranscriptOut,
    status_code=201,
    errors=(409, 501),
)
async def upload_transcript_route(
    client_entity_id: EntityId, body: TranscriptUploadIn, ctx: Ctx
) -> TranscriptOut:
    """File the staged transcript as retrieved evidence and parse it by code."""
    client_id = await live_entity(ctx, client_entity_id, "transcript.upload")
    return await backend().upload_transcript(ctx, client_entity_id, client_id, body)


@consents_router.post(
    "/transcripts/{transcript_id}/comparisons",
    action="transcript.compare",
    response_model=TranscriptComparisonOut,
    status_code=201,
    errors=(409, 501),
)
async def compare_transcript_route(
    transcript_id: TranscriptId, body: TranscriptComparisonIn, ctx: Ctx
) -> TranscriptComparisonOut:
    """Compare with the return as filed (its latest approved engine import), by code."""
    await live_transcript(ctx, transcript_id, "transcript.compare")
    return await backend().compare(ctx, transcript_id, body)


@consents_router.get(
    "/transcripts/{transcript_id}/comparison",
    action="tax_profile.read",
    response_model=TranscriptComparisonOut,
    errors=(501,),
)
async def latest_comparison_route(
    transcript_id: TranscriptId, ctx: Ctx
) -> TranscriptComparisonOut:
    """The transcript's latest comparison (404 when it was never compared)."""
    await live_transcript(ctx, transcript_id, "tax_profile.read")
    return await backend().comparison(ctx, transcript_id)


__all__ = [
    "PROFILE_ACTIONS",
    "TaxProfileBackend",
    "backend",
    "live_entity",
    "live_transcript",
    "profile",
    "register_tax_profile_backend",
]
