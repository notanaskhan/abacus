"""Report templates as firm content (P-11-T06; P-11 §3 F1, §4.2 "Migration 2"; C11 §2, §4, §5;
SPEC-520 AC-1 to AC-5).

A template is one firm's wording for one generated-document family: a DocBlock body, a clause
library, declared variables and synthetic sample data. Rows arrive only through an import (the
`POST /v1/report-templates/import` route, or the scenario loader's service call on the synthetic
tenant): never from a migration, a constant or the seed (AGENTS.md rule 16).

- **Import** (`report_template.import`): the caller (reporting) has already validated the bundle
  against the DocBlock vocabulary; this stores it as the next insert-only version of the
  template named by family and name (created on first import), with its `content_sha256`, and
  audits `report_template.imported` naming the person (INV-5). Importing the same content as the
  latest version stores nothing and returns that version (`created=False`).
- **Publish** (`report_template.publish`, fresh second factor by the matrix): a person only (an
  agent, the system or support is refused and audited `decision.refused_non_human`), never the
  person who imported that version (C11 §4: four eyes; 403 `publisher_is_importer`), and not the
  version already current (409 `already_published`). Republishing an earlier version is the
  rollback: no deploy, no new wording.
- **Consent templates** (T-01-T17; DF-16): the `consent_7216` family carries its consent terms
  (one purpose, the mandatory-statement version, the counsel attestation by the importer, the
  stated expiry) in `report_template_consent_terms`, frozen with the version. A partner publishes
  or deprecates one (`consent_template.publish`, fresh second factor) instead of the template
  publishers; a consent version without terms is never published.
- **Deprecate** withdraws the current version (409 `not_current` otherwise): nothing is current
  until a version is published again.
- **Current version**: the version of the latest `published` publication, unless a later
  `deprecated` row names that same version. Computed on read, never stored.

methodology imports only identity and platform, so it stores and reads JSON; the DocBlock types
and their validation live in `reporting` (which may import methodology, never the reverse).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    names_of,
)
from abacus.modules.methodology.models import (
    ReportTemplate,
    ReportTemplateConsentTerms,
    ReportTemplatePublication,
    ReportTemplateVersion,
)

CONSENT_FAMILY: Final = "consent_7216"
CONSENT_PUBLISH: Final = "consent_template.publish"
READ: Final = "report_template.read"
IMPORT: Final = "report_template.import"
PUBLISH: Final = "report_template.publish"
TEMPLATE: Final = "report_template"
VERSION: Final = "report_template_version"
Source = Literal["import", "scenario_loader"]


# P-11-T15 (DEC-1656): the app role holds no UPDATE on these insert-only tables, and a row lock
# (`FOR UPDATE`, even `FOR SHARE`) needs it, so imports and publications of one template are
# serialised by a transaction-scoped advisory lock on the firm and the template's identity.
_LOCK: Final = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")


async def _lock(session: AsyncSession, tenant_id: UUID, key: str) -> None:
    await session.execute(_LOCK, {"key": f"report_template:{tenant_id}:{key}"})


class AlreadyPublished(DomainConflict):
    """The version is already the template's current version."""

    code = "already_published"


class NotCurrent(DomainConflict):
    """Only the current version can be deprecated."""

    code = "not_current"


class ConsentTermsMissing(DomainConflict):
    """A consent template version without its terms is never published."""

    code = "consent_terms_missing"


class PublisherIsImporter(DomainForbidden):
    """C11 §4: a different person publishes the wording they did not import (four eyes)."""

    code = "publisher_is_importer"


@dataclass(frozen=True)
class ConsentTerms:
    purpose: str
    statement_version: str
    expiry_months: int | None


@dataclass(frozen=True)
class ConsentTermsView:
    purpose: str
    statement_version: str
    counsel_attested_by_user_id: UUID
    counsel_attested_by: str
    counsel_attested_at: datetime
    recipients_source: str
    expiry_months: int | None


@dataclass(frozen=True)
class TemplateBundle:
    """A validated bundle, as JSON-ready values (reporting validates; methodology stores)."""

    family: str
    name: str
    description: str
    layout_key: str
    body: list[object]
    clauses: list[object]
    variables: list[object]
    sample_data: dict[str, object]
    content_sha256: str
    consent: ConsentTerms | None = None


