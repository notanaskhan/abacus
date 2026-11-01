"""Methodology records (SPEC-008; K-01-T02 re-owned them from engagements, ADR-140): templates,
their insert-only versions with areas, request items and account rules, and the version
lifecycle (`methodology_version_states`, mutable under guarded transitions) with its insert-only
events. Classification: titles, item text and guidance are internal (ADR-031)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ARRAY, FetchedValue, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class MethodologyTemplate(Base):
    __tablename__ = "methodology_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    name: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime]
    # SPEC-024: the engagement types it serves, fixed when the template is created.
    engagement_types: Mapped[list[str]] = mapped_column(ARRAY(String))
    family: Mapped[str | None]  # K-01-T02 (0180): `ebp`, `fs` or `ssars`


class MethodologyVersion(Base):
    __tablename__ = "methodology_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    template_id: Mapped[UUID]
    version: Mapped[int]
    source_fingerprint: Mapped[str]
    imported_by: Mapped[UUID]
    created_at: Mapped[datetime]
    # K-01-T02 (0180): set on insert.
    label: Mapped[str]
    drafted_from_version_id: Mapped[UUID | None]
    origin: Mapped[str] = mapped_column(server_default=FetchedValue())


class MethodologyArea(Base):
    __tablename__ = "methodology_areas"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    position: Mapped[int]


class MethodologyRequestItem(Base):
    __tablename__ = "methodology_request_items"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    area_code: Mapped[str]
    description: Mapped[str]
    retrievability_tier: Mapped[str]
    # SPEC-031 (TASK-060): guidance carried to engagements.
    why: Mapped[str | None]
    good_looks_like: Mapped[str | None]
    blocks_fieldwork: Mapped[bool] = mapped_column(server_default=FetchedValue())
    effort: Mapped[str | None]
    # SPEC-035 Q3 (TASK-074): approved drafted guidance and who approved it.
    guidance_source: Mapped[str | None]
    guidance_approved_by: Mapped[UUID | None]


class MethodologyAccountRule(Base):
    __tablename__ = "methodology_account_rules"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    area_code: Mapped[str]
    account_from: Mapped[str]
    account_to: Mapped[str]


class MethodologyVersionState(Base):
    """A version's lifecycle (K-01-T02, migration 0180): the one mutable methodology row, changed
    only by guarded transitions. Legacy versions read `published` with `legacy_import`."""

    __tablename__ = "methodology_version_states"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    template_id: Mapped[UUID]
    status: Mapped[str]
    effective_from: Mapped[date | None]
    effective_to: Mapped[date | None]
    approved_by: Mapped[UUID | None]
    approved_at: Mapped[datetime | None]
    approved_actor_kind: Mapped[str | None]
    approval_basis: Mapped[str | None]
    standards_set_id: Mapped[UUID | None]
    quality_management_ref: Mapped[str | None]
    engagement_types: Mapped[list[str]] = mapped_column(ARRAY(String))
    default_for_new_engagements: Mapped[bool]
    row_version: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class MethodologyVersionEvent(Base):
    """What happened to a version (K-01-T02): insert-only, identifiers and codes in `facts`."""

    __tablename__ = "methodology_version_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    seq: Mapped[int] = mapped_column(server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    version_id: Mapped[UUID]
    kind: Mapped[str]
    actor_user_id: Mapped[UUID | None]
    actor_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    on_behalf_of_user_id: Mapped[UUID | None]
    at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    facts: Mapped[dict[str, object]] = mapped_column(JSONB, server_default=FetchedValue())


class Program(Base):
    """A version's program (K-01-T05, migration 0224): frozen once the version is published."""

    __tablename__ = "programs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    version_id: Mapped[UUID]
    code: Mapped[str]
    name: Mapped[str]
    position: Mapped[int]
    publisher_program_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ProgramStep(Base):
    """A program's numbered step with its stable lineage key (K-01-T05, migration 0224)."""

    __tablename__ = "program_steps"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    version_id: Mapped[UUID]
    program_id: Mapped[UUID]
    step_key: Mapped[str]
    number: Mapped[int]
    text: Mapped[str]
    assertions: Mapped[list[str]] = mapped_column(ARRAY(String))
    standard_refs: Mapped[list[str]] = mapped_column(ARRAY(String))
    level: Mapped[str]
    mandatory: Mapped[bool]
    lock_note: Mapped[str | None]
    # SQL NULL for None (the column refuses a JSON null; K-01-T14 copies steps in bulk).
    guidance: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB(none_as_null=True))
    prepopulates: Mapped[list[str]] = mapped_column(ARRAY(String))
    depends_on_step_keys: Mapped[list[str]] = mapped_column(ARRAY(String))
    publisher_step_id: Mapped[UUID | None]
    origin: Mapped[str]
    proposed_by_run_id: Mapped[UUID | None]
    # K-01-T21: the importer's confidence in the step's boundaries (0224's column).
    parse_confidence: Mapped[Decimal | None]
    parse_flag: Mapped[str | None]
    flag_resolution: Mapped[str | None]
    # K-01-T18: who resolved the parse flag, and when (0224's columns).
    flag_resolved_by: Mapped[UUID | None]
    flag_resolved_at: Mapped[datetime | None]
    # K-01-T05 (0224): who last edited a draft step, and when (K-01-T14 writes them).
    edited_by: Mapped[UUID | None]
    edited_at: Mapped[datetime | None]
    row_version: Mapped[int] = mapped_column(server_default=FetchedValue())
    # A-04-T07 (0614): the request and workpaper templates the step points at (pack validation).
    template_refs: Mapped[list[str]] = mapped_column(ARRAY(String), server_default=FetchedValue())


