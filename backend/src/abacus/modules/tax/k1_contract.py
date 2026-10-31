"""K-1 packages and their portal view, the stub (T-02-T02; T-02 §4.3; C5 additive v1.x). Contract:
`docs/contracts/k1-packages.md`.

A K-1 package is one recipient's K-1 (with K-3 and state K-1s) from an issuing 1065, 1120-S or
1041. Drafts never reach the portal; a person releases final packages after the release check,
with an approval grant and an Undo window (`tax/k1_release.py`, K1RELEASE-001). A recipient sees
only their own released packages (POR-13), downloads them (audited) and updates their W-9/W-8 or
address for a person to accept (DV-10).

Firm routes answer 404 for a client principal, 403 for a principal the matrix refuses, 404 with
`tax.k1_release` off. Portal routes (T-02-T26, `tax/k1_portal.py`) answer 404 to a firm principal
and with the flag off; a recipient reads only their own released packages, with the second step
for anything that carries amounts.

Classification: box amounts are TRI; recipient names and addresses confidential; a TIN shows its
last four only.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_K1_RELEASE
from abacus.kernel._statuses import K1PackageStatus, RecipientDetailsChangeStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    current_context,
    current_member,
    mask_tins_for,
)
from abacus.modules.tax import k1_disclosures, k1_portal, k1_release
from abacus.modules.tax import k1_packages as k1

Ctx = Annotated[AuthContext, Depends(current_context)]
Member = Annotated[AuthContext, Depends(current_member)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
PackageId = Annotated[UUID, Path()]
DocumentKind = Literal["k1", "k3", "state_k1", "letter"]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class K1BoxLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_kind: Annotated[DocumentKind, classified("internal")]
    box_code: Annotated[str, classified("internal")]
    description: Annotated[str, classified("internal")]
    amount: Annotated[Decimal, classified("restricted", tri=True)]
    is_total: Annotated[bool, classified("internal")]


class K1DocumentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[DocumentKind, classified("internal")]
    jurisdiction: Annotated[str | None, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    is_draft: Annotated[bool, classified("internal")]


class K1HandoffOut(BaseModel):
    """T-02-T25: a draft shared to another return's intake (TXP-12's Internal handoff column).
    The target is named only to a reader of it (DEC-88); otherwise "Another return", no id."""

    model_config = ConfigDict(frozen=True)

    target_return_id: Annotated[UUID | None, classified("internal")]
    target_name: Annotated[str, classified("confidential")]
    target_form: Annotated[str | None, classified("internal")]
    status: Annotated[Literal["draft_shared", "final_replaced"], classified("internal")]
    shared_at: Annotated[datetime, classified("internal")]
    replaced_at: Annotated[datetime | None, classified("internal")]


class K1RelatedReturnOut(BaseModel):
    """T-02-T25: a return of the recipient's own client for the year, a share target. Offered
    only to a reader of both returns (DEC-88)."""

    model_config = ConfigDict(frozen=True)

    return_id: Annotated[UUID, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    form: Annotated[str, classified("internal")]
    status: Annotated[str, classified("internal")]


class K1DetailsChangeTagOut(BaseModel):
    """T-02-T25 (DV-10): a pending recipient-details change, the row's second line."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[Literal["w9", "w8", "address"], classified("internal")]
    submitted_at: Annotated[datetime, classified("confidential")]


