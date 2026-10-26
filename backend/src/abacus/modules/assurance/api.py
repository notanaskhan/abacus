"""Public interface of the assurance module; other modules import only this (ADR-008).

The audit line's read models and actions: the AUD-06 trial balance first (SPEC-309).
"""

from abacus.modules.assurance.audits_contract import audits_router
from abacus.modules.assurance.completion import g6, g7, g8, g9
from abacus.modules.assurance.completion_routes import dashboard_router
from abacus.modules.assurance.completion_routes import router as completion_router
from abacus.modules.assurance.mapping import mapping_facts, mapping_reviewables
from abacus.modules.assurance.mapping_routes import firm_router as grouping_router
from abacus.modules.assurance.mapping_routes import router as mapping_router
from abacus.modules.assurance.phase import SUBSCRIPTIONS as PHASE_SUBSCRIPTIONS
from abacus.modules.assurance.phase import record_phase, update_profile
from abacus.modules.assurance.providers import register as register_a01_providers
from abacus.modules.assurance.routes import router
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

# A-02-T10: the live C9 routes are declared on `tb_router` in `tb_read_model`, so it is
# imported from there (loading the module registers them before the API mounts the router).
from abacus.modules.assurance.tb_read_model import tb_router
from abacus.modules.assurance.trial_balance import tb_facts, tb_reviewables
from abacus.modules.engagements.api import register_gate_provider
from abacus.modules.identity.api import AbacusRouter
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
)

# SPEC-313 (TASK-331): trial balances appear in the sign-off matrix and count toward G5.
register_reviewable("trial_balance", tb_reviewables)
# SPEC-316 (TASK-345): the account mapping is signed like a working paper.
register_reviewable("mapping_set", mapping_reviewables)
# P-04-T15 (DEC-216): each one's facts, with its preparers from the ledger's own records.
register_reviewable_facts("trial_balance", tb_facts)
register_reviewable_facts("mapping_set", mapping_facts)

# SPEC-314 (TASK-332): EQR concurrence, the representation letter, release and the archive.
register_gate_provider("G6", g6)
register_gate_provider("G7", g7)
register_gate_provider("G8", g8)
register_gate_provider("G9", g9)

# A-01-T05 (SPEC-330 AC-13): C1's `gate.met` derives the phase a computed gate opens. The worker
# collects these with every module's; assurance has no workflows of its own yet.
SUBSCRIPTIONS = PHASE_SUBSCRIPTIONS
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

# A-01-T02 (A-01 §5.1): the AUD-01 segments every firm has; X-01 (SOC & IT) and X-03 (Internal
# audit) register theirs with an entitlement.
register_audit_segment("fs", None)
register_audit_segment("ebp", None)
register_audit_segment("review", None)
# A-01-T09 (DEC-312): A-01's Overview rows and index tags, through the same slots as A-02's.
register_a01_providers()

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "AuditSection",
    "IndexTag",
    "RunSummary",
    "SectionState",
    "completion_router",
    "record_phase",
    "register_audit_section",
    "register_audit_segment",
    "register_index_tag",
    "register_run_summary",
    "router",
    "update_profile",
]
