"""Public interface of the assurance module; other modules import only this (ADR-008).

The audit line's read models and actions: the AUD-06 trial balance first (SPEC-309).
"""

# A-03-T08: the C9 v2 routes call this lazily; imported here so its error codes are catalogued.
from abacus.kernel.audit_owners import register_engagement_owners
from abacus.kernel.dispatch import register_work_classes
from abacus.kernel.uow.relay import Handler, OutboxEvent
from abacus.modules.adjustments.api import (
    register_entry_decision_hook,
    register_entry_proposed_hook,
    register_evidence_engagement,
)
from abacus.modules.agents.api import (
    register_mode_mapping,
    register_mode_preparer,
    register_suggestion_applier,
    register_suggestion_target,
)
from abacus.modules.assurance import (
    completion_errors,  # A-07 refusal codes (A-07-T06)
    ebp_attribute,
    ebp_form5500_mode,
    ebp_investments,
    ebp_provisions,
    ebp_reconcile,
    ebp_trust_mode,
    ic_mode,
    related_parties_mode,
    soc1_mode,
)
from abacus.modules.assurance import mapping_live as mapping_live
from abacus.modules.assurance.a07_registrations import SUBSCRIPTIONS as A07_SUBSCRIPTIONS
from abacus.modules.assurance.a07_registrations import register as register_a07_live_path
from abacus.modules.assurance.aud27 import register_estimate_conclusion_kind
from abacus.modules.assurance.audits_contract import audits_router
from abacus.modules.assurance.bring_down import (
    BRING_DOWN_ID_PREFIX,
    BringDownInput,
    BringDownResult,
    BringDownWorkflow,
    bring_down,
)
from abacus.modules.assurance.checklist_suggestions import (
    CHECKLIST_SUGGESTION_TARGET,
    apply_checklist_suggestion,
    statement_document_engagement,
)
from abacus.modules.assurance.checklist_suggestions import (
    SUBSCRIPTIONS as CHECKLIST_SUGGESTION_SUBSCRIPTIONS,
)
from abacus.modules.assurance.checklist_suggestions import (
    on_suggestion_created as on_checklist_suggestion,
)
from abacus.modules.assurance.completion import on_entry_client_decision, on_entry_proposed
from abacus.modules.assurance.completion_contract import router as audit_completion_router
from abacus.modules.assurance.completion_decisions import AUDIT_KINDS as DECISION_KINDS
from abacus.modules.assurance.completion_decisions import audit_owners as decision_owners
from abacus.modules.assurance.completion_decisions import register_completion_decision_kinds
from abacus.modules.assurance.completion_facts import register_completion_facts
from abacus.modules.assurance.completion_projector import SUBSCRIBED as COMPLETION_SUBSCRIBED
from abacus.modules.assurance.completion_projector import on_completion_event
from abacus.modules.assurance.completion_routes import dashboard_router
from abacus.modules.assurance.completion_routes import router as completion_router
from abacus.modules.assurance.completion_targets import AUDIT_KINDS as COMPLETION_TARGET_KINDS
from abacus.modules.assurance.completion_targets import (
    audit_owners as completion_target_owners,
)

