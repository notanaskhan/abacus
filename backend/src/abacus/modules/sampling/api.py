"""Public interface of the sampling module; other modules import only this (ADR-008).

Populations and selection by code (ADR-132; SPEC-037; TASK-083): pure functions over ledger
snapshots, with versioned rules, so another auditor can re-perform a selection.
"""

# The routers the API mounts, in order (P-39; F-03-T07). A-03-T02: the sampling contract stub.
from abacus.kernel.audit_owners import register_engagement_owners
from abacus.kernel.dispatch import WorkClass, register_work_classes
from abacus.modules.review.api import (
    register_gate_kind,
    register_reviewable,
    register_reviewable_facts,
)
from abacus.modules.sampling.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.sampling.compute import (
    CURRENT as SAMPLER_CURRENT,
)
from abacus.modules.sampling.compute import (
    SAMPLER_VERSIONS,
    Record,
    StratumRule,
    attribute_size,
    projected_misstatement,
    udl,
    udl_percent,
)
from abacus.modules.sampling.compute import (
    je_scoring as je_scoring,  # A-08-T10: the JE scoring engine, for the Granite Peak scenario
)
from abacus.modules.sampling.contract import (
    ROUTERS,
    ApproveIn,
    GeneralLedgerSourceIn,
    ParametersIn,
    PopulationIn,
    SampleSetIn,
    StratumIn,
    TieComparisonIn,
    TieIn,
    UploadSourceIn,
    VersionIn,
)
from abacus.modules.sampling.draw_activities import ACTIVITIES as DRAW_ACTIVITIES
from abacus.modules.sampling.draw_types import SampleDrawInput
from abacus.modules.sampling.draw_workflow import SampleDrawWorkflow

# A-03-T13: the item-request fan-out (its routes import it lazily; imported here so its errors
# are the module's own at start-up).
from abacus.modules.sampling.item_requests import (
    ApprovedItem,
    ApprovedSample,
    RecipientNotContact,
    SampleNotApproved,
    SampleRow,
    approved_items,
    approved_sample_rows,
    version_seed,
)

# A-08-T12: JE testing's scoring run (batch queue: nobody waits on a 400,000-line population).
from abacus.modules.sampling.je_scoring_activities import ACTIVITIES as JE_ACTIVITIES
from abacus.modules.sampling.je_scoring_types import JeScoringInput
from abacus.modules.sampling.je_scoring_workflow import JeScoringWorkflow
from abacus.modules.sampling.payments import (
    PAYMENTS_RULE_VERSION,
    Band,
    Bill,
    bills_by_party,
    build_payments,
    recorded_bill,
    select_payments,
    ties,
)
from abacus.modules.sampling.population import (
    RULE_VERSION,
    Entry,
    Population,
    build_population,
    tie_out,
)

# A-03-T07: populations and completeness ties (the routes call the service; T10 reads them).
from abacus.modules.sampling.populations import (
    TIE_VERSION,
    create_population,
    population_view,
    record_tie,
)
from abacus.modules.sampling.registry import AUDIT_SECTION

# A-03-T10: sample sets, the draw and the approval.
from abacus.modules.sampling.sample_sets import (
    GATE_KIND,
    TARGET,
    Projection,
    approval_gate,
    approve,
    create_sample_set,
    draw,
    projection_of,
    reviewable_facts,
    reviewables,
    sample_set_view,
    section_state,
    version_row,
)
from abacus.modules.sampling.selected_entries import SelectedEntry, selected_entry
from abacus.modules.sampling.selection import (
    CRITERIA_VERSION,
    DEFAULT_KEYWORDS,
    RANDOM_METHOD,
    RULES,
    Parameters,
    Selected,
    manual_kinds_for,
    seeded_v1,
    select,
)

ACTIVITIES = (*DRAW_ACTIVITIES, *JE_ACTIVITIES)
# A-03-T10: the draw runs on the interactive queue (a person waits on it, AUD-11e).
WORKFLOWS: dict[type, WorkClass] = {
    SampleDrawWorkflow: "interactive",
    JeScoringWorkflow: "batch",
}
register_work_classes(WORKFLOWS)
SUBSCRIPTIONS: dict[str, object] = {}
# A version is signed like a working paper: L1 the preparer, L2 the approval (ADR-160).
register_reviewable(TARGET, reviewables)
register_reviewable_facts(TARGET, reviewable_facts)
register_gate_kind(GATE_KIND, approval_gate)

# A-08-T17 (DEC-5307): the named approver's HOME-02 gate on a pending sample expansion.
from abacus.modules.sampling.expansions import register_expansion_gate  # noqa: E402

register_expansion_gate()
# The audit explorer hides events about walled engagements (SPEC-304; DEC-1387).
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ACTIVITIES",
    "AUDIT_SECTION",
    "CRITERIA_VERSION",
    "DEFAULT_KEYWORDS",
    "PAYMENTS_RULE_VERSION",
    "RANDOM_METHOD",
    "ROUTERS",
    "RULES",
    "RULE_VERSION",
    "SAMPLER_CURRENT",
    "SAMPLER_VERSIONS",
    "SUBSCRIPTIONS",
    "TIE_VERSION",
    "WORKFLOWS",
    "ApproveIn",
    "ApprovedItem",
    "ApprovedSample",
    "Band",
    "Bill",
    "Entry",
    "GeneralLedgerSourceIn",
    "JeScoringInput",
    "JeScoringWorkflow",
    "Parameters",
    "ParametersIn",
    "Population",
    "PopulationIn",
    "Projection",
    "RecipientNotContact",
    "Record",
    "SampleDrawInput",
    "SampleDrawWorkflow",
    "SampleNotApproved",
    "SampleRow",
    "SampleSetIn",
    "Selected",
    "SelectedEntry",
    "StratumIn",
    "StratumRule",
    "TieComparisonIn",
    "TieIn",
    "UploadSourceIn",
    "VersionIn",
    "approve",
    "approved_items",
    "approved_sample_rows",
    "attribute_size",
    "bills_by_party",
    "build_payments",
    "build_population",
    "create_population",
    "create_sample_set",
    "draw",
    "je_scoring",
    "manual_kinds_for",
    "population_view",
    "projected_misstatement",
    "projection_of",
    "record_tie",
    "recorded_bill",
    "sample_set_view",
    "section_state",
    "seeded_v1",
    "select",
    "select_payments",
    "selected_entry",
    "tie_out",
    "ties",
    "udl",
    "udl_percent",
    "version_row",
    "version_seed",
]
