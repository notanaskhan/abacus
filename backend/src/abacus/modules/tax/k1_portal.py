"""POR-13: a K-1 recipient's own packages in the portal (T-02-T26; T-02 §3.6, §4.3; DEC-34, DEC-78,
DEC-129; DEC-1478). Amber.

- **Own only.** A client person reads the packages their active `k1_recipient` grants name
  (`portal_scopes`; one grant, one package), and only from release on: `released`, `viewed`,
  `downloaded`, `bounced`, and a released package later superseded by a corrected one. A draft,
  a package of the same return granted to someone else, and every other client's package answer
  404, the same as an unknown id. The matrix's `scope_only` has already placed the person on the
  issuing return; the package check is this file's (`own_only`, DEC-1162).
- **The MFA floor** (DEC-34): K-1s are TRI-bearing deliverables, so the detail, the downloads and
  the details change need the portal session's second step (409 `mfa_required` otherwise); the
  list carries no amounts and does not.
- **Reads and downloads** write an access event (`schedule_k.read`, flagged `tri`) before anything
  leaves, and a package event. The first detail read moves `released` to `viewed`, the first
  download (zip or one document) to `downloaded`; neither moves back. The zip is deterministic:
  the final documents in a fixed order with fixed timestamps, so the same package always answers
  the same bytes. Draft documents never leave (DEC-78).
- **Details change** (DV-10): a signed W-9 or W-8 (an evidence version the person uploaded) or a
  structured address, pending until a person at the firm decides it (T-02-T20's review).
- **Electronic furnishing** (Treas. Reg. §1.6031(b)-1T(b)): the recipient's consent or refusal is
  recorded on the package with the disclosure version they saw.

Every write runs through the unit of work with its audit row, attributed to the recipient. Box
values are TRI: never logged, never in an error's facts.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.access import AccessSubject, record_reads, register_access_kind
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.evidence.api import version_content
from abacus.modules.identity.api import AuthContext, portal_scopes
from abacus.modules.tax import k1_packages as k1

READ: Final = "portal_k1.read"
DOWNLOAD: Final = "portal_k1.download"
UPDATE: Final = "portal_k1.update_details"
ACCESS_KIND: Final = "schedule_k.read"
VISIBLE: Final = frozenset({"released", "viewed", "downloaded", "bounced"})
_ZIP_TIME: Final = (2026, 1, 1, 0, 0, 0)
_ADDRESS_FIELDS: Final = ("line1", "line2", "city", "state", "postal_code", "country")
_ORDER: Final = {"k1": 0, "k3": 1, "state_k1": 2, "letter": 3}

register_access_kind(ACCESS_KIND, ["tri"])


class K1MfaRequired(DomainConflict):
    """K-1s carry amounts (TRI): the portal session's second step first (DEC-34)."""

    code = "mfa_required"


class DetailsChangeInvalid(DomainInvalid):
    """A W-9 or W-8 names the uploaded file; an address its structured fields (`facts.field`)."""

    code = "details_change_invalid"


@dataclass(frozen=True)
class Download:
    file_name: str
    media_type: str
    body: bytes


def _client(ctx: AuthContext) -> None:
    if not ctx.client:
        raise NotFound(k1.KIND)  # a firm principal never reaches the portal routes


def _second_step(ctx: AuthContext) -> None:
    if ctx.mfa_at is None and not ctx.portal_second_step:
        raise K1MfaRequired


async def _granted(ctx: AuthContext) -> list[UUID]:
    found = await portal_scopes(ctx)
    return [
        s.scope_id
        for s in found.scopes
        if s.role == "k1_recipient" and s.scope_kind == "k1_package"
    ]


_VISIBLE_ROWS = text(
    "SELECT id, work_item_id, status, released_at FROM k1_packages WHERE id = ANY(:ids) "
    "AND released_at IS NOT NULL AND (status = ANY(:visible) OR status = 'superseded')"
)


async def _mine(ctx: AuthContext) -> dict[UUID, UUID]:
    """The person's released packages and their issuing returns; drafts never."""
    granted = await _granted(ctx)
    if not granted:
        return {}
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(_VISIBLE_ROWS, {"ids": granted, "visible": sorted(VISIBLE)})
        ).all()
    return {cast(UUID, r.id): cast(UUID, r.work_item_id) for r in rows}


async def _own(ctx: AuthContext, package_id: UUID) -> UUID:
    """The issuing return of one of the person's released packages, or 404."""
    _client(ctx)
    found = (await _mine(ctx)).get(package_id)
    if found is None:
        raise NotFound("k1_package")
    return found


_PACKAGES = text(
    "SELECT p.id, p.recipient_id, r.display_name, r.recipient_kind, p.form, p.tax_year, "
    "p.status, p.k3_status, p.state_codes, p.released_at, p.version_no FROM k1_packages p "
    "JOIN k1_recipients r ON r.id = p.recipient_id WHERE p.id = ANY(:ids) "
    "ORDER BY p.tax_year DESC, r.display_name, p.version_no DESC"
)
_DOCUMENTS = text(
    "SELECT id, package_id, kind, jurisdiction, evidence_version_id, is_draft FROM k1_documents "
    "WHERE package_id = ANY(:ids) AND NOT is_draft ORDER BY created_at, id"
)