# A-04-T08/T09: the pure materiality engine, for the recommender's evaluation (BOUND-001).
from abacus.modules.assurance.compute import materiality as materiality_engine
from abacus.modules.assurance.draft_mappings import gap_inputs, risk_inputs, risk_narrative_inputs
from abacus.modules.assurance.ebp_contract import router as ebp_router
from abacus.modules.assurance.ebp_designed import register as register_ebp_designed
from abacus.modules.assurance.ebp_designed import register_modes as register_ebp_modes
from abacus.modules.assurance.ebp_form5500 import ACTIVITIES as FORM5500_ACTIVITIES
from abacus.modules.assurance.ebp_form5500 import SUBSCRIPTIONS as FORM5500_SUBSCRIPTIONS
from abacus.modules.assurance.ebp_form5500 import WORKFLOWS as FORM5500_WORKFLOWS
from abacus.modules.assurance.ebp_investments import AUDIT_KINDS as CERTIFICATION_KINDS
from abacus.modules.assurance.ebp_investments import audit_owners as certification_owners
from abacus.modules.assurance.ebp_plan import AUDIT_KINDS as EBP_PLAN_KINDS
from abacus.modules.assurance.ebp_plan import audit_owners as ebp_plan_owners
from abacus.modules.assurance.ebp_remittances import AUDIT_KINDS as LATE_REMITTANCE_KINDS
from abacus.modules.assurance.ebp_remittances import audit_owners as late_remittance_owners
from abacus.modules.assurance.ebp_remittances import late_remittances
from abacus.modules.assurance.eqr_service import SUBSCRIPTIONS as EQR_SUBSCRIPTIONS
from abacus.modules.assurance.eqr_service import register_eqr_checklist_template
from abacus.modules.assurance.findings import AUDIT_KINDS as FINDING_KINDS
from abacus.modules.assurance.findings import audit_owners as finding_owners
from abacus.modules.assurance.findings import register_exception_routes
from abacus.modules.assurance.findings_contract import router as findings_router
from abacus.modules.assurance.form5500_workflow import (  # A-05-T54: for the history recorder
    TIEOUT_ID_PREFIX,
    Form5500TieOutWorkflow,
    TieOutCounts,
    TieOutInput,
)
from abacus.modules.assurance.fraud_brainstorm import AUDIT_KINDS as FRAUD_KINDS
from abacus.modules.assurance.fraud_brainstorm import GATE_KIND as FRAUD_GATE
from abacus.modules.assurance.fraud_brainstorm import SUGGESTION_TARGET as FRAUD_MINUTES
from abacus.modules.assurance.fraud_brainstorm import apply_minutes_suggestion, minutes_gate
from abacus.modules.assurance.fraud_brainstorm import audit_owners as fraud_owners
from abacus.modules.assurance.gates import register as register_gates
from abacus.modules.assurance.home_counts import register_home_counts
from abacus.modules.assurance.ic_redraft import SUBSCRIPTIONS as IC_REDRAFT_SUBSCRIPTIONS
from abacus.modules.assurance.internal_control import AUDIT_KINDS as CONTROL_KINDS
from abacus.modules.assurance.internal_control import (
    ExceptionRouter,
    ExceptionRow,
    RouteRequest,
    exception_route_available,
    record_exceptions,
    register_exception_route,
)
from abacus.modules.assurance.internal_control import audit_owners as control_owners
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
from abacus.modules.assurance.phase import (
    PHASE_GATES,
    follows_gate,
    record_phase,
    update_profile,
)
from abacus.modules.assurance.phase import SUBSCRIPTIONS as PHASE_SUBSCRIPTIONS
from abacus.modules.assurance.planning_contract import router as planning_router
from abacus.modules.assurance.planning_gate import g4_facts
from abacus.modules.assurance.providers import register as register_a01_providers
from abacus.modules.assurance.release import RELEASE_MODE_SETTING
from abacus.modules.assurance.release_contract import router as audit_release_router
from abacus.modules.assurance.release_facts import register as register_release_facts
from abacus.modules.assurance.release_workflow import ACTIVITIES as RELEASE_ACTIVITIES
from abacus.modules.assurance.release_workflow import WORKFLOWS as RELEASE_WORKFLOWS
from abacus.modules.assurance.rep_letters import register_rep_triggers
from abacus.modules.assurance.review_gates import register_review_gates
from abacus.modules.assurance.risks import AUDIT_KINDS as RISK_KINDS
from abacus.modules.assurance.risks import Edit as RiskEdit
from abacus.modules.assurance.risks import (
    NewRisk,
    apply_risk_suggestion,
    presumed_preparer,
    register_approval_kind,
    risk_engagement,
)
from abacus.modules.assurance.risks import audit_owners as risk_owners
from abacus.modules.assurance.risks import create as create_risk
from abacus.modules.assurance.risks import edit as edit_risk
from abacus.modules.assurance.risks import request_approval as request_risk_approval
from abacus.modules.assurance.routes import router
from abacus.modules.assurance.run_badges import run_badges
from abacus.modules.assurance.schedule_h_mappings import schedule_h_mappings_router
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
from abacus.modules.assurance.severity_suggestions import (
    SEVERITY_SUGGESTION_TARGET,
    apply_severity_suggestion,
    deficiency_engagement,
)
from abacus.modules.assurance.severity_suggestions import (
    on_suggestion_created as on_severity_suggestion,
)
from abacus.modules.assurance.soc_reports import AUDIT_KINDS as SOC_REPORT_KINDS
from abacus.modules.assurance.soc_reports import audit_owners as soc_report_owners
from abacus.modules.assurance.soc_reports import register_reliance_kind
from abacus.modules.assurance.tb_mapping_contract import MappingConfirmIn, MappingRunIn
from abacus.modules.assurance.tb_mapping_contract import router as tb_mapping_router