class MethodologyImport(Base):
    """K-01-T18 (0580): one upload of a firm's methodology files, to a version in review."""

    __tablename__ = "methodology_imports"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    template_id: Mapped[UUID]
    version_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    started_by: Mapped[UUID]
    started_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    agent_run_id: Mapped[UUID | None]
    pages_done: Mapped[int] = mapped_column(server_default=FetchedValue())
    pages_total: Mapped[int | None]
    failure_code: Mapped[str | None]
    idempotency_key: Mapped[str]


class MethodologySourceFile(Base):
    """K-01-T18 (0580), insert-only: a stored, scanned source file. `storage_key` and
    `storage_version_id` are never serialised."""

    __tablename__ = "methodology_source_files"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    import_id: Mapped[UUID]
    version_id: Mapped[UUID | None]
    role: Mapped[str]
    rendition_of_file_id: Mapped[UUID | None]
    filename: Mapped[str]
    media_type: Mapped[str]
    storage_key: Mapped[str]
    storage_version_id: Mapped[str]
    sha256: Mapped[str]
    bytes: Mapped[int]
    page_count: Mapped[int | None]
    sheet_count: Mapped[int | None]
    scan_status: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class MethodologySourcePage(Base):
    """K-01-T18 (0580), insert-only: a document page's size and word boxes (K-01-T20 fills)."""

    __tablename__ = "methodology_source_pages"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    file_id: Mapped[UUID] = mapped_column(primary_key=True)
    page: Mapped[int] = mapped_column(primary_key=True)
    width: Mapped[float]
    height: Mapped[float]
    words: Mapped[list[object]] = mapped_column(JSONB)


class ProgramStepSource(Base):
    """K-01-T18 (0580), insert-only: where a step came from and whether code verified its quote."""

    __tablename__ = "program_step_sources"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    step_id: Mapped[UUID] = mapped_column(primary_key=True)
    source_file_id: Mapped[UUID] = mapped_column(primary_key=True)
    page_from: Mapped[int] = mapped_column(primary_key=True)
    page_to: Mapped[int]
    bbox: Mapped[list[object] | None] = mapped_column(JSONB)
    quote: Mapped[str | None]
    verified: Mapped[bool]
    verify_reason: Mapped[str | None]
    verified_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ProgramStepPbcLink(Base):
    """A step's link to one of the version's PBC request items (insert-only)."""

    __tablename__ = "program_step_pbc_links"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    step_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_position: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[UUID]


# --- K-02-T04 (0401): firm standards and threshold policies, one pair of tables per family ------


class _StandardParent:
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    kind: Mapped[str]
    key: Mapped[str]
    name: Mapped[str]
    owner_id: Mapped[UUID]
    applies_to: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    row_version: Mapped[int] = mapped_column(server_default=FetchedValue())


class _StandardVersion:
    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    parent_id: Mapped[UUID]
    version: Mapped[int]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    # Set only by publish (an UPDATE); the app role may not insert them (0401's column grants),
    # so a draft's INSERT must leave them out.
    effective_from: Mapped[date | None] = mapped_column(server_default=FetchedValue())
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    payload_schema_version: Mapped[int] = mapped_column(server_default=FetchedValue())
    payload_hash: Mapped[str]
    change_summary: Mapped[str | None]
    drafted_from_version_id: Mapped[UUID | None]
    drafted_by: Mapped[UUID]
    drafted_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    published_by: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    published_actor_kind: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    published_at: Mapped[datetime | None] = mapped_column(server_default=FetchedValue())
    row_version: Mapped[int] = mapped_column(server_default=FetchedValue())


class FirmStandard(_StandardParent, Base):
    __tablename__ = "firm_standards"


class FirmStandardVersion(_StandardVersion, Base):
    __tablename__ = "firm_standard_versions"


class ThresholdPolicy(_StandardParent, Base):
    __tablename__ = "threshold_policies"


class ThresholdPolicyVersion(_StandardVersion, Base):
    __tablename__ = "threshold_policy_versions"


# --- P-11-T06 (0460): report templates, firm content for C11 -----------------------------------


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    family: Mapped[str]
    name: Mapped[str]
    description: Mapped[str]
    created_by_user_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ReportTemplateVersion(Base):
    __tablename__ = "report_template_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    template_id: Mapped[UUID]
    version_no: Mapped[int]
    layout_key: Mapped[str]
    body: Mapped[list[object]] = mapped_column(JSONB)
    clauses: Mapped[list[object]] = mapped_column(JSONB)
    variables: Mapped[list[object]] = mapped_column(JSONB)
    sample_data: Mapped[dict[str, object]] = mapped_column(JSONB)
    source: Mapped[str]
    content_sha256: Mapped[str]
    imported_by_user_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ReportTemplatePublication(Base):
    __tablename__ = "report_template_publications"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    version_id: Mapped[UUID]
    action: Mapped[str]
    by_user_id: Mapped[UUID]
    mfa_at: Mapped[datetime | None]
    at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ReportTemplateConsentTerms(Base):
    """T-01-T17 (0461): a `consent_7216` version's terms; recipients come from the register."""

    __tablename__ = "report_template_consent_terms"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    template_version_id: Mapped[UUID]
    purpose: Mapped[str]
    statement_version: Mapped[str]
    counsel_attested_by_user_id: Mapped[UUID]
    counsel_attested_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    recipients_source: Mapped[str] = mapped_column(server_default=FetchedValue())
    expiry_months: Mapped[int | None]
