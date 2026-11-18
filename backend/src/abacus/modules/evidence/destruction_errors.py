"""Q-05 records governance error codes (SPEC-711; Q-05-T02, DEC-5609), declared before their
services (Q-05-T11, T13, T15). Facts are identifiers and counts only. The 410 `destroyed` answer
arrives with the destruction service (Q-05-T15), which adds its own error class."""

from __future__ import annotations

from abacus.kernel.errors import DomainConflict


class BatchPhraseMismatch(DomainConflict):
    """The typed confirmation is not `DESTROY <ref>` (AC-23)."""

    code = "batch_phrase_mismatch"


class SameApprover(DomainConflict):
    """The second approval is by the person who gave the first (AC-22)."""

    code = "same_approver"


class ApproverRoleTaken(DomainConflict):
    """The batch already carries an approval in this role (AC-22)."""

    code = "approver_role_taken"


class RetentionNotExpired(DomainConflict):
    """The record's retention or storage lock has not expired (OQ-2)."""

    code = "retention_not_expired"


class Held(DomainConflict):
    """A legal hold covers the record: it is excluded, never destroyed (AC-24)."""

    code = "held"