# A-02-T10: the live C9 routes are declared on `tb_router` in `tb_read_model`, so it is
# imported from there (loading the module registers them before the API mounts the router).
from abacus.modules.assurance.tb_read_model import tb_router
from abacus.modules.assurance.trail_owners import AUDIT_KINDS as TRAIL_KINDS
from abacus.modules.assurance.trail_owners import audit_owners as trail_owners
from abacus.modules.assurance.trial_balance import adopt as adopt_trial_balance
from abacus.modules.assurance.trial_balance import tb_facts, tb_reviewables
from abacus.modules.engagements.api import work_item_engagement
from abacus.modules.evidence.api import engagement_of_version
from abacus.modules.identity.api import (
    AbacusRouter,
    register_firm_setting,
    register_scope_resolver,
)
from abacus.modules.review.api import (
    register_gate_kind,
    register_reviewable,
    register_reviewable_facts,
)
from abacus.modules.workpapers.api import register_sign_off_guard

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
    audit_completion_router,  # A-07-T04 AUD-18/AUD-19 stub (docs/contracts/audit-completion.md)
    audit_release_router,  # A-07-T05 AUD-21 to AUD-25 stub (docs/contracts/audit-completion.md)
    schedule_h_mappings_router,  # A-05-T62 close: the firm's Schedule H line mapping (DEC-2823)
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
register_gates()  # A-04-T43, A-07-T15: G4 to G9 from assurance/gates.py
# A-06-T10 (DEC-2062): a client's decision on an entry moves its misstatement.
register_entry_decision_hook(on_entry_client_decision)
# A-06-T17 (DEC-2956): record mode's evidence must be an email on the entry's own engagement.
register_evidence_engagement(engagement_of_version)
register_entry_proposed_hook(on_entry_proposed)
# A-04-T22 (DEC-2058): the planning modes' mappings for the section drafter.
register_mode_mapping("gap", gap_inputs)
register_mode_mapping("risk_narrative", risk_narrative_inputs)
register_mode_mapping("risk", risk_inputs)  # A-04-T24 (DEC-2060)
register_mode_mapping(ebp_provisions.MODE, ebp_provisions.provisions_inputs)  # A-05-T16
register_mode_mapping(ebp_attribute.MODE, ebp_attribute.attribute_inputs)  # A-05-T21
register_mode_mapping(ebp_reconcile.MODE, ebp_reconcile.reconcile_inputs)  # A-05-T27
register_mode_mapping(ic_mode.MODE, ic_mode.ic_inputs)  # A-04-T29
register_mode_mapping(soc1_mode.MODE, soc1_mode.soc1_inputs)  # A-04-T35
register_mode_mapping(ebp_trust_mode.MODE, ebp_trust_mode.trust_inputs)  # A-05-T36
register_mode_mapping(ebp_form5500_mode.MODE, ebp_form5500_mode.form5500_inputs)  # A-05-T55
register_mode_mapping(related_parties_mode.MODE, related_parties_mode.related_party_inputs)  # T56
register_sign_off_guard(ebp_provisions.KIND, ebp_provisions.sign_off_guard)  # A-05-T16
register_sign_off_guard(ebp_investments.KIND, ebp_investments.sign_off_guard)  # A-05-T39
# A-04-T23 (DEC-2059): code inserts the presumed fraud risks before a narrative draft.
register_mode_preparer("risk_narrative", presumed_preparer)
register_firm_setting(RELEASE_MODE_SETTING)


