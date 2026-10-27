"""Engagements' human gates in the C13 projection (P-07-T47; P-07 §4.8; DEC-539). PROTECTED.

Engagements computes what waits (`engagements.api.*_due`, from its own records); review may
depend on engagements and never the reverse, so the registration lives here, through the same
`register_gate_source` every owner uses. Each source's subject type is its registered gate name
(C13's planned `subkind`, I-01-T04), and its kind is the DF-25 class Home bands it under:

| Gate | DF-25 kind | Read action | Who it waits on |
|---|---|---|---|
| `acceptance_decision_due` | `decision` | `acceptance.read` | the engagement partner |
| `independence_conclusion_due` | `decision` | `independence.read` | the engagement partner |
| `independence_confirmation_due` | `sign_off_request` | `independence.read` | the member |
| `eqr_eligibility_due` | `decision` | `independence.read` | each quality owner not on it |

Every gate here is the named assignee's alone (`assigned_only`, DEC-544): the owner assigns each
one to a person, and an unassigned row of these kinds is shown to nobody.

The projection only says that something waits: deciding, concluding, confirming and approving
stay the owners' human-only routes (INV-1), and nothing here can act.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import (
    ACCEPTANCE_DECISION_DUE,
    EQR_ELIGIBILITY_DUE,
    INDEPENDENCE_CONCLUSION_DUE,
    INDEPENDENCE_CONFIRMATION_DUE,
    DueGate,
    acceptance_decisions_due,
    eqr_eligibility_due,
    independence_conclusions_due,
    independence_confirmations_due,
)
from abacus.modules.review.gates import GateSource, OpenGate, register_gate_source

Due = Callable[[TenantContext, UUID | None], Awaitable[Sequence[DueGate]]]

_ACCEPTANCE: Final = frozenset({"acceptance.sent_to_partner", "acceptance.decided"})
_INDEPENDENCE: Final = frozenset(
    {
        "independence.requested",
        "independence.confirmed",
        "independence.declined",
        "independence.concluded",
    }
)
_EQR: Final = frozenset({"engagement_member.added", "eqr.eligibility_approved"})


def _open(due: Due) -> Callable[[TenantContext, UUID | None], Awaitable[list[OpenGate]]]:
    async def open_for(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
        return [
            OpenGate(
                g.subject_id,
                g.engagement_id,
                assignee_user_id=g.assignee_user_id,
                role=g.role,
                client_id=g.client_id,
            )
            for g in await due(tenant, engagement_id)
        ]

    open_for.__qualname__ = f"engagement_gates.{due.__name__}"
    return open_for


SOURCES: Final = (
    GateSource(
        ACCEPTANCE_DECISION_DUE,
        "decision",
        "acceptance.read",
        _ACCEPTANCE,
        _open(acceptance_decisions_due),
        assigned_only=True,
    ),
    GateSource(
        INDEPENDENCE_CONCLUSION_DUE,
        "decision",
        "independence.read",
        _INDEPENDENCE,
        _open(independence_conclusions_due),
        assigned_only=True,
    ),
    GateSource(
        INDEPENDENCE_CONFIRMATION_DUE,
        "sign_off_request",
        "independence.read",
        _INDEPENDENCE,
        _open(independence_confirmations_due),
        assigned_only=True,
    ),
    GateSource(
        EQR_ELIGIBILITY_DUE,
        "decision",
        "independence.read",  # the quality owner reads it in scope; approving is its own route
        _EQR,
        _open(eqr_eligibility_due),
        assigned_only=True,
    ),
)


def register_engagement_gates() -> None:
    for source in SOURCES:
        register_gate_source(source)


__all__ = ["SOURCES", "register_engagement_gates"]
