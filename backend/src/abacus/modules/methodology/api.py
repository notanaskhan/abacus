"""Public interface of the methodology module; other modules import only this (ADR-008).

K-01-T02 re-owned SPEC-008's templates and versions from engagements: the workbook import, the
reads, drafted-guidance publishing and the version lifecycle. `methodology` imports only
`identity` and `platform`.
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

# The routers the API mounts, in order (P-39; F-03-T07). K-01-T01's stubs follow the live
# SPEC-008 routes.
ROUTERS: tuple[AbacusRouter, ...] = (
    methodology_router,
    methodology_lifecycle_router,
    programs_router,
    knowledge_router,
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
    "Effort",
    "EngagementType",
    "Methodology",
    "MethodologyVersionView",
    "Problem",
    "ReviewItem",
    "TemplateInvalid",
    "TemplateItem",
    "TemplateNameInvalid",
    "TemplateVersionSummary",
    "Tier",
    "UsageCounter",
    "VersionNotLatest",
    "Viewer",
    "area_for",
    "import_template",
    "latest_versions",
    "methodology_router",
    "methodology_templates",
    "methodology_version",
    "parse_workbook",
    "publish_drafted_version",
    "register_catalog_provider",
    "register_usage_counter",
    "templates_in_firm",
    "version_detail",
    "version_in",
]
