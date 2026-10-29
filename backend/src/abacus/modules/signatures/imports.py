"""Record-mode import (N-02-T08; N-02 §3.1; SIG-01 r; DF-12; ADR-149; DEC-818).

A person who had a package signed in the firm's own e-signature tool imports it: the completed
document and the provider's certificate (each staged first through `stage_file`: scanned before
storage, refused closed), the signers' facts as that person typed them, and the attestation.

One import, in order:
1. Checks: a firm person (a client principal answers 404), `envelope.import_record` on the client
   or the engagement (the wall answers 404), the flag, the client, engagement and work item
   agree, every signer belongs to the client or the firm, and every file is the importer's own
   and unconsumed.
2. Retention: the `signature_evidence` record type's retain-until, the longer of the firm's
   policy and the published floor; no floor means no import (`retention_floor_missing`).
3. Records bucket, COMPLIANCE mode: each file's bytes and one JSON manifest (hashes, signer
   facts, importer, attestation), write-once (`evidence.api.put_record`).
4. One unit of work: the envelope (`provider = 'record'`, `status = 'completed'`, numbered),
   its document (the signed copy filed as client-scoped evidence under Signed authorizations),
   signers (signed), one `signature_evidence` row per signer naming the package, the events
   `envelope.imported` and `envelope.completed`, the files consumed, audit `envelope.imported`
   and outbox `envelope.completed` naming the importer.

The database refuses the rest: `imported_by` only by the person the transaction names, events
and evidence insert-only (0292).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Final, Literal
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel._flags import SIGNATURES_ENVELOPES
from abacus.kernel.clock import system_now
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, service_line_of, work_item_engagement
from abacus.modules.evidence.api import (
    file_signed_copy,
    put_record,
    read_staged,
    retain_until_for,
    screen_and_stage,
)
from abacus.modules.identity.api import AuthContext, Resource, authorise, names_of
from abacus.modules.organisations.api import client_exists, client_record, contact_facts
from abacus.modules.signatures.events import EnvelopeCompleted

RECORD_TYPE: Final = "signature_evidence"
SOURCE_KIND: Final = "record_import"
EFILE_PURPOSES: Final = frozenset({"form_8879", "form_8879_pe", "form_8879_f"})
_CONSENT: Final = frozenset({"consent_7216"})
ACTION: Final = "envelope.import_record"


class RetentionFloorMissing(DomainConflict):
    """No retention floor or firm policy covers signature evidence yet: nothing is imported,
    because COMPLIANCE storage needs a retain-until date (N-02 §3.13)."""

    code = "retention_floor_missing"


class ImportFileUnavailable(DomainConflict):
    """A named file is not the importer's own staged file, or another import used it."""

    code = "import_file_unavailable"


class ImportScopeMismatch(DomainInvalid):
    """The engagement, work item or a signer belongs to another client (`facts.field`)."""

    code = "import_scope_mismatch"


@dataclass(frozen=True)
class StagedFile:
    id: UUID
    file_name: str
    media_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class SignerFacts:
    contact_id: UUID | None
    user_id: UUID | None
    role: str
    signed_on: date
    identity_method: str


@dataclass(frozen=True)
class ImportRequest:
    purpose: str
    form_code: str | None
    client_id: UUID
    engagement_id: UUID | None
    work_item_id: UUID | None
    title: str
    provider_name: str
    signers: tuple[SignerFacts, ...]
    upload_ids: tuple[UUID, ...]


