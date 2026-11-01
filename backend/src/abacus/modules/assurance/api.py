"""Public interface of the assurance module; other modules import only this (ADR-008).

The audit line's read models and actions: the AUD-06 trial balance first (SPEC-309).
"""

# A-03-T08: the C9 v2 routes call this lazily; imported here so its error codes are catalogued.
from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.agents.api import register_suggestion_applier, register_suggestion_target
from abacus.modules.assurance import mapping_live as mapping_live
from abacus.modules.assurance.archive_gate import g9
from abacus.modules.assurance.audits_contract import audits_router
from abacus.modules.assurance.completion import g6, g7
from abacus.modules.assurance.completion_routes import dashboard_router
from abacus.modules.assurance.completion_routes import router as completion_router

# A-04-T08/T09: the pure materiality engine, for the recommender's evaluation (BOUND-001).
from abacus.modules.assurance.compute import materiality as materiality_engine
from abacus.modules.assurance.ebp_contract import router as ebp_router
from abacus.modules.assurance.ebp_designed import register as register_ebp_designed
from abacus.modules.assurance.ebp_designed import register_modes as register_ebp_modes
from abacus.modules.assurance.ebp_plan import AUDIT_KINDS as EBP_PLAN_KINDS
from abacus.modules.assurance.ebp_plan import audit_owners as ebp_plan_owners
from abacus.modules.assurance.findings_contract import router as findings_router
from abacus.modules.assurance.home_counts import register_home_counts
from abacus.modules.assurance.mapping import SUBSCRIPTIONS as MAPPING_SUBSCRIPTIONS
from abacus.modules.assurance.mapping import import_csv as import_grouping_csv
from abacus.modules.assurance.mapping import mapping_facts, mapping_reviewables
from abacus.modules.assurance.mapping import publish as publish_grouping_version
from abacus.modules.assurance.mapping_routes import firm_router as grouping_router
from abacus.modules.assurance.mapping_routes import router as mapping_router
from abacus.modules.assurance.materiality import AUDIT_KINDS as MATERIALITY_KINDS
from abacus.modules.assurance.materiality import audit_owners as materiality_owners
from abacus.modules.assurance.materiality import propose as propose_materiality
from abacus.modules.assurance.materiality import reassess as reassess_materiality
from abacus.modules.assurance.materiality import register as register_materiality_kinds
from abacus.modules.assurance.materiality import register_materiality_dependents
from abacus.modules.assurance.phase import SUBSCRIPTIONS as PHASE_SUBSCRIPTIONS
from abacus.modules.assurance.phase import record_phase, update_profile
from abacus.modules.assurance.planning_contract import router as planning_router
from abacus.modules.assurance.providers import register as register_a01_providers
from abacus.modules.assurance.release import RELEASE_MODE_SETTING, g8
from abacus.modules.assurance.review_gates import register_review_gates
from abacus.modules.assurance.risks import AUDIT_KINDS as RISK_KINDS
from abacus.modules.assurance.risks import apply_risk_suggestion, risk_engagement
from abacus.modules.assurance.risks import audit_owners as risk_owners
from abacus.modules.assurance.routes import router
from abacus.modules.assurance.run_badges import run_badges
from abacus.modules.assurance.sections import (
    AuditSection,
    IndexTag,
    RunSummary,
    SectionState,
    register_audit_section,
    register_audit_segment,
    register_index_tag,
    register_run_summary,
)
from abacus.modules.assurance.service_orgs import AUDIT_KINDS as SERVICE_ORG_KINDS
from abacus.modules.assurance.service_orgs import audit_owners as service_org_owners
from abacus.modules.assurance.tb_mapping_contract import MappingConfirmIn, MappingRunIn
from abacus.modules.assurance.tb_mapping_contract import router as tb_mapping_router

# A-02-T10: the live C9 routes are declared on `tb_router` in `tb_read_model`, so it is
# imported from there (loading the module registers them before the API mounts the router).
from abacus.modules.assurance.tb_read_model import tb_router
from abacus.modules.assurance.trial_balance import adopt as adopt_trial_balance
from abacus.modules.assurance.trial_balance import tb_facts, tb_reviewables
from abacus.modules.engagements.api import register_gate_provider, work_item_engagement
from abacus.modules.identity.api import AbacusRouter, register_firm_setting
from abacus.modules.review.api import register_reviewable, register_reviewable_facts

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    tb_router,  # C9 v1 (docs/contracts/c09-ledger.md): A-02-T03 stubs, A-02-T10 live reads
    audits_router,  # A-01-T02 audits family stub (docs/contracts/audits-cockpit.md)
    completion_router,
    mapping_router,
    grouping_router,
    dashboard_router,
    tb_mapping_router,  # C9 v2 (docs/contracts/ledger-mapping.md): A-03-T03 stub
    planning_router,  # A-04-T01 audit planning stub (docs/contracts/audit-planning.md)
    ebp_router,  # A-05-T04 ebp-workpapers v1 stub (docs/contracts/ebp-workpapers.md)
    findings_router,  # A-06-T05 completion family stub (docs/contracts/completion.md)
)