# A-01-T05 (SPEC-330 AC-13): C1's `gate.met` derives the phase a computed gate opens. The worker
# collects these with every module's; assurance has no workflows of its own yet.
async def _on_suggestion_created(event: OutboxEvent) -> None:
    """`suggestion.created` for both seams: each ignores another target's suggestion."""
    await on_checklist_suggestion(event)
    await on_severity_suggestion(event)


# A-03-T14: a new trial balance version leaves a signed mapping stale (`mapping_set.went_stale`).
# A-06-T16 seam (TASK-3395): an agent's suggested checklist answer is mirrored on its item.
_BASE_SUBSCRIPTIONS = (
    dict(PHASE_SUBSCRIPTIONS)
    | dict(MAPPING_SUBSCRIPTIONS)
    | dict(IC_REDRAFT_SUBSCRIPTIONS)
    | dict(A07_SUBSCRIPTIONS)
    | dict(EQR_SUBSCRIPTIONS)
    | dict(FORM5500_SUBSCRIPTIONS)
    | dict(CHECKLIST_SUGGESTION_SUBSCRIPTIONS)
    | {"suggestion.created": _on_suggestion_created}
)


def _then_project(first: Handler) -> Handler:
    """A-07-T22: an event another handler already consumes also reaches the projector after it."""

    async def run(event: OutboxEvent) -> None:
        await first(event)
        await on_completion_event(event)

    return run


# A-07-T22 (DEC-2806): the completion projector, inert until M16 (`completion_dark`).
SUBSCRIPTIONS = _BASE_SUBSCRIPTIONS | {
    kind: (
        _then_project(_BASE_SUBSCRIPTIONS[kind])
        if kind in _BASE_SUBSCRIPTIONS
        else on_completion_event
    )
    for kind in COMPLETION_SUBSCRIBED
}
# A-05-T54: Form5500TieOut, code only, on the background class.
# A-07-T30 (DEC-3107): ReleaseWorkflow on the time-sensitive class.
WORKFLOWS: dict[type, str] = (
    dict(FORM5500_WORKFLOWS) | {BringDownWorkflow: "background"} | dict(RELEASE_WORKFLOWS)
)
ACTIVITIES: tuple[object, ...] = (*FORM5500_ACTIVITIES, bring_down, *RELEASE_ACTIVITIES)
register_work_classes(WORKFLOWS)  # type: ignore[arg-type]  # registry kind literal