async def _views(tenant: TenantContext, ids: Sequence[UUID]) -> list[k1.PackageView]:
    if not ids:
        return []
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_PACKAGES, {"ids": list(ids)})).all()
        docs = (await session.execute(_DOCUMENTS, {"ids": list(ids)})).all()
    by_package: dict[UUID, list[k1.DocumentView]] = {}
    for d in docs:
        by_package.setdefault(d.package_id, []).append(
            k1.DocumentView(d.id, d.kind, d.jurisdiction, d.evidence_version_id, d.is_draft)
        )
    return [
        k1.PackageView(
            r.id,
            r.recipient_id,
            r.display_name,
            r.recipient_kind,
            r.form,
            int(r.tax_year),
            r.status,
            r.k3_status,
            tuple(r.state_codes or ()),
            r.released_at,
            int(r.version_no),
            ("download", "update_details") if r.status != "superseded" else ("download",),
            tuple(by_package.get(r.id, [])),
        )
        for r in rows
    ]


async def packages(ctx: AuthContext) -> list[k1.PackageView]:
    """`GET /v1/portal/k1s`: the person's own released packages (no amounts on a row)."""
    _client(ctx)
    return await _views(ctx.tenant, list(await _mine(ctx)))


async def _facts(tenant: TenantContext, return_id: UUID) -> tuple[UUID | None, UUID | None]:
    """The issuing return's engagement and client, for the access event's scope."""
    found = await k1.package_return_scope(tenant, return_id)
    return (found.engagement_id, found.client_id) if found is not None else (None, None)


async def _read_logged(ctx: AuthContext, package_id: UUID, return_id: UUID) -> None:
    engagement, client = await _facts(ctx.tenant, return_id)
    await record_reads(
        ctx.tenant,
        ACCESS_KIND,
        [
            AccessSubject(
                "schedule_k_package",  # digit-free, as the audit's (DEC-1471)
                package_id,
                client_id=client,
                engagement_id=engagement,
                work_item_id=return_id,
            )
        ],
    )


async def _advance(
    ctx: AuthContext,
    package_id: UUID,
    return_id: UUID,
    to: str,
    kind: str,
    facts: Mapping[str, object],
) -> None:
    """A package event and audit row, and the status moved forward only (released → viewed →
    downloaded); a bounced or superseded package keeps its word."""
    order = {"released": 0, "viewed": 1, "downloaded": 2}
    async with uow(ctx.tenant) as tx:
        status = await tx.session.scalar(
            text("SELECT status FROM k1_packages WHERE id = :p FOR UPDATE"), {"p": package_id}
        )
        if status in order and order[str(status)] < order[to]:
            await tx.session.execute(
                text("UPDATE k1_packages SET status = :s WHERE id = :p"),
                {"s": to, "p": package_id},
            )
        await k1.record_event(tx, ctx.tenant_id, package_id, kind, ctx.user_id, facts)
        tx.record(
            f"schedule_k_package.{kind}",
            target=Target(k1.KIND, return_id),
            after=Ref(package=package_id),
        )


async def package(ctx: AuthContext, package_id: UUID) -> k1.PackageView:
    """`GET /v1/portal/k1s/{id}`: the statement with its box lines; the first read is Viewed."""
    return_id = await _own(ctx, package_id)
    _second_step(ctx)
    await _read_logged(ctx, package_id, return_id)
    [view] = await _views(ctx.tenant, [package_id])
    async with tenant_session(ctx.tenant) as session:
        lines = (
            await session.execute(
                text(
                    "SELECT document_kind, box_code, description, amount, is_total "
                    "FROM k1_box_lines WHERE package_id = :p ORDER BY document_kind, position"
                ),
                {"p": package_id},
            )
        ).all()
    await _advance(ctx, package_id, return_id, "viewed", "viewed", {})
    return replace(
        view,
        lines=tuple(
            k1.LineView(r.document_kind, r.box_code, r.description, r.amount, r.is_total)
            for r in lines
        ),
    )


def _name(doc: k1.DocumentView, n: int) -> str:
    base = doc.kind if doc.jurisdiction is None else f"{doc.kind}_{doc.jurisdiction.lower()}"
    return f"{n:02d}_{base}.pdf"


