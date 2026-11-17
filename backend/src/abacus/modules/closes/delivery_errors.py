"""CAS delivery, hand-off and information-return error codes (SPEC-701; C-02-T02, DEC-5501).

Declared before the services (C-02-T21, T23, T29, T33, T39, T46) so the catalogue and the C-02-T07
stubs name them.
"""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict, DomainForbidden


class ReleasePreconditionsUnmet(DomainConflict):
    """Release is blocked: accounts unreconciled, issues open or entries neither posted nor
    recorded (`facts.unreconciled`, `facts.open_issues`, `facts.entries_unposted`)."""

    code = "release_preconditions_unmet"


class ClientApprovalRequired(DomainConflict):
    """The close locks only after the client approves its package."""

    code = "client_approval_required"


class HandoffNotAvailable(DomainConflict):
    """The tax hand-off opens only from a locked December close."""

    code = "handoff_not_available"


class CloseNotLocked(DomainConflict):
    """The action needs the close Locked (the information-return batch, the hand-off)."""

    code = "close_not_locked"


class TinRevealRefused(DomainForbidden):
    """A TIN reveal was refused (offshore user, or no reveal reason)."""

    code = "tin_reveal_refused"