# A-01-T02 (A-01 §5.1): the AUD-01 segments every firm has; X-01 (SOC & IT) and X-03 (Internal
# audit) register theirs with an entitlement.
register_audit_segment("fs", None)
register_audit_segment("ebp", None)
register_audit_segment("review", None)
# A-01-T09 (DEC-312): A-01's Overview rows and index tags, through the same slots as A-02's.
register_a01_providers()
# A-07-T22 (DEC-2806): the completion items assurance derives itself.
register_completion_facts()
# A-07-T24 (DEC-2808): the specific representations' triggers assurance reads itself.
register_rep_triggers()
# A-07-T19: the live-path registrations, inert until the A-07 flags (T33).
register_a07_live_path()
# A-07-T30 (DEC-3107): AUD-24's also-required items assurance computes itself.
register_release_facts()
# A-05-T53: the estimate conclusion, the EP's card (AU-C 540).
register_estimate_conclusion_kind()
# I-01-T08: this module's HOME-01 tile or pill (platform.register_home_count).
register_home_counts()
register_exception_routes()  # DEC-2354: AUD-09 and AUD-10's routes into Findings and the SUM
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
# S31 end pass: A-07's completion rows (projector, subsequent events, letters).
register_engagement_owners(COMPLETION_TARGET_KINDS, completion_target_owners)
register_engagement_owners(SOC_REPORT_KINDS, soc_report_owners)  # A-04-T31
register_engagement_owners(CONTROL_KINDS, control_owners)  # A-04-T25 (DEC-2264)
register_engagement_owners(DECISION_KINDS, decision_owners)  # A-06-T13 (DEC-2264)
register_engagement_owners(LATE_REMITTANCE_KINDS, late_remittance_owners)  # A-05-T30
register_engagement_owners(TRAIL_KINDS, trail_owners)  # A-07-T18, A-05-T53 (S30 end pass)
register_engagement_owners(CERTIFICATION_KINDS, certification_owners)  # A-05-T39
# A-04-T12 (DEC-1950): the materiality cards' kinds and appliers; versions placed for the trail.
register_materiality_kinds()
register_approval_kind()  # A-04-T18 (DEC-2056): the `significant_risk` card
register_completion_decision_kinds()  # A-06-T13 (DEC-2213): severity and the SUM conclusion
register_reliance_kind()  # A-04-T31 (DEC-2236): the `service_org_reliance` card
register_engagement_owners(MATERIALITY_KINDS, materiality_owners)
# A-04-T13 (DEC-1951): the register's rows placed for the trail; the agent's `risk` suggestions
# written by their owner when a person adopts them (AC4.7).
register_engagement_owners(RISK_KINDS, risk_owners)
# A-04-T19 (DEC-2055): the fraud brainstorm's session and inquiries placed for the trail, the
# agent's minutes written by their owner when a person adopts them, and HOME-02's gate.
register_engagement_owners(FRAUD_KINDS, fraud_owners)
register_engagement_owners(FINDING_KINDS, finding_owners)  # A-06-T11 (DEC-2063)
register_suggestion_applier(
    FRAUD_MINUTES, apply_minutes_suggestion, engagement_of=work_item_engagement
)
register_gate_kind(FRAUD_GATE, minutes_gate)
register_suggestion_applier("risk", apply_risk_suggestion, engagement_of=risk_engagement)
# A-04-T15 (DEC-1953): the recommender's suggestion names the work item's materiality.
register_suggestion_target("materiality", engagement_of=work_item_engagement)
# A-06-T16 seam (TASK-3395): the agent suggests a disclosure answer; a person adopts it.
register_suggestion_applier(
    CHECKLIST_SUGGESTION_TARGET,
    apply_checklist_suggestion,
    engagement_of=statement_document_engagement,
)

# A-06-T16 seam (DEC-2952): the agent proposes a deficiency severity; a person adopts it.
register_suggestion_applier(
    SEVERITY_SUGGESTION_TARGET,
    apply_severity_suggestion,
    engagement_of=deficiency_engagement,
)

# A-06-T25: reporting may not import agents; the statements' run record arrives through here.
from abacus.modules.agents.api import (  # noqa: E402
    close_deterministic_run,
    deterministic_run_facts,
    open_deterministic_run,
)
from abacus.modules.assurance.completion_decisions import (  # noqa: E402 -- A-06-T28
    request_severity_decision,
    request_sum_conclusion,
)
from abacus.modules.assurance.findings import NewFinding, record_finding  # noqa: E402
from abacus.modules.assurance.findings import to_deficiency as finding_to_deficiency  # noqa: E402
from abacus.modules.assurance.findings import (  # noqa: E402
    to_misstatement as finding_to_misstatement,
)
from abacus.modules.assurance.internal_control import route_exception  # noqa: E402
from abacus.modules.assurance.mapping import start as start_mapping  # noqa: E402
from abacus.modules.assurance.sum_service import pass_on_sum, record_prior_year  # noqa: E402
from abacus.modules.assurance.sum_service import record_factor as record_sum_factor  # noqa: E402
from abacus.modules.assurance.sum_service import (  # noqa: E402
    set_effect as set_misstatement_effect,
)
from abacus.modules.assurance.sum_service import snapshot as sum_snapshot  # noqa: E402
from abacus.modules.reporting.api import RunRecordPort, register_run_record  # noqa: E402

register_run_record(
    RunRecordPort(open_deterministic_run, close_deterministic_run, deterministic_run_facts)
)