def deterministic_zip(files: Sequence[tuple[str, bytes]]) -> bytes:
    """The same files always make the same bytes: fixed order, times and permissions."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(files):
            info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body)
    return buffer.getvalue()


async def download(ctx: AuthContext, package_id: UUID) -> Download:
    """`GET /v1/portal/k1s/{id}/download`: every final document, one zip, an access event."""
    return_id = await _own(ctx, package_id)
    _second_step(ctx)
    [view] = await _views(ctx.tenant, [package_id])
    docs = sorted(view.documents, key=lambda d: (_ORDER.get(d.kind, 9), d.jurisdiction or ""))
    await _read_logged(ctx, package_id, return_id)
    files = [
        (_name(d, n), await version_content(ctx.tenant, d.evidence_version_id))
        for n, d in enumerate(docs, start=1)
    ]
    body = deterministic_zip(files)
    await _advance(
        ctx, package_id, return_id, "downloaded", "downloaded", {"documents": len(files)}
    )
    return Download(f"K-1_{view.tax_year}_{view.form}.zip", "application/zip", body)


async def one_document(ctx: AuthContext, package_id: UUID, document_id: UUID) -> Download:
    """`GET …/attachments/{doc}`: one final document, an access event."""
    return_id = await _own(ctx, package_id)
    _second_step(ctx)
    [view] = await _views(ctx.tenant, [package_id])
    doc = next((d for d in view.documents if d.id == document_id), None)
    if doc is None:
        raise NotFound("k1_document")
    await _read_logged(ctx, package_id, return_id)
    body = await version_content(ctx.tenant, doc.evidence_version_id)
    await _advance(
        ctx, package_id, return_id, "downloaded", "downloaded", {"document": str(doc.id)}
    )
    return Download(_name(doc, 1), "application/pdf", body)


def _address(raw: Mapping[str, str] | None) -> dict[str, str]:
    if raw is None or set(raw) - set(_ADDRESS_FIELDS):
        raise DetailsChangeInvalid(facts={"field": "address"})
    out = {k: str(raw.get(k, "")).strip() for k in _ADDRESS_FIELDS if raw.get(k)}
    for required in ("line1", "city", "postal_code", "country"):
        if not out.get(required):
            raise DetailsChangeInvalid(facts={"field": required})
    if any(len(v) > 200 or any(not c.isprintable() for c in v) for v in out.values()):
        raise DetailsChangeInvalid(facts={"field": "address"})
    return out


async def submit_details_change(
    ctx: AuthContext,
    recipient_id: UUID,
    kind: str,
    upload_id: UUID | None,
    address: Mapping[str, str] | None,
) -> k1.DetailsChange:
    """`POST /v1/portal/k1-recipients/{rid}/details-changes`: pending for the firm (DV-10)."""
    _client(ctx)
    _second_step(ctx)
    mine = await _mine(ctx)
    async with tenant_session(ctx.tenant) as session:
        owned = await session.scalar(
            text(
                "SELECT work_item_id FROM k1_packages WHERE recipient_id = :r AND id = ANY(:ids)"
            ),
            {"r": recipient_id, "ids": list(mine)},
        )
    if owned is None:
        raise NotFound("k1_recipient")
    stored_address: dict[str, str] | None = None
    if kind == "address":
        stored_address = _address(address)
        upload_id = None
    elif kind in ("w9", "w8"):
        if upload_id is None or address is not None:
            raise DetailsChangeInvalid(facts={"field": "upload_id"})
    else:
        raise DetailsChangeInvalid(facts={"field": "kind"})
    async with uow(ctx.tenant) as tx:
        change = await tx.session.scalar(
            text(
                "INSERT INTO recipient_details_changes (tenant_id, recipient_id, kind, "
                "evidence_version_id, address, submitted_by) VALUES (:t, :r, :k, :v, "
                "CAST(:a AS jsonb), :by) RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "r": recipient_id,
                "k": kind,
                "v": upload_id,
                "a": None if stored_address is None else json.dumps(stored_address),
                "by": ctx.user_id,
            },
        )
        tx.record(
            "recipient_details_change.submitted",
            target=Target(k1.KIND, cast(UUID, owned)),
            after=Ref(recipient=recipient_id, change=cast(UUID, change)),
        )
    found = next(
        c for c in await k1.details_changes_of(ctx.tenant, recipient_id) if c.id == change
    )
    return found


async def e_furnishing(
    ctx: AuthContext, package_id: UUID, decision: str, disclosure_version_id: UUID
) -> tuple[str, date]:
    """`POST …/e-furnishing-consent`: the recipient's consent or refusal, with the disclosure."""
    return_id = await _own(ctx, package_id)
    _second_step(ctx)
    if decision not in ("given", "declined"):
        raise DetailsChangeInvalid(facts={"field": "decision"})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("UPDATE k1_packages SET e_furnishing_consent = :d WHERE id = :p"),
            {"d": decision, "p": package_id},
        )
        await k1.record_event(
            tx,
            ctx.tenant_id,
            package_id,
            "e_furnishing_consent_recorded",
            ctx.user_id,
            {"decision": decision, "disclosure_version_id": str(disclosure_version_id)},
        )
        tx.record(
            "schedule_k_package.e_furnishing_consent_recorded",
            target=Target(k1.KIND, return_id),
            after=Ref(package=package_id, disclosure=disclosure_version_id),
        )
    return decision, await clock.today(ctx.tenant)


__all__ = [
    "ACCESS_KIND",
    "DOWNLOAD",
    "READ",
    "UPDATE",
    "DetailsChangeInvalid",
    "Download",
    "K1MfaRequired",
    "deterministic_zip",
    "download",
    "e_furnishing",
    "one_document",
    "package",
    "packages",
    "submit_details_change",
]