@dataclass(frozen=True)
class ImportedVersion:
    template_id: UUID
    version_id: UUID
    version_no: int
    created: bool


@dataclass(frozen=True)
class Publication:
    action: str
    by_user_id: UUID
    by: str
    at: datetime


@dataclass(frozen=True)
class TemplateVersionView:
    template_id: UUID
    version_id: UUID
    version_no: int
    layout_key: str
    body: list[object]
    clauses: list[object]
    variables: list[object]
    sample_data: dict[str, object]
    content_sha256: str
    imported_by_user_id: UUID
    publications: list[Publication]
    family: str = ""
    consent: ConsentTermsView | None = None


@dataclass(frozen=True)
class TemplateSummary:
    id: UUID
    family: str
    name: str
    description: str
    current_version: int | None
    published_at: datetime | None


@dataclass(frozen=True)
class _Pub:
    version_id: UUID
    action: str
    by_user_id: UUID
    at: datetime


def current_of(publications: Sequence[_Pub]) -> _Pub | None:
    """The latest `published` row whose version has no later `deprecated` row (AC-4)."""
    ordered = sorted(publications, key=lambda p: p.at)
    for i in range(len(ordered) - 1, -1, -1):
        row = ordered[i]
        if row.action != "published":
            continue
        later = ordered[i + 1 :]
        if any(p.action == "deprecated" and p.version_id == row.version_id for p in later):
            continue
        return row
    return None


async def _refused(ctx: AuthContext, object_id: UUID) -> None:
    """A non-human's attempt, recorded in its own unit of work for the person it ran for."""
    tenant = (
        ctx.tenant
        if ctx.tenant.actor_kind == "human"
        else TenantContext(
            ctx.tenant_id,
            "system",
            f"report_templates:refusal:{object_id}",
            on_behalf_of_user_id=ctx.tenant.on_behalf_of_user_id or ctx.user_id,
        )
    )
    async with uow(tenant) as tx:
        tx.record("decision.refused_non_human", target=Target(TEMPLATE, object_id))


async def _human(ctx: AuthContext, action: str, object_id: UUID) -> None:
    """INV-1: a client principal never reaches templates (404); an agent, the system or support
    is refused and audited."""
    if ctx.client:
        raise NotFound(TEMPLATE)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        await _refused(ctx, object_id)
        raise Forbidden(action, "role")


async def _publications(session: AsyncSession, template_id: UUID) -> list[_Pub]:
    rows = await session.execute(
        select(
            ReportTemplatePublication.version_id,
            ReportTemplatePublication.action,
            ReportTemplatePublication.by_user_id,
            ReportTemplatePublication.at,
        )
        .join(
            ReportTemplateVersion, ReportTemplateVersion.id == ReportTemplatePublication.version_id
        )
        .where(ReportTemplateVersion.template_id == template_id)
        .order_by(ReportTemplatePublication.at, ReportTemplatePublication.id)
    )
    return [_Pub(r.version_id, r.action, r.by_user_id, r.at) for r in rows]


async def import_template(
    ctx: AuthContext, bundle: TemplateBundle, *, source: Source = "import"
) -> ImportedVersion:
    """Store `bundle` as the next version of its template (AC-1). Human only."""
    await _human(ctx, IMPORT, ctx.tenant_id)
    await authorise(ctx, IMPORT, Resource.firm(ctx.tenant_id))
    try:
        return await _store(ctx, bundle, source)
    except _Unchanged as unchanged:
        return unchanged.version


class _Unchanged(Exception):
    """The latest version already has this content: leave the unit of work writing nothing (it
    rolls back; a unit of work that commits must audit, P-11-T15 / DEC-1656)."""

    def __init__(self, version: ImportedVersion) -> None:
        super().__init__()
        self.version = version


