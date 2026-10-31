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
    current_version,
    current_version_of_kind,
    policy_payload,
    register_standard_examples,
)
from abacus.modules.methodology.standards_catalog import register_standards_providers
from abacus.modules.methodology.standards_contract import (
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
)

__all__ = [
    "METHODOLOGY_USAGE_TYPE",
    "ROUTERS",
    "AccountRule",
    "ApprovedGuidance",
    "Area",
    "CatalogItem",
    "CatalogProvider",
    "ChangeEntry",
    "CitedStep",
    "ConfidenceDecision",
    "Effort",
    "EngagementType",
    "EntryClassification",
    "ExampleRow",
    "ExamplesProvider",
    "ImportedReportTemplateVersion",
    "MaterialityCheck",
    "MaterialityRangeFor",
    "Methodology",
    "MethodologyVersionView",
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
    "classify_entry",
    "confidence_hold",
    "consent_expiry_months",
    "current_report_template_version",
    "current_version",
    "current_version_of_kind",
    "deprecate_report_template",
    "import_report_template",
    "import_template",
    "latest_versions",
    "materiality_range_for",
    "methodology_router",
    "methodology_templates",
    "methodology_version",
    "parse_workbook",
    "policy_payload",
    "publish_drafted_version",
    "publish_report_template",
    "published_consent_template",
    "register_catalog_provider",
    "register_standard_examples",
    "register_usage_counter",
    "report_template_parts",
    "report_template_variable_keys",
    "report_template_version",
    "report_templates_in_firm",
    "required_review_levels",
    "return_approval_policy",
    "ssars_framework_for",
    "step_at",
    "submit_version",
    "templates_in_firm",
    "validate_materiality",
    "variance_exceeded",
    "version_detail",
    "version_effective_on",
    "version_in",
    "version_state",
]
