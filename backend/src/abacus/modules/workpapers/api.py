"""Public interface of the workpapers module; other modules import only this (ADR-008).

Working papers (A-04; SPEC-308): the grid, formulas, citations and sign-offs.
"""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.agents.api import register_section_source, register_suggestion_applier
from abacus.modules.evidence.api import register_citable
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.review.api import (
    register_field_owner,
    register_reviewable,
    register_reviewable_facts,
)
from abacus.modules.workpapers.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.workpapers.contract import router as a04_router
from abacus.modules.workpapers.core import (
    CELL_OWNER,
    CELL_TARGET,
    cell_facts,
    display_workpaper_cell,
    verify_workpaper_cell,
)
from abacus.modules.workpapers.designed import PaperFact, work_item_papers
from abacus.modules.workpapers.drafting import (
    SOURCE as SECTION_SOURCE,
)
from abacus.modules.workpapers.drafting import (
    apply_cell_suggestion,
    draft_paper,
    paper_engagement,
)
from abacus.modules.workpapers.layouts import (
    AddressInvalid,
    DesignedLayout,
    SheetLayout,
    designed_layout,
    register_designed_layout,
    resolve,
)
from abacus.modules.workpapers.procedures import (
    WORKPAPER_KINDS,
    PackConfigurationError,
    PackError,
    bound_steps,
    pack_errors,
    validate_pack,
)
from abacus.modules.workpapers.routes import checks_router, router
from abacus.modules.workpapers.service import (
    CodeTaken,
    NoAssuranceItem,
    WorkpaperInvalid,
    workpaper_facts,
    workpaper_reviewables,
)
from abacus.modules.workpapers.tb_fields import OWNER as TB_FIELD_OWNER
from abacus.modules.workpapers.tie_out import (
    IssueLink,
    checks_for,
    link_issue,
    tie_digests,
)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    checks_router,
    a04_router,  # A-04-T01 workpaper core stub (docs/contracts/workpapers-core.md)
)

# SPEC-313 (TASK-331): papers appear in the sign-off matrix and count toward G5.
register_reviewable("workpaper", workpaper_reviewables)
# P-04-T14: one paper's facts (content hash, version, preparers) for the sign-off rules.
register_reviewable_facts("workpaper", workpaper_facts)
# A-02-T17 (C3): the trial balance's annotated fields (`wp_ref`, `area_override` per line). The
# trial balance itself is registered as a reviewable by assurance (SPEC-313).
register_field_owner(TB_FIELD_OWNER)
# A-04-T04 (DEC-1762): a cell's field history (SHL-09) and its C4 citable kind.
register_field_owner(CELL_OWNER)
register_reviewable_facts(CELL_TARGET, cell_facts)
register_citable("workpaper_cell", verify_workpaper_cell, display_workpaper_cell)
# A-04-T11 (DEC-1868): the section drafter reads papers through this source, and a person's
# adoption of its `workpaper_cell` suggestion lands through this applier.
register_section_source(SECTION_SOURCE)
register_suggestion_applier(CELL_TARGET, apply_cell_suggestion, engagement_of=paper_engagement)

__all__ = [
    "CELL_TARGET",
    "ROUTERS",
    "WORKPAPER_KINDS",
    "AddressInvalid",
    "CodeTaken",
    "DesignedLayout",
    "IssueLink",
    "NoAssuranceItem",
    "PackConfigurationError",
    "PackError",
    "PaperFact",
    "SheetLayout",
    "WorkpaperInvalid",
    "apply_cell_suggestion",
    "bound_steps",
    "checks_for",
    "checks_router",
    "designed_layout",
    "draft_paper",
    "link_issue",
    "pack_errors",
    "paper_engagement",
    "register_designed_layout",
    "resolve",
    "router",
    "tie_digests",
    "validate_pack",
    "work_item_papers",
]
