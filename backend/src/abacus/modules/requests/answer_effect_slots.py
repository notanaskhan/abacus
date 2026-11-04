"""The answer-effect registration slot (T-03-T02 stub; T-03 §4.4, F3; DEC-2201).

`register_answer_effect(kind, handler)` lets another module own an effect kind (N-04 registers
`route_upload_to_notices`). The slot fails closed: an effect whose kind has no handler is
recorded `pending_handler` by the engine (T-03-T06) and the upload stays in the binder; nothing
is dropped and nothing guesses. Handlers run inside the engine's unit of work as the system
actor with the rule and publisher provenance; they never act as the agent.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

EffectKind = Literal[
    "create_request_item",
    "raise_review_point",
    "flag_internal_review",
    "route_upload_to_notices",
]
EFFECT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "create_request_item",
        "raise_review_point",
        "flag_internal_review",
        "route_upload_to_notices",
    }
)


@dataclass(frozen=True, slots=True)
class EffectRequest:
    """What the engine hands a handler: the answer, the rule and its provenance."""

    tenant_id: UUID
    questionnaire_id: UUID
    question_id: UUID
    answer_id: UUID | None
    rule_key: str
    template_version_id: UUID | None
    evidence_version_id: UUID | None = None
    # The questionnaire's named owner: a handler that must name a person names this one.
    owner_user_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class EffectResult:
    """The target the handler created (a request item, an issue, a notice intake)."""

    target_type: str
    target_id: UUID


class HandlerUnavailable(Exception):
    """A handler that cannot act for this firm now (its module's flag is off): the engine
    records `pending_handler` and nothing moves (N-04-T13, DEC-2245)."""


EffectHandler = Callable[[EffectRequest], Awaitable[EffectResult]]
_HANDLERS: dict[str, EffectHandler] = {}


def register_answer_effect(kind: EffectKind, handler: EffectHandler) -> None:
    """One handler per kind; registering a second is a programming error."""
    if kind not in EFFECT_KINDS:
        raise ValueError(f"unknown answer effect kind {kind!r}")
    if kind in _HANDLERS and _HANDLERS[kind] is not handler:
        raise ValueError(f"answer effect {kind!r} already has a handler")
    _HANDLERS[kind] = handler


def answer_effect_handler(kind: str) -> EffectHandler | None:
    """The registered handler, or None (the engine records `pending_handler`: fail closed)."""
    return _HANDLERS.get(kind)
