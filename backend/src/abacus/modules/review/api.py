"""Public interface of the review module; other modules import only this (ADR-008).

The review grammar (P-04): sign-offs first (SPEC-308); review notes, issues, decisions and
checkpoints follow.
"""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.engagements.api import register_gate_provider
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.review.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.review.card_reassign import register_card_reassign
from abacus.modules.review.contract import (
    checkpoints_router,
    decision_cards_router,
    fields_router,
    human_gates_router,
    issues_router,
    review_notes_router,
    sign_offs_router,
)
from abacus.modules.review.decisions import (
    DecisionCardState,
    RationaleRequired,
    RecommendationChanged,
    raise_decision_card,
)
from abacus.modules.review.engagement_gates import register_engagement_gates
from abacus.modules.review.field_values import (
    FieldValueInvalid,
    PreviousValue,
    previous_value,
    record_value,
    typed_value,
)
from abacus.modules.review.gates import (
    C13_EVENTS,
    GateSource,
    OpenGate,
    rebuild_human_gates,
    register_gate_source,
)
from abacus.modules.review.gates import SUBSCRIPTIONS as GATE_SUBSCRIPTIONS
from abacus.modules.review.hashing import Json, NotCanonical, canonical_json, content_hash
from abacus.modules.review.issue_refs import issue_engagement
from abacus.modules.review.matrix import review_gate
from abacus.modules.review.mfa import MfaRequired
from abacus.modules.review.notes import notes_for, open_note_counts
from abacus.modules.review.notification_states import register_notification_states
from abacus.modules.review.routes import router
from abacus.modules.review.sealing import open_text, record_text_reads, seal_text
from abacus.modules.review.service import (
    LEVELS,
    AlreadySigned,
    LevelState,
    NotesOpen,
    NotPrepared,
    PreparerCannotReview,
    SignOffInvalid,
    StaleSignOff,
    record_sign_off,
    sign_off_states,
    stale_of,
    states_of,
)
from abacus.modules.review.sign_offs import (
    STATEMENTS,
    ContentChanged,
    Incomplete,
    IndependencePending,
    LevelNotPermitted,
    OpenReviewNotes,
    Segregation,
    UncitedChange,
)
from abacus.modules.review.slots import (
    REQUIRED_LEVELS,
    CardContext,
    CardFactor,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    FieldOwner,
    Reassessment,
    Reviewable,
    ReviewableFacts,
    ReviewableFactsProvider,
    ReviewableProvider,
    UnregisteredKind,
    decision_kind,
    field_owner,
    gate_met,
    register_decision_kind,
    register_field_owner,
    register_fix_runner,
    register_gate_kind,
    register_reviewable,
    register_reviewable_facts,
    register_suggestion_owner,
    reviewable_fact_types,
    reviewable_facts,
    reviewables_of,
    run_fix,
)
from abacus.modules.review.stale import SUBSCRIPTIONS as STALE_SUBSCRIPTIONS
from abacus.modules.review.stale import detect_stale

# The routers the API mounts, in order (P-39; F-03-T07).
# C3 stubs behind `review.grammar_api` (P-04-T07, T08, T11).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    sign_offs_router,
    review_notes_router,
    human_gates_router,
    decision_cards_router,
    issues_router,
    checkpoints_router,
    fields_router,
)

# SPEC-313 (TASK-331): G5, review complete, is the review module's.
register_gate_provider("G5", review_gate)
register_engagement_gates()  # P-07-T47 (C13): acceptance, independence and EQR gates
register_card_reassign()  # I-01-T07: a decision card awaiting its role moves to another holder
register_engagement_owners(AUDIT_KINDS, audit_owners)  # ED-112: `sign_off.went_stale`
# P-04-T26 (C16): what a card, note or sign-off says now, for the drawer's facts and Approvals.
register_notification_states()

# P-04-T16 (C13): the human-gate projector, on the events its sources may change; P-04-T19:
# the stale sign-off detector, on the owners' change events (no event is in both).
SUBSCRIPTIONS = dict(GATE_SUBSCRIPTIONS) | dict(STALE_SUBSCRIPTIONS)
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

# I-01-T07: owners resolve their gates' presentation facts and register how a gate moves.
from abacus.modules.review.gate_actions import (  # noqa: E402
    Candidate,
    GateFacts,
    ProposedBy,
    ReassignHook,
    register_gate_presenter,
    register_reassign_hook,
)

__all__ = [
    "ACTIVITIES",
    "C13_EVENTS",
    "LEVELS",
    "REQUIRED_LEVELS",
    "ROUTERS",
    "STATEMENTS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "AlreadySigned",
    "Candidate",
    "CardContext",
    "CardFactor",
    "CardOption",
    "CardSubject",
    "ComputedCard",
    "ContentChanged",
    "DecisionCardState",
    "DecisionKind",
    "FieldOwner",
    "FieldValueInvalid",
    "GateFacts",
    "GateSource",
    "Incomplete",
    "IndependencePending",
    "Json",
    "LevelNotPermitted",
    "LevelState",
    "MfaRequired",
    "NotCanonical",
    "NotPrepared",
    "NotesOpen",
    "OpenGate",
    "OpenReviewNotes",
    "PreparerCannotReview",
    "PreviousValue",
    "ProposedBy",
    "RationaleRequired",
    "Reassessment",
    "ReassignHook",
    "RecommendationChanged",
    "Reviewable",
    "ReviewableFacts",
    "ReviewableFactsProvider",
    "ReviewableProvider",
    "Segregation",
    "SignOffInvalid",
    "StaleSignOff",
    "UncitedChange",
    "UnregisteredKind",
    "canonical_json",
    "content_hash",
    "decision_kind",
    "detect_stale",
    "field_owner",
    "gate_met",
    "issue_engagement",
    "notes_for",
    "open_note_counts",
    "open_text",
    "previous_value",
    "raise_decision_card",
    "rebuild_human_gates",
    "record_sign_off",
    "record_text_reads",
    "record_value",
    "register_decision_kind",
    "register_field_owner",
    "register_fix_runner",
    "register_gate_kind",
    "register_gate_presenter",
    "register_gate_source",
    "register_reassign_hook",
    "register_reviewable",
    "register_reviewable_facts",
    "register_suggestion_owner",
    "reviewable_fact_types",
    "reviewable_facts",
    "reviewables_of",
    "router",
    "run_fix",
    "seal_text",
    "sign_off_states",
    "stale_of",
    "states_of",
    "typed_value",
]