async def _firm_only(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("envelopes")


async def _flag(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, SIGNATURES_ENVELOPES):
        raise NotFound(SIGNATURES_ENVELOPES.name)


async def stage_file(ctx: AuthContext, *, file_name: str, content: bytes) -> StagedFile:
    """One file for a later import: scanned before storage, refused closed (SPEC-029 AC-1)."""
    await _firm_only(ctx)
    await authorise(ctx, ACTION, Resource.firm(ctx.tenant_id))
    await _flag(ctx)
    screened = await screen_and_stage(ctx.tenant_id, content, file_name, None)
    file_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO envelope_import_files (id, tenant_id, uploaded_by, file_name, "
                "media_type, size_bytes, sha256, storage_key, storage_version_id) VALUES "
                "(:id, :tenant, :user, :name, :media, :size, :sha, :key, :version)"
            ),
            {
                "id": file_id,
                "tenant": ctx.tenant_id,
                "user": ctx.user_id,
                "name": screened.file_name,
                "media": screened.media_type,
                "size": screened.stored.size,
                "sha": screened.sha256,
                "key": screened.stored.key,
                "version": screened.stored.version_id,
            },
        )
        tx.record(
            "envelope_import_file.staged",
            target=Target("envelope_import_file", file_id),
            after=Ref(sha256=screened.sha256, size=screened.stored.size),
        )
    return StagedFile(
        file_id, screened.file_name, screened.media_type, screened.stored.size, screened.sha256
    )


def policy_family(
    purpose: str,
) -> Literal["efile_authorization", "engagement_letter", "consent", "general"]:
    if purpose in EFILE_PURPOSES:
        return "efile_authorization"
    if purpose == "engagement_letter":
        return "engagement_letter"
    if purpose in _CONSENT:
        return "consent"
    return "general"


async def check_import(ctx: AuthContext, request: ImportRequest) -> Resource:
    """The route's check before its `Idempotency-Key` lookup, so a replay is authorised too."""
    await _firm_only(ctx)
    engagement_id = request.engagement_id
    if request.work_item_id is not None:
        owner = await work_item_engagement(ctx.tenant, request.work_item_id)
        if owner is None:
            raise NotFound("work_item")
        if engagement_id is not None and owner != engagement_id:
            raise ImportScopeMismatch(facts={"field": "work_item_id"})
        engagement_id = owner
    if engagement_id is not None:
        ref = await get_ref(ctx, engagement_id)
        resource = ref.resource()
        if ref.client_id != request.client_id:
            raise ImportScopeMismatch(facts={"field": "engagement_id"})
    else:
        if not await client_exists(ctx.tenant, request.client_id):
            raise NotFound("client")
        resource = Resource.client(ctx.tenant_id, request.client_id)
    await authorise(ctx, ACTION, resource)
    await _flag(ctx)
    return resource


async def _signer_names(ctx: AuthContext, request: ImportRequest) -> tuple[str, list[str]]:
    contacts = [s.contact_id for s in request.signers if s.contact_id is not None]
    users = [s.user_id for s in request.signers if s.user_id is not None]
    async with tenant_session(ctx.tenant) as session:
        found = await contact_facts(session, contacts)
        client = await client_record(session, request.client_id)
    if client is None:
        raise NotFound("client")
    people = await names_of(users)
    names: list[str] = []
    for signer in request.signers:
        if (signer.contact_id is None) == (signer.user_id is None):
            raise ImportScopeMismatch(facts={"field": "signers"})
        if signer.contact_id is not None:
            fact = found.get(signer.contact_id)
            if fact is None or fact.client_id != request.client_id:
                raise ImportScopeMismatch(facts={"field": "signers"})
            names.append(fact.display_name)
        elif signer.user_id is not None:
            if signer.user_id not in people:
                raise ImportScopeMismatch(facts={"field": "signers"})
            names.append(people[signer.user_id])
    return client.name, names


_FILES = text(
    "SELECT id, file_name, media_type, size_bytes, sha256, storage_key, storage_version_id "
    "FROM envelope_import_files WHERE id = ANY(:ids) AND uploaded_by = :user "
    "AND consumed_envelope_id IS NULL FOR UPDATE"
)


@dataclass(frozen=True)
class Imported:
    envelope_id: UUID
    client_name: str
    engagement_id: UUID | None
    number: int
    document_id: UUID
    filed_version_id: UUID
    signer_ids: tuple[UUID, ...]
    signer_names: tuple[str, ...]
    document_sha256: str
    package_sha256: str
    retain_until: datetime
    completed_at: datetime


