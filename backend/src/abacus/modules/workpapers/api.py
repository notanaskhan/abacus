"""Public interface of the workpapers module; other modules import only this (ADR-008).

Working papers (A-04; SPEC-308): the grid, formulas, citations and sign-offs.
"""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.agents.api import register_section_source, register_suggestion_applier
from abacus.modules.collaboration.api import register_anchor
from abacus.modules.evidence.api import register_citable
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.review.api import (
    register_field_owner,
    register_reviewable,
    register_reviewable_facts,
)
from abacus.modules.workpapers.anchors import KIND as WORKPAPER_KIND
from abacus.modules.workpapers.anchors import WORKPAPER_ANCHORS
from abacus.modules.workpapers.attribute_grid import TARGET as ATTRIBUTE_TEST
from abacus.modules.workpapers.attribute_grid import (
    Attribute,
    ExceptionPrefill,
    Grid,
    create_test,
    exception_prefill,
    grid,
    latest_test_of_variant,
    mark,
    record_agent_result,
    test_facts,
    test_reviewables,
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
    latest_version_id,
    paper_engagement,
    paper_id_of_kind,
    paper_of_kind,
)
from abacus.modules.workpapers.guards import register_sign_off_guard
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
    create_workpaper,
    matrix_sections,
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

# P-05-T09: a paper's sheets, rows and cells carry comment threads and to-dos (AUD-09).
register_anchor(WORKPAPER_KIND, WORKPAPER_ANCHORS)
# SPEC-313 (TASK-331): papers appear in the sign-off matrix and count toward G5.
register_reviewable("workpaper", workpaper_reviewables)
# A-05-T22 (DEC-2212): an attribute test is adopted by its C3 sign-off (SHL-12).
register_reviewable(ATTRIBUTE_TEST, test_reviewables)
register_reviewable_facts(ATTRIBUTE_TEST, test_facts)
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

# T-05-T27 (DEC-4519): the closed formula grammar (ADR-237), for the tax workbook's write path.
# T-05-T35 (DEC-4620): the workbook DAG (ADR-237 §3), for the tax workbook's bounded recompute.
from abacus.modules.workpapers.compute.dag import CellInput as FormulaCellInput  # noqa: E402
from abacus.modules.workpapers.compute.dag import CycleError as FormulaCycleError  # noqa: E402
from abacus.modules.workpapers.compute.dag import Workbook as FormulaWorkbook  # noqa: E402
from abacus.modules.workpapers.compute.dag import build_graph as build_formula_graph  # noqa: E402
from abacus.modules.workpapers.compute.dag import canonical as canonical_address  # noqa: E402
from abacus.modules.workpapers.compute.dag import dirty as dirty_cells  # noqa: E402
from abacus.modules.workpapers.compute.dag import evaluate as evaluate_workbook  # noqa: E402
from abacus.modules.workpapers.compute.dag import recompute as recompute_workbook  # noqa: E402
from abacus.modules.workpapers.compute.formula import FormulaError  # noqa: E402
from abacus.modules.workpapers.compute.formula import parse as parse_formula  # noqa: E402
from abacus.modules.workpapers.compute.formula import render as render_formula  # noqa: E402
from abacus.modules.workpapers.service import CellEdit, set_cells  # noqa: E402 -- A-06-T28

__all__ = [
    "CELL_TARGET",
    "ROUTERS",
    "WORKPAPER_KINDS",
    "AddressInvalid",
    "Attribute",
    "CellEdit",
    "CodeTaken",
    "DesignedLayout",
    "ExceptionPrefill",
    "FormulaCellInput",
    "FormulaCycleError",
    "FormulaError",
    "FormulaWorkbook",
    "Grid",
    "IssueLink",
    "NoAssuranceItem",
    "PackConfigurationError",
    "PackError",
    "PaperFact",
    "SheetLayout",
    "WorkpaperInvalid",
    "apply_cell_suggestion",
    "bound_steps",
    "build_formula_graph",
    "canonical_address",
    "checks_for",
    "checks_router",
    "create_test",
    "create_workpaper",  # A-04-T28: the planning slice opens EBP-140 through the service
    "designed_layout",
    "dirty_cells",
    "draft_paper",
    "evaluate_workbook",
    "exception_prefill",
    "grid",
    "latest_test_of_variant",
    "latest_version_id",  # A-05-T16 (DEC-2489): EBP-02's document values
    "link_issue",
    "mark",
    "matrix_sections",  # A-06-T23: AUD-17 sections by paper kind
    "pack_errors",
    "paper_engagement",
    "paper_id_of_kind",
    "paper_of_kind",
    "parse_formula",
    "recompute_workbook",
    "record_agent_result",
    "register_designed_layout",
    "register_sign_off_guard",  # A-05-T16 (DEC-2069)
    "render_formula",
    "resolve",
    "router",
    "set_cells",
    "tie_digests",
    "validate_pack",
    "work_item_papers",
]

# Q-03-T235 (DEC-3304): ADM-07 and AUD-29 name this module's targets through the platform slot.
from abacus.modules.workpapers.audit_labels import register as _register_audit_labels  # noqa: E402
from abacus.modules.workpapers.audit_labels import (  # noqa: E402
    workpaper_code_exists as workpaper_code_exists,
)

_register_audit_labels()

# P-10-T39: the engagement run's `workpaper` step is this module's to answer (BOUND-002).
from abacus.modules.workpapers.run_steps import register as _register_run_steps  # noqa: E402

_register_run_steps()

# W-02-T11 (DEC-4716): this module's Workbench tool on C17, registered at import.
from abacus.modules.workpapers import (  # noqa: E402
    agent_tools as _workbench_tools,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers at import
)
