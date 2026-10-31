"""§7216 consent capture (T-01-T10; T-01 §3.1 Stories 1.1 to 1.5; SPEC-501 AC-32 to AC-38; DF-16;
C7, C11, C19).

organisations owns the consent rows but cannot render or draft (its only dependencies are
identity and platform), so this module, which may import methodology, reporting, evidence and
signatures, does the work behind C19's request, renewal and record routes and registers itself in
organisations' capture slot at import:

1. **Request** (Story 1.1): the filing unit and its signers (both spouses on a joint unit), no
   standing decline or open request for the purpose and years, a third-party scope only on
   return information that exists (Story 1.5). For each purpose, its own document (one purpose
   per document, Rev. Proc. 2013-14 §5.05): the firm's current published `consent_7216` template
   for that purpose (409 `consent_template_missing`), its variables resolved here
   (`taxpayer.name`, `taxpayer.names`, `tax_years`, `consent.recipients` from the provider-terms
   register, DF-16), rendered by P-11's renderer in its isolated child, the bytes written once to
   COMPLIANCE storage (`consent_evidence`, at the retention floor). Then one C7 envelope is
   drafted from the `consent_set` source with every document and every required signer, and
   the consent rows are written naming it. Sending stays a person's act in SIG-02.
2. **Renewal**: the same purpose, scope and years for one entity, a new document from today's
   template and register, `renewal_of_id` set; a decline stands (409 `consent_declined`).
3. **Record mode** (Story 1.3): the signed PDF the firm collected elsewhere (staged import files),
   written once to COMPLIANCE storage; the consent is `signed` with `source = 'record'`.
4. **Signing** (Story 1.2): `envelope.completed` on a `consent_set` envelope signs its consents
   (organisations), each expiring by its template's stated term or one year.

A render refusal (`missing_variable`, `missing_glyph`, `recipients_unavailable`…) answers 422
`consent_render_refused` with the renderer's code; nothing is drafted or written.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, cast
from uuid import UUID, uuid4

from abacus.kernel.clock import now
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import OutboxEvent
from abacus.modules.evidence.api import put_record, read_staged, retain_until_for
from abacus.modules.identity.api import AuthContext
from abacus.modules.methodology.api import (
    PublishedConsentTemplate,
    consent_expiry_months,
    published_consent_template,
)
from abacus.modules.organisations.api import (
    ConsentDraft,
    ConsentDraftsOut,
    ConsentRecordIn,
    ConsentRenewalIn,
    ConsentRequestIn,
    FilingUnit,
    check_scope,
    consent_counts,
    consent_outs,
    consent_template_versions_on,
    envelope_completed,
    filing_unit,
    record_request,
    record_signed,
    refuse_declined,
    register_consent_capture,
    renewal_basis,
)
from abacus.modules.reporting.api import (
    CONSENT_RECIPIENTS_KEY,
    RecipientsUnavailable,
    RenderingRefused,
    RenderInput,
    consent_recipients,
    render_isolated,
)
from abacus.modules.requests.api import register_binder_consents
from abacus.modules.signatures.api import (
    EnvelopeSource,
    SourceDocument,
    SourceDraft,
    SourceSigner,
    create_draft,
    register_envelope_source,
    staged_files,
)

SOURCE: Final = "consent_set"
RECORD_TYPE: Final = "consent_evidence"
SERVICE_LINE: Final = "tax"
_PURPOSE: Final = "consent_7216"  # the envelope purpose (C7)


class ConsentTemplateMissing(DomainConflict):
    """No published consent template covers this purpose yet (counsel-approved content)."""

    code = "consent_template_missing"


class ConsentRenderRefused(DomainInvalid):
    """The renderer refused the document (its code in the facts); nothing was drafted."""

    code = "consent_render_refused"


class ConsentRetentionMissing(DomainConflict):
    """No retention floor covers consent evidence yet: COMPLIANCE storage needs a date."""

    code = "consent_retention_missing"


class RenewalSpansEntities(DomainInvalid):
    """One renewal drafts one envelope, so its consents belong to one taxpayer."""

    code = "renewal_spans_entities"


@dataclass(frozen=True)
class _Rendered:
    draft: ConsentDraft
    sha256: str
    pages: int


# The draft source reads what the capture rendered for the set it is drafting (same request).
_STASH: dict[UUID, tuple[FilingUnit, list[_Rendered]]] = {}


def _years(years: Sequence[int]) -> str:
    ordered = [str(y) for y in sorted(years)]
    return ordered[0] if len(ordered) == 1 else f"{', '.join(ordered[:-1])} and {ordered[-1]}"


def _values(unit: FilingUnit, years: Sequence[int], recipients_line: str) -> dict[str, str]:
    """The consent kind's variables, all resolved here from the database (never the browser)."""
    names = [s.name for s in unit.signers]
    return {
        "taxpayer.name": unit.entity_name,
        "taxpayer.names": " and ".join(names) if names else unit.entity_name,
        "client.name": unit.entity_name,
        "tax_years": _years(years),
        CONSENT_RECIPIENTS_KEY: recipients_line,
    }