async def import_record(ctx: AuthContext, request: ImportRequest) -> Imported:
    """Import one signed package (the module docstring's steps 2-4); after `check_import`."""
    if len(set(request.upload_ids)) != len(request.upload_ids):
        raise ImportFileUnavailable
    client_name, names = await _signer_names(ctx, request)
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(_FILES, {"ids": list(request.upload_ids), "user": ctx.user_id})
        ).all()
    by_id = {row.id: row for row in rows}
    if set(by_id) != set(request.upload_ids):
        raise ImportFileUnavailable
    files = [by_id[i] for i in request.upload_ids]  # the first is the completed document
    engagement_id = request.engagement_id
    if engagement_id is None and request.work_item_id is not None:
        engagement_id = await work_item_engagement(ctx.tenant, request.work_item_id)
    line = (
        await service_line_of(ctx.tenant, engagement_id) if engagement_id is not None else None
    ) or "any"
    now = system_now()
    keep = await retain_until_for(ctx.tenant, RECORD_TYPE, line, now)
    if keep is None:
        raise RetentionFloorMissing

    envelope_id = uuid4()
    for row in files:  # each file's bytes, write-once in COMPLIANCE mode
        content = await read_staged(
            ctx.tenant_id, row.storage_key, row.storage_version_id, row.sha256, row.size_bytes
        )
        await put_record(ctx.tenant_id, RECORD_TYPE, content, keep)
    manifest = json.dumps(
        {
            "envelope_id": str(envelope_id),
            "tenant_id": str(ctx.tenant_id),
            "provider": "record",
            "provider_name": request.provider_name,
            "purpose": request.purpose,
            "files": [
                {"role": "completed_document" if i == 0 else "certificate", "sha256": r.sha256}
                | {"size_bytes": r.size_bytes, "media_type": r.media_type}
                for i, r in enumerate(files)
            ],
            "signers": [
                {
                    "contact_id": str(s.contact_id) if s.contact_id else None,
                    "user_id": str(s.user_id) if s.user_id else None,
                    "role": s.role,
                    "signed_on": s.signed_on.isoformat(),
                    "identity_method": s.identity_method,
                }
                for s in request.signers
            ],
            "imported_by": str(ctx.user_id),
            "attested": True,
            "imported_at": now.isoformat(),
        },
        sort_keys=True,
    ).encode()
    package = await put_record(ctx.tenant_id, RECORD_TYPE, manifest, keep)
    package_sha = hashlib.sha256(manifest).hexdigest()
    hashes = [r.sha256 for r in files]
    document = files[0]

    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO envelope_numbers (tenant_id) VALUES (:tenant) "
                "ON CONFLICT (tenant_id) DO NOTHING"
            ),
            {"tenant": ctx.tenant_id},
        )
        number = int(
            (
                await tx.session.execute(
                    text(
                        "UPDATE envelope_numbers SET next_value = next_value + 1 "
                        "RETURNING next_value - 1"
                    )
                )
            ).scalar_one()
        )
        await tx.session.execute(
            text(
                "INSERT INTO envelopes (id, tenant_id, number, purpose, form_code, policy_family, "
                "source_kind, source_id, client_id, engagement_id, work_item_id, title, provider, "
                "provider_name, status, retention_record_type, drafted_by_kind, drafted_by, "
                "imported_by, completed_at) VALUES (:id, :tenant, :number, :purpose, :form, "
                ":family, :source_kind, :id, :client, :engagement, :work_item, :title, 'record', "
                ":provider_name, 'completed', :record_type, 'human', :user, :user, :now)"
            ),
            {
                "id": envelope_id,
                "tenant": ctx.tenant_id,
                "number": number,
                "purpose": request.purpose,
                "form": request.form_code,
                "family": policy_family(request.purpose),
                "source_kind": SOURCE_KIND,
                "client": request.client_id,
                "engagement": engagement_id,
                "work_item": request.work_item_id,
                "title": request.title,
                "provider_name": request.provider_name,
                "record_type": RECORD_TYPE,
                "user": ctx.user_id,
                "now": now,
            },
        )
        filed = await file_signed_copy(
            tx,
            tenant_id=ctx.tenant_id,
            client_id=request.client_id,
            engagement_id=engagement_id,
            work_item_id=request.work_item_id,
            title=request.title,
            stored_key=document.storage_key,
            stored_version_id=document.storage_version_id,
            sha256=document.sha256,
            size_bytes=document.size_bytes,
            media_type=document.media_type,
            actor_kind=ctx.tenant.actor_kind,
            actor_id=ctx.tenant.actor_id,
        )
        document_id = uuid4()
        await tx.session.execute(
            text(
                'INSERT INTO envelope_documents (id, tenant_id, envelope_id, "order", '
                "evidence_version_id, sha256, read_only, tri) VALUES (:id, :tenant, :envelope, 1, "
                ":version, :sha, true, :tri)"
            ),
            {
                "id": document_id,
                "tenant": ctx.tenant_id,
                "envelope": envelope_id,
                "version": filed,
                "sha": document.sha256,
                "tri": request.purpose in EFILE_PURPOSES,
            },
        )
        signer_ids: list[UUID] = []
        for order, signer in enumerate(request.signers, start=1):
            signer_id = uuid4()
            signer_ids.append(signer_id)
            signed_at = datetime.combine(signer.signed_on, time(12, 0), tzinfo=now.tzinfo)
            await tx.session.execute(
                text(
                    'INSERT INTO envelope_signers (id, tenant_id, envelope_id, "order", '
                    "party_kind, contact_id, user_id, role, identity_method, status, signed_at, "
                    "signature_method) VALUES (:id, :tenant, :envelope, :order, :party, "
                    ":contact, :user, :role, :method, 'signed', :signed_at, 'provider_adopted')"
                ),
                {
                    "id": signer_id,
                    "tenant": ctx.tenant_id,
                    "envelope": envelope_id,
                    "order": order,
                    "party": "contact" if signer.contact_id is not None else "user",
                    "contact": signer.contact_id,
                    "user": signer.user_id,
                    "role": signer.role,
                    "method": signer.identity_method,
                    "signed_at": signed_at,
                },
            )
            await tx.session.execute(
                text(
                    "INSERT INTO signature_evidence (tenant_id, envelope_id, signer_id, "
                    "signed_at, identity_result, signature_method, document_sha256s, "
                    "package_key, package_sha256, retain_until) VALUES (:tenant, :envelope, "
                    ":signer, :signed_at, :result, 'provider_adopted', :hashes, :key, :sha, "
                    ":keep)"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "envelope": envelope_id,
                    "signer": signer_id,
                    "signed_at": signed_at,
                    "result": f"Recorded from the {request.provider_name} certificate",
                    "hashes": hashes,
                    "key": package.key,
                    "sha": package_sha,
                    "keep": keep.date(),
                },
            )
        for kind in ("envelope.imported", "envelope.completed"):
            await tx.session.execute(
                text(
                    "INSERT INTO envelope_events (tenant_id, envelope_id, kind, source, "
                    "occurred_at, payload_sha256) VALUES (:tenant, :envelope, :kind, 'firm', "
                    ":now, :sha)"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "envelope": envelope_id,
                    "kind": kind,
                    "now": now,
                    "sha": package_sha,
                },
            )
        await tx.session.execute(
            text(
                "UPDATE envelope_import_files SET consumed_envelope_id = :envelope "
                "WHERE id = ANY(:ids) AND consumed_envelope_id IS NULL"
            ),
            {"envelope": envelope_id, "ids": list(request.upload_ids)},
        )
        tx.record(
            "envelope.imported",
            target=Target("envelope", envelope_id),
            after=Ref(
                number=number,
                files=len(files),
                signers=len(signer_ids),
                package_sha256=package_sha,
            ),
        )
        tx.emit(
            EnvelopeCompleted(
                envelope_id=envelope_id,
                client_id=request.client_id,
                engagement_id=engagement_id,
                purpose=request.purpose,
                provider="record",
                source_kind=SOURCE_KIND,
                source_id=envelope_id,
                imported_by=ctx.user_id,
            )
        )
    return Imported(
        envelope_id,
        client_name,
        engagement_id,
        number,
        document_id,
        filed,
        tuple(signer_ids),
        tuple(names),
        document.sha256,
        package_sha,
        keep,
        now,
    )
