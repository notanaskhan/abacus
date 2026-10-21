"""Public interface of the review module; other modules import only this (ADR-008).

The review grammar (P-04): sign-offs first (SPEC-308); review notes, issues, decisions and
checkpoints follow.
"""

from abacus.modules.review.service import (
    LEVELS,
    AlreadySigned,
    LevelState,
    NotPrepared,
    PreparerCannotReview,
    SignOffInvalid,
    record_sign_off,
    sign_off_states,
    states_of,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[()] = ()

__all__ = [
    "LEVELS",
    "ROUTERS",
    "AlreadySigned",
    "LevelState",
    "NotPrepared",
    "PreparerCannotReview",
    "SignOffInvalid",
    "record_sign_off",
    "sign_off_states",
    "states_of",
]