async def _retain_until(tenant: TenantContext) -> datetime:
    keep = await retain_until_for(tenant, RECORD_TYPE, SERVICE_LINE, await now(tenant))
    if keep is None:
        raise ConsentRetentionMissing
    return keep


async def _render(
    ctx: AuthContext,
    unit: FilingUnit,
    template: PublishedConsentTemplate,
    years: Sequence[int],
    scope: dict[str, str],
    on: date,
    *,
    renewal_of: UUID | None = None,
) -> _Rendered:
    version = template.version
    try:
        recipients = consent_recipients(on)
    except RecipientsUnavailable as refused:
        raise ConsentRenderRefused(facts={"code": refused.code}) from None
    values = _values(unit, years, recipients.line)
    library = {
        str(c["clause_id"]): cast(list[object], c["standard"])
        for c in cast(list[dict[str, object]], version.clauses)
    }
    content_hash = hashlib.sha256(
        json.dumps({"template": version.content_sha256, "values": values}, sort_keys=True).encode()
    ).hexdigest()
    request = RenderInput(
        layout_key=version.layout_key,
        blocks=version.body,
        values=values,
        title=template.name,
        as_of=await now(ctx.tenant),
        mode="final",
        content_hash=content_hash,
        library=library,
    )
    try:
        out = await asyncio.to_thread(render_isolated, request)
    except RenderingRefused as refused:
        raise ConsentRenderRefused(facts={"code": refused.code}) from None
    await put_record(ctx.tenant_id, RECORD_TYPE, out.pdf, await _retain_until(ctx.tenant))
    terms = version.consent
    if terms is None:  # published_consent_template returns consent versions only
        raise ConsentRenderRefused(facts={"code": "not_a_consent_template"})
    draft = ConsentDraft(
        purpose=terms.purpose,
        template_version_id=version.version_id,
        text_sha256=out.render_hash,
        provider_terms_version=recipients.provider_terms_version,
        recipients=[{"kind": "provider", "name": recipients.line, "country": "US"}],
        scope=scope,
        expiry_months=terms.expiry_months,
        renewal_of_id=renewal_of,
    )
    return _Rendered(draft, out.render_hash, out.page_count)


async def _template(ctx: AuthContext, purpose: str) -> PublishedConsentTemplate:
    found = await published_consent_template(ctx, purpose)
    if found is None:
        raise ConsentTemplateMissing(facts={"purpose": purpose})
    return found


async def _draft_source(ctx: AuthContext, set_id: UUID) -> SourceDraft:
    """The `consent_set` source's prefill: every rendered document, every required signer."""
    unit, rendered = _STASH[set_id]
    return SourceDraft(
        purpose=_PURPOSE,
        policy_family="consent",
        client_id=unit.client_id,
        title=f"§7216 consents · {unit.entity_name}",
        documents=tuple(
            SourceDocument(
                sha256=r.sha256,
                page_count=r.pages,
                source_ref=f"{RECORD_TYPE}:{r.sha256}",
            )
            for r in rendered
        ),
        signers=tuple(
            SourceSigner(identity_method="email_code", contact_id=s.contact_id)
            for s in unit.signers
        ),
        signer_order="parallel" if unit.joint else "sequential",
    )


async def _no_documents(ctx: AuthContext, set_id: UUID) -> Sequence[object]:
    return []


async def _envelope(
    ctx: AuthContext, unit: FilingUnit, years: Sequence[int], rendered: list[_Rendered]
) -> ConsentDraftsOut:
    set_id = uuid4()
    _STASH[set_id] = (unit, rendered)
    try:
        envelope_id = await create_draft(ctx, SOURCE, set_id)
    finally:
        _STASH.pop(set_id, None)
    ids = await record_request(
        ctx, unit, years, [r.draft for r in rendered], envelope_id, set_id=set_id
    )
    return ConsentDraftsOut(envelope_id=envelope_id, consents=await consent_outs(ctx, ids))


