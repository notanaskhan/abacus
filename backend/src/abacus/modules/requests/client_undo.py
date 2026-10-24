"""The client's Undo of an Ignore and of Mark as Done (R-01-T08; DEC-24, ADR-161 clause 6,
DEC-334). Contract: `docs/contracts/portal-pbc.md` §2, §6, §7.

Each Undo is a compensating event, never a delete: the act's own rows stay (the SPEC-042 response,
the `request_item.ignored` and `binder.marked_done` audit events, the ignore note in the thread),
and the Undo appends its own (`request_item.ignore_undone`, `binder.mark_done_undone`). Only the
person who acted may undo it, once. Unlike the firm's 10-second Undo, which holds an effect that
leaves the firm, a client's Ignore and Mark as Done hold none: their Undo stays open until the firm
acts on the request or the binder (R-01 OQ-2, DEC-240), then answers 409 `firm_already_acted`.

`COMPENSATIONS` is the requests module's table of these moves: each compensating event, the act it
undoes, and the firm's acts that close it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from abacus.kernel.errors import DomainConflict


@dataclass(frozen=True)
class Compensation:
    undoes: str  # the audit action of the act undone
    target_type: str
    closed_by: frozenset[str]  # the firm's audit actions after which Undo answers 409


# The firm's acts on a request that close a client's Undo (DEC-24; R-01 Stories 3.1 and 4.1).
FIRM_ITEM_ACTS: Final = frozenset(
    {"request_item.sent", "request_item.waived", "request_item.returned_to_client"}
)
COMPENSATIONS: Final[dict[str, Compensation]] = {
    "request_item.ignore_undone": Compensation(
        "request_item.ignored", "request_item", FIRM_ITEM_ACTS
    ),
    "binder.mark_done_undone": Compensation("binder.marked_done", "binder", FIRM_ITEM_ACTS),
}
# `request_item.ignore` requires a reason (matrix `requires: reason`): the Undo's is this code.
UNDO_REASON: Final = "undo"
# A request the client may still undo an Ignore on: the firm has not waived, received or sent
# it back since (the Ignore leaves the status `requested`, OQ-3).
UNDOABLE_ITEM: Final = frozenset({"requested", "returned"})


class FirmAlreadyActed(DomainConflict):
    """The firm has acted on the request or the binder since: the client's Undo is closed."""

    code = "firm_already_acted"


class NothingToUndo(DomainConflict):
    """The act was already undone (a second Undo), or never happened."""

    code = "nothing_to_undo"
