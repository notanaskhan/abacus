"""The client stage projection (P-08-T12; POR-02; DEC-209). Pure functions, no I/O.

A work item's canonical C2 status code becomes what the client sees: an ordered stage tracker
(done, current, upcoming) and one pill, both as client stage codes the portal's copy registry
words (`apps/web/src/screens/POR-02/copy.ts`). No firm status word, level or reviewer ever comes
out of here ("In review · Manager" stays in the firm app). A finished item has no work card: it is
an Earlier row, so the projection is None.

Kinds: a 1040 return, an entity return, a close (CAS), a financial statement audit and a SOC 2
examination. Every registry code of the kind's object maps to exactly one stage or to done; a test
proves it over the generated enums.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from abacus.kernel._statuses import AuditEngagementStatus, CloseStatus, ReturnStatus
from abacus.modules.portal.codes import PillCode, PillVariant, StageCode, StageState

Kind = Literal["return_1040", "return_entity", "close", "audit", "soc2"]


@dataclass(frozen=True)
class Stage:
    code: StageCode
    state: StageState


@dataclass(frozen=True)
class Projection:
    stages: tuple[Stage, ...]
    pill: PillCode
    variant: PillVariant


STAGES: Final[dict[Kind, tuple[StageCode, ...]]] = {
    "return_1040": ("gather_documents", "prepare", "review", "sign_form_8879", "file"),
    "return_entity": ("gather_documents", "prepare", "review", "file"),
    "close": ("requests", "reconcile", "review", "statements"),
    "audit": ("planning", "fieldwork", "statements_review", "report"),
    "soc2": ("scoping", "system_description", "testing", "exceptions", "report"),
}

# (current stage, pill) per canonical code; None means done: the item is an Earlier row.
_DONE: Final = None
_RETURN: Final[dict[str, tuple[StageCode, PillCode] | None]] = {
    ReturnStatus.NOT_STARTED: ("gather_documents", "getting_started"),
    ReturnStatus.GATHERING: ("gather_documents", "getting_started"),
    ReturnStatus.PREPARING: ("prepare", "preparing_return"),
    ReturnStatus.PREPARED: ("review", "reviewing_return"),
    ReturnStatus.IN_REVIEW: ("review", "reviewing_return"),
    # A firm-side problem reads as review in progress, never red to the client (POR-02).
    ReturnStatus.ACTION_REQUIRED: ("review", "reviewing_return"),
    ReturnStatus.APPROVED: ("sign_form_8879", "reviewing_return"),
    ReturnStatus.AWAITING_SIGNATURE: ("sign_form_8879", "reviewing_return"),
    ReturnStatus.FILED: ("file", "reviewing_return"),
    ReturnStatus.REJECTED: ("file", "reviewing_return"),
    ReturnStatus.FIXING: ("file", "reviewing_return"),
    ReturnStatus.ACCEPTED: _DONE,
}
_CLOSE: Final[dict[str, tuple[StageCode, PillCode] | None]] = {
    CloseStatus.NOT_STARTED: ("requests", "reconciling_accounts"),
    CloseStatus.IN_PROGRESS: ("reconcile", "reconciling_accounts"),
    CloseStatus.IN_REVIEW: ("review", "reconciling_accounts"),
    CloseStatus.APPROVED: ("statements", "reconciling_accounts"),
    CloseStatus.DELIVERED: _DONE,
    CloseStatus.LOCKED: _DONE,
}
_AUDIT: Final[dict[str, tuple[StageCode, PillCode] | None]] = {
    AuditEngagementStatus.PLANNING: ("planning", "finishing_audit"),
    AuditEngagementStatus.FIELDWORK: ("fieldwork", "finishing_audit"),
    AuditEngagementStatus.IN_REVIEW: ("statements_review", "finishing_audit"),
    AuditEngagementStatus.COMPLETION: ("statements_review", "finishing_audit"),
    AuditEngagementStatus.READY_TO_RELEASE: ("report", "finishing_audit"),
    AuditEngagementStatus.RELEASED: _DONE,
    AuditEngagementStatus.ARCHIVING: _DONE,
    AuditEngagementStatus.ARCHIVED: _DONE,
}
# A SOC 2 examination runs on the audit engagement's codes (DEC-209).
_SOC2: Final[dict[str, tuple[StageCode, PillCode] | None]] = {
    AuditEngagementStatus.PLANNING: ("scoping", "testing_under_way"),
    AuditEngagementStatus.FIELDWORK: ("testing", "testing_under_way"),
    AuditEngagementStatus.IN_REVIEW: ("exceptions", "testing_under_way"),
    AuditEngagementStatus.COMPLETION: ("exceptions", "testing_under_way"),
    AuditEngagementStatus.READY_TO_RELEASE: ("report", "testing_under_way"),
    AuditEngagementStatus.RELEASED: _DONE,
    AuditEngagementStatus.ARCHIVING: _DONE,
    AuditEngagementStatus.ARCHIVED: _DONE,
}
# An entity return has no Form 8879 stage: once approved, its signing is part of filing.
_RETURN_ENTITY: Final[dict[str, tuple[StageCode, PillCode] | None]] = {
    code: ("file", found[1]) if found is not None and found[0] == "sign_form_8879" else found
    for code, found in _RETURN.items()
}
MAPS: Final[dict[Kind, dict[str, tuple[StageCode, PillCode] | None]]] = {
    "return_1040": _RETURN,
    "return_entity": _RETURN_ENTITY,
    "close": _CLOSE,
    "audit": _AUDIT,
    "soc2": _SOC2,
}


class UnknownStatus(ValueError):
    """A code the kind's registry object doesn't have: a caller bug, never shown to a client."""


def client_view(kind: Kind, code: str) -> Projection | None:
    """The client's view of a work item at `code`; None once it is done (an Earlier row)."""
    table = MAPS[kind]
    if code not in table:
        raise UnknownStatus(f"{kind}: {code!r}")
    found = table[code]
    if found is None:
        return None
    current, pill = found
    order = STAGES[kind]
    at = order.index(current)
    stages = tuple(
        Stage(c, "done" if i < at else "current" if i == at else "upcoming")
        for i, c in enumerate(order)
    )
    return Projection(stages, pill, "state")


def filed_and_accepted() -> Projection:
    """The one done pill a work card can still show (a filed return's card, POR-02 d)."""
    return Projection((), "filed_and_accepted", "success")
