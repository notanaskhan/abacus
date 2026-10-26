"""Public interface of the methodology module; other modules import only this (ADR-008).

K-01-T02 re-owned SPEC-008's templates and versions from engagements: the workbook import, the
reads, drafted-guidance publishing and the version lifecycle. `methodology` imports only
`identity` and `platform`.
"""

from abacus.modules.identity.api import AbacusRouter
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

# The routers the API mounts, in order (P-39; F-03-T07). K-01-T01's stubs follow the live
# SPEC-008 routes.
ROUTERS: tuple[AbacusRouter, ...] = (
    methodology_router,
    methodology_lifecycle_router,
    programs_router,
    knowledge_router,
)

__all__ = [
    "ROUTERS",
    "AccountRule",
    "ApprovedGuidance",
    "Area",
    "Effort",
    "EngagementType",
    "Methodology",
    "MethodologyVersionView",
    "Problem",
    "TemplateInvalid",
    "TemplateItem",
    "TemplateNameInvalid",
    "TemplateVersionSummary",
    "Tier",
    "VersionNotLatest",
    "area_for",
    "import_template",
    "latest_versions",
    "methodology_router",
    "methodology_templates",
    "methodology_version",
    "parse_workbook",
    "publish_drafted_version",
    "templates_in_firm",
    "version_detail",
    "version_in",
]