class Capture:
    """C19's request, renewal and record, registered in organisations' capture slot."""

    async def request(self, ctx: AuthContext, body: object) -> object:
        asked = cast(ConsentRequestIn, body)
        unit = await filing_unit(ctx, asked.client_entity_id)
        purposes = list(dict.fromkeys(asked.purposes))
        years = sorted(set(asked.tax_years))
        await refuse_declined(ctx.tenant, unit.entity_id, purposes, years)
        on = (await now(ctx.tenant)).date()
        for purpose in purposes:
            check_scope(purpose, asked.scope, years, on)
        rendered = [
            await _render(ctx, unit, await _template(ctx, p), years, asked.scope or {}, on)
            for p in purposes
        ]
        return await _envelope(ctx, unit, years, rendered)

    async def renew(self, ctx: AuthContext, body: object) -> object:
        asked = cast(ConsentRenewalIn, body)
        basis = await renewal_basis(ctx, asked.consent_ids)
        entities = {b.entity_id for b in basis}
        years_seen = {b.tax_years for b in basis}
        if len(entities) != 1 or len(years_seen) != 1:
            raise RenewalSpansEntities(facts={"entities": len(entities)})
        unit = await filing_unit(ctx, entities.pop())
        years = list(years_seen.pop())
        on = (await now(ctx.tenant)).date()
        rendered = [
            await _render(
                ctx,
                unit,
                await _template(ctx, b.purpose),
                years,
                b.scope,
                on,
                renewal_of=b.consent_id,
            )
            for b in basis
        ]
        return await _envelope(ctx, unit, years, rendered)

    async def record(self, ctx: AuthContext, body: object) -> object:
        asked = cast(ConsentRecordIn, body)
        unit = await filing_unit(ctx, asked.client_entity_id)
        files = await staged_files(ctx, asked.upload_ids)
        keep = await _retain_until(ctx.tenant)
        for staged in files:  # each file's bytes, write-once in COMPLIANCE mode
            content = await read_staged(
                ctx.tenant_id,
                staged.storage_key,
                staged.storage_version_id,
                staged.sha256,
                staged.size_bytes,
            )
            await put_record(ctx.tenant_id, RECORD_TYPE, content, keep)
        terms = await consent_expiry_months(ctx.tenant, [asked.template_version_id])
        draft = ConsentDraft(
            purpose=asked.purpose,
            template_version_id=asked.template_version_id,
            text_sha256=files[0].sha256,  # the first file is the signed document
            provider_terms_version="recorded",
            expiry_months=terms.get(asked.template_version_id),
        )
        consent_id = await record_signed(ctx, unit, asked.tax_years, draft, asked.signed_on)
        return (await consent_outs(ctx, [consent_id]))[0]


CAPTURE: Final = Capture()


async def on_envelope_completed(event: OutboxEvent) -> None:
    """C7 `envelope.completed` for a `consent_set` envelope signs its consents (Story 1.2)."""
    if event.payload.get("source_kind") != SOURCE:
        return
    tenant = TenantContext(event.tenant_id, "system", "consents:envelope_completed")
    envelope_id = UUID(str(event.payload["envelope_id"]))
    method = "record" if event.payload.get("provider") == "record" else "email_code"
    versions = await consent_template_versions_on(tenant, envelope_id)
    months = await consent_expiry_months(tenant, list(set(versions.values())))
    await envelope_completed(
        tenant,
        envelope_id,
        method=method,
        expiry_months={cid: months.get(v) for cid, v in versions.items()},
    )


async def binder_consents(
    tenant: TenantContext, rows: Sequence[tuple[UUID, UUID, str | None]]
) -> dict[UUID, tuple[int, int]]:
    """BND-01's §7216 consents tag (DEC-1288): for a return binder (season `TY<year>`), the
    client's consents for that year in force and asked for; none when none is asked for."""
    years: dict[UUID, tuple[UUID, int]] = {}
    for binder, client, season in rows:
        if season is not None and season.startswith("TY") and season[2:].isdigit():
            years[binder] = (client, int(season[2:]))
    counts = await consent_counts(tenant, sorted(set(years.values())))
    return {
        binder: counts[pair]
        for binder, pair in years.items()
        if pair in counts and counts[pair][1] > 0
    }


def register() -> None:
    """At import (tax/api.py): the capture slot, the `consent_set` envelope source and BND-01's
    consents tag."""
    register_consent_capture(CAPTURE)
    register_binder_consents(binder_consents)
    register_envelope_source(
        EnvelopeSource(
            kind=SOURCE,
            documents=_no_documents,
            signers=_no_documents,
            retention_record_type=RECORD_TYPE,
            completed_label="Signed",
            draft=_draft_source,
        )
    )