__all__ = [
    "ACTIVITIES",
    "BRING_DOWN_ID_PREFIX",
    "PHASE_GATES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "TIEOUT_ID_PREFIX",
    "WORKFLOWS",
    "AuditSection",
    "BringDownInput",
    "BringDownResult",
    "BringDownWorkflow",
    "ExceptionRouter",
    "ExceptionRow",
    "Form5500TieOutWorkflow",
    "IndexTag",
    "MappingConfirmIn",
    "MappingRunIn",
    "NewFinding",
    "NewRisk",  # A-04-T28: the planning slice records the register through the service
    "RiskEdit",
    "RouteRequest",
    "RunSummary",
    "SectionState",
    "TieOutCounts",
    "TieOutInput",
    "acknowledge_letter",
    "adopt_trial_balance",
    "completion_errors",
    "completion_router",
    "create_risk",
    "edit_risk",
    "exception_route_available",
    "finding_to_deficiency",
    "finding_to_misstatement",
    "follows_gate",
    "g4_facts",
    "governance_letter",
    "governance_rooms",
    "import_grouping_csv",
    "late_remittances",  # A-05-T30: AUD-27 and EBP-07 read the one late remittance
    "mapping_live",
    "materiality_engine",
    "pass_on_sum",
    "propose_materiality",  # P-04-T36: the scenario loader proposes as the person named
    "publish_grouping_version",
    "reassess_materiality",
    "record_exceptions",
    "record_finding",
    "record_phase",
    "record_prior_year",
    "record_sum_factor",
    "register_audit_section",
    "register_audit_segment",
    "register_eqr_checklist_template",
    "register_exception_route",
    "register_index_tag",
    "register_materiality_dependents",
    "register_run_summary",
    "request_risk_approval",
    "request_severity_decision",
    "request_sum_conclusion",
    "room_letters",
    "route_exception",
    "router",
    "set_misstatement_effect",
    "start_mapping",
    "sum_snapshot",
    "update_profile",
]

# A-01-T27 (DEC-717): the Processing pill and audit-bar run time read C6 v1 engagement runs.
register_run_summary(run_badges)

# A-06-T15 (DEC-2215): a reviewable on C3's matrix and G5.
from abacus.modules.assurance.review_targets import (  # noqa: E402
    SUM_TARGET,
    sum_facts,
    sum_reviewables,
)
from abacus.modules.review.api import (  # noqa: E402
    register_reviewable as _register_reviewable,
)
from abacus.modules.review.api import (  # noqa: E402
    register_reviewable_facts as _register_reviewable_facts,
)

_register_reviewable(SUM_TARGET, sum_reviewables)
_register_reviewable_facts(SUM_TARGET, sum_facts)

# S28 (TASK-3400, DEC-2399): AUD-17's Materiality, Findings and Completion Checklist rows.
from abacus.modules.assurance import completion_reviewables as _rows  # noqa: E402

for _kind, _listed, _facts in (
    (_rows.MATERIALITY, _rows.materiality_reviewables, _rows.materiality_facts),
    (_rows.FINDINGS, _rows.findings_reviewables, _rows.findings_facts),
    (_rows.CHECKLIST, _rows.checklist_reviewables, _rows.checklist_facts),
):
    _register_reviewable(_kind, _listed)
    _register_reviewable_facts(_kind, _facts)

# A-05-T49 (DEC-2603): `ebp_audits` holds for a real firm only once the EBP CPA memo is signed.
from abacus.modules.assurance.compute.ebp.review import review_signed  # noqa: E402
from abacus.modules.platform.api import register_module_review  # noqa: E402

register_module_review("ebp_audits", review_signed)

# R-02-T12 (DEC-3010): POR-15's governance room. A `governance_room` scope is a governance body,
# resolved to its client; the room's reads and the acknowledgement live in `governance_room`.
from abacus.modules.assurance.governance_room import (  # noqa: E402
    CommitteeMember as CommitteeMember,
)
from abacus.modules.assurance.governance_room import (  # noqa: E402
    LetterChanged as LetterChanged,
)
from abacus.modules.assurance.governance_room import (  # noqa: E402
    acknowledge as acknowledge_letter,
)
from abacus.modules.assurance.governance_room import letter as governance_letter  # noqa: E402
from abacus.modules.assurance.governance_room import letters as room_letters  # noqa: E402
from abacus.modules.assurance.governance_room import (  # noqa: E402
    record_acknowledgement as record_acknowledgement,
)
from abacus.modules.assurance.governance_room import room_scope  # noqa: E402
from abacus.modules.assurance.governance_room import rooms as governance_rooms  # noqa: E402

register_scope_resolver("governance_room", room_scope)