# SPEC-313 (TASK-331): trial balances appear in the sign-off matrix and count toward G5.
register_reviewable("trial_balance", tb_reviewables)
# SPEC-316 (TASK-345): the account mapping is signed like a working paper.
register_reviewable("mapping_set", mapping_reviewables)
# P-04-T15 (DEC-216): each one's facts, with its preparers from the ledger's own records.
register_reviewable_facts("trial_balance", tb_facts)
register_reviewable_facts("mapping_set", mapping_facts)

# SPEC-314 (TASK-332): EQR concurrence, the representation letter, release and the archive.
# A-01-T23 (DEC-590): G8 and G9 are met by SPEC-314's in-app act or by the record-mode
# external release and archive, whichever the firm's `assurance_release_mode` allowed.
register_gate_provider("G6", g6)
register_gate_provider("G7", g7)
register_gate_provider("G8", g8)
register_gate_provider("G9", g9)
register_firm_setting(RELEASE_MODE_SETTING)

# A-01-T05 (SPEC-330 AC-13): C1's `gate.met` derives the phase a computed gate opens. The worker
# collects these with every module's; assurance has no workflows of its own yet.
# A-03-T14: a new trial balance version leaves a signed mapping stale (`mapping_set.went_stale`).
SUBSCRIPTIONS = dict(PHASE_SUBSCRIPTIONS) | dict(MAPPING_SUBSCRIPTIONS)
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

# A-01-T02 (A-01 §5.1): the AUD-01 segments every firm has; X-01 (SOC & IT) and X-03 (Internal
# audit) register theirs with an entitlement.
register_audit_segment("fs", None)
register_audit_segment("ebp", None)
register_audit_segment("review", None)
# A-01-T09 (DEC-312): A-01's Overview rows and index tags, through the same slots as A-02's.
register_a01_providers()
# I-01-T08: this module's HOME-01 tile or pill (platform.register_home_count).
register_home_counts()
# I-01-T08 (C13): SPEC-004's review queue as `evidence_review` gates.
register_review_gates()

# A-05-T09 (DEC-1954): the nine EBP designed workpapers' rail rows, layouts and export section.
register_ebp_designed()
# A-05-T10 (DEC-1955): EBP-01's plan, providers and checks placed for the trail.
register_engagement_owners(EBP_PLAN_KINDS, ebp_plan_owners)
# A-05-T12 (DEC-1956): which papers each EBP section-draft mode drafts.
register_ebp_modes()
# A-04-T07: the trail places a service organization on its engagement (SPEC-304; DEC-121).
register_engagement_owners(SERVICE_ORG_KINDS, service_org_owners)
# A-04-T12 (DEC-1950): the materiality cards' kinds and appliers; versions placed for the trail.
register_materiality_kinds()
register_engagement_owners(MATERIALITY_KINDS, materiality_owners)
# A-04-T13 (DEC-1951): the register's rows placed for the trail; the agent's `risk` suggestions
# written by their owner when a person adopts them (AC4.7).
register_engagement_owners(RISK_KINDS, risk_owners)
register_suggestion_applier("risk", apply_risk_suggestion, engagement_of=risk_engagement)
# A-04-T15 (DEC-1953): the recommender's suggestion names the work item's materiality.
register_suggestion_target("materiality", engagement_of=work_item_engagement)

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "AuditSection",
    "IndexTag",
    "MappingConfirmIn",
    "MappingRunIn",
    "RunSummary",
    "SectionState",
    "adopt_trial_balance",
    "completion_router",
    "import_grouping_csv",
    "mapping_live",
    "materiality_engine",
    "propose_materiality",  # P-04-T36: the scenario loader proposes as the person named
    "publish_grouping_version",
    "reassess_materiality",
    "record_phase",
    "register_audit_section",
    "register_audit_segment",
    "register_index_tag",
    "register_materiality_dependents",
    "register_run_summary",
    "router",
    "update_profile",
]

# A-01-T27 (DEC-717): the Processing pill and audit-bar run time read C6 v1 engagement runs.
register_run_summary(run_badges)