class K1MaskedTinOut(BaseModel):
    """A recipient's taxpayer ID, kind and last four only; the detail's, never a list row's
    (ADR-031)."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["ssn", "ein", "itin"], classified("internal")]
    # Null for an offshore reader: the central mask nulls a field that allows it (DEC-52).
    last4: Annotated[
        str | None, Field(pattern=r"^[0-9]{4}$"), classified("restricted", pii_kind="tin")
    ] = None


class K1PackageOut(BaseModel):
    """A TXP-12 row (and a POR-13 row, released and later only)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    recipient_id: Annotated[UUID, classified("internal")]
    recipient_name: Annotated[str, classified("confidential")]
    recipient_kind: Annotated[
        Literal["gp", "lp", "shareholder", "beneficiary"], classified("internal")
    ]
    # No TIN on a list row (MaskedTinOut is never in a list, ADR-031); the recipient detail
    # carries it masked.
    form: Annotated[Literal["1065", "1120s", "1041"], classified("internal")]
    tax_year: Annotated[int, classified("internal")]
    status: Annotated[K1PackageStatus, classified("internal")]
    k3_status: Annotated[
        Literal["included", "not_required", "not_included"], classified("internal")
    ]
    state_codes: Annotated[list[str], classified("internal")]
    released_at: Annotated[datetime | None, classified("confidential")]
    version_no: Annotated[int, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    # T-02-T20 (additive): TXP-12's expanded row (K-1, K-3, state K-1s, letter).
    documents: Annotated[list[K1DocumentOut], classified("internal")] = []
    # T-02-T25 (additive; firm rows only, empty on the portal): TXP-12's row lines.
    period_start: Annotated[date | None, classified("internal")] = None
    period_end: Annotated[date | None, classified("internal")] = None
    ownership_note: Annotated[str | None, classified("confidential")] = None
    locality: Annotated[str | None, classified("confidential")] = None
    delivery_contact_name: Annotated[str | None, classified("confidential")] = None
    supersedes_package_id: Annotated[UUID | None, classified("internal")] = None
    handoffs: Annotated[list[K1HandoffOut], classified("confidential")] = []
    details_change: Annotated[K1DetailsChangeTagOut | None, classified("confidential")] = None
    related_returns: Annotated[list[K1RelatedReturnOut], classified("confidential")] = []
    # T-02-T27 (additive): the issuing client's name, a POR-13 card's heading.
    issuer_name: Annotated[str | None, classified("confidential")] = None
    # S20e (additive; DV-12): the recipient's electronic-furnishing decision (portal rows only).
    e_furnishing_consent: Annotated[
        Literal["unknown", "given", "declined"] | None, classified("internal")
    ] = None


class K1PackageDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    package: Annotated[K1PackageOut, classified("confidential")]
    lines: Annotated[list[K1BoxLineOut], classified("restricted", tri=True)]
    documents: Annotated[list[K1DocumentOut], classified("internal")]
    # T-02-T25 (additive): the recipient's masked TIN, the detail only (ADR-031); on the portal
    # (T-02-T27) the recipient's own, with whether an address is on file (Your details).
    tin: Annotated[K1MaskedTinOut | None, classified("restricted")] = None
    address_on_file: Annotated[bool | None, classified("internal")] = None


class K1DisclosureOut(BaseModel):
    """S20e (DV-12): the firm's counsel-approved electronic-furnishing text, one version."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    body: Annotated[str, classified("internal")]
    imported_at: Annotated[datetime, classified("internal")]


class K1DisclosureIn(BaseModel):
    model_config = _frozen()

    body: Annotated[str, Field(min_length=1, max_length=20_000), classified("internal")]


class PortalK1ExpectedOut(BaseModel):
    """T-02-T27 (POR-13 b): a K-1 the person will receive, not released yet. No amounts, no
    documents, no package id."""

    model_config = ConfigDict(frozen=True)

    issuer_name: Annotated[str, classified("confidential")]
    form: Annotated[Literal["1065", "1120s", "1041"], classified("internal")]
    tax_year: Annotated[int, classified("internal")]
    k3_status: Annotated[
        Literal["included", "not_required", "not_included"], classified("internal")
    ]
    expected_on: Annotated[date | None, classified("internal")]


class K1ViewerManifestOut(BaseModel):
    """What SHL-08 opens for one document (C4)."""

    model_config = ConfigDict(frozen=True)

    document_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    page_count: Annotated[int | None, classified("internal")]


class K1ReleaseCheckOut(BaseModel):
    """Release eligibility: failing checks as codes, never prose."""

    model_config = ConfigDict(frozen=True)

    eligible: Annotated[bool, classified("internal")]
    failing: Annotated[list[str], classified("internal")]
    package_ids: Annotated[list[UUID], classified("internal")]
    # T-02-T25 (additive): the firm's "Deliverable ready" version a release must name.
    email_template_version_id: Annotated[UUID | None, classified("internal")] = None


class K1ShareIn(BaseModel):
    model_config = _frozen()

    package_ids: Annotated[list[UUID], Field(min_length=1, max_length=500), classified("internal")]
    target_return_ids: Annotated[
        list[UUID], Field(min_length=1, max_length=50), classified("internal")
    ]


class K1ShareOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    shared: Annotated[int, classified("internal")]


class K1ReleaseIn(BaseModel):
    model_config = _frozen()

    package_ids: Annotated[list[UUID], Field(min_length=1, max_length=500), classified("internal")]
    channel: Annotated[Literal["portal"], classified("internal")]
    email_template_version_id: Annotated[UUID, classified("internal")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class K1ReleaseOut(BaseModel):
    """A release waits out its Undo window (`not_before`), then runs."""

    model_config = ConfigDict(frozen=True)

    release_id: Annotated[UUID, classified("internal")]
    status: Annotated[
        Literal["pending", "undone", "running", "completed", "failed"], classified("internal")
    ]
    not_before: Annotated[datetime, classified("internal")]


class K1ResendIn(BaseModel):
    model_config = _frozen()

    contact_id: Annotated[UUID, classified("internal")]


class RecipientDetailsChangeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    recipient_id: Annotated[UUID, classified("internal")]
    kind: Annotated[Literal["w9", "w8", "address"], classified("internal")]
    status: Annotated[RecipientDetailsChangeStatus, classified("internal")]
    submitted_at: Annotated[datetime, classified("confidential")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]


class ReviewReasonIn(BaseModel):
    model_config = _frozen()

    reason: Annotated[str | None, Field(max_length=500), classified("confidential")] = None


class PortalDetailsChangeIn(BaseModel):
    model_config = _frozen()

    kind: Annotated[Literal["w9", "w8", "address"], classified("internal")]
    upload_id: Annotated[UUID | None, classified("internal")] = None
    address: Annotated[dict[str, str] | None, classified("confidential")] = None


class EFurnishingConsentIn(BaseModel):
    model_config = _frozen()

    decision: Annotated[Literal["given", "declined"], classified("internal")]
    disclosure_version_id: Annotated[UUID, classified("internal")]


class EFurnishingConsentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: Annotated[UUID, classified("internal")]
    e_furnishing_consent: Annotated[
        Literal["unknown", "given", "declined"], classified("internal")
    ]
    decided_on: Annotated[date, classified("confidential")]


k1_router = AbacusRouter(prefix="/v1", tags=["k1-packages"])
portal_k1_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])


async def _gate(ctx: AuthContext) -> None:
    """T-02-T20: a client principal 404, then the flag; each service authorises its action on
    the issuing return (a principal it refuses answers 403 or 404 there)."""
    if ctx.client:
        raise NotFound("k1_package")
    if not await flag_enabled(ctx.tenant, TAX_K1_RELEASE):
        raise NotFound(TAX_K1_RELEASE.name)


def _doc_out(d: k1.DocumentView) -> K1DocumentOut:
    return K1DocumentOut(
        id=d.id,
        kind=cast(DocumentKind, d.kind),
        jurisdiction=d.jurisdiction,
        evidence_version_id=d.evidence_version_id,
        is_draft=d.is_draft,
    )


def _package_out(p: k1.PackageView) -> K1PackageOut:
    return K1PackageOut(
        id=p.id,
        recipient_id=p.recipient_id,
        recipient_name=p.recipient_name,
        recipient_kind=cast(Literal["gp", "lp", "shareholder", "beneficiary"], p.recipient_kind),
        form=cast(Literal["1065", "1120s", "1041"], p.form),
        tax_year=p.tax_year,
        status=K1PackageStatus(p.status),
        k3_status=cast(Literal["included", "not_required", "not_included"], p.k3_status),
        state_codes=list(p.state_codes),
        released_at=cast(datetime | None, p.released_at),
        version_no=p.version_no,
        allowed_actions=list(p.allowed_actions),
        documents=[_doc_out(d) for d in p.documents],
        period_start=p.period_start,
        period_end=p.period_end,
        ownership_note=p.ownership_note,
        locality=p.locality,
        delivery_contact_name=p.delivery_contact_name,
        supersedes_package_id=p.supersedes_package_id,
        handoffs=[
            K1HandoffOut(
                target_return_id=h.target_return_id,
                target_name=h.target_name,
                target_form=h.target_form,
                status=cast(Literal["draft_shared", "final_replaced"], h.status),
                shared_at=cast(datetime, h.shared_at),
                replaced_at=cast(datetime | None, h.replaced_at),
            )
            for h in p.handoffs
        ],
        details_change=(
            K1DetailsChangeTagOut(
                id=p.details_change.id,
                kind=cast(Literal["w9", "w8", "address"], p.details_change.kind),
                submitted_at=cast(datetime, p.details_change.submitted_at),
            )
            if p.details_change
            else None
        ),
        issuer_name=p.issuer_name,
        e_furnishing_consent=cast(
            Literal["unknown", "given", "declined"] | None, p.e_furnishing_consent
        ),
        related_returns=[
            K1RelatedReturnOut(
                return_id=x.return_id, client_name=x.client_name, form=x.form, status=x.status
            )
            for x in p.related_returns
        ],
    )


def _tin_out(p: k1.PackageView) -> K1MaskedTinOut | None:
    if p.tin_kind is None or p.tin_last4 is None:
        return None
    return K1MaskedTinOut(kind=cast(Literal["ssn", "ein", "itin"], p.tin_kind), last4=p.tin_last4)


def _change_out(c: k1.DetailsChange) -> RecipientDetailsChangeOut:
    return RecipientDetailsChangeOut(
        id=c.id,
        recipient_id=c.recipient_id,
        kind=cast(Literal["w9", "w8", "address"], c.kind),
        status=RecipientDetailsChangeStatus(c.status),
        submitted_at=cast(datetime, c.submitted_at),
        evidence_version_id=c.evidence_version_id,
    )


@k1_router.get(
    "/tax-returns/{return_id}/k1-packages",
    action="k1_package.read",
    response_model=ListPage[K1PackageOut],
    errors=(501,),
)
async def list_k1_packages_route(
    return_id: Annotated[UUID, Path()], ctx: Ctx
) -> ListPage[K1PackageOut]:
    """TXP-12: rows with documents (the expanded row); `counts` are the tiles by status."""
    await _gate(ctx)
    rows, counts = await k1.packages_of(ctx, return_id)
    return ListPage[K1PackageOut](
        items=[_package_out(p) for p in rows], total=len(rows), counts=counts
    )


@k1_router.get(
    "/k1-packages/{package_id}",
    action="k1_package.read",
    response_model=K1PackageDetailOut,
    errors=(501,),
)
async def k1_package_route(package_id: PackageId, ctx: Ctx) -> K1PackageDetailOut:
    await _gate(ctx)
    p = await k1.package(ctx, package_id)
    # The masked TIN reaches an offshore reader null (DEC-52; AC9.4): the one central mask.
    return await mask_tins_for(
        ctx,
        K1PackageDetailOut(
            package=_package_out(p),
            lines=[
                K1BoxLineOut(
                    document_kind=cast(DocumentKind, line.document_kind),
                    box_code=line.box_code,
                    description=line.description,
                    amount=line.amount,
                    is_total=line.is_total,
                )
                for line in p.lines
            ],
            documents=[_doc_out(d) for d in p.documents],
            tin=_tin_out(p),
        ),
    )


@k1_router.get(
    "/k1-packages/{package_id}/documents/{document_id}",
    action="k1_package.read",
    response_model=K1ViewerManifestOut,
    errors=(501,),
)
async def k1_document_route(
    package_id: PackageId, document_id: Annotated[UUID, Path()], ctx: Ctx
) -> K1ViewerManifestOut:
    await _gate(ctx)
    d = await k1.k1_document(ctx, package_id, document_id)
    return K1ViewerManifestOut(
        document_id=d.id, evidence_version_id=d.evidence_version_id, page_count=None
    )


@k1_router.post(
    "/tax-returns/{return_id}/k1-packages:share-internal",
    action="k1_package.share_internal",
    response_model=K1ShareOut,
    errors=(409, 501),
)
async def share_k1_route(
    return_id: Annotated[UUID, Path()], body: K1ShareIn, ctx: Ctx
) -> K1ShareOut:
    """DEC-88: a hand-off, an `internal_handoff` copy and a final-approval dependency each."""
    await _gate(ctx)
    return K1ShareOut(
        shared=await k1.share_internal(ctx, return_id, body.package_ids, body.target_return_ids)
    )


@k1_router.get(
    "/tax-returns/{return_id}/k1-packages/release-check",
    action="k1_package.read",
    response_model=K1ReleaseCheckOut,
    errors=(501,),
)
async def k1_release_check_route(
    return_id: Annotated[UUID, Path()], ctx: Ctx
) -> K1ReleaseCheckOut:
    await _gate(ctx)
    found = await k1_release.eligibility(ctx, return_id)
    return K1ReleaseCheckOut(
        eligible=found.eligible,
        failing=list(found.failing),
        package_ids=list(found.package_ids),
        email_template_version_id=await k1_release.template_in_use(ctx),
    )


@k1_router.post(
    "/tax-returns/{return_id}/k1-packages:release",
    action="k1_package.release",
    response_model=K1ReleaseOut,
    status_code=202,
    errors=(409,),
)
async def release_k1_route(
    return_id: Annotated[UUID, Path()],
    body: K1ReleaseIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> K1ReleaseOut:
    """T-02-T21: a single-use grant held 10 s for Undo; then `K1ReleaseWorkflow` delivers."""
    await _gate(ctx)
    made = await k1_release.request_release(
        ctx,
        return_id,
        body.package_ids,
        body.email_template_version_id,
        body.seen_version,
        idempotency_key,
    )
    return K1ReleaseOut(
        release_id=made.id, status=_status(made.status), not_before=made.not_before
    )


@k1_router.post(
    "/k1-releases/{release_id}:undo",
    action="k1_package.release",
    response_model=K1ReleaseOut,
    errors=(409,),
)
async def undo_k1_release_route(release_id: Annotated[UUID, Path()], ctx: Ctx) -> K1ReleaseOut:
    await _gate(ctx)
    made = await k1_release.undo(ctx, release_id)
    return K1ReleaseOut(
        release_id=made.id, status=_status(made.status), not_before=made.not_before
    )


ReleaseStatus = Literal["pending", "undone", "running", "completed", "failed"]


def _status(status: str) -> ReleaseStatus:
    return cast(ReleaseStatus, status)


@k1_router.post(
    "/k1-packages/{package_id}:resend",
    action="k1_package.resend",
    response_model=K1PackageOut,
    errors=(409, 501),
)
async def resend_k1_route(
    package_id: PackageId, body: K1ResendIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> K1PackageOut:
    """The corrected contact; T21's workflow sends the new invitation."""
    await _gate(ctx)
    await k1.resend(ctx, package_id, body.contact_id)
    return _package_out(await k1.package(ctx, package_id))


@k1_router.get(
    "/k1-recipients/{recipient_id}/details-changes",
    action="k1_recipient.review_details",
    response_model=list[RecipientDetailsChangeOut],
    errors=(501,),
)
async def details_changes_route(
    recipient_id: Annotated[UUID, Path()], ctx: Ctx
) -> list[RecipientDetailsChangeOut]:
    await _gate(ctx)
    return [_change_out(c) for c in await k1.details_changes(ctx, recipient_id)]


@k1_router.post(
    "/recipient-details-changes/{change_id}:accept",
    action="k1_recipient.review_details",
    response_model=RecipientDetailsChangeOut,
    errors=(409, 501),
)
async def accept_details_change_route(
    change_id: Annotated[UUID, Path()], body: ReviewReasonIn, ctx: Ctx
) -> RecipientDetailsChangeOut:
    """DV-10: recorded for the firm to apply in CCH (no full TIN is stored)."""
    await _gate(ctx)
    return _change_out(await k1.decide_details_change(ctx, change_id, True, body.reason))


@k1_router.post(
    "/recipient-details-changes/{change_id}:reject",
    action="k1_recipient.review_details",
    response_model=RecipientDetailsChangeOut,
    errors=(409, 501),
)
async def reject_details_change_route(
    change_id: Annotated[UUID, Path()], body: ReviewReasonIn, ctx: Ctx
) -> RecipientDetailsChangeOut:
    await _gate(ctx)
    return _change_out(await k1.decide_details_change(ctx, change_id, False, body.reason))


def _download(made: k1_portal.Download) -> Response:
    return Response(
        made.body,
        media_type=made.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{made.file_name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _portal_gate(ctx: AuthContext) -> None:
    """A firm principal never reaches the portal routes; then the flag."""
    if not ctx.client:
        raise NotFound("k1_package")
    if not await flag_enabled(ctx.tenant, TAX_K1_RELEASE):
        raise NotFound(TAX_K1_RELEASE.name)


@portal_k1_router.get("/k1s", action="portal_k1.read", response_model=list[K1PackageOut])
async def portal_k1s_route(ctx: Member) -> list[K1PackageOut]:
    """POR-13: the recipient's own packages, released and later only (T-02-T26)."""
    await _portal_gate(ctx)
    return [_package_out(p) for p in await k1_portal.packages(ctx)]


def _disclosure_out(d: k1_disclosures.Disclosure) -> K1DisclosureOut:
    return K1DisclosureOut(
        id=d.id, version_no=d.version_no, body=d.body, imported_at=d.imported_at
    )


@k1_router.post(
    "/k1-furnishing-disclosures",
    action="k1_disclosure.import",
    response_model=K1DisclosureOut,
    status_code=201,
)
async def import_k1_disclosure_route(body: K1DisclosureIn, ctx: Ctx) -> K1DisclosureOut:
    """S20e (DV-12): a firm admin's new version of the counsel-approved text (content, never a
    seed for a real firm)."""
    await _gate(ctx)
    return _disclosure_out(await k1_disclosures.import_disclosure(ctx, body.body))


@portal_k1_router.get(
    "/k1-furnishing-disclosure", action="portal_k1.read", response_model=K1DisclosureOut
)
async def portal_k1_disclosure_route(ctx: Member) -> K1DisclosureOut:
    """S20e (DV-12): the newest disclosure a recipient reads before consenting; 404 while none
    is published."""
    await _portal_gate(ctx)
    return _disclosure_out(await k1_portal.furnishing_disclosure(ctx))


@portal_k1_router.get(
    "/k1s/expected", action="portal_k1.read", response_model=list[PortalK1ExpectedOut]
)
async def portal_k1s_expected_route(ctx: Member) -> list[PortalK1ExpectedOut]:
    """POR-13 b (T-02-T27): "Not released yet · Expected by …" with no amounts or documents."""
    await _portal_gate(ctx)
    return [
        PortalK1ExpectedOut(
            issuer_name=e.issuer_name,
            form=cast(Literal["1065", "1120s", "1041"], e.form),
            tax_year=e.tax_year,
            k3_status=cast(Literal["included", "not_required", "not_included"], e.k3_status),
            expected_on=e.expected_on,
        )
        for e in await k1_portal.expected(ctx)
    ]


@portal_k1_router.get(
    "/k1s/{package_id}", action="portal_k1.read", response_model=K1PackageDetailOut, errors=(409,)
)
async def portal_k1_route(package_id: PackageId, ctx: Member) -> K1PackageDetailOut:
    """The statement with its box lines (TRI, the second step); the first read is Viewed."""
    await _portal_gate(ctx)
    p = await k1_portal.package(ctx, package_id)
    return await mask_tins_for(
        ctx,
        K1PackageDetailOut(
            package=_package_out(p),
            lines=[
                K1BoxLineOut(
                    document_kind=cast(DocumentKind, line.document_kind),
                    box_code=line.box_code,
                    description=line.description,
                    amount=line.amount,
                    is_total=line.is_total,
                )
                for line in p.lines
            ],
            documents=[_doc_out(d) for d in p.documents],
            tin=_tin_out(p),
            address_on_file=p.address_on_file,
        ),
    )


@portal_k1_router.get(
    "/k1s/{package_id}/download", action="portal_k1.download", response_model=bytes, errors=(409,)
)
async def portal_k1_download_route(package_id: PackageId, ctx: Member) -> Response:
    """A deterministic zip of the final documents; an access event per download."""
    await _portal_gate(ctx)
    return _download(await k1_portal.download(ctx, package_id))


@portal_k1_router.get(
    "/k1s/{package_id}/attachments/{document_id}",
    action="portal_k1.download",
    response_model=bytes,
    errors=(409,),
)
async def portal_k1_attachment_route(
    package_id: PackageId, document_id: Annotated[UUID, Path()], ctx: Member
) -> Response:
    await _portal_gate(ctx)
    return _download(await k1_portal.one_document(ctx, package_id, document_id))


@portal_k1_router.post(
    "/k1-recipients/{recipient_id}/details-changes",
    action="portal_k1.update_details",
    response_model=RecipientDetailsChangeOut,
    status_code=201,
    errors=(409,),
)
async def portal_details_change_route(
    recipient_id: Annotated[UUID, Path()], body: PortalDetailsChangeIn, ctx: Member
) -> RecipientDetailsChangeOut:
    """A signed W-9 or W-8, or a structured address, for a person at the firm to decide."""
    await _portal_gate(ctx)
    return _change_out(
        await k1_portal.submit_details_change(
            ctx, recipient_id, body.kind, body.upload_id, body.address
        )
    )


@portal_k1_router.post(
    "/k1s/{package_id}/e-furnishing-consent",
    action="portal_k1.update_details",
    response_model=EFurnishingConsentOut,
    errors=(409,),
)
async def portal_e_furnishing_route(
    package_id: PackageId, body: EFurnishingConsentIn, ctx: Member
) -> EFurnishingConsentOut:
    await _portal_gate(ctx)
    decision, on = await k1_portal.e_furnishing(
        ctx, package_id, body.decision, body.disclosure_version_id
    )
    return EFurnishingConsentOut(
        package_id=package_id,
        e_furnishing_consent=cast(Literal["given", "declined"], decision),
        decided_on=on,
    )
