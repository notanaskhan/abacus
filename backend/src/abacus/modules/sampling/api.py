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
    attribute_size,
    projected_misstatement,
    udl,
    udl_percent,
)
from abacus.modules.sampling.contract import ROUTERS
from abacus.modules.sampling.draw_activities import ACTIVITIES
from abacus.modules.sampling.draw_types import SampleDrawInput
from abacus.modules.sampling.draw_workflow import SampleDrawWorkflow
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
from abacus.modules.sampling.populations import TIE_VERSION, population_view
from abacus.modules.sampling.registry import AUDIT_SECTION

# A-03-T10: sample sets, the draw and the approval.
from abacus.modules.sampling.sample_sets import (
    GATE_KIND,
    TARGET,
    approval_gate,
    draw,
    reviewable_facts,
    reviewables,
    section_state,
)
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

# A-03-T10: the draw runs on the interactive queue (a person waits on it, AUD-11e).
WORKFLOWS: dict[type, WorkClass] = {SampleDrawWorkflow: "interactive"}
register_work_classes(WORKFLOWS)
SUBSCRIPTIONS: dict[str, object] = {}
# A version is signed like a working paper: L1 the preparer, L2 the approval (ADR-160).
register_reviewable(TARGET, reviewables)
register_reviewable_facts(TARGET, reviewable_facts)
register_gate_kind(GATE_KIND, approval_gate)
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
    "Band",
    "Bill",
    "Entry",
    "Parameters",
    "Population",
    "SampleDrawInput",
    "SampleDrawWorkflow",
    "Selected",
    "attribute_size",
    "bills_by_party",
    "build_payments",
    "build_population",
    "draw",
    "manual_kinds_for",
    "population_view",
    "projected_misstatement",
    "recorded_bill",
    "section_state",
    "seeded_v1",
    "select",
    "select_payments",
    "tie_out",
    "ties",
    "udl",
    "udl_percent",
]
