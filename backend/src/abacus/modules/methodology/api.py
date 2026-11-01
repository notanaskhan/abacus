"""Public interface of the methodology module; other modules import only this (ADR-008).

K-01-T02 re-owned SPEC-008's templates and versions from engagements: the workbook import, the
reads, drafted-guidance publishing and the version lifecycle. K-02-T08: C21 part B, firm
standards and threshold policies (`standards.py`); the deterministic functions stay stubs until
K-02-T10.
`methodology` imports only `identity` and `platform`.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.methodology.catalog import (
    CatalogItem,
    CatalogProvider,
    ChangeEntry,
    ReviewItem,
    UsageCounter,
    Viewer,
    register_catalog_provider,
    register_usage_counter,
)
from abacus.modules.methodology.catalog_provider import (
    USAGE_TYPE as METHODOLOGY_USAGE_TYPE,
)
from abacus.modules.methodology.catalog_provider import register_methodology_providers
from abacus.modules.methodology.contract import (
    knowledge_router,
    methodology_lifecycle_router,
    programs_router,
)
from abacus.modules.methodology.document_import import (
    DocumentImporter,
    ImportedVersion,
    ImportNotParsing,
    ImportSource,
    ParsedProgram,
    ParsedStep,
    assign_flags,
    fail_document_import,
    finish_document_import,
    import_source,
    import_status,
    ordered,
    record_progress,
    register_document_importer,
    store_pages,
    stored_pages,
    verify_quote,
)
from abacus.modules.methodology.extraction import (
    ExtractedSource,
    PiiHold,
    SourceEncrypted,
    SourceMalformed,
    SourceTooLong,
    extract_source,
    pii_hold,
)
from abacus.modules.methodology.import_routes import methodology_import_router
from abacus.modules.methodology.lifecycle import (
    approve_version,
    submit_version,
    version_effective_on,
    version_state,
)
from abacus.modules.methodology.programs import CitedStep, step_at
from abacus.modules.methodology.report_templates import (
    ConsentTerms as ReportTemplateConsentTerms,
)
from abacus.modules.methodology.report_templates import (
    ImportedVersion as ImportedReportTemplateVersion,
)
from abacus.modules.methodology.report_templates import (
    Publication as ReportTemplatePublicationView,
)
from abacus.modules.methodology.report_templates import (
    PublishedConsentTemplate,
    consent_expiry_months,
    published_consent_template,
)
from abacus.modules.methodology.report_templates import TemplateBundle as ReportTemplateBundle
from abacus.modules.methodology.report_templates import (
    TemplateParts as ReportTemplateParts,
)
from abacus.modules.methodology.report_templates import TemplateSummary as ReportTemplateSummary
from abacus.modules.methodology.report_templates import (
    TemplateVersionView as ReportTemplateVersionView,
)
from abacus.modules.methodology.report_templates import (
    current_version_id as current_report_template_version,
)
from abacus.modules.methodology.report_templates import (
    deprecate_version as deprecate_report_template,
)
from abacus.modules.methodology.report_templates import (
    import_template as import_report_template,
)
from abacus.modules.methodology.report_templates import (
    publish_version as publish_report_template,
)
from abacus.modules.methodology.report_templates import templates as report_templates_in_firm
from abacus.modules.methodology.report_templates import (
    version_parts as report_template_parts,
)
from abacus.modules.methodology.report_templates import (
    version_variable_keys as report_template_variable_keys,
)
from abacus.modules.methodology.report_templates import (
    version_view as report_template_version,
)
from abacus.modules.methodology.routes import methodology_router
from abacus.modules.methodology.service import (
    ApprovedGuidance,
    EngagementType,
    MethodologyVersionView,
    TemplateNameInvalid,
    TemplateVersionSummary,
    VersionNotLatest,
    import_template,
    latest_versions,
    methodology_templates,
    methodology_version,
    publish_drafted_version,
    templates_in_firm,
    version_detail,
    version_in,
)
from abacus.modules.methodology.standards import (
    attribute_sample_size,
    current_version,
    current_version_of_kind,
    policy_payload,
    register_standard_examples,
)
from abacus.modules.methodology.standards_catalog import register_standards_providers
from abacus.modules.methodology.standards_contract import (
    AttributeSampleSizesPayload,
    AttributeSize,
    ConfidenceDecision,
    EntryClassification,
    ExampleRow,
    ExamplesProvider,
    MaterialityCheck,
    MaterialityRangeFor,
    PolicyRef,
    RequiredLevels,
    ReturnApproval,
    ReturnApprovalPolicyPayload,
    SsarsFramework,
    StandardKind,
    VarianceResult,
    classify_entry,
    confidence_hold,
    materiality_range_for,
    required_review_levels,
    return_approval_policy,
    ssars_framework_for,
    validate_materiality,
    variance_exceeded,
)
from abacus.modules.methodology.standards_loading import (
    create_standard,
    import_standard_workbook,
    publish_standard,
    standard_by_key,
    standard_workbook,
)
from abacus.modules.methodology.standards_routes import standards_router
from abacus.modules.methodology.workbook import (
    AccountRule,
    Area,
    Effort,
    Methodology,
    Problem,
    TemplateInvalid,
    TemplateItem,
    Tier,
    area_for,
    parse_workbook,
)

# K-01-T03: methodology's own catalog categories (methodology versions, PBC templates).
register_methodology_providers()
# K-02-T08: firm standards on KNW-01 and in search (C15, metadata only).
register_standards_providers()

# The routers the API mounts, in order (P-39; F-03-T07). K-01-T01's stubs follow the live
# SPEC-008 routes.
ROUTERS: tuple[AbacusRouter, ...] = (
    methodology_router,
    methodology_lifecycle_router,
    programs_router,
    knowledge_router,
    standards_router,  # C21 part B (K-02-T08; import and export K-02-T11)
    methodology_import_router,  # K-01-T18: import review (KNW-02 c, d)
)

__all__ = [
    "METHODOLOGY_USAGE_TYPE",
    "ROUTERS",
    "AccountRule",
    "ApprovedGuidance",
    "Area",
    "AttributeSampleSizesPayload",
    "AttributeSize",
    "CatalogItem",
    "CatalogProvider",
    "ChangeEntry",
    "CitedStep",
    "ConfidenceDecision",
    "DocumentImporter",
    "Effort",
    "EngagementType",
    "EntryClassification",
    "ExampleRow",
    "ExamplesProvider",
    "ExtractedSource",
    "ImportNotParsing",
    "ImportSource",
    "ImportedReportTemplateVersion",
    "ImportedVersion",
    "MaterialityCheck",
    "MaterialityRangeFor",
    "Methodology",
    "MethodologyVersionView",
    "ParsedProgram",
    "ParsedStep",
    "PiiHold",
    "PolicyRef",
    "Problem",
    "PublishedConsentTemplate",
    "ReportTemplateBundle",
    "ReportTemplateConsentTerms",
    "ReportTemplateParts",
    "ReportTemplatePublicationView",
    "ReportTemplateSummary",
    "ReportTemplateVersionView",
    "RequiredLevels",
    "ReturnApproval",
    "ReturnApprovalPolicyPayload",
    "ReviewItem",
    "SourceEncrypted",
    "SourceMalformed",
    "SourceTooLong",
    "SsarsFramework",
    "StandardKind",
    "TemplateInvalid",
    "TemplateItem",
    "TemplateNameInvalid",
    "TemplateVersionSummary",
    "Tier",
    "UsageCounter",
    "VarianceResult",
    "VersionNotLatest",
    "Viewer",
    "approve_version",
    "area_for",
    "assign_flags",
    "attribute_sample_size",
    "classify_entry",
    "confidence_hold",
    "consent_expiry_months",
    "create_standard",
    "current_report_template_version",
    "current_version",
    "current_version_of_kind",
    "deprecate_report_template",
    "extract_source",
    "fail_document_import",
    "finish_document_import",
    "import_report_template",
    "import_source",
    "import_standard_workbook",
    "import_status",
    "import_template",
    "latest_versions",
    "materiality_range_for",
    "methodology_router",
    "methodology_templates",
    "methodology_version",
    "ordered",
    "parse_workbook",
    "pii_hold",
    "policy_payload",
    "publish_drafted_version",
    "publish_report_template",
    "publish_standard",
    "published_consent_template",
    "record_progress",
    "register_catalog_provider",
    "register_document_importer",
    "register_standard_examples",
    "register_usage_counter",
    "report_template_parts",
    "report_template_variable_keys",
    "report_template_version",
    "report_templates_in_firm",
    "required_review_levels",
    "return_approval_policy",
    "ssars_framework_for",
    "standard_by_key",
    "standard_workbook",
    "step_at",
    "store_pages",
    "stored_pages",
    "submit_version",
    "templates_in_firm",
    "validate_materiality",
    "variance_exceeded",
    "verify_quote",
    "version_detail",
    "version_effective_on",
    "version_in",
    "version_state",
]
