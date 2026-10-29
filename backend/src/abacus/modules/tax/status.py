"""The return status machine (T-02-T07; T-02 §3, §4.2; SPEC-502 AC-8).

The registry's `return` codes (blueprint §3.3.1) and the moves between them. Code computes the
next status from the current one and an event; the server refuses any move this table does not
hold (409 `transition_refused`). Person-gated moves (final approval, transmission, filing) are
raised by T-01's red files through their own events, never by a client request: a request may
only ask for `start_preparation` or `start_review` (`tax_return.status_change`).
"""

from __future__ import annotations

from typing import Final

from abacus.kernel._statuses import ReturnStatus as S
from abacus.kernel.errors import DomainConflict

# (from, event) -> to. `None` as from: any status the event may leave.
TRANSITIONS: Final[dict[tuple[S, str], S]] = {
    (S.NOT_STARTED, "intake_opened"): S.GATHERING,
    (S.GATHERING, "start_preparation"): S.PREPARING,
    (S.NOT_STARTED, "start_preparation"): S.PREPARING,
    (S.PREPARING, "prepared"): S.PREPARED,
    (S.PREPARED, "start_review"): S.IN_REVIEW,
    (S.IN_REVIEW, "issues_raised"): S.ACTION_REQUIRED,
    (S.ACTION_REQUIRED, "issues_cleared"): S.IN_REVIEW,
    (S.IN_REVIEW, "final_approved"): S.APPROVED,
    (S.APPROVED, "envelope_sent"): S.AWAITING_SIGNATURE,
    (S.AWAITING_SIGNATURE, "transmission_recorded"): S.FILED,
    (S.FILED, "ack_accepted"): S.ACCEPTED,
    (S.FILED, "ack_rejected"): S.REJECTED,
    (S.REJECTED, "fix_started"): S.FIXING,
    (S.FIXING, "start_review"): S.IN_REVIEW,
    # A content change after approval sends the return back to review (the binding relocks).
    (S.APPROVED, "content_changed"): S.IN_REVIEW,
    (S.AWAITING_SIGNATURE, "content_changed"): S.IN_REVIEW,
}
# The only events a person's request may name; the rest come from the system and T-01.
REQUESTABLE: Final = frozenset({"start_preparation", "start_review"})


class TransitionRefused(DomainConflict):
    """409: the table holds no move from this status on this event."""

    code = "transition_refused"


class StaleReturn(DomainConflict):
    """409: the return moved since the caller read it (`seen_version` is behind)."""

    code = "stale_version"


def next_status(current: S, event: str) -> S:
    found = TRANSITIONS.get((current, event))
    if found is None:
        raise TransitionRefused(facts={"status": current.value, "event": event})
    return found