async def _store(ctx: AuthContext, bundle: TemplateBundle, source: Source) -> ImportedVersion:
    async with uow(ctx.tenant) as tx:
        await _lock(tx.session, ctx.tenant_id, f"{bundle.family}:{bundle.name}")
        template = (
            await tx.session.execute(
                select(ReportTemplate).where(
                    ReportTemplate.family == bundle.family, ReportTemplate.name == bundle.name
                )
            )
        ).scalar_one_or_none()
        if template is None:
            template_id = uuid4()
            await tx.session.execute(
                insert(ReportTemplate).values(
                    id=template_id,
                    tenant_id=ctx.tenant_id,
                    family=bundle.family,
                    name=bundle.name,
                    description=bundle.description,
                    created_by_user_id=ctx.user_id,
                )
            )
            latest: ReportTemplateVersion | None = None
        else:
            template_id = template.id
            latest = (
                await tx.session.execute(
                    select(ReportTemplateVersion)
                    .where(ReportTemplateVersion.template_id == template_id)
                    .order_by(ReportTemplateVersion.version_no.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        if latest is not None and latest.content_sha256 == bundle.content_sha256:
            raise _Unchanged(
                ImportedVersion(template_id, latest.id, latest.version_no, created=False)
            )
        version_no = (latest.version_no if latest is not None else 0) + 1
        version_id = uuid4()
        await tx.session.execute(
            insert(ReportTemplateVersion).values(
                id=version_id,
                tenant_id=ctx.tenant_id,
                template_id=template_id,
                version_no=version_no,
                layout_key=bundle.layout_key,
                body=bundle.body,
                clauses=bundle.clauses,
                variables=bundle.variables,
                sample_data=bundle.sample_data,
                source=source,
                content_sha256=bundle.content_sha256,
                imported_by_user_id=ctx.user_id,
            )
        )
        if bundle.consent is not None:
            await tx.session.execute(
                insert(ReportTemplateConsentTerms).values(
                    id=uuid4(),
                    tenant_id=ctx.tenant_id,
                    template_version_id=version_id,
                    purpose=bundle.consent.purpose,
                    statement_version=bundle.consent.statement_version,
                    counsel_attested_by_user_id=ctx.user_id,
                    expiry_months=bundle.consent.expiry_months,
                )
            )
        tx.record(
            "report_template.imported",
            target=Target(VERSION, version_id),
            after=Ref(
                template=template_id,
                version=version_no,
                content_sha256=bundle.content_sha256,
            ),  # identifiers only (ADR-018); the version row records its source
        )
    return ImportedVersion(template_id, version_id, version_no, created=True)


async def _version(
    session: AsyncSession, template_id: UUID, version_no: int
) -> ReportTemplateVersion:
    found = (
        await session.execute(
            select(ReportTemplateVersion).where(
                ReportTemplateVersion.template_id == template_id,
                ReportTemplateVersion.version_no == version_no,
            )
        )
    ).scalar_one_or_none()
    if found is None:
        raise NotFound(VERSION)
    return found


async def _terms(session: AsyncSession, version_id: UUID) -> ReportTemplateConsentTerms | None:
    return (
        await session.execute(
            select(ReportTemplateConsentTerms).where(
                ReportTemplateConsentTerms.template_version_id == version_id
            )
        )
    ).scalar_one_or_none()


async def _publisher(ctx: AuthContext, template_id: UUID) -> ReportTemplate:
    """The template, after the publisher's action for its family: a partner for a consent
    template (`consent_template.publish`), the template publishers for every other (AC-3)."""
    async with tenant_session(ctx.tenant) as session:
        template = (
            await session.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
        ).scalar_one_or_none()
    if template is None:
        raise NotFound(TEMPLATE)
    action = CONSENT_PUBLISH if template.family == CONSENT_FAMILY else PUBLISH
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    return template


async def publish_version(ctx: AuthContext, template_id: UUID, version_no: int) -> None:
    """Publish (or republish, to roll back) one version (AC-3, AC-4). Human only, fresh second
    factor by the matrix, never the version's importer."""
    await _human(ctx, PUBLISH, template_id)
    template = await _publisher(ctx, template_id)
    async with uow(ctx.tenant) as tx:
        await _lock(tx.session, ctx.tenant_id, str(template_id))
        version = await _version(tx.session, template_id, version_no)
        if version.imported_by_user_id == ctx.user_id:
            raise PublisherIsImporter(facts={"version_id": str(version.id)})
        if template.family == CONSENT_FAMILY and await _terms(tx.session, version.id) is None:
            raise ConsentTermsMissing(facts={"version_id": str(version.id)})
        current = current_of(await _publications(tx.session, template_id))
        if current is not None and current.version_id == version.id:
            raise AlreadyPublished(facts={"version_id": str(version.id)})
        await tx.session.execute(
            insert(ReportTemplatePublication).values(
                id=uuid4(),
                tenant_id=ctx.tenant_id,
                version_id=version.id,
                action="published",
                by_user_id=ctx.user_id,
                mfa_at=ctx.mfa_at,
            )
        )
        tx.record(
            "report_template.published",
            target=Target(VERSION, version.id),
            before=Ref(version=current.version_id) if current is not None else None,
            after=Ref(template=template_id, version=version_no),
        )


async def deprecate_version(ctx: AuthContext, template_id: UUID, version_no: int) -> None:
    """Withdraw the current version (T-01-T17): nothing is current until one is published."""
    await _human(ctx, PUBLISH, template_id)
    await _publisher(ctx, template_id)
    async with uow(ctx.tenant) as tx:
        await _lock(tx.session, ctx.tenant_id, str(template_id))
        version = await _version(tx.session, template_id, version_no)
        current = current_of(await _publications(tx.session, template_id))
        if current is None or current.version_id != version.id:
            raise NotCurrent(facts={"version_id": str(version.id)})
        await tx.session.execute(
            insert(ReportTemplatePublication).values(
                id=uuid4(),
                tenant_id=ctx.tenant_id,
                version_id=version.id,
                action="deprecated",
                by_user_id=ctx.user_id,
                mfa_at=ctx.mfa_at,
            )
        )
        tx.record(
            "report_template.deprecated",
            target=Target(VERSION, version.id),
            after=Ref(template=template_id, version=version_no),
        )


async def _names(user_ids: set[UUID]) -> Mapping[UUID, str]:
    return await names_of(sorted(user_ids)) if user_ids else {}


async def version_view(
    ctx: AuthContext, template_id: UUID, version_no: int
) -> TemplateVersionView:
    if ctx.client:
        raise NotFound(TEMPLATE)
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        version = await _version(session, template_id, version_no)
        pubs = [p for p in await _publications(session, template_id) if p.version_id == version.id]
        family = (
            await session.execute(
                select(ReportTemplate.family).where(ReportTemplate.id == template_id)
            )
        ).scalar_one()
        terms = await _terms(session, version.id)
    people = {p.by_user_id for p in pubs}
    if terms is not None:
        people.add(terms.counsel_attested_by_user_id)
    names = await _names(people)
    return TemplateVersionView(
        template_id=template_id,
        version_id=version.id,
        version_no=version.version_no,
        layout_key=version.layout_key,
        body=version.body,
        clauses=version.clauses,
        variables=version.variables,
        sample_data=version.sample_data,
        content_sha256=version.content_sha256,
        imported_by_user_id=version.imported_by_user_id,
        publications=[
            Publication(p.action, p.by_user_id, names.get(p.by_user_id, ""), p.at) for p in pubs
        ],
        family=family,
        consent=None
        if terms is None
        else ConsentTermsView(
            purpose=terms.purpose,
            statement_version=terms.statement_version,
            counsel_attested_by_user_id=terms.counsel_attested_by_user_id,
            counsel_attested_by=names.get(terms.counsel_attested_by_user_id, ""),
            counsel_attested_at=terms.counsel_attested_at,
            recipients_source=terms.recipients_source,
            expiry_months=terms.expiry_months,
        ),
    )


async def templates(ctx: AuthContext, family: str | None) -> list[TemplateSummary]:
    """The firm's templates, each with its current published version (C11 §1)."""
    if ctx.client:
        raise NotFound(TEMPLATE)
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        query = select(ReportTemplate).order_by(ReportTemplate.family, ReportTemplate.name)
        if family is not None:
            query = query.where(ReportTemplate.family == family)
        found = list((await session.execute(query)).scalars())
        numbers = {
            r.id: r.version_no
            for r in await session.execute(
                select(ReportTemplateVersion.id, ReportTemplateVersion.version_no).where(
                    ReportTemplateVersion.template_id.in_([t.id for t in found])
                )
            )
        }
        out: list[TemplateSummary] = []
        for t in found:
            current = current_of(await _publications(session, t.id))
            out.append(
                TemplateSummary(
                    id=t.id,
                    family=t.family,
                    name=t.name,
                    description=t.description,
                    current_version=numbers.get(current.version_id) if current else None,
                    published_at=current.at if current else None,
                )
            )
    return out


async def current_version_id(tenant: TenantContext, template_id: UUID) -> UUID | None:
    """For the renderer (P-11-T08): the version a new draft renders from, or None."""
    async with tenant_session(tenant) as session:
        current = current_of(await _publications(session, template_id))
    return current.version_id if current is not None else None


async def version_variable_keys(session: AsyncSession, version_id: UUID) -> tuple[str, ...] | None:
    """For the renderer (P-11-T08), in the caller's unit of work: the variable keys a template
    version declares, in its order; None when the version is not this firm's (RLS). The renderer
    resolves only these (a whitelist)."""
    row = await session.get(ReportTemplateVersion, version_id)
    if row is None:
        return None
    keys: list[str] = []
    for item in row.variables:
        if isinstance(item, dict):
            key = cast(dict[str, object], item).get("key")
            if isinstance(key, str):
                keys.append(key)
    return tuple(keys)


@dataclass(frozen=True)
class TemplateParts:
    """A template version's parts, for a consumer composing from it (N-02-T32's letter)."""

    version_id: UUID
    layout_key: str
    body: list[object]
    clauses: list[object]
    variable_keys: tuple[str, ...]
    # N-02-T34: what ENG-04's structure pane names ("BH Tax Advisory Letter v4") and the labels.
    template_name: str = ""
    version_no: int = 0
    variables: tuple[object, ...] = ()


async def version_parts(session: AsyncSession, version_id: UUID) -> TemplateParts | None:
    """In the caller's unit of work: the version's layout, body, clause library and declared
    keys; None when the version is not this firm's (RLS)."""
    row = await session.get(ReportTemplateVersion, version_id)
    if row is None:
        return None
    keys = await version_variable_keys(session, version_id) or ()
    name = await session.scalar(
        select(ReportTemplate.name).where(ReportTemplate.id == row.template_id)
    )
    return TemplateParts(
        row.id,
        row.layout_key,
        list(row.body),
        list(row.clauses),
        keys,
        template_name=name or "",
        version_no=row.version_no,
        variables=tuple(row.variables),
    )


# --- T-01-T10: what consent capture reads -------------------------------------------------------


@dataclass(frozen=True)
class PublishedConsentTemplate:
    template_id: UUID
    name: str
    version: TemplateVersionView


async def published_consent_template(
    ctx: AuthContext, purpose: str
) -> PublishedConsentTemplate | None:
    """The firm's current published `consent_7216` template for `purpose`, or None (T-01-T10).
    Two templates for one purpose: the most recently published wins."""
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                select(ReportTemplate.id, ReportTemplate.name, ReportTemplateVersion.version_no)
                .join(
                    ReportTemplateVersion, ReportTemplateVersion.template_id == ReportTemplate.id
                )
                .join(
                    ReportTemplateConsentTerms,
                    ReportTemplateConsentTerms.template_version_id == ReportTemplateVersion.id,
                )
                .where(
                    ReportTemplate.family == CONSENT_FAMILY,
                    ReportTemplateConsentTerms.purpose == purpose,
                )
            )
        ).all()
        best: tuple[datetime, UUID, str, UUID] | None = None
        numbers = {(r.id, r.version_no) for r in rows}
        for template_id in {r.id for r in rows}:
            current = current_of(await _publications(session, template_id))
            if current is None:
                continue
            candidate = (current.at, template_id, "", current.version_id)
            if best is None or candidate[0] > best[0]:
                name = next(r.name for r in rows if r.id == template_id)
                best = (current.at, template_id, name, current.version_id)
        if best is None:
            return None
        version_no = (
            await session.execute(
                select(ReportTemplateVersion.version_no).where(ReportTemplateVersion.id == best[3])
            )
        ).scalar_one()
    if (best[1], version_no) not in numbers:
        return None  # the current version carries no terms for this purpose
    view = await version_view(ctx, best[1], version_no)
    return PublishedConsentTemplate(best[1], best[2], view)


async def consent_expiry_months(
    tenant: TenantContext, version_ids: list[UUID]
) -> dict[UUID, int | None]:
    """Each consent template version's stated expiry in months (C-17), for the signing consumer."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(
                ReportTemplateConsentTerms.template_version_id,
                ReportTemplateConsentTerms.expiry_months,
            ).where(ReportTemplateConsentTerms.template_version_id.in_(version_ids))
        )
        return {r.template_version_id: r.expiry_months for r in rows}
