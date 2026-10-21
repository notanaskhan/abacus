"""Public interface of the review module; other modules import only this (ADR-008).

The review grammar (P-04): sign-offs first (SPEC-308); review notes, issues, decisions and
checkpoints follow.
"""

from abacus.modules.engagements.api import register_gate_provider
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.review.matrix import review_gate
from abacus.modules.review.notes import open_note_counts
from abacus.modules.review.routes import router
from abacus.modules.review.service import (
    LEVELS,
    AlreadySigned,
    LevelState,
    NotesOpen,
    NotPrepared,
    PreparerCannotReview,
    SignOffInvalid,
    record_sign_off,
    sign_off_states,
    states_of,
)
from abacus.modules.review.slots import (
    REQUIRED_LEVELS,
    Reviewable,
    ReviewableProvider,
    register_reviewable,
    reviewables_of,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

# SPEC-313 (TASK-331): G5, review complete, is the review module's.
register_gate_provider("G5", review_gate)

__all__ = [
    "LEVELS",
    "REQUIRED_LEVELS",
    "ROUTERS",
    "AlreadySigned",
    "LevelState",
    "NotPrepared",
    "NotesOpen",
    "PreparerCannotReview",
    "Reviewable",
    "ReviewableProvider",
    "SignOffInvalid",
    "open_note_counts",
    "record_sign_off",
    "register_reviewable",
    "reviewables_of",
    "router",
    "sign_off_states",
    "states_of",
]
